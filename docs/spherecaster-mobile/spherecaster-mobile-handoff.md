# The Telling — Mobile Handoff Design Document

**Product:** The Telling — Audiobook Production Studio (SphereCaster Press)
**Web origin:** `https://app.spherecaster.com`
**Target:** Native mobile apps for iOS and Android
**Document type:** Engineering + product handoff / implementation design
**Status:** Draft v1 — for review
**Date:** 2026-08-12

---

## 0. How to read this document

This is a handoff design document. It is meant to give a mobile team enough
product context, architectural direction, and scoping to start building
without re-discovering the web product from scratch. It is opinionated where a
decision is needed and explicit where a decision is still open.

Sections that carry the most weight for a first sprint:

- §3 — What actually translates to mobile (and what should not)
- §5 — Recommended architecture
- §6 — Screen inventory and navigation
- §7 — The audio pipeline on mobile (the single hardest problem)
- §12 — Phased roadmap
- §13 — Open questions the web team must answer before build

---

## 1. Product summary

The Telling is a browser-based **audiobook production studio** published by
SphereCaster Press. It converts structured manuscripts into
professional-quality audiobooks using text-to-speech (TTS) synthesis with
fine-grained, per-passage voice control. It is a *production tool for authors
and publishers*, not a consumer listening app.

Its sibling/consumer surface is **PalmCaster** (`spherecaster.com/books`), the
catalog/storefront where finished works are published. The Telling is the
*creation* side; PalmCaster is the *distribution/listening* side. This
distinction matters for mobile scoping — see §3.

### Positioning in one sentence

> "Drop in a manuscript, cast voices to your narrator and characters,
> synthesize, master in the browser, and export a finished audiobook —
> re-rendering only the passages you change."

---

## 2. The production pipeline (as observed)

The web app presents a **seven-stage pipeline**. This is the core mental model
the mobile app must respect, whether or not every stage lives on the phone.

| # | Stage | What it does | Key mechanic |
|---|-------|--------------|--------------|
| 1 | **Ingest & segment** | Author drops in structured chapter files; the system slices prose at sentence and paragraph boundaries into synthesis-ready **passages**. | Deterministic segmentation; passage is the atomic unit. |
| 2 | **Cast the voices** | Assign voices to the narrator and to individual characters, using current speech models. Legacy voice profiles are auto-mapped to current models. | Character → voice mapping; model versioning. |
| 3 | **Voice it** | Synthesis runs to completion unattended. Rate limits and cooldowns are handled with throttling and retry. | Long-running, async, provider-rate-limited jobs. |
| 4 | **Reconcile changes** | Editing a paragraph re-renders only that paragraph — never the whole book. | **Text fingerprinting** for selective re-render. |
| 5 | **Master** | Set *pacing, resonance, and intensity*; compile chapter audio in the browser. | In-browser mixing via **WebCodecs**. |
| 6 | **Export** | Ship per-chapter files with custom **ID3v2** metadata, or one continuous stitched master in optimized **AAC**. | Per-chapter or single-file export. |
| 7 | **Revise & reship** | Return, change a scene, re-voice only the delta, re-export. | "Version control for audio." |

### Domain data model implied by the pipeline

```
Project (audiobook / volume; may belong to a multi-volume work)
 └─ Chapter (ordered; unit of export)
     └─ Passage (sentence/paragraph unit; the atomic synthesis + fingerprint unit)
         ├─ text
         ├─ text_fingerprint (drives selective re-render)
         ├─ speaker / character assignment
         ├─ render_state (pending | rendering | rendered | stale | failed)
         └─ audio_asset (per-passage rendered clip)

Character (narrator + named roles)
 └─ voice_assignment → { model_id, voice_id, legacy_profile? }

Master (compiled chapter audio; pacing/resonance/intensity settings)
Export (artifact: per-chapter files w/ ID3v2, or stitched AAC master)
```

This model is the contract the mobile app should sync against. Confirm exact
field names and states with the web team (§13).

---

## 3. What translates to mobile — and what should not

The single most important scoping decision: **The Telling is a
production-heavy, desktop-shaped tool.** Manuscript ingestion, long-form text
editing, and in-browser mastering are poor fits for a phone. Trying to port
all seven stages 1:1 to a 6-inch screen would produce a bad app and a long
timeline.

Recommended framing: **the mobile app is a companion + review + control
surface for production, plus a first-class listening/QA experience** — not a
full desktop replacement (at least in v1–v2).

| Pipeline stage | Mobile fit | Recommendation |
|---|---|---|
| 1. Ingest & segment | Poor (file handling, large text) | Defer. Allow *viewing* segmented passages; author-side ingestion stays on web. Optionally: import a file via Files/SAF in a later phase. |
| 2. Cast the voices | **Good** | Full support. Casting is list-and-pick UI — ideal for touch. Preview voices inline. |
| 3. Voice it (synthesize) | **Good as control** | Trigger/monitor renders; receive push on completion. Execution stays server-side. |
| 4. Reconcile changes | Medium | Support light passage-level text edits + re-render. Heavy editing stays web. |
| 5. Master | **Hard** — see §7 | Move mastering server-side; phone sends settings, plays result. Do **not** attempt WebCodecs-equivalent mixing on device in v1. |
| 6. Export | **Good** | Trigger export, monitor, download, and share via native share sheet / Files. |
| 7. Revise & reship | **Good** | Natural fit for a companion app: review, tweak, re-voice delta, re-export on the go. |
| **Review & QA listening** | **Excellent** | *New* first-class mobile capability: listen to rendered chapters/passages, flag issues, approve. This is where mobile adds unique value. |

### The strategic insight

Authors already produce at a desk. What they *cannot* do well today is
**review and steer production away from the desk** — listen to a freshly
rendered chapter on a commute, catch a mispronunciation, flag the passage,
kick off a re-render, and approve the export. That review/steer loop is the
mobile app's reason to exist. Build that first; expand toward editing later.

---

## 4. Evaluation notes & confidence

What is **directly observed** from the public site:

- Marketing pages (`/`, `#how`, `#showcase`, `#who`), the seven-stage pipeline
  copy, terminology (passages, fingerprinting, WebCodecs, ID3v2, AAC, legacy
  profile auto-mapping), and navigation into `/studio?login=1` /
  `/studio?signup=1`.
- The consumer catalog at `spherecaster.com/books` (PalmCaster), which lists
  formats (Hardbound, Paperback, E-book, Audiobook), series, and sorting.

What is **not observable** (studio is authentication-gated):

- The actual studio UI, its component structure, and the JS framework/bundle.
- The synthesis provider(s), model IDs, and rate-limit specifics.
- The real API surface, auth mechanism, and data schema.
- Pricing/entitlement model.

**Confidence:** High on product intent and pipeline shape; Low on internal
implementation specifics. Every "assumed" item below is flagged, and §13
collects the questions that must be answered before or during build. This
document is safe to plan against but must be reconciled with the web team's
actual API before committing schemas.

---

## 5. Recommended architecture

### 5.1 Client framework

**Recommendation: React Native (with the New Architecture / Fabric + TurboModules), TypeScript.**

Rationale:

- One codebase for iOS + Android with near-native UI, matched to a small
  studio-scale team.
- The web product is almost certainly TypeScript; RN maximizes shared types,
  validation logic, and (potentially) shared API-client code.
- Native audio and background work are reachable via native modules where RN
  falls short (see §7).

Alternatives considered:

- **Flutter** — excellent UI performance and consistency; viable. Weaker
  code/type sharing with a TS web app, and audio still needs platform channels.
  Choose this if the team's strength is Dart, not TS.
- **Fully native (Swift + Kotlin)** — best audio control, highest cost. Justify
  only if on-device mastering becomes a hard v1 requirement (it should not — §7).
- **PWA / wrapped webview** — rejected. Background synthesis, native audio
  session handling, offline audio, push, and store distribution all fight the
  webview model. A thin webview for a legacy editor screen is acceptable as an
  interim bridge, not as the app.

### 5.2 System shape

```
┌─────────────────────────────┐        ┌──────────────────────────────┐
│  Mobile app (iOS / Android) │        │  The Telling backend          │
│                             │        │                              │
│  • Auth + session           │◀──────▶│  • Auth / accounts           │
│  • Project/chapter/passage  │  REST/ │  • Segmentation service      │
│    browse + light edit      │  gRPC  │  • Synthesis orchestrator ───┼──▶ TTS provider(s)
│  • Casting UI               │        │  • Mastering (server-side) ──┼──▶ render farm
│  • Render/export control    │        │  • Export/packaging (ID3v2,  │
│  • Native audio playback    │◀──────▶│    AAC stitch)               │
│  • Offline cache            │  CDN   │  • Object storage / CDN ─────┼──▶ audio assets
│  • Push receipt             │◀──push─│  • Push (APNs / FCM)         │
└─────────────────────────────┘        └──────────────────────────────┘
```

**Key architectural bet:** move **mastering and export packaging to the
server** so the phone never needs a WebCodecs equivalent. The phone sends
mastering *parameters* (pacing/resonance/intensity per chapter/passage) and
streams/downloads the rendered result. This is the difference between a
6-week app and a 6-month one. See §7 for the full argument.

### 5.3 Data & sync

- **Local store:** SQLite (via WatermelonDB, or Expo SQLite + a light ORM) for
  project/chapter/passage metadata and render state. Audio assets cached on the
  filesystem, indexed by asset id + fingerprint.
- **Sync model:** server is source of truth. Pull project trees on open;
  subscribe to render/export state changes (see §5.4). Passage edits are
  optimistic with server reconciliation on the fingerprint.
- **Cache invalidation:** keyed on `text_fingerprint` + `model_id`. If either
  changes server-side, the cached passage audio is stale and re-fetched.

### 5.4 Realtime / long-running jobs

Synthesis, mastering, and export are **long-running and asynchronous**. Mobile
OSes aggressively suspend apps, so the app must not depend on staying
foregrounded.

- **Job status transport:** WebSocket/SSE while foregrounded for live progress;
  **push notification** (APNs/FCM) for terminal transitions (render complete,
  export ready, render failed) so the user is pulled back.
- **On resume:** always re-fetch job state from the server rather than trusting
  a possibly-stale socket. Treat push as a *hint*, the API as the *truth*.

---

## 6. Screen inventory & navigation

Proposed information architecture. Tab bar with four roots plus modal flows.

```
Tab 1  Library        → Projects → Chapters → Passages
Tab 2  Cast           → Characters ↔ Voices (per project)
Tab 3  Render Queue   → active + recent synthesis/master/export jobs
Tab 4  Account        → profile, entitlements, storage, settings

Modal / drill-in flows:
  • Passage detail (text, speaker, render state, audio, re-render)
  • Voice picker + preview
  • Master settings (pacing / resonance / intensity)
  • Export sheet (per-chapter ID3v2 vs stitched AAC; share/download)
  • Player (chapter + passage-level scrub, flag, approve)
```

### 6.1 Screen-by-screen

1. **Auth** — Sign in / Create free account (maps to `/studio?login=1` /
   `?signup=1`). Support OAuth/SSO if the web app does; secure token storage in
   Keychain/Keystore.

2. **Library (Projects)** — List of projects/volumes with cover, title, author,
   and a production-status chip (e.g. *3/12 chapters rendered*, *export ready*).
   Multi-volume works grouped.

3. **Project → Chapters** — Ordered chapter list; each row shows render
   progress, staleness (any passage re-render pending), and last-exported time.

4. **Chapter → Passages** — The reading/QA spine. Each passage shows text,
   assigned speaker, render state (pending/rendering/rendered/**stale**/failed),
   and an inline play button. Stale passages are visually distinct — this is the
   "reconcile" surface.

5. **Passage detail** — Full text, speaker reassignment, light text edit
   (edit → new fingerprint → offer re-render), audio scrubber, per-passage
   *pacing/resonance/intensity* overrides if the model supports them, and a
   **Flag / Approve** control for QA.

6. **Cast** — Character list ↔ voice assignments for the project. Tap a
   character → **Voice picker** with searchable voice list, model grouping,
   legacy-profile mapping indicator, and **inline preview** (play a sample line
   in that voice). Re-casting a character marks affected passages stale.

7. **Render Queue** — Unified job center: synthesis, master, and export jobs
   with progress, throttling/cooldown state, retry affordance, and failure
   detail. Deep-linked from push notifications.

8. **Master settings** — Per-chapter (and optionally per-passage) *pacing,
   resonance, intensity*. Sends parameters to the server-side master; shows a
   preview once compiled.

9. **Export** — Choose per-chapter (with editable ID3v2 metadata: title, author,
   narrator, track, cover art) or single stitched AAC master. Trigger →
   monitor → download → **native share sheet** / save to Files.

10. **Player** — First-class listening for QA: chapter playback with
    passage-boundary scrubbing, playback speed, background audio + lock-screen
    controls, sleep timer, and quick **flag-this-passage** during listening.

11. **Account** — Profile, entitlements/plan, on-device storage usage &
    cache management, downloads, notification prefs, sign out.

### 6.2 Navigation principles

- Deep-linkable everywhere (push → exact passage/job).
- The **passage** is the smallest addressable unit across browse, edit, render,
  and QA — keep its representation consistent in every screen.
- Destructive/expensive actions (mass re-render, re-export) confirm and show
  cost/time estimate.

---

## 7. The audio pipeline on mobile (the hardest problem)

The web app masters **in the browser using WebCodecs** and exports stitched
AAC with ID3v2. There is no drop-in WebCodecs on iOS/Android native, and
reimplementing a mixing/mastering engine per platform is expensive and
error-prone. Two viable strategies:

### Strategy A — Server-side mastering (RECOMMENDED for v1–v2)

- The phone sends **parameters** (pacing/resonance/intensity, chapter
  composition, export format) to a server-side mastering/packaging service that
  already exists conceptually (the render farm behind stages 5–6).
- The phone **plays and downloads** finished audio; it never mixes.
- **Pros:** small, fast, consistent output identical to web; no per-platform
  DSP; trivially correct ID3v2/AAC. **Cons:** requires network to master/export;
  needs a server API that may not exist yet as a headless service (§13).

**Playback stack:**
- iOS: `AVAudioEngine` / `AVPlayer` with a properly configured
  `AVAudioSession` (`.playback` category) for background + lock-screen +
  CarPlay/AirPlay; `MPNowPlayingInfoCenter` + remote command center.
- Android: Media3 (ExoPlayer) with a `MediaSessionService` /
  `MediaLibraryService`, `AudioAttributes` for speech, audio-focus handling,
  and a media-style notification.
- In RN: wrap via `react-native-track-player` (covers both platforms'
  background audio, lock-screen controls, and queueing) unless a custom native
  module is warranted.

### Strategy B — On-device mastering (defer; only if truly required)

- iOS: `AVAudioEngine` graph + `AVAudioUnitTimePitch`/EQ for
  pacing/resonance/intensity; `AVAssetWriter` for AAC; ID3v2 via a tag library.
- Android: `AudioTrack`/Oboe + `MediaCodec`/`MediaMuxer` for AAC; ID3v2 tagging
  library.
- **Only pursue** if offline mastering/export is a hard product requirement.
  Even then, ship Strategy A first and treat B as an enhancement.

### Decision

Adopt **Strategy A**. Record Strategy B as a future capability behind a clear
requirement ("author must be able to export with no connectivity"). Confirm in
§13 whether a headless server master/export API exists or must be built.

### Audio storage & bandwidth

- Rendered passage clips and chapter masters can be large. Cache on device with
  an LRU budget the user can see and clear (Account screen).
- Prefer **streaming/range requests** for QA listening; **explicit download**
  for offline. Show sizes before download on cellular; respect a Wi-Fi-only
  toggle.
- Key every cached asset by `asset_id + fingerprint + model_id` so a re-render
  cleanly supersedes the old clip.

---

## 8. Background execution, notifications, offline

### Background execution
- Do **not** run synthesis/master on-device in the background — it is
  server-side. The app's background needs are (a) **audio playback** (allowed
  via the audio background mode) and (b) **short refreshes** to reconcile job
  state (iOS BGTaskScheduler / Android WorkManager).
- Downloads that must survive backgrounding: iOS `URLSession` background
  configuration; Android `WorkManager` + `DownloadManager`.

### Notifications
- APNs (iOS) + FCM (Android). Categories: *render complete*, *render failed*,
  *export ready*. Each deep-links to the relevant job/passage.
- Respect quiet-hours and per-category opt-outs (Account settings).

### Offline
- **Read-optative offline:** browse cached project trees, read passage text,
  play downloaded audio, queue edits/casting changes that sync on reconnect.
- Editing/casting while offline queues intent; **re-render and export require
  connectivity** and surface that clearly rather than failing silently.

---

## 9. Feature parity matrix (web → mobile v1)

| Capability | Web | Mobile v1 | Notes |
|---|---|---|---|
| Manuscript ingest & segment | ✅ | ➖ view only | Author-side ingest stays on web. |
| Browse projects/chapters/passages | ✅ | ✅ | Core. |
| Cast voices to narrator/characters | ✅ | ✅ | With inline voice preview. |
| Voice preview | ✅ (assumed) | ✅ | Sample line per voice/model. |
| Trigger synthesis | ✅ | ✅ | Server-executed; monitored on device. |
| Monitor synthesis (throttle/cooldown) | ✅ | ✅ | Render Queue + push. |
| Selective re-render (fingerprint) | ✅ | ✅ | Edit passage → re-voice delta. |
| Light passage text edit | ✅ | ✅ | Heavy editing stays web. |
| Master (pacing/resonance/intensity) | ✅ (in-browser) | ✅ params → server | See §7. |
| Export per-chapter w/ ID3v2 | ✅ | ✅ | Editable metadata + cover. |
| Export stitched AAC master | ✅ | ✅ | Server-packaged; share/download. |
| Revise & reship | ✅ | ✅ | Companion sweet spot. |
| QA listening + flag/approve | (implicit) | ✅ **new** | Mobile's differentiator. |
| Multi-volume management | ✅ (assumed) | ✅ | Grouped in Library. |

---

## 10. Non-functional requirements

- **Performance:** lists (passages can number in the thousands per book) must
  virtualize; render-state chips must update without full re-render. Target
  60fps scrolling and <150ms interaction latency on mid-tier devices
  (e.g. iPhone SE 2, Pixel 6a).
- **Accessibility:** full VoiceOver/TalkBack labels; Dynamic Type / font
  scaling (this is a *text* product — respect it); sufficient contrast;
  captions/transcript alignment during playback is a natural win.
- **Localization:** structure for i18n from day one even if English-only at
  launch; audiobook production is inherently language-aware.
- **Security:** tokens in Keychain/Keystore; certificate pinning to the API;
  no manuscript text or audio in logs/analytics; biometric app-lock option
  (manuscripts are unpublished IP).
- **Privacy/store compliance:** clear data-use disclosure; App Tracking
  Transparency (iOS) if any tracking; Android Data Safety form; handle
  account deletion per store policy.
- **Observability:** crash reporting, structured analytics on the
  render/export funnel, and audio-playback error telemetry.

---

## 11. Platform-specific considerations

### iOS
- `AVAudioSession` category `.playback`; background mode `audio`.
- `MPNowPlayingInfoCenter` + `MPRemoteCommandCenter` for lock screen / CarPlay.
- Background downloads via background `URLSession`.
- BGTaskScheduler for opportunistic job-state refresh.
- Files app integration for import/export; share sheet for finished audio.
- App Store review: ensure any external purchase links comply; declare
  background audio use honestly.

### Android
- Media3/ExoPlayer + `MediaSessionService`; proper audio focus + becoming-noisy
  handling; media-style notification.
- Storage Access Framework for file import/export; scoped storage compliance.
- WorkManager + `DownloadManager` for durable background downloads.
- FCM for push; notification channels per category.
- Play Console: Data Safety, foreground-service type `mediaPlayback`.

---

## 12. Phased roadmap

**Phase 0 — Foundations (spec + spike)**
- Confirm API surface, auth, data schema, and whether a headless server-side
  master/export exists (§13). Audio playback spike on both platforms with a
  real rendered file. De-risk background download + push.

**Phase 1 — Companion & QA (MVP)**
- Auth, Library, Chapters, Passages (browse + play), Render Queue + push,
  QA listening with flag/approve. Read-mostly. Ships the review/steer loop.

**Phase 2 — Control**
- Casting with voice preview, trigger synthesis, selective re-render on
  passage edit, server-side master params, export (ID3v2 + stitched AAC) with
  share. This is "production from your pocket."

**Phase 3 — Depth & offline**
- Offline caching/downloads, richer editing, multi-volume workflows,
  per-passage mastering overrides, optional on-device export (Strategy B) if
  the requirement is confirmed.

**Phase 4 — Polish & platform surfaces**
- CarPlay/Android Auto for QA listening, widgets (render progress), Handoff/
  deep-link continuity with web, localization.

---

## 13. Open questions for the web team (blockers first)

**Must answer before build:**
1. **API:** Is there a documented REST/gRPC API, or is the studio a
   tightly-coupled SPA with private endpoints? Can it expose a stable contract?
2. **Auth:** Mechanism (session cookie, OAuth, JWT)? Refresh/rotation?
   SSO/social login?
3. **Mastering/export as a service:** Does mastering exist server-side, or is
   WebCodecs in-browser the *only* implementation today? (Determines §7
   feasibility and Phase 2 timeline.)
4. **Data schema:** Confirm entity names, fields, and render-state enum for
   Project/Chapter/Passage/Character/Voice/Master/Export.
5. **Synthesis provider(s) & models:** Which TTS provider(s), model IDs, voice
   catalog shape, and the exact rate-limit/cooldown semantics to reflect in UI.

**Should answer during Phase 0/1:**
6. Fingerprinting algorithm and staleness rules (so the app renders "stale"
   accurately).
7. Voice preview: is there an endpoint to synthesize a sample line on demand?
8. Entitlements/pricing model and how it gates features on mobile (+ store
   billing implications).
9. File formats accepted at ingest and whether mobile import is desired.
10. Relationship to PalmCaster: should finished works publish to PalmCaster
    from mobile, and is any listener-side surface in scope?
11. Analytics/observability standards to match the web product.

---

## 14. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| No headless server master/export API exists (WebCodecs is the only path) | High — blocks Phase 2 mastering/export | Confirm in Phase 0; if true, prioritize building the server service or scope mobile to review-only until it exists. |
| Long-running jobs vs. OS background limits | Medium | Server-side execution + push; never depend on foreground. |
| Large audio storage/bandwidth on device | Medium | Streaming for QA, explicit downloads, LRU cache with user control, Wi-Fi-only default. |
| Manuscript IP leakage | High (trust) | Keychain/Keystore, pinning, no content in logs/analytics, biometric lock. |
| Studio API is private/unstable SPA-internal | High — schema churn | Negotiate a versioned contract; wrap in a mobile BFF if needed. |
| Scope creep toward full desktop parity | Medium — timeline | Hold the "companion + QA first" line; editing is Phase 3. |

---

## 15. Handoff checklist

- [ ] Web team confirms API contract, auth, and data schema (§13 #1, #2, #4)
- [ ] Decision recorded on server-side vs on-device mastering (§7)
- [ ] Voice catalog + preview endpoint confirmed (§13 #5, #7)
- [ ] Push (APNs/FCM) infra and payload schema agreed (§5.4, §8)
- [ ] Framework decision ratified (RN recommended) (§5.1)
- [ ] Phase 1 backlog cut from §6/§9 with acceptance criteria
- [ ] Design: high-fidelity comps for Library, Passages, Cast, Player, Export
- [ ] Store accounts, signing, and Data Safety / privacy disclosures prepared
- [ ] Analytics/observability plan aligned with web (§13 #11)

---

## Appendix A — Glossary

- **Passage** — atomic sentence/paragraph unit of text; the unit of synthesis,
  fingerprinting, and selective re-render.
- **Fingerprint** — hash of passage text (and likely voice/model) used to
  detect change and drive selective re-render and cache invalidation.
- **Cast / Casting** — assigning voices to the narrator and named characters.
- **Legacy profile auto-mapping** — old voice profiles automatically mapped to
  current speech models.
- **Master** — compiled chapter audio with pacing/resonance/intensity applied.
- **Stitched AAC master** — single continuous exported audiobook file (AAC).
- **ID3v2** — metadata tags embedded in exported per-chapter files.
- **PalmCaster** — SphereCaster Press's consumer catalog/listening surface
  (distinct from The Telling production studio).

## Appendix B — Evidence & method

Findings are based on the public marketing surface of `app.spherecaster.com`
(home, `#how`, `#showcase`, `#who`) and the PalmCaster catalog at
`spherecaster.com/books`. The `/studio` application is authentication-gated and
was not inspected; all statements about its internal UI, API, framework, and
schema are explicitly marked as assumptions and consolidated as open questions
in §13. This document should be reconciled against the web team's actual
implementation before schemas or endpoints are committed to code.
