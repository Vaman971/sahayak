# 0001: uv monorepo with ports-and-adapters gateway

- Status: accepted
- Date: 2026-10-02

## Context
We are designing Sahayak, a real-time, low-latency code-mixed voice agent for handling complex insurance and EMI queries. Real-time voice agents carry specific architectural risks: tight vendor lock-in to external speech/AI providers (e.g., Sarvam, OpenAI, Deepgram), expensive API bills during testing, non-deterministic latency spikes, and fragmented shared code between multiple microservices (gateway, core banking mock, tool servers). 

We require an architecture that satisfies three constraints:
1. **Deterministic, zero-cost testing:** The ability to run rapid offline unit and integration tests without burning API tokens or relying on external network stability.
2. **Vendor pluggability:** Freedom to swap or benchmark different speech engines (e.g., testing Sarvam Saaras against alternative providers) without refactoring the core turn-orchestration engine.
3. **Monorepo ergonomics:** A unified repository setup where shared schemas, config, and utilities stay strictly typed and versioned across services without publishing intermediate packages to PyPI.

## Decision
We adopt a **uv workspace monorepo** containing decoupled services, paired with a **ports-and-adapters (hexagonal) architecture** for the core `voice-gateway` service. 

Under this design, the central session orchestrator interacts solely with abstract Python Protocols (`ASRPort`, `TTSPort`, `LLMPort`, `VADPort`), while concrete vendor SDKs and network calls live entirely within isolated adapter packages (`adapters/sarvam`, `adapters/silero`, `adapters/fakes`). Shared configurations, logging, and schemas are centralized in `packages/core` and linked via uv workspace references.

## Alternatives Considered
- **Single flat package repository:** Quickest to set up initially, but couples domain session logic directly with third-party vendor clients. This forces tests to monkey-patch external SDKs, leaks vendor models across business logic, and makes benchmarking alternative providers tedious.
- **Multi-repo architecture (Polyrepo):** Separating the gateway, MCP tools, and mock banking services into isolated repositories creates excessive tooling overhead, requires internal PyPI package publishing workflows for shared schemas (`sahayak-core`), and complicates atomic cross-service integration testing.
- **Direct vendor integration in session orchestrator:** Writing vendor-specific API and WebSocket calls directly inside the call session state machine. This eliminates abstraction layers but makes deterministic testing impossible, turns barge-in handling into provider-dependent spaghetti code, and permanently couples the platform to one vendor's API contract.

## Consequences
**What gets easier:**
- **Instant offline testing:** Real call scenarios can be simulated in milliseconds using deterministic fake adapters in `pytest` without incurring API fees or network delays.
- **Benchmarking & vendor independence:** Swapping or multi-homing providers (e.g., comparing Sarvam's real-time ASR against Deepgram or Whisper) only requires implementing a new adapter complying with the port protocol.
- **Developer velocity:** `uv workspace` gives sub-second package resolution, strict unified lockfiles, and direct cross-package imports across `core` and `voice-gateway` without manual builds.

**What gets harder:**
- **Initial boilerplate:** Requires defining strict interface protocols, abstract data structures, and fake implementations upfront before processing the first live audio frame.
- **Adapter parity maintenance:** If an underlying provider introduces specialized streaming features (such as provider-specific mid-call parameter reconfigurations or unique WebSocket control flags), the port abstractions must be thoughtfully updated to accommodate them without leaking vendor concepts into the core state machine.