from voice_gateway.session.events import (
    CancelTurn,
    ClearPlayback,
    FinalizeAsr,
    OpenAsr,
    ReplyAudioStarted,
    ReplyFinished,
    SpeechEnded,
    SpeechStarted,
    StartReply,
    TranscriptFinal,
)
from voice_gateway.session.state import State, TurnStateMachine


def test_happy_path() -> None:
    sm = TurnStateMachine()
    assert sm.handle(SpeechStarted()) == [OpenAsr(1)]
    assert sm.state is State.USER_SPEAKING
    assert sm.handle(SpeechEnded()) == [FinalizeAsr(1)]
    assert sm.state is State.THINKING
    assert sm.handle(TranscriptFinal(1, " claim status batao ")) == [
        StartReply(1, "claim status batao")
    ]
    assert sm.handle(ReplyAudioStarted(1)) == []
    assert sm.state is State.SPEAKING
    sm.handle(ReplyFinished(1))
    assert sm.state is State.LISTENING


def test_empty_transcript_returns_to_listening() -> None:
    sm = TurnStateMachine()
    sm.handle(SpeechStarted())
    sm.handle(SpeechEnded())
    assert sm.handle(TranscriptFinal(1, "   ")) == []
    assert sm.state == State.LISTENING


def test_barge_in_while_speaking() -> None:
    sm = TurnStateMachine()
    for ev in (SpeechStarted(), SpeechEnded(), TranscriptFinal(1, "hi"), ReplyAudioStarted(1)):
        sm.handle(ev)
    actions = sm.handle(SpeechStarted())
    assert actions == [CancelTurn(1), ClearPlayback(), OpenAsr(2)]
    assert sm.state is State.USER_SPEAKING
    assert sm.interruptions == 1


def test_stale_events_from_cancelled_turn_are_ignored() -> None:
    sm = TurnStateMachine()
    for ev in (SpeechStarted(), SpeechEnded(), TranscriptFinal(1, "hi"), ReplyAudioStarted(1)):
        sm.handle(ev)
    sm.handle(SpeechStarted())  # barge-in -> turn 2
    sm.handle(ReplyFinished(1))  # late event from the cancelled turn
    sm.handle(TranscriptFinal(1, "old"))
    assert sm.state is State.USER_SPEAKING
    assert sm.turn_id == 2


def test_audio_without_reply_is_ignored() -> None:
    sm = TurnStateMachine()
    sm.handle(SpeechStarted())
    sm.handle(SpeechEnded())
    sm.handle(ReplyAudioStarted(1))  # no StartReply was ever issued
    assert sm.state is State.THINKING
