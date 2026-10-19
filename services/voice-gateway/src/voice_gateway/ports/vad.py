"""
VAD is synchronous on Purpose.

Its pure CPU on 640 bytes; making it `async` would add overhead and hide
the real constraint, which is "be fast".
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class VadEvent(StrEnum):
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"


@dataclass(frozen=True, slots=True)
class VadResult:
    event: VadEvent | None = None
    frames: list[bytes] = field(default_factory=list)  # audio to forward to ASR


class VADPort(Protocol):
    """Called once per 20ms frame. Synchronous: must stay well under 1 ms of CPU."""

    def process(self, frame: bytes) -> VadResult: ...  # TODO

    def reset(self) -> None: ...  # TODO
