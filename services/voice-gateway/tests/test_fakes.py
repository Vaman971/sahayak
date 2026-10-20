from collections.abc import AsyncIterator

from voice_gateway.adapters.fakes.asr import ScriptedASR
from voice_gateway.adapters.fakes.llm import FakeLLM
from voice_gateway.adapters.fakes.tts import ToneTTS
from voice_gateway.ports.llm import ChatMessage


# generic type function similar to TypeVar
async def agen[T](items: list[T]) -> AsyncIterator[T]:
    for item in items:
        yield item


async def test_scripted_asr_returns_script() -> None:
    asr = ScriptedASR(["claim status batao"], latency_s=0)
    out = [t async for t in asr.stream(agen([b"\x00" * 640] * 5))]
    assert len(out) == 1
    assert out[0].text == "claim status batao"
    assert out[0].is_final


async def test_scripted_asr_describes_length_when_unscripted() -> None:
    asr = ScriptedASR(latency_s=0)
    out = [t async for t in asr.stream(agen([b"\x00" * 640] * 50))]  # 1 s
    assert out[0].text == "1000 ms ki awaaz"


async def test_fake_llm_streams_reply_containing_user_text() -> None:
    llm = FakeLLM(first_token_delay_s=0, token_delay_s=0)
    tokens = [t async for t in llm.stream_reply([ChatMessage("user", "EMI kab hai")])]
    assert len(tokens) > 3
    assert "EMI kab hai" in "".join(tokens)


async def test_tone_tts_length_tracks_text() -> None:
    tts = ToneTTS(first_audio_delay_s=0, ms_per_char=60)
    chunks = [c async for c in tts.synthesize(agen(["hello"]))]
    total = sum(len(c) for c in chunks)
    assert total == 5 * 60 * 16 * 2  # 5 chars * 60 ms * 16 samples/ms * 2 bytes
