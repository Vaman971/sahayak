# 0002: raw audio capture without browser dsp enhancements

- Status: accepted
- Date: 2026-10-31

## Context
When streaming voice from a web browser to an upstream speech pipeline, browsers provide built-in digital signal processing: acoustic echo cancellation, automatic gain control, and noise suppression via `navigator.mediaDevices.getUserMedia`. 

While helpful for consumer conferencing, automated audio pre-processing introduces artifacts that interfere with downstream voice AI pipelines:
1. **Unpredictable noise floors:** Noise suppression algorithms dynamically gate room background sounds. Tuning a voice activity detector against gated audio risks misclassifying real-world caller environments such as raw telephony where the noise floor sits higher.
2. **Signal distortion on tonal or loud speech:** Heavy browser noise suppression and limiters frequently mistake sustained, loud, or tonal vocalizations for machine noise or feedback, aggressively clamping or suppressing human speech.
3. **Cold-start convergence latency:** Browser filters require 1 to 2 seconds to learn acoustic room properties, distorting the opening syllables of a caller's greeting.

To determine our client capture strategy, we executed an A/B benchmark comparing browser processing enabled against raw audio capture over identical 16 kHz mono streams, measuring root-mean-square loudness and peak levels.

| Metric | Browser DSP Enabled | Raw Audio Capture |
| --- | --- | --- |
| Ambient Silence (RMS) | -52.0 to -64.0 dBFS | -45.5 dBFS (stable) |
| Conversational Speech (RMS) | -14.0 to -35.0 dBFS | -16.0 to -32.0 dBFS |
| Loud Peaks | -0.1 dBFS (limiter engaged, 0 clips) | -2.6 dBFS (natural headroom) |
| Perceptual Quality | Distorted greeting; loud vocalizations muted | Natural, consistent reproduction throughout |

## Decision
We disable browser-side audio enhancements by default in `client/index.html` and `client/app.js` (`echoCancellation: false`, `noiseSuppression: false`, `autoGainControl: false`), capturing pristine raw audio directly from the input stream.

Our capture and buffering specifications are established as follows:
1. **Capture format:** 16 kHz, single-channel mono, 16-bit signed pulse-code modulation (`pcm_s16le`).
2. **AudioWorklet frame aggregation:** Browser `AudioWorkletProcessor` receives audio in native 128-sample blocks ($\approx 8\text{ ms}$ at 16 kHz). We buffer these in memory using an `Int16Array` accumulator to emit strict 20 ms frames (320 samples, 640 bytes) over the WebSocket.
3. **Pluggable digital signal processing:** Echo cancellation remains accessible as an opt-in client toggle for speakerphone configurations, while production VAD baseline tuning is calibrated strictly against raw -45.5 dBFS noise floors.
4. **Playback jitter management:** Inbound server audio feeds an 80,000-sample (5-second) ring buffer in `player-worklet.js` with a 60 ms pre-buffer (960 samples) threshold before initiating playback, preventing underruns caused by packet arrival jitter.

## Alternatives Considered
- **Default browser digital signal processing:** Standard WebRTC practice, but our measurements revealed automatic gain control hard-limiting at -0.1 dBFS and noise suppression completely dropping sustained loud syllables.
- **Server-side post-hoc artifact filtering:** Ingesting mangled browser-processed audio and attempting to reconstruct lost vocal energy downstream. This adds pipeline latency and cannot restore voice signals erased by browser gating.
- **Immediate per-sample transmission:** Forwarding each native 128-sample chunk without worklet frame aggregation. This incurs substantial network protocol overhead and breaks alignment with standard 20 ms downstream VAD and ASR processing windows.

## Consequences
**What gets easier:**
- **Deterministic VAD and ASR performance:** The speech model receives transparent, unaltered voice waveforms, eliminating clipping artifacts and ensuring predictable separation between background room noise (-45.5 dBFS) and spoken input (-16 to -32 dBFS).
- **Parity with telephony streams:** Browser testing mirrors raw 8 kHz and 16 kHz telephony codecs without masking acoustic defects behind client-side filters.
- **Clean start-of-utterance capture:** Eliminates initial filter