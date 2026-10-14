import numpy as np
from voice_gateway.audio.meter import LevelMeter
from voice_gateway.audio.pcm import float32_to_pcm16


def test_silence() -> None:
    m = LevelMeter()
    m.add(b"\x00\x00" * 320)
    s = m.snapshot()
    assert s.rms_dbfs == -120.0
    assert s.clipped == 0


def test_power_average_not_db_average() -> None:
    loud = float32_to_pcm16(np.full(320, 0.1, dtype=np.float32))  # -20 dBFS
    quiet = float32_to_pcm16(np.full(320, 0.001, dtype=np.float32))  # -60 dBFS
    m = LevelMeter()
    m.add(loud)
    m.add(quiet)
    # dB-average would say -40; power-average is about -23
    assert -23.5 < m.snapshot().rms_dbfs < -22.5


def test_counts_clipping() -> None:
    m = LevelMeter()
    m.add(float32_to_pcm16(np.array([1.0, -1.0, 0.0, 0.5], dtype=np.float32)))
    s = m.snapshot()
    assert s.clipped == 2
    assert s.peak_dbfs > -0.1
