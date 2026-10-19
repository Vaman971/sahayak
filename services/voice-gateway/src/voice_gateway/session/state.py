from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import assert_never

from voice_gateway.session.events import (
    Action,
    CancelTurn,
    ClearPlayback,
    Event,
    FinalizeAsr,
    OpenAsr,
    ReplyAudioStarted,
    ReplyFinished,
    SpeechEnded,
    SpeechStarted,
    StartReply,
    TranscriptFinal,
)


class State(StrEnum):
    LISTENING = "listening"
    USER_SPEAKING = "user_speaking"
    THINKING = "thinking"
    SPEAKING = "speaking"


@dataclass(frozen=True, slots=True)
class Transition:
    before: State
    after: State
    event: str


@dataclass
class TurnStateMachine:
    """Pure turn logic: events in, actions out. No I/O, no clock, no asyncio."""

    state: State = State.LISTENING
    turn_id: int = 0
    reply_turn: int | None = None  # turn whose reply is currently running
    interruptions: int = 0
    history: deque[Transition] = field(
        default_factory=lambda: deque(maxlen=100)
    )  # a debuggable trail per call without unbounded memory growth

    def handle(self, event: Event) -> list[Action]:
        before = self.state  # what state was the conversation in
        actions = self._dispatch(event)  # what action taken
        self.history.append(
            Transition(before, self.state, type(event).__name__)
        )  # having the change of state traced
        return actions

    def _begin_user_turn(self) -> list[Action]:
        self.turn_id += 1
        self.reply_turn = None  # without it a stray ReplyAudioStarted for the current turn
        # could flip us into SPEAKING before any reply was ever started
        self.state = State.USER_SPEAKING
        return [OpenAsr(self.turn_id)]  # when a user speaks, ASR triggers

    def _dispatch(self, event: Event) -> list[Action]:
        match event:
            case SpeechStarted():
                if self.state is State.LISTENING:
                    return self._begin_user_turn()
                if self.state in (State.THINKING, State.SPEAKING):
                    self.interruptions += 1
                    old = self.turn_id
                    return [CancelTurn(old), ClearPlayback(), *self._begin_user_turn()]

                return []  # already USER_SPEAKING

            case SpeechEnded():
                if self.state is State.USER_SPEAKING:
                    self.state = State.THINKING
                    return [FinalizeAsr(self.turn_id)]
                return []

            case TranscriptFinal(turn_id=tid, text=text):
                if tid != self.turn_id or self.state is not State.THINKING:
                    return []  # stale or out of order

                if not text.strip():
                    self.state = State.LISTENING  # cough, click, false trigger
                    return []

                self.reply_turn = tid  # now its time to prepare for a reply
                return [StartReply(tid, text.strip())]

            case ReplyAudioStarted(turn_id=tid):
                if self.state is State.THINKING and tid == self.reply_turn:
                    self.state = State.SPEAKING
                return []

            case ReplyFinished(turn_id=tid):
                if tid == self.reply_turn and self.state in (State.THINKING, State.SPEAKING):
                    self.state = State.LISTENING
                    self.reply_turn = None
                return []

            case _:
                assert_never(event)  # to prove mypy, we handled every event type
