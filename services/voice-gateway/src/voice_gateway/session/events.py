from dataclasses import dataclass


# ---- events: things that happened (inputs to the state machine) ----
@dataclass(frozen=True, slots=True)
class SpeechStarted:
    pass


@dataclass(frozen=True, slots=True)
class SpeechEnded:
    pass


@dataclass(frozen=True, slots=True)
class TranscriptFinal:
    turn_id: int
    text: str


@dataclass(frozen=True, slots=True)
class ReplyAudioStarted:
    turn_id: int  # helpful to send one last event after this turn is cancelled
    # (eg: reply finishes or transcript ready)


@dataclass(frozen=True, slots=True)
class ReplyFinished:
    turn_id: int


Event = SpeechStarted | SpeechEnded | TranscriptFinal | ReplyAudioStarted | ReplyFinished


# ---- action: things the orchestrator must do (outputs) ----
@dataclass(frozen=True, slots=True)
class OpenAsr:
    turn_id: int


@dataclass(frozen=True, slots=True)
class FinalizeAsr:
    turn_id: int


@dataclass(frozen=True, slots=True)
class StartReply:
    turn_id: int
    user_text: str


@dataclass(frozen=True, slots=True)
class CancelTurn:
    turn_id: int


@dataclass(frozen=True, slots=True)
class ClearPlayback:
    pass


Action = OpenAsr | FinalizeAsr | StartReply | CancelTurn | ClearPlayback
