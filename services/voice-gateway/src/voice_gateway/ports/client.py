from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StateChanged:
    state: str
    turn_id: int


@dataclass(frozen=True, slots=True)
class UserTranscript:
    turn_id: int
    text: str


@dataclass(frozen=True, slots=True)
class AgentText:
    turn_id: int
    text: str


@dataclass(frozen=True, slots=True)
class TurnLatency:
    turn_id: int
    endpoint_ms: int  # VAD hangover: silence we wait before deciding the user finished
    asr_ms: float  # speech end -> final transcript
    llm_ms: float  # transcript -> first token
    tts_ms: float  # first token -> first audio frame sent
    total_ms: float  # speech end -> first audio frame sent


Notice = StateChanged | UserTranscript | AgentText | TurnLatency


class ClientPort(Protocol):
    async def send_audio(self, pcm: bytes) -> None: ...

    async def clear_playback(self) -> None: ...

    async def notify(self, notice: Notice) -> None: ...
