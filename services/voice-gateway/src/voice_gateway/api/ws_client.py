import asyncio
import contextlib
from dataclasses import asdict
from typing import assert_never

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from voice_gateway.api.protocol import AgentTextMsg, ClearMsg, LatencyMsg, StateMsg, TranscriptMsg
from voice_gateway.ports.client import AgentText, Notice, StateChanged, TurnLatency, UserTranscript

_SEND_ERRORS = (WebSocketDisconnect, RuntimeError, OSError)


class WebSocketClient:
    """ClientPort over a FastAPI WebSocket. One lock: one writer at a time."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws
        self._lock = asyncio.Lock()
        self.closed = False

    async def send_audio(self, pcm: bytes) -> None:
        async with self._lock:
            if self.closed:
                return
            try:
                await self._ws.send_bytes(pcm)
            except _SEND_ERRORS:
                self.closed = True

    async def send_model(self, model: BaseModel) -> None:
        async with self._lock:
            if self.closed:
                return

            try:
                await self._ws.send_text(model.model_dump_json())
            except _SEND_ERRORS:
                self.closed = True

    async def clear_playback(self) -> None:
        await self.send_model(ClearMsg())

    async def notify(self, notice: Notice) -> None:
        msg: BaseModel
        match notice:
            case StateChanged(state=state, turn_id=tid):
                msg = StateMsg(state=state, turn_id=tid)
            case UserTranscript(turn_id=tid, text=text):
                msg = TranscriptMsg(turn_id=tid, text=text)
            case AgentText(turn_id=tid, text=text):
                msg = AgentTextMsg(turn_id=tid, text=text)
            case TurnLatency():
                msg = LatencyMsg(**asdict(notice))
            case _:
                assert_never(notice)

        await self.send_model(msg)

    async def close(self) -> None:
        async with self._lock:
            if self.closed:
                return
            self.closed = True
            with contextlib.suppress(*_SEND_ERRORS):
                await self._ws.close()
