from collections.abc import AsyncIterator
from typing import Protocol


class TTSPort(Protocol):
    """Text chunks in, PCM16 16Khz mono audio out, both streaming."""

    def synthesize(self, text: AsyncIterator[str]) -> AsyncIterator[bytes]: ...
