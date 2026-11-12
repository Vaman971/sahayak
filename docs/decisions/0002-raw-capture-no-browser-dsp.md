# 0002: Capture raw microphone audio; browser processing off by default

- Status: accepted
- Date: 2026-10-10
- Revised: 2026-11-11 (default enforcement; speakerphone evidence pending)

## Context
`getUserMedia` can apply echo cancellation (AEC), noise suppression (NS), and automatic
gain control (AGC) before our code sees the audio. Our VAD and ASR are tuned on the audio
we capture, so any processing becomes part of the model's input.

A/B in Chrome, one laptop headset, one room (n=1 per condition; directional, not statistical):

| Metric                 | AEC + NS + AGC on                 | All off            |
| ---------------------- | --------------------------------- | ------------------ |
| Silence (RMS)          | -52 to -64 dBFS, drifting         | -45.5 dBFS, steady |
| Speech (RMS)           | -14 to -35 dBFS                   | -16 to -32 dBFS    |
| Loud peaks             | -0.1 dBFS, 0 clipped (limiter)    | -2.6 dBFS          |
| Listening              | Opening syllables and sustained loud vowels lost | Clean throughout |

The three blocks were toggled together, so the symptoms are attributed to NS and AGC
by likelihood, not by isolation.

## Decision
Capture with AEC, NS and AGC disabled by default. Enforce the default in code
(Chrome restores form state on reload, which silently re-enabled processing in two
later sessions). Keep a single opt-in toggle for all three, for speakerphone testing.

## Alternatives considered
- **All processing on (browser default):** rejected; it removed speech we need and
  made the noise floor drift between sessions.
- **AEC only:** the likely production setting for speakerphone callers. Deferred
  until we measure AEC in isolation.
- **Server-side noise suppression we control (e.g. RNNoise):** identical behaviour
  across clients, tuning and production. Deferred until real caller audio shows
  noise hurting ASR; it adds a stage we would have to keep identical everywhere.

## Consequences
- Easier: what the mic hears is what the server gets, so level, VAD and latency
  issues can be traced to one place.
- Easier: VAD and ASR are tuned on the same audio path they run on.
- Harder: open-speaker playback can leak into the mic and trigger false barge-in.
  Testing assumes headphones until AEC-only is evaluated.
- Not solved by this decision: the noise floor still varies by room and caller,
  so the VAD must adapt rather than rely on one measured floor.

## Revisit when
- The AEC-only experiment is run (speakers, AEC on vs off).
- We add telephony input (8 kHz, carrier-processed audio).