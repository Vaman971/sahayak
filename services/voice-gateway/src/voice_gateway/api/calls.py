import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from sahayak_core.config import Settings, get_settings
from sahayak_core.logging import get_logger

from voice_gateway.adapters.fakes.asr import ScriptedASR
from voice_gateway.adapters.fakes.llm import FakeLLM
from voice_gateway.adapters.fakes.tts import ToneTTS
from voice_gateway.adapters.vad.energy import energy_vad
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
from voice_gateway.api.ws_client import WebSocketClient
from voice_gateway.audio.format import PCM16_16K_MONO
from voice_gateway.audio.framing import FrameAssembler
from voice_gateway.audio.meter import LevelMeter
from voice_gateway.audio.recorder import WavRecorder
from voice_gateway.session.orchestrator import CallSession, SessionConfig

router = APIRouter()
log = get_logger()

START_TIMEOUT_S = 5.0
METER_EVERY_FRAMES = 50  # 50 X 20 ms = 1s

# App-level close codes live in 4000-4999 (RFC 6455 reserves lower ones)
CLOSE_BAD_START = 4400
CLOSE_START_TIMEOUT = 4408


class _InboundTap:
    """Per-call inbound stats: frame count, level meter, optional recording."""

    def __init__(self, settings: Settings) -> None:
        self.fmt = PCM16_16K_MONO
        self.frames = 0
        self.meter = LevelMeter()
        self.recorder = WavRecorder(self.fmt) if settings.record_calls else None

    @property
    def audio_seconds(self) -> float:
        return self.frames * self.fmt.frame_ms / 1000  # audio samples per second

    def on_frame(self, frame: bytes) -> None:
        self.frames += 1
        self.meter.add(frame)
        if self.recorder is not None:
            self.recorder.write(frame)

        if self.frames % METER_EVERY_FRAMES == 0:  # when audio of 1s is captured
            s = self.meter.snapshot()
            log.debug(
                "audio.level",
                audio_s=self.audio_seconds,
                rms_dbfs=s.rms_dbfs,
                peak_dbfs=s.peak_dbfs,
                clipped=s.clipped,
            )

            self.meter.reset()


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


async def _receive_audio(
    ws: WebSocket,
    on_frame: Callable[[bytes], Awaitable[None]],
    send_model: Callable[[BaseModel], Awaitable[None]],
) -> bool:
    """Reads until disconnect or stop. Returns True if the client sent 'stop'"""
    assembler = FrameAssembler(PCM16_16K_MONO.frame_bytes)
    while True:
        message = await ws.receive()
        if message["type"] == "websocket.disconnect":
            return False

        if (data := message.get("bytes")) is not None:
            for frame in assembler.push(data):
                await on_frame(frame)
            continue
        text = message.get("text")
        if text is None:
            continue

        try:
            ctrl = CLIENT_MSG.validate_json(text)
        except ValidationError as e:
            await send_model(ErrorMsg(code="bad_message", message=str(e)))
            continue

        if isinstance(ctrl, PingMsg):
            await send_model(PongMsg(t=ctrl.t))
        elif isinstance(ctrl, StopMsg):
            return True


async def _run_echo(ws: WebSocket, client: WebSocketClient, tap: _InboundTap) -> bool:
    async def on_frame(frame: bytes) -> None:
        tap.on_frame(frame)
        await client.send_audio(frame)

    return await _receive_audio(ws, on_frame, client.send_model)


async def _run_agent(
    ws: WebSocket, client: WebSocketClient, tap: _InboundTap, call_id: str
) -> bool:
    vad = energy_vad()
    session = CallSession(
        call_id=call_id,
        client=client,
        vad=vad,
        asr=ScriptedASR(),
        llm=FakeLLM(),
        tts=ToneTTS(),
        config=SessionConfig(endpoint_ms=vad.end_handover_ms),
    )

    stopped = False

    async def on_frame(frame: bytes) -> None:
        tap.on_frame(frame)
        session.push_audio(frame)

    async def recieve() -> None:
        nonlocal stopped  # accessing the variable at line 162
        try:
            stopped = await _receive_audio(ws, on_frame, client.send_model)
        finally:
            session.close()  # recieved ending always shuts the session down

    # TaskGroup runs the: session and the receiver as siblings.
    # If either crashes, the group cancels the other and re-raises.
    async with asyncio.TaskGroup() as tg:
        tg.create_task(session.run(), name="session")
        tg.create_task(recieve(), name="receive")

    log.info(
        "session.stats",
        dropped_frames=session.dropped_frames,
        interruptions=session.interruptions,
    )
    return stopped


@router.websocket("/v1/calls/ws")
async def call_ws(ws: WebSocket) -> None:
    settings = get_settings()
    await ws.accept()
    call_id = uuid.uuid4().hex[:12]

    with structlog.contextvars.bound_contextvars(call_id=call_id):
        start = await _await_start(ws)
        if start is None:
            return

        tap = _InboundTap(settings)
        client = WebSocketClient(ws)
        t0 = time.monotonic()

        await client.send_model(ReadyMsg(call_id=call_id, frame_bytes=tap.fmt.frame_bytes))
        log.info("call.started", mode=start.mode)

        stopped = False
        try:
            if start.mode == "echo":
                stopped = await _run_echo(ws, client, tap)
            else:
                stopped = await _run_agent(ws, client, tap, call_id)
        except WebSocketDisconnect:
            pass
        finally:
            wall = round(time.monotonic() - t0, 2)
            log.info(
                "call.ended", frames=tap.frames, audio_seconds=tap.audio_seconds, wall_seconds=wall
            )
            if stopped:
                await client.send_model(
                    SummaryMsg(
                        frames=tap.frames, audio_seconds=tap.audio_seconds, wall_seconds=wall
                    )
                )
                await client.close()
            if tap.recorder is not None and tap.frames > 0:
                path = settings.recordings_dir / f"{call_id}.wav"
                await tap.recorder.save(path)
                log.info("call.recording_saved", path=str(path))
