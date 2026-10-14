import numpy as np
from voice_gateway.audio.pcm import dbfs, float32_to_pcm16, pcm16_to_float32


def test_round_trip_is_close() -> None:
    x = np.linspace(-0.9, 0.9, 1000, dtype=np.float32)
    y = pcm16_to_float32(float32_to_pcm16(x))

    assert np.max(np.abs(x - y)) < 1e-4


def test_clipping_does_not_wrap() -> None:
    loud = np.array([1.5, -1.5], dtype=np.float32)
    out = np.frombuffer(float32_to_pcm16(loud), dtype="<i2")
    assert out[0] == 32767
    assert out[1] == -32767


def dbfs_of_silence_is_floor() -> None:
    assert dbfs(b"\x00\x00" * 320) == -120.0


def test_dbfs_of_full_scale_sine_is_about_minus_3() -> None:
    t = np.arange(16000, dtype=np.float32) / 16000
    sine = (0.999 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    assert abs(dbfs(float32_to_pcm16(sine)) - (-3.0)) < 0.1
