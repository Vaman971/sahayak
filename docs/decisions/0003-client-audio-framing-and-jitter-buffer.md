# 0003: audio worklet frame aggregation and playback jitter buffer

- Status: accepted
- Date: 2026-10-15

## Context
Real-time voice models require audio chunked at fixed intervals. Our backend VAD and ASR pipelines expect 20 ms frames of 16 kHz mono PCM (`pcm_s16le`, 640 bytes).

However, browser capture and network delivery operate on mismatched boundaries:
1. **Capture mismatch:** The Web Audio API processes sound in blocks of 128 samples ($\approx 8\text{ ms}$ at 16 kHz). Forwarding each 128-sample block directly introduces high WebSocket frame overhead.
2. **Network arrival jitter:** Packets returning from the server over Wi-Fi arrive in uneven bursts. Feeding raw network chunks straight to audio output leads to buffer starvation (underruns), heard as audible clicks and crackling.

## Decision
1. **Capture format:** 16 kHz, single-channel mono, 16-bit signed PCM (`pcm_s16le`).
2. **Client frame aggregation (`capture-worklet.js`):** Accumulate incoming 128-sample blocks into an `Int16Array` buffer and emit strict 320-sample (20 ms, 640-byte) frames over the WebSocket using transferable array buffers.
3. **Playback jitter buffering (`player-worklet.js`):** Route incoming audio to an 80,000-sample (5-second) circular ring buffer. Require a 60 ms pre-buffer (960 samples) before initiating playback, and support an immediate `"clear"` control message to discard buffered audio on barge-in.

## Alternatives Considered
- **Direct 128-sample transmission:** Eliminates client-side accumulation latency ($\approx 12\text{ ms}$), but increases WebSocket packet volume by $2.5\times$ and shifts reassembly overhead to the server `FrameAssembler`.
- **Immediate unbuffered playback:** Lower latency to speaker, but results in frequent underruns whenever network delivery jitter exceeds 8 ms.

## Consequences
**What gets easier:**
- **Downstream alignment:** Backend receives uniform 640-byte frames aligned to standard 20 ms VAD inference windows.
- **Smooth playback:** The 60 ms pre-buffer tolerates transient network jitter without buffer starvation.
- **Fast barge-in response:** The circular buffer can be flushed instantly on an interruption signal, cutting agent playback latency to near zero.

**What gets harder:**
- **Latency trade-off:** Accumulating 20 ms at capture adds up to 12 ms of buffering lag, and the 60 ms playback buffer adds a fixed 60 ms delay to Time-To-First-Audio (TTFA).