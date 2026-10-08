import asyncio
import wave
from pathlib import Path

from voice_gateway.audio.format import AudioFormat


class WavRecorder:
    """Buffers frames in memory; writes WAV off the event loop at call end."""

    def __init__(self, fmt: AudioFormat) -> None:
        self._fmt = fmt
        self._chunks: list[bytes] = []

    def write(self, frame: bytes) -> None:
        self._chunks.append(frame)

    @property
    def seconds(self) -> float:
        return sum(map(len, self._chunks)) / self._fmt.bytes_per_second

    def _save_sync(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(self._fmt.channels)
            w.setsampwidth(self._fmt.sample_width)
            w.setframerate(self._fmt.sample_rate)
            w.writeframes(b"".join(self._chunks))

    async def save(self, path: Path) -> None:
        await asyncio.to_thread(self._save_sync, path)
