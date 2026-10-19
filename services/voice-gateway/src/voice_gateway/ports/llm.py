from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


class LLMPort(Protocol):
    """Streams reply text as it is generated. Tool calls are added in a later step."""

    def stream_reply(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]: ...
