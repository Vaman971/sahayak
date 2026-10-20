import numpy as np
from voice_gateway.adapters.threshold_vad import ThresholdVAD
from voice_gateway.audio.pcm import float32_to_pcm16
from voice_gateway.ports.vad import VadEvent

SILENCE = b"\x00\x00" * 320
t = np.arange(320, dtype=np.float32) / 16000
LOUD = float32_to_pcm16((0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32))  # about -13 dBFS


def test_start_needs_three_loud_frames_and_includes_preroll() -> None:
    vad = ThresholdVAD()
    for _ in range(5):
        assert vad.process(SILENCE).event is None
    assert vad.process(LOUD).event is None
    assert vad.process(LOUD).event is None
    r = vad.process(LOUD)
    assert r.event is VadEvent.SPEECH_START
    assert len(r.frames) == 8  # 5 silence + 3 loud of pre-roll


def test_single_click_does_not_start_speech() -> None:
    vad = ThresholdVAD()
    vad.process(LOUD)
    for _ in range(10):
        assert vad.process(SILENCE).event is None


def test_end_after_500ms_of_quiet() -> None:
    vad = ThresholdVAD()
    for _ in range(3):
        vad.process(LOUD)
    events = [vad.process(SILENCE).event for _ in range(25)]
    assert events[:24] == [None] * 24
    assert events[24] is VadEvent.SPEECH_END


def test_short_pause_does_not_end_speech() -> None:
    vad = ThresholdVAD()
    for _ in range(3):
        vad.process(LOUD)
    for _ in range(10):  # 200 ms pause between words
        assert vad.process(SILENCE).event is None
    r = vad.process(LOUD)
    assert r.event is None
    assert r.frames == [LOUD]
