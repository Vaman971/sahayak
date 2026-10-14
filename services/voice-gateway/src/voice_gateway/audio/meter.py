import math
from dataclasses import dataclass

import numpy as np

FULL_SCALE = 32768.0
NEAR_CLIP = 32700  # samples at or above this are effectively clipping


@dataclass(frozen=True, slots=True)
class LevelStats:
    rms_dbfs: float
    peak_dbfs: float
    clipped: int
    samples: int


def _to_db(x: float) -> float:
    return 20.0 * math.log10(max(x, 1e-6))


class LevelMeter:
    """Accumulates power (not dB) over a window, plus peak and clip count."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._sumsq = 0.0
        self._n = 0
        self._peak = 0
        self._clipped = 0

    def add(self, frame: bytes) -> None:
        x = np.frombuffer(frame, dtype="<i2").astype(np.int32)
        if x.size == 0:
            return

        a = np.abs(x)
        self._sumsq += float(np.sum(x * x, dtype=np.float64))
        self._n += int(x.size)
        self._peak = max(self._peak, int(a.max()))
        self._clipped += int(
            np.count_nonzero(a >= NEAR_CLIP)
        )  # number of values present greated then the clipping limit

    def snapshot(self) -> LevelStats:
        if self._n == 0:
            return LevelStats(rms_dbfs=-120.0, peak_dbfs=-120.0, clipped=0, samples=0)

        rms = math.sqrt(self._sumsq / self._n) / FULL_SCALE
        return LevelStats(
            rms_dbfs=round(_to_db(rms), 1),
            peak_dbfs=round(_to_db(self._peak / FULL_SCALE), 1),
            clipped=self._clipped,
            samples=self._n,
        )
