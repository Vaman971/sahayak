# 0002: raw audio capture without browser dsp enhancements

- Status: accepted
- Date: 2026-10-10

## Context
Browsers apply automatic digital signal processing via `getUserMedia`: acoustic echo cancellation (AEC), noise suppression (NS), and automatic gain control (AGC). 

While convenient for conferencing, this dynamic processing interferes with our downstream speech models:
1. **Shifting noise floor:** Noise suppression dynamically gates background sound, making it hard to calibrate a baseline energy threshold for Voice Activity Detection (VAD).
2. **Gain limiting and attenuation:** On loud vocalizations, AGC engages hard limiting, while NS tends to attenuate sustained vowels and greeting syllables during filter convergence.

We ran a directional A/B benchmark in Chrome on a single laptop headset ($n=1$ per condition; directional, not statistical), toggling the DSP suite on versus off:

| Metric | All DSP Enabled (AEC, NS, AGC) | Raw Capture (All DSP Disabled) |
| --- | --- | --- |
| Ambient Silence (RMS) | -52.0 to -64.0 dBFS (drifting) | -45.5 dBFS (stable) |
| Conversational Speech (RMS) | -14.0 to -35.0 dBFS | -16.0 to -32.0 dBFS |
| Loud Peaks | -0.1 dBFS (limiter engaged) | -2.6 dBFS |
| Observation | Initial syllables attenuated; likely NS/AGC (not isolated per block) | Consistent signal level; steady room noise floor |

## Decision
Disable browser-side audio enhancements by default in `client/app.js` (`echoCancellation: false`, `noiseSuppression: false`, `autoGainControl: false`). Keep AEC available as an opt-in toggle in the UI for open-speaker testing.

## Alternatives Considered
- **All browser DSP enabled:** Discarded because dynamic gating prevents reliable local VAD energy tuning.
- **Selective DSP (AEC on, NS/AGC off):** The likely production configuration for open-speaker callers. Deferred until we test whether Chrome's AEC distorts speech when isolated from NS/AGC.
- **Server-side noise suppression (e.g., RNNoise):** Applying controlled DSP on the server ensures identical behavior across all clients. Viable, but introduces unnecessary CPU overhead before baseline VAD is tuned.

## Consequences
**What gets easier:**
- **Predictable VAD tuning:** A stable -45.5 dBFS noise floor allows clean separation between silence and speech (-16 to -32 dBFS).
- **Signal visibility:** What the microphone picks up is what the backend receives, making pipeline latency and level bugs easier to isolate.

**What gets harder:**
- **Speakerphone feedback and false barge-in:** Without AEC, agent playback from open laptop speakers will bleed back into the microphone, triggering false barge-ins. Testing currently requires headphones.