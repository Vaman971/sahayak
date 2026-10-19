import asyncio
import math
from collections.abc import AsyncIterator

import numpy as np

from voice_gateway.audio.format import PCM16_16K_MONO, AudioFormat
from voice_gateway.audio.pcm import float32_to_pcm16


class ToneTTS:
    """Turns text into a tone whose length tracks the text, so you cab *hear* the agent."""

    def __init__(
        self,
        fmt: AudioFormat = PCM16_16K_MONO,
        ms_per_char: int = 60,
        freq_hz: float = 220.0,
        amplitude: float = 0.2,
        first_audio_delay_s: float = 0.15,
    ) -> None:
        self._fmt = fmt
        self._ms_per_char = ms_per_char
        self._freq = freq_hz
        self._amp = amplitude
        self._first_delay = first_audio_delay_s

    async def synthesize(self, text: AsyncIterator[str]) -> AsyncIterator[bytes]:
        sr = self._fmt.sample_rate
        w = 2 * math.pi * self._freq / sr  # A sine wave cycle is 2pi radians ($360^\circ$).
        # At 16,000 samples per second, this calculates the angle step ($\omega$).
        # that the wave advances for every single audio sample
        phase = 0.0
        first = True

        async for chunk in text:
            if first:
                await asyncio.sleep(self._first_delay)
                first = False
            n = len(chunk) * self._ms_per_char * sr // 1000
            if n == 0:
                continue
            idx = np.arange(n, dtype=np.float64)
            samples = (self._amp * np.sin(phase + w * idx)).astype(np.float32)
            phase = (phase + w * n) % (2 * math.pi)  # continous phase: no clicks between chunks
            yield float32_to_pcm16(samples)
