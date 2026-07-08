---
name: pexip-client-intake
description: Use at the start of any new Pexip-related task to scope the work before writing code. Triggers when the user says "I want to build a Pexip app", "add Pexip to my app", "use Pexip Infinity", "integrate Pexip video", "set up @pexip/infinity", or any open-ended Pexip project request without specifics. Ask the questions in this skill BEFORE proposing an implementation. Do not invoke for narrow, specific questions like "how does onPeerDisconnect work" — only for project-shaped requests.
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

### Q1.5. Which client SDK? (ask if answer to Q1 is A, B, or D)

```
A) PexRTC — Pexip's official documented JavaScript API
   (loaded from the Conferencing Node at /static/webrtc/js/pexrtc.js,
   callback-based: makeCall → onSetup → connect(pin) → onConnect)
B) @pexip/infinity — the modular TypeScript SDK that webapp3 uses
   (installed via npm, signal-based: infinityClient.call() → onPinRequired)
C) Not sure / haven't decided yet
```

Routing:
- **A** → Route to `pexip-pexrtc` skill. It covers the full PexRTC API: call lifecycle, PIN handling, roster, screenshare, host controls, React patterns, and working examples.
- **B** → Continue with Q2. All skills in this package cover `@pexip/infinity`.
- **C** → Recommend:
  - **PexRTC** (`pexip-pexrtc`) if they want a quick integration with minimal setup, follows Pexip's official docs, no npm/build step needed
  - **`@pexip/infinity`** (existing skills: `pexip-call-lifecycle`, `pexip-signals-pattern`, etc.) if they're building a full-featured webapp3-level application with typed signals, media processors, and modular architecture
  - **REST Client API** (`pexip-rest-client-api`) if they're building outside the browser (mobile, server-side, CLI) or need raw HTTP control

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

All client-side skills in this package (`pexip-call-lifecycle`, `pexip-signals-pattern`, `pexip-media-pipeline`, `pexip-presentation`, etc.) cover the **`@pexip/infinity` npm SDK** — the same SDK that Pexip's own webapp3 uses internally.

They do **not** cover **PexRTC**, which is Pexip's officially documented JavaScript client API. PexRTC uses a different pattern (`makeCall` + `onSetup` + `connect(pin)`) and is loaded as a script tag from the Conferencing Node.

If a developer mentions `makeCall`, `onSetup`, `connect(pin)`, or loading `pexrtc.js`, they're using PexRTC — route them to Pexip's official docs, not to these skills.

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
