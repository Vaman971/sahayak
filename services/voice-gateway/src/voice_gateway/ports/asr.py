from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    is_final: bool
    language: str | None = None


class ASRPort(Protocol):
    """One call per user utterance: consume audio until it ends, yield transcripts."""

    def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[Transcript]: ...
