import asyncio
from collections.abc import AsyncIterator, Sequence

from voice_gateway.ports.llm import ChatMessage


class FakeLLM:
    """Streams a templated reply word by word with realistic-ish timing."""

    def __init__(self, first_token_delay_s: float = 0.3, token_delay_s: float = 0.03) -> None:
        self._first = first_token_delay_s
        self._each = token_delay_s

    async def stream_reply(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")

        reply = f"Aapne kaha: {user}. Main abhi check karta hoon."
        await asyncio.sleep(
            self._first
        )  # wait for the amount of time a token takes to appear, to make it feel realistic

        for word in reply.split(" "):
            yield word + " "
            await asyncio.sleep(self._each)  # wait for the time each token takes to appear
