import pytest
from voice_gateway.audio.framing import FrameAssembler


def test_exact_frame_passes_through() -> None:
    fa = FrameAssembler(4)
    assert fa.push(b"abcd") == [b"abcd"]
    assert fa.pending == 0


def test_partial_frames_accumulate() -> None:
    fa = FrameAssembler(4)
    assert fa.push(b"ab") == []
    assert fa.push(b"cdef") == [b"abcd"]
    assert fa.pending == 2


def test_many_frames_in_one_push() -> None:
    fa = FrameAssembler(2)
    assert fa.push(b"abcdefg") == [b"ab", b"cd", b"ef"]
    assert fa.pending == 1


def test_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError):
        FrameAssembler(0)
