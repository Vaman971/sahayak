import asyncio
from collections.abc import Callable

import numpy as np
from voice_gateway.adapters.fakes.asr import ScriptedASR
from voice_gateway.adapters.fakes.llm import FakeLLM
from voice_gateway.adapters.fakes.tts import ToneTTS
from voice_gateway.adapters.vad.energy import energy_vad
from voice_gateway.audio.pcm import float32_to_pcm16
from voice_gateway.ports.client import AgentText, Notice, StateChanged, TurnLatency, UserTranscript
from voice_gateway.session.orchestrator import CallSession, SessionConfig

SILENCE = b"\x00\x00" * 320
_t = np.arange(320, dtype=np.float32) / 16000  # to keep between -1 to 1
LOUD = float32_to_pcm16((0.3 * np.sin(2 * np.pi * 300 * _t)).astype(np.float32))


class RecordingClient:
    def __init__(self) -> None:
        self.audio: list[bytes] = []
        self.notices: list[Notice] = []
        self.clears = 0

    async def send_audio(self, pcm: bytes) -> None:
        self.audio.append(pcm)

    async def clear_playback(self) -> None:
        self.clears += 1

    async def notify(self, notice: Notice) -> None:
        self.notices.append(notice)

    def states(self) -> list[tuple[str, int]]:
        return [(n.state, n.turn_id) for n in self.notices if isinstance(n, StateChanged)]


async def eventually(pred: Callable[[], bool], wait_time: float = 3.0) -> None:
    async with asyncio.timeout(wait_time):
        while not pred():  # noqa: ASYNC110
            await asyncio.sleep(0.005)


def make_session(
    client: RecordingClient, *, pace: bool = False, ms_per_char: int = 5
) -> CallSession:
    vad = energy_vad()
    return CallSession(
        call_id="test",
        client=client,
        vad=vad,
        asr=ScriptedASR(["claim status batao"], latency_s=0.01),
        llm=FakeLLM(first_token_delay_s=0.01, token_delay_s=0.0),
        tts=ToneTTS(first_audio_delay_s=0.0, ms_per_char=ms_per_char),
        config=SessionConfig(pace=pace),
    )


def speak(session: CallSession, loud: int = 20, trailing_silence: int = 30) -> None:
    for frame in [SILENCE] * 5 + [LOUD] * loud + [SILENCE] * trailing_silence:
        session.push_audio(frame)


async def test_full_turn_produces_transcript_reply_audio_and_latency() -> None:
    client = RecordingClient()
    session = make_session(client)
    runner = asyncio.create_task(session.run())

    speak(session)
    await eventually(lambda: ("listening", 1) in client.states())
    session.close()
    await runner

    assert client.states() == [
        ("user_speaking", 1),
        ("thinking", 1),
        ("speaking", 1),
        ("listening", 1),
    ]

    assert UserTranscript(1, "claim status batao") in client.notices
    assert any(isinstance(n, AgentText) for n in client.notices)
    assert any(isinstance(n, TurnLatency) for n in client.notices)
    assert client.audio
    assert all(len(f) == 640 for f in client.audio)


async def test_barge_in_cancels_reply_and_clears_playback() -> None:
    client = RecordingClient()
    session = make_session(client, pace=True, ms_per_char=60)  # ~3 s reply, paced in real time
    runner = asyncio.create_task(session.run())

    speak(session)
    await eventually(lambda: ("speaking", 1) in client.states())

    for frame in [LOUD] * 5:  # caller talks over the agent
        session.push_audio(frame)

    await eventually(lambda: ("user_speaking", 2) in client.states())

    sent_at_barge_in = len(client.audio)
    await asyncio.sleep(0.3)
    assert len(client.audio) == sent_at_barge_in, "no turn-1 audio may follow a barge-in"
    assert client.clears == 1
    assert session.interruptions == 1

    session.close()
    await runner
