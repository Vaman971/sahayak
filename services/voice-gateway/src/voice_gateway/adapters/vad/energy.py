import math

from voice_gateway.adapters.vad.segmenter import SegmenterConfig, SegmentingVAD
from voice_gateway.audio.pcm import dbfs

SEGMENT_CONFIG = SegmenterConfig()


class EnergyClassifier:
    """Baseline: fixed dBFS threshold, mapped to a soft 0..1 score witha sigmoid."""

    def __init__(self, threshold_dbfs: float = -35.0, softness_db: float = 3.0) -> None:
        self._threshold = threshold_dbfs
        self._softness = softness_db

    def score(self, frame: bytes) -> float:
        x = (dbfs(frame) - self._threshold) / self._softness
        return 1.0 / (1.0 + math.exp(-x))

    def reset(self) -> None:
        pass


def energy_vad(
    threshold_dbfs: float = -35.0, config: SegmenterConfig = SEGMENT_CONFIG
) -> SegmentingVAD:
    return SegmentingVAD(EnergyClassifier(threshold_dbfs), config)
