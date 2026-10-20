from collections import deque

from voice_gateway.audio.pcm import dbfs
from voice_gateway.ports.vad import VadEvent, VadResult


class ThresholdVAD:
    """
    Deliberately naive: fixed dbFS threshold + hysteresis + pre-roll.

    Replaced in Replaced in Step 4.
    """

    def __init__(
        self,
        threshold_dbfs: float = -35.0,  # after testing
        start_frames: int = 3,  # 60 ms of loud audio to start
        end_frames: int = 25,  # 500 ms of quite quite to end
        preroll_frames: int = 10,  # 200 ms kept from before the start
    ) -> None:
        self._threshold = threshold_dbfs
        self._start_frames = start_frames
        self._end_frames = end_frames
        self._preroll: deque[bytes] = deque(maxlen=preroll_frames)
        self.reset()

    def reset(self) -> None:
        self._in_speech = False
        self._loud_run = 0
        self._quite_run = 0
        self._preroll.clear()

    def process(self, frame: bytes) -> VadResult:
        loud = dbfs(frame) > self._threshold

        if not self._in_speech:
            self._preroll.append(frame)
            self._loud_run = self._loud_run + 1 if loud else 0
            if self._loud_run >= self._start_frames:
                self._in_speech = True
                self._quite_run = 0

                frames = list(self._preroll)
                self._preroll.clear()

                return VadResult(VadEvent.SPEECH_START, frames)
            return VadResult()

        self._quite_run = 0 if loud else self._quite_run + 1
        if self._quite_run >= self._end_frames:
            self._in_speech = False
            self._loud_run = 0
            return VadResult(VadEvent.SPEECH_END)

        return VadResult(frames=[frame])
