from collections import deque
from dataclasses import dataclass

from voice_gateway.ports.vad import FrameClassifier, VadEvent, VadResult


@dataclass(frozen=True, slots=True)
class SegmenterConfig:
    on_threshold: float = 0.5  # score needed to count toward starting speech
    off_threshold: float = 0.35  # score below which a frame counts towards ending it
    start_frames: int = 3  # 60 ms  above on_threshold to start
    end_frames: int = 25  # 500 ms below off_threshold to end
    preroll_frames: int = 10  # 200 ms handed to ASR from before the start


CONFIG = SegmenterConfig()


class SegmentingVAD:
    """Turns per-frame speech scores into utterance boundaries. Implements VADPort."""

    def __init__(
        self,
        classifier: FrameClassifier,
        config: SegmenterConfig = CONFIG,
        frame_ms: int = 20,
    ) -> None:
        self._classifier = classifier
        self._cfg = config
        self._frame_ms = frame_ms
        self._preroll: deque[bytes] = deque(maxlen=config.preroll_frames)
        self.last_score = 0.0
        self.reset()

    @property
    def config(self) -> SegmenterConfig:
        return self._cfg

    @property
    def end_handover_ms(self) -> int:
        return self._cfg.end_frames * self._frame_ms

    def reset(self) -> None:
        self._classifier.reset()
        self._in_speech = False
        self._on_run = 0
        self._off_run = 0
        self._preroll.clear()

    def process(self, frame: bytes) -> VadResult:
        p = self._classifier.score(frame)
        self.last_score = p

        if not self._in_speech:
            self._preroll.append(frame)
            self._on_run = self._on_run + 1 if p >= self._cfg.on_threshold else 0
            if self._on_run >= self._cfg.start_frames:
                self._in_speech = True
                self._off_run = 0
                frames = list(self._preroll)
                self._preroll.clear()
                return VadResult(VadEvent.SPEECH_START, frames)
            return VadResult()

        self._off_run = self._off_run + 1 if p < self._cfg.off_threshold else 0
        if self._off_run >= self._cfg.end_frames:
            self._in_speech = False
            self._on_run = 0
            return VadResult(VadEvent.SPEECH_END)

        return VadResult(frames=[frame])
