import math
from typing import cast

import numpy as np
import numpy.typing as npt

Float32Array = npt.NDArray[np.float32]


def pcm16_to_float32(data: bytes) -> Float32Array:
    """pulse code modulation of 16kHZ audio buffer into float32 for scientific computing"""
    ints = np.frombuffer(
        data, dtype="<i2"
    )  # <i2 means less-endian unsigned  2 byte (16 bits) integer
    return cast(
        Float32Array, ints.astype(np.float32) / np.float32(32768.0)
    )  # cast the 2 byte integer into 4 byte floting point number between [-1, 1], to avoid overflow


def float32_to_pcm16(samples: Float32Array) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)  # if any sample crosses -1 to 1,
    # it could lead to overflow and could produce overly highed piched sound

    return (clipped * 32767.0).astype("<i2").tobytes()


def dbfs(data: bytes) -> float:
    """Loudness or decibles relative to full scale: 0 dBFS is max, silence is around -60 or lower"""
    x = pcm16_to_float32(data)
    if x.size == 0:
        return -120.0
    rms = float(
        np.sqrt(np.mean(np.square(x, dtype=np.float64)))
    )  # root mean square => actual amplitube unit of sound wave
    return 20.0 * math.log10(max(rms, 1e-6))  # rms to decibles
