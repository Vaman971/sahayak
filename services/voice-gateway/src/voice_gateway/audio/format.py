from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioFormat:
    sample_rate: int = 16_000
    channels: int = 1
    sample_width: int = 2  # bytes per sample (int16)
    frame_ms: int = 20

    @property
    def samples_per_frame(self) -> int:
        return self.sample_rate * self.frame_ms // 1000

    @property
    def frame_bytes(self) -> int:
        return self.samples_per_frame * self.channels * self.sample_width

    @property
    def bytes_per_second(self) -> int:
        return self.sample_rate * self.channels * self.sample_width


PCM16_16K_MONO = AudioFormat()
