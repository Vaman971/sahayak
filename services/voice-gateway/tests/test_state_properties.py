from hypothesis import given, settings
from hypothesis import strategies as st
from voice_gateway.session.events import (
    CancelTurn,
    Event,
    ReplyAudioStarted,
    ReplyFinished,
    SpeechEnded,
    SpeechStarted,
    StartReply,
    TranscriptFinal,
)
from voice_gateway.session.state import State, TurnStateMachine

turn_ids = st.integers(min_value=0, max_value=6)
events: st.SearchStrategy[Event] = st.one_of(
    st.just(SpeechStarted()),
    st.just(SpeechEnded()),
    st.builds(TranscriptFinal, turn_id=turn_ids, text=st.sampled_from(["", "  ", "hello"])),
    st.builds(ReplyAudioStarted, turn_id=turn_ids),
    st.builds(ReplyFinished, turn_id=turn_ids),
)


# property based testing
@settings(max_examples=2000)
@given(st.lists(events, max_size=200))
def test_invariants_hold_for_any_event_sequence(seq: list[Event]) -> None:
    """Creating 2000 random event sequences including absurd ones.

    (eg: ten ReplyFinished in a row, stale ids, events in the wrong order).
    """
    sm = TurnStateMachine()
    replies_started: set[int] = set()
    prev_turn = 0

    for ev in seq:
        actions = sm.handle(ev)

        assert sm.turn_id >= prev_turn, "turn ids never go backwards"
        prev_turn = sm.turn_id

        for a in actions:
            if isinstance(a, StartReply):
                assert a.turn_id == sm.turn_id, "replies only start for the current turn"
                replies_started.add(a.turn_id)
            if isinstance(a, CancelTurn):
                assert a.turn_id < sm.turn_id, "we only cancel past turns"

        if sm.state is State.SPEAKING:
            assert sm.turn_id in replies_started, "never speak without a started reply"
        assert sm.interruptions <= sm.turn_id
