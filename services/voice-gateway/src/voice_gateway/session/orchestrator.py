import asyncio
import time
from collections.abc import AsyncIterator, Coroutine
from dataclasses import asdict, dataclass, field
from typing import Any, assert_never

from sahayak_core.logging import get_logger

from voice_gateway.audio.format import PCM16_16K_MONO, AudioFormat
from voice_gateway.audio.framing import FrameAssembler
from voice_gateway.ports.asr import ASRPort
from voice_gateway.ports.client import (
    AgentText,
    ClientPort,
    StateChanged,
    TurnLatency,
    UserTranscript,
)
from voice_gateway.ports.llm import ChatMessage, LLMPort
from voice_gateway.ports.tts import TTSPort
from voice_gateway.ports.vad import VadEvent, VADPort
from voice_gateway.session.chunker import clauses
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
from voice_gateway.session.state import State, TurnStateMachine

log = get_logger()

DEFAULT_SYSTEM_PROMPT = (
    "You are Sahayak, a polite voice assistant for insurance and EMI queries. "
    "Reply in the caller's language mix, in one or two short sentences."
)


@dataclass(frozen=True, slots=True)
class SessionConfig:
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    mailbox_size: int = 1000
    audio_high_water: int = 100  # frames (2 s) queued before we start dropping input
    playout_queue_frames: int = 250  # 5 s of reply audio buffered at most
    playout_lead_ms: int = 200  # how far ahead of real time we send audio
    pace: bool = True
    endpoint_ms: int = 500  # must match the VAD's end hangover


SESSION = SessionConfig()


# ---- mailbox and playout items (private to the session) ----
@dataclass(frozen=True, slots=True)
class _AudioIn:
    frame: bytes


@dataclass(frozen=True, slots=True)
class _Shutdown:
    pass


@dataclass(frozen=True, slots=True)
class _Frame:
    turn_id: int
    pcm: bytes


@dataclass(frozen=True, slots=True)
class _EndOfReply:
    turn_id: int


_MailboxItem = _AudioIn | _Shutdown | Event
_PlayoutItem = _Frame | _EndOfReply


@dataclass
class Turn:
    turn_id: int
    asr_audio: asyncio.Queue[bytes | None] = field(default_factory=asyncio.Queue)
    asr_task: asyncio.Task[None] | None = None
    reply_task: asyncio.Task[None] | None = None
    marks: dict[str, float] = field(default_factory=dict)

    def cancel(self) -> None:
        for task in (self.asr_task, self.reply_task):
            if task is not None and not task.done():
                task.cancel()


def _ms(start: float, end: float) -> float:
    return round((end - start) * 1000, 1)


class CallSession:
    def __init__(
        self,
        *,
        call_id: str,
        client: ClientPort,
        vad: VADPort,
        asr: ASRPort,
        llm: LLMPort,
        tts: TTSPort,
        config: SessionConfig = SESSION,
        fmt: AudioFormat = PCM16_16K_MONO,
    ) -> None:
        self.call_id = call_id
        self._client = client
        self._vad = vad
        self._asr = asr
        self._llm = llm
        self._tts = tts
        self._cfg = config
        self._fmt = fmt

        self._sm = TurnStateMachine()
        self._mailbox: asyncio.Queue[_MailboxItem] = asyncio.Queue(maxsize=config.mailbox_size)
        self._playout: asyncio.Queue[_PlayoutItem] = asyncio.Queue(
            maxsize=config.playout_queue_frames
        )
        self._turns: dict[int, Turn] = {}
        self._cancelled: set[int] = set()
        self._history: list[ChatMessage] = [ChatMessage("system", config.system_prompt)]
        self._playout_task: asyncio.Task[None] | None = None

        self.dropped_frames = 0

    @property
    def interruptions(self) -> int:
        return self._sm.interruptions

    # --------------------------------------------------------------- inputs
    def push_audio(self, frame: bytes) -> None:
        """Called by the transport for every 20 ms frame. Never blocks."""
        if self._mailbox.qsize() >= self._cfg.audio_high_water:
            self.dropped_frames += 1  # late real-time audio is worthless: drop, count
            return
        self._mailbox.put_nowait(_AudioIn(frame))

    def close(self) -> None:
        self._post(_Shutdown())

    def _post(self, item: _MailboxItem) -> None:
        # Events always fit: audio stops at the high-water mark, far below maxsize
        try:
            self._mailbox.put_nowait(item)
        except asyncio.QueueFull:
            log.error("session.mailbox_full", item=type(item).__name__)

    # --------------------------------------------------------------- lifecycle
    async def run(self) -> None:
        try:
            async with asyncio.TaskGroup() as tg:
                self._playout_task = tg.create_task(self._playout_loop(), name="playout")
                tg.create_task(self._control_loop(), name="control")
        finally:
            for turn in self._turns.values():
                turn.cancel()

    def _spawn(self, coro: Coroutine[Any, Any, None], name: str) -> asyncio.Task[None]:
        task = asyncio.create_task(coro, name=name)  # copies contextvars: call_id rides along
        task.add_done_callback(self._on_task_done)
        return task

    @staticmethod
    def _on_task_done(task: asyncio.Task[None]) -> None:
        if not task.cancelled() and (exc := task.exception()) is not None:
            log.error("session.task_failed", task=task.get_name(), exc_info=exc)

    # ------------------------------------------------------------ control loop
    async def _control_loop(self) -> None:
        while True:
            item = await self._mailbox.get()  # FIFO: first event in, is the first event out
            match item:
                case _Shutdown():
                    break
                case _AudioIn(frame=frame):
                    await self._on_audio(frame)
                case _:
                    await self._dispatch(item)
        if self._playout_task is not None:
            self._playout_task.cancel()

    async def _on_audio(self, frame: bytes) -> None:
        result = self._vad.process(frame)
        if result.event is VadEvent.SPEECH_START:
            await self._dispatch(SpeechStarted())  # open ASR before we forward pre-roll

        self._forward_to_asr(result.frames)
        if result.event is VadEvent.SPEECH_END:
            await self._dispatch(SpeechEnded())

    def _forward_to_asr(self, frames: list[bytes]) -> None:
        if not frames or self._sm.state is not State.USER_SPEAKING:
            return

        turn = self._turns.get(self._sm.turn_id)
        if turn is not None:
            for f in frames:
                turn.asr_audio.put_nowait(f)

    async def _dispatch(self, event: Event) -> None:
        before = self._sm.state
        if isinstance(event, SpeechEnded) and (turn := self._turns.get(self._sm.turn_id)):
            turn.marks["speech_end"] = time.monotonic()

        for action in self._sm.handle(event):
            await self._apply(action)

        if self._sm.state is not before:
            log.info("turn.state", before=before, after=self._sm.state, turn_id=self._sm.turn_id)
            await self._client.notify(StateChanged(self._sm.state.value, self._sm.turn_id))

    async def _apply(self, action: Action) -> None:
        match action:
            case OpenAsr(turn_id=tid):
                for old_id in list(self._turns):  # only the current turn stays alive
                    self._turns.pop(old_id).cancel()
                turn = Turn(tid)
                self._turns[tid] = turn
                turn.asr_task = self._spawn(self._run_asr(turn), f"asr-{tid}")
            case FinalizeAsr(turn_id=tid):
                target_turn = self._turns.get(tid)
                if target_turn is not None:
                    target_turn.asr_audio.put_nowait(None)  # end-of-utterance sentinel
            case StartReply(turn_id=tid, user_text=text):
                turn = self._turns[tid]
                turn.reply_task = self._spawn(self._run_reply(turn, text), f"reply-{tid}")
            case CancelTurn(turn_id=tid):
                self._cancelled.add(tid)
                if tid in self._turns:
                    self._turns.pop(tid).cancel()
            case ClearPlayback():
                self._drain_playout()
                await self._client.clear_playback()
            case _:
                assert_never(action)

    def _drain_playout(self) -> None:
        while True:
            try:
                self._playout.get_nowait()
            except asyncio.QueueEmpty:
                return

    # --------------------------------------------------------------- turn work
    async def _run_asr(self, turn: Turn) -> None:
        async def audio() -> AsyncIterator[bytes]:
            while (frame := await turn.asr_audio.get()) is not None:
                yield frame

        parts: list[str] = []
        try:
            async for t in self._asr.stream(audio()):
                if t.is_final:
                    parts.append(t.text)
        except Exception:  # Cancelled Error is BaseException, so it still propogates
            log.exception("asr.failed", turn_id=turn.turn_id)

        text = " ".join(parts).strip()
        turn.marks["transcript"] = time.monotonic()
        if text:
            await self._client.notify(UserTranscript(turn.turn_id, text))
        self._post(TranscriptFinal(turn.turn_id, text))

    async def _run_reply(self, turn: Turn, user_text: str) -> None:
        tid = turn.turn_id
        self._history.append(ChatMessage("user", user_text))
        spoken: list[str] = []

        async def marked_tokens() -> AsyncIterator[str]:
            async for tok in self._llm.stream_reply(list(self._history)):
                turn.marks.setdefault("first_token", time.monotonic())
                yield tok

        async def speakable() -> AsyncIterator[str]:
            async for clause in clauses(marked_tokens()):
                spoken.append(clause)
                await self._client.notify(AgentText(tid, clause))
                yield clause

        try:
            assembler = FrameAssembler(self._fmt.frame_bytes)
            async for pcm in self._tts.synthesize(speakable()):
                for frame in assembler.push(pcm):
                    await self._playout.put(_Frame(tid, frame))  # blocks when full: backpressure

            if (tail := assembler.flush_padded()) is not None:
                await self._playout.put(_Frame(tid, tail))  # leftover bytes
        except Exception:
            log.exception("reply.failed", turn_id=tid)

        # Only reached if NOT cancelled
        if spoken:
            self._history.append(ChatMessage("assistant", " ".join(spoken)))

        await self._playout.put(_EndOfReply(tid))

    # ----------------------------------------------------------------- playout
    async def _playout_loop(self) -> None:
        frame_s = self._fmt.frame_ms / 1000
        lead_s = self._cfg.playout_lead_ms / 1000
        current: int | None = None
        clock_start = 0.0
        sent = 0

        while True:
            item = await self._playout.get()
            if item.turn_id in self._cancelled:
                continue
            if isinstance(item, _EndOfReply):
                self._post(ReplyFinished(item.turn_id))
                current = None
                continue

            now = time.monotonic()
            first = item.turn_id != current
            if first:
                current, clock_start, sent = item.turn_id, now, 0

            ahead = sent * frame_s - (now - clock_start)  # seconds of audio sent beyond real time
            if ahead < 0:  # TTS fell behind real time: re-anchor the clock
                clock_start, sent, ahead = now, 0, 0.0

            if self._cfg.pace and ahead > lead_s:
                await asyncio.sleep(ahead - lead_s)
                if item.turn_id in self._cancelled:  # barge-in happened while we slept
                    continue

            await self._client.send_audio(item.pcm)
            sent += 1
            if first:
                await self._on_first_audio(item.turn_id)

    async def _on_first_audio(self, tid: int) -> None:
        self._post(ReplyAudioStarted(tid))
        turn = self._turns.get(tid)
        if turn is None:
            return

        m = turn.marks
        m["first_audio"] = time.monotonic()
        if {"speech_end", "transcript", "first_token"} <= m.keys():
            lat = TurnLatency(
                turn_id=tid,
                endpoint_ms=self._cfg.endpoint_ms,
                asr_ms=_ms(m["speech_end"], m["transcript"]),
                llm_ms=_ms(m["transcript"], m["first_token"]),
                tts_ms=_ms(m["first_token"], m["first_audio"]),
                total_ms=_ms(m["speech_end"], m["first_audio"]),
            )
            log.info("turn.latency", **asdict(lat))
            await self._client.notify(lat)
