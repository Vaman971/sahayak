from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

PROTOCOL_VERSION = 1


# ----- client -> server --------
class StartMsg(BaseModel):
    type: Literal["start"]
    protocol: int = PROTOCOL_VERSION
    sample_rate: Literal[16000]
    encoding: Literal["pcm_s16le"]
    frame_ms: Literal[20]
    mode: Literal["echo"] = "echo"


class StopMsg(BaseModel):
    type: Literal["stop"]


class PingMsg(BaseModel):
    type: Literal["ping"]
    t: float


ClientMsg = Annotated[StartMsg | StopMsg | PingMsg, Field(discriminator="type")]
CLIENT_MSG: TypeAdapter[StartMsg | StopMsg | PingMsg] = TypeAdapter(ClientMsg)


# ---- server -> client ----
class ReadyMsg(BaseModel):
    type: Literal["ready"] = "ready"
    call_id: str
    frame_bytes: int


class PongMsg(BaseModel):
    type: Literal["pong"] = "pong"
    t: float


class SummaryMsg(BaseModel):
    type: Literal["summary"] = "summary"
    frames: int
    audio_seconds: float
    wall_seconds: float


class ErrorMsg(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
