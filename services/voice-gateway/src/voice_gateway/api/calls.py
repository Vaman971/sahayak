import asyncio
import time
import uuid

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sahayak_core.config import get_settings

from voice_gateway.api.protocol import (
    CLIENT_MSG,
    ErrorMsg,
    PingMsg,
    PongMsg,
    ReadyMsg,
    StartMsg,
    StopMsg,
    SummaryMsg,
)
from voice_gateway.audio.format import PCM16_16K_MONO
from voice_gateway.audio.framing import FrameAssembler
from voice_gateway.audio.pcm import dbfs
from voice_gateway.audio.recorder import WavRecorder

router = APIRouter()
log = structlog.get_logger()

START_TIMEOUT_S = 5.0
METER_EVERY_FRAMES = 50  # 50 X 20 ms = 1s

# App-level close codes live in 4000-4999 (RFC 6455 reserves lower ones)
CLOSE_BAD_START = 4400
CLOSE_START_TIMEOUT = 4408


async def _close_with_error(ws: WebSocket, close_code: int, code: str, message: str) -> None:
    await ws.send_text(ErrorMsg(code=code, message=message).model_dump_json())
    await ws.close(code=close_code)


async def _await_start(ws: WebSocket) -> StartMsg | None:
    try:
        message = await asyncio.wait_for(ws.receive(), timeout=START_TIMEOUT_S)
    except TimeoutError:
        await _close_with_error(ws, CLOSE_START_TIMEOUT, "start_timeout", "no start within 5 s")
        return None

    if message["type"] == "websocket.disconnect":
        return None

    text = message.get("text")
    if text is None:
        await _close_with_error(ws, CLOSE_BAD_START, "bad_start", "first message must be JSON text")
        return None

    try:
        msg = CLIENT_MSG.validate_json(text)
    except ValidationError as e:
        await _close_with_error(ws, CLOSE_BAD_START, "bad_start", str(e))
        return None

    if not isinstance(msg, StartMsg):
        await _close_with_error(ws, CLOSE_BAD_START, "bad_start", "first message must be 'start'")
        return None

    return msg


@router.websocket("/v1/calls/ws")
async def call_ws(ws: WebSocket) -> None:
    settings = get_settings()
    await ws.accept()
    call_id = uuid.uuid4().hex[:12]

    with structlog.contextvars.bound_contextvars(call_id=call_id):
        start = await _await_start(ws)
        if start is None:
            return

        fmt = PCM16_16K_MONO
        assembler = FrameAssembler(fmt.frame_bytes)
        recorder = WavRecorder(fmt) if settings.record_calls else None
        frames = 0
        level_sum = 0.0
        t0 = time.monotonic()

        await ws.send_text(ReadyMsg(call_id=call_id, frame_bytes=fmt.frame_bytes).model_dump_json())
        log.info("call.started", mode=start.mode, frame_bytes=fmt.frame_bytes)

        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break

                data = message.get("bytes")
                if data is not None:
                    for frame in assembler.push(data):
                        frames += 1
                        level_sum += dbfs(frame)
                        if recorder is not None:
                            recorder.write(frame)
                        await ws.send_bytes(frame)  # echo
                        if frames % METER_EVERY_FRAMES == 0:
                            log.debug(
                                "audio.level",
                                dbfs=round(level_sum / METER_EVERY_FRAMES, 1),
                                audio_s=frames * fmt.frame_ms / 1000,
                            )
                            level_sum = 0.0
                    continue

                text = message.get("text")
                if text is None:
                    continue
                try:
                    ctrl = CLIENT_MSG.validate_json(text)
                except ValidationError as e:
                    await ws.send_text(
                        ErrorMsg(code="bad_message", message=str(e)).model_dump_json()
                    )
                    continue

                if isinstance(ctrl, PingMsg):
                    await ws.send_text(PongMsg(t=ctrl.t).model_dump_json())
                elif isinstance(ctrl, StopMsg):
                    summary = SummaryMsg(
                        frames=frames,
                        audio_seconds=frames * fmt.frame_ms / 1000,
                        wall_seconds=round(time.monotonic() - t0, 2),
                    )
                    await ws.send_text(summary.model_dump_json())
                    await ws.close()
                    break
        except WebSocketDisconnect:
            pass
        finally:
            log.info(
                "call.ended",
                frames=frames,
                audio_seconds=frames * fmt.frame_ms / 1000,
                wall_seconds=round(time.monotonic() - t0, 2),
                leftover_bytes=assembler.pending,
            )
            if recorder is not None and frames > 0:
                path = settings.recordings_dir / f"{call_id}.wav"
                await recorder.save(path)
                log.info("call.recording_saved", path=str(path))
