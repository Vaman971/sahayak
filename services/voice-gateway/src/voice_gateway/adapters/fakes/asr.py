import asyncio
from collections import deque
from collections.abc import AsyncIterator, Sequence

from voice_gateway.ports.asr import Transcript

BYTES_PER_MS = 32  # 16Khz X 2 bytes / 1000 (how many bytes arrrive in a single millisecond)


class ScriptedASR:
    """consumes the utterance, then returns the next scripted line (or a size description)."""

    def __init__(self, scripts: Sequence[str] = (), latency_s: float = 0.2) -> None:
        self._scripts = deque(scripts)
        self._latency = latency_s

    async def stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        n = 0
        async for chunk in audio:
            n += len(chunk)

        await asyncio.sleep(self._latency)

        text = self._scripts.popleft() if self._scripts else f"{n // BYTES_PER_MS} ms ki awaaz"
        yield Transcript(text=text, is_final=True)
