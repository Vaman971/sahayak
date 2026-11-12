import re
from collections.abc import AsyncIterator

# Punctuation followed by whitespace: avoids splitting "4.5" or "Rs.500"
_BOUNDARY = re.compile(r"[.!?|,;:]\s")


def _find_cut(buf: str, min_chars: int, max_chars: int) -> int | None:
    for m in _BOUNDARY.finditer(buf):
        if m.end() >= min_chars:
            return m.end()
    if len(buf) >= max_chars:
        space = buf.rfind(" ", 0, max_chars)
        return space + 1 if space > 0 else max_chars
    return None


async def clauses(
    tokens: AsyncIterator[str], min_chars: int = 12, max_chars: int = 120
) -> AsyncIterator[str]:
    """Groups streamed LLM tokens into speakable clauses for TTS."""
    buf = ""
    async for tok in tokens:
        buf += tok
        while (cut := _find_cut(buf, min_chars, max_chars)) is not None:
            piece, buf = buf[:cut].strip(), buf[cut:]

            if piece:
                yield piece
    if buf.strip():
        yield buf.strip()
