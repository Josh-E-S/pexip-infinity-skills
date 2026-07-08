---
name: pexip-client-intake
description: Use at the start of any open-ended Pexip client-side project — browser app, embedded widget, native mobile, or server-side bot — to scope the work before writing code. Triggers when the user says "I want to build a Pexip app", "add Pexip video to my app", "use Pexip Infinity", "integrate Pexip", "embed Pexip", "build a video calling app with Pexip", or any open-ended Pexip client request without specifics. Ask the questions in this skill BEFORE proposing an implementation — especially to route between PexRTC (browser, 95% of cases), @pexip/infinity (webapp3-level TypeScript), and the REST Client API (native/server). Do not invoke for narrow specific questions like "how does onPeerDisconnect work" or "what does makeCall do" — only for project-shaped requests.
license: MIT
---

# Pexip project intake

Pexip apps have many shapes — a one-page demo, an embedded widget, a full white-labeled clone of webapp3. The right skill set, dependencies, and architecture choices differ a lot. **Don't guess.** Ask the user a small number of targeted questions, then route to the right skills.

Keep it brief. Most projects need 3–4 questions answered, not 10.

## Critical rule: don't fabricate test endpoints

**Never offer a specific demo URL, hostname, or test-VMR alias unless the user provided it or you've verified it from current docs.** If the user wants to test:

- Ask if they have a Pexip Infinity deployment they already use
- Ask if they have a node a colleague can share
- Suggest contacting Pexip via their official channels for a trial

Do not offer plausible-sounding hostnames like `demo.pexip.example` or `meet.example.com`. Either it'll be a dead URL or it'll route somewhere unintended. Either way, the user wastes time.

## The minimum questions

Ask **one at a time**, with multiple-choice options where possible. Stop as soon as you have enough to recommend the right skills.

### Q1. What are you building? (always ask)

```
A) A new standalone Pexip app from scratch
B) Adding Pexip video to an existing app (web component, page, modal)
C) Customizing/branding webapp3 itself
D) Building a Pexip plugin (iframe inside the meeting UI)
E) Other — please describe
```

Routing:
- **A** → core skills (signals-pattern, call-lifecycle, media-pipeline, preflight, reconnect)
- **B** → same core skills, but with a "minimal embed" framing — usually skip preflight, simplify branding
- **C** → branding-manifest is the primary skill; user usually doesn't need to write call code
- **D** → plugin-host (note: that skill is the **host** side; for plugin-author docs, point to Pexip's separate plugin SDK docs)
- **E** → ask follow-up

### Q1.5. Which client API? (ask if answer to Q1 is A, B, or D)

**Default to PexRTC unless told otherwise.** It covers 95% of Pexip web integrations.

```
A) PexRTC — browser app, script-tag load, no npm/build step
   (the default: Pexip's official JS API, callback-based)
B) @pexip/infinity — building a webapp3-level TypeScript app with npm
   (typed signals, modular architecture, same SDK Pexip uses internally)
C) REST Client API — non-browser: native mobile, desktop, server-side, CLI
   (raw HTTP + SSE, you manage the WebRTC peer connection yourself)
D) Not sure
```

Routing:
- **A** → Route to `pexip-pexrtc`. It covers the full PexRTC API end-to-end — makeCall, connect, PIN/IDP auth, roster, host controls, screenshare, chat, breakouts, FECC, captions, and React patterns. A single skill gets a working app in one shot.
- **B** → Continue with Q2. All skills in this package (`pexip-call-lifecycle`, `pexip-signals-pattern`, etc.) cover `@pexip/infinity`.
- **C** → Route to `pexip-rest-client-api`. Covers token auth, SDP/ICE exchange, SSE event stream, and all REST control endpoints for non-browser environments.
- **D** → Recommend **PexRTC** by default. Ask only one follow-up: "Is this for a browser, or are you building a native mobile/desktop app?" Browser → PexRTC. Native/server → REST API. If they want full TypeScript + npm architecture at webapp3 scale → `@pexip/infinity`.

**The real decision axis is WebRTC abstraction, not browser vs. server:**

| | PexRTC | `@pexip/infinity` | REST Client API |
|---|---|---|---|
| Who handles SDP/ICE? | PexRTC | `@pexip/infinity` | You |
| Load method | `<script>` tag from node | `npm install` | HTTP from anywhere |
| API style | Callbacks | Typed signals | HTTP + SSE |
| Deployment | Browser only | Browser / Node | Any HTTP client |
| Pexip official docs | Yes (full) | No public docs | Yes (full) |
| Best for | Quick browser embed | Full TS webapp | Native / server / CLI |

### Q2. Which features matter for v1? (always ask)

```
[ ] Audio/video call (always required)
[ ] Screen sharing
[ ] Chat (group)
[ ] Direct messages (1:1)
[ ] Participant list with mute/admit/kick
[ ] Background blur/replace
[ ] Live captions
[ ] Breakout rooms
[ ] Layout selection
[ ] Far-end camera control (PTZ — rare, hardware-specific)
[ ] Plugin support
[ ] Custom branding (colors, logo, hidden buttons)
```

Map each to its skill. If they pick everything, point at `ARCHITECTURE.md` for the full reading order rather than dumping all 16 skills at once.

### Q3. Where is your Pexip Infinity deployed? (always ask, never guess)

```
A) On-prem Pexip Infinity at a node we control
B) Pexip-hosted cloud deployment
C) Don't have one yet / just exploring
```

If **C**: stop and tell the user they'll need access to a Pexip node before runtime testing. The skills can still be used for the *code*, but joining a real meeting requires a real node. Suggest they contact Pexip via official channels.

If **A** or **B**: ask for the node FQDN to use as the `node` parameter in `infinityClient.call({...})`. **Don't fill it in for them.**

### Q4. Any auth requirements? (ask only if relevant — A1 says "new app" or "embedded")

```
A) Direct join (anyone with the URL can join, possibly with PIN)
B) IDP/SSO (server-driven via onIdp event)
C) Custom auth in front of Pexip (we authenticate, then pass to Pexip)
D) Not sure / handle later
```

Route to call-lifecycle (PIN/IDP/extension flow is documented there).

### Q5. (Conditional) If they picked branding in Q2 or "C" in Q1: ###

```
A) Just colors + logo
B) Colors + logo + hidden UI elements
C) Custom join flow (e.g. terms-of-service step)
D) Multiple brands served from different paths
```

Route to branding-manifest with the appropriate sub-section.

## SDK disambiguation

Three distinct client APIs exist — route to the right one early:

- **PexRTC** (`pexip-pexrtc`) — browser apps, script-tag load, callback-based. Covers everything: call setup, PIN, roster, host controls, screenshare, chat, breakouts, FECC, captions. The default for web integrations. If a developer mentions `makeCall`, `onSetup`, `connect(pin)`, or loading `pexrtc.js`, they're using PexRTC.
- **`@pexip/infinity`** (`pexip-call-lifecycle` etc.) — the npm SDK that Pexip's own webapp3 is built on. Typed signals, modular architecture. The other skills in this package cover it exclusively. If a developer mentions `createInfinityClient`, `infinityClientSignals`, or `@pexip/infinity`, they're using this.
- **REST Client API** (`pexip-rest-client-api`) — raw HTTP + SSE, no JS library. Right for native mobile, desktop, server-side bots, CLI. Developer manages the WebRTC peer connection themselves. If a developer mentions `/api/client/v2/`, `request_token`, or "I'm not in a browser", they're using this.

## Don't ask these (defaults are fine)

These are choices the user usually doesn't have an opinion on; pick sensible defaults from the skill content:

- TypeScript or JS? → assume TypeScript (matches webapp3 + skill snippets)
- React version? → 19+ (matches webapp3); document hooks-only patterns
- Build tool? → Vite is common; webapp3 uses it. Mention but don't ask.
- State management? → don't need any beyond `@pexip/signal`. The skills explicitly avoid Redux/Zustand.

If the user has strong opinions on these, they'll mention it unprompted. Don't make them justify defaults.

## After the questions: the recommendation format

Once you have enough, respond with this shape:

```
Based on your answers, here's what I'd build:

  Skills to read first (in order):
  - signals-pattern  (foundation)
  - call-lifecycle   (call setup)
  - media-pipeline   (getUserMedia + processors)
  - [feature-specific skills]

  Skills to skip for v1:
  - [list with one-line reason each]

  First step:
  [concrete next action — e.g. "create the signal hubs in src/signals/"]

  Open questions before I write code:
  - [anything still unclear, max 2-3]
```

Then **wait for confirmation** before writing implementation code. The user may want to adjust scope, defer features, or pull in skills you didn't recommend.

## When to skip this skill

Don't run intake for:

- Specific narrow questions: *"How does onPeerDisconnect work?"* → just answer with `call-lifecycle`
- Debugging: *"Why is my video tile black?"* → use `media-pipeline/self-healing.md`
- Lookups: *"What's the manifest.json schema?"* → use `pexip-branding-manifest`

Intake is for **project-shaped requests** where the user hasn't yet decided what they're building. If the question is already specific, answer it directly and skip the intake.

## Example session

> User: "I want to add Pexip video to my React app."

```
A few quick questions before I dig in:

1. What kind of integration are you thinking?

   A) A dedicated meeting page (like a separate route)
   B) An embedded video panel/modal inside an existing page
   C) Replacing webapp3 entirely with your own UI
   D) Other?
```

> User: "B — a panel inside our existing app."

```
Got it. Next:

2. Which features do you need for v1? (pick all that apply)

   [ ] Audio/video call (always)
   [ ] Screen sharing
   [ ] Chat
   [ ] Participant list
   [ ] Background blur

   Skip these for v1 unless you actively need them:
   - Breakouts, layouts, FECC, captions, plugins
```

> User: "Audio/video + chat + participant list."

```
Last question:

3. Where will the app connect to? You'll need a Pexip Infinity
   node FQDN for `infinityClient.call({node: '...'})`.

   - On-prem deployment? Cloud trial? Just exploring?

   I won't make up a node URL — that needs to come from your
   deployment.
```

> User: "We have an on-prem at infinity.example.com."

```
Plan:

  Skills to read (in order):
  - signals-pattern    (foundation, ~5 min)
  - call-lifecycle     (call setup + state machine)
  - media-pipeline     (getUserMedia + minimal processors)
  - chat               (sendMessage + onMessage handlers)
  - participants       (GroupKey filters for the list)

  Skip for v1:
  - preflight          (you said embedded panel — likely permission flow lives elsewhere)
  - presentation       (no screen share)
  - reconnect          (add later if you see toast spam)
  - branding-manifest  (assume default brand)

  First step:
  Create the signal hubs in src/signals/ following the patterns
  in signals-pattern/SKILL.md.

  Open questions:
  - Should the panel render preflight (device picker), or do users
    just join with browser defaults?
  - Auth: direct-join URL with optional PIN, or something custom?
```

That's the full flow. Don't pad it. The user can ask follow-ups.

## Reference source

- **Authoritative Pexip docs:**
  - Pexip client SDK overview: https://docs.pexip.com/developer/clientapi.htm
  - `@pexip/infinity` JS client API reference: https://docs.pexip.com/api_client/api_pexrtc.htm
  - Webapp3 source / patterns: https://github.com/pexip/pexip-webapp3
- **Related skills (this package):**
  - Server-side router: `pexip`
  - Webapp patterns: `pexip-signals-pattern`, `pexip-call-lifecycle`, `pexip-media-pipeline`
  - Operator runbook (server side): `pexip-operations`
