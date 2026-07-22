# Relocation & Routine Copilot — Product & Architecture Design

**Status:** Design phase (Steps 1–9), decisions locked. No code written yet.
**Purpose of this document:** working spec for build, and a reference artifact for product/technical discussions later (including interviews).

**Locked MVP decisions:**
- Pilot cities: **New York, Los Angeles, Boston** (all have dense, reliable Google Places/Routes/Weather coverage).
- Subdomain: **`app.yourdomain.com`** (see Step 5 — subdomain choice has no cost impact; picked for clarity).
- Weather provider: **Google Weather API** (see Step 5 — cheaper and lower-friction than Open-Meteo for this product).
- LangGraph checkpointer: **Firestore-backed from the start** (see Step 4 — free at MVP scale, avoids a migration later).

---

## Step 1 — Refined Product Concept

### Core problem (sharpened)
Relocation doesn't just move a person's address — it deletes their decision-making shortcuts. Before the move, "where do I work out" and "where do I get work done" were solved problems, answered by habit. After the move, every one of those decisions has to be remade from scratch, using fragmented, low-trust sources (Google Maps ratings without context, Reddit threads, guesswork). The cost isn't information scarcity — it's decision fatigue during a period of already-elevated stress. The product's job is to compress a 2–3 week trial-and-error period into a small number of confident first choices.

### Target user (MVP-narrowed)
Broad target list (students, international students, relocating professionals, neighborhood movers, digital nomads, travelers) is too wide for an MVP — each has different trust needs (visa/insurance context for international students, expense-account context for professionals, itinerant context for nomads). MVP should narrow to:

**Early-career professionals and graduate/university students, age ~20–32, who relocated to a new city within the last 0–6 months, in an English-language, mid-to-high Google-Places-coverage city.** This group is digitally native, values routine (fitness + focused work are core identity habits for this segment), is price-sensitive but not price-desperate, and is likely to already be comparing Google Maps tabs and ChatGPT sessions manually — meaning the behavior we're replacing already exists, we're just consolidating it.

International students and digital nomads are natural phase-two expansions (they need added trust layers: visa-adjacent info, multi-city persistence) — not MVP.

### Strongest value proposition
Not "local recommendations" (Google Maps/Yelp already do this) and not "a chatbot that talks about a city" (generic LLMs already do this, badly, without live data). The differentiated claim is:

*"One agent that combines live place, route, and weather data with your specific constraints, ranks options with visible logic instead of guessing, tells you what it actually knows versus what it's inferring, and gets better at recommending for you the more you use it — without you re-answering the same questions."*

Three defensible differentiators:
1. **Deterministic, explainable ranking** — not an LLM guessing which gym is "best." Trust is the product; a black-box LLM ranking undermines it.
2. **Confidence-labeled data** — explicit verified/estimated/unavailable distinction, which competitors don't surface.
3. **Preference memory that reduces friction over time** — the tenth query should require fewer questions than the first.

### Product differentiation vs. adjacent tools
- **vs. Google Maps/Yelp:** no personalization, no cross-category synthesis (can't jointly reason about gym + weather + calendar), no memory.
- **vs. generic ChatGPT/Claude web use:** no live structured data, no persistent scoring logic, answers drift and can hallucinate hours/prices.
- **vs. Strava/AllTrails:** route data without workspace/fitness/weather integration, no "new to this city" framing or onboarding.
- **vs. relocation-specific apps (visa/logistics tools):** those solve paperwork, not daily-routine rebuilding.

### Scope boundaries (MVP)
In scope: one city at a time per user, English UI, web app (responsive, not native mobile), Google Places/Routes/Weather-backed, one LangGraph coordinator agent with tool nodes, structured (non-vector) preference memory, Google Calendar write access gated behind explicit per-event approval. **Pilot launch cities: New York, Los Angeles, Boston** — chosen for consistently strong Google Places/Routes/Weather data density, high concentration of the early-career/student target user, and enough neighborhood variety to stress-test the ranking and route logic across different urban densities.

Explicitly out of scope for MVP: multi-city itineraries, native mobile apps, social/community features, real-time crowdsourced crowd-level data, semantic/vector memory, non-Google LLM providers (architecture should allow it, but won't be built), payment/booking integrations, SMS auth.

### Key risks
- **API cost at scale** — Places Details, Routes, and Weather calls are the primary variable cost; must be caching- and field-mask-disciplined from day one, not retrofitted.
- **Data completeness gaps** — Places API doesn't reliably expose noise level, outlet availability, or Wi-Fi quality for workspaces; must be handled with confidence labeling rather than invented data.
- **Weather API coverage/accuracy varies by geography** — need a fallback provider strategy (Open-Meteo) behind the same interface.
- **Cold start** — a brand-new user has no behavioral signal; first-session recommendations depend entirely on onboarding answers being good enough to be useful, not just collected.
- **Liability language around routes** — "safe route" claims are a legal and trust risk if wrong; must consistently use "lower-traffic based on available data" framing.
- **Calendar trust** — a single unapproved write destroys trust in the entire product; must be structurally impossible (approval is a graph interrupt, not a prompt instruction).
- **Latency stacking** — a single user request can trigger geocode + places + routes + weather + LLM calls sequentially; needs parallelization and tool-call budgets or perceived latency will be poor.
- **Geographic coverage variance** — smaller cities/countries will have thinner Places/Routes data; MVP should explicitly launch in 1–3 well-covered pilot cities.

### Assumptions to validate early
- Users will tolerate a 5–8 question onboarding flow if it visibly improves first results (should A/B or at least user-test this).
- Google Places coverage in pilot cities is good enough that "unavailable data" is the exception, not the norm.
- Deterministic scoring (transparent weights) will be perceived as more trustworthy than an LLM-generated ranking, even if slightly less "smart" — this is a core product bet worth stating explicitly.
- Users relocating want a copilot they drive (approve/reject), not an autonomous agent that acts for them — this justifies the LangGraph human-in-the-loop design over a fully autonomous chatbot.

### Data limitations to design around
- Workspace ambiance attributes (quiet, outlets, lighting) are largely unavailable from structured APIs — MVP should mark these as "estimated from reviews" or "unavailable," not silently omit or fabricate them.
- Route "safety" has no reliable structured data source — MVP substitutes road-classification and park-coverage heuristics, labeled as such.
- Class schedules/live availability for fitness studios are rarely exposed via Places API — MVP should say "check studio site/app for live class times" rather than guessing.

### Privacy concerns
Location is used per-session for search radius, not continuously tracked. Calendar access starts as read (busy/free only) with event-creation requiring per-action, per-event user confirmation — never a standing "you may schedule for me" grant. Preference and behavioral data (accepted/rejected recommendations) is PII-adjacent and must sit behind Firestore security rules scoped to the authenticated user, with a visible settings path to export or delete all stored data before any public launch.

---

## Step 2 — MVP Definition

| Feature | MVP | Phase 2 | Future | Do Not Build Yet |
|---|---|---|---|---|
| Fitness discovery (gyms, studios, parks) w/ deterministic ranking | ✅ | | | |
| Confidence-labeled data (verified/estimated/unavailable) | ✅ | | | |
| Workspace discovery (cafés, libraries, coworking) | ✅ | | | |
| Weather-aware "best time today" recommendation | ✅ | | | |
| Structured preference memory (explicit fields) | ✅ | | | |
| Chat interface + recommendation cards + map | ✅ | | | |
| Onboarding preference form | ✅ | | | |
| Accept/reject feedback loop (structured, not learned model yet) | ✅ | | | |
| Running/walking route generation (basic: park/road-classification heuristic) | ✅ (basic) | Advanced (elevation, feedback-tuned) | | |
| Google Calendar read (free/busy) + event creation with approval | | ✅ | | |
| Multi-city / travel mode persistence | | ✅ | | |
| Review-text mining for ambiance attributes (NLP over reviews) | | ✅ | | |
| Route feedback loop that adjusts future route generation | | ✅ | | |
| PostgreSQL/PostGIS for advanced geo queries | | ✅ (if scale demands) | | |
| Redis caching layer | | ✅ (if request volume demands) | | |
| Push notifications ("good weather window in 1 hour") | | | ✅ | |
| Social/community features (shared routes, friend recs) | | | ✅ | |
| Native mobile app | | | ✅ | |
| Multi-LLM routing (Gemini/OpenAI fallback) | | | ✅ (architecture ready, not built) | |
| Semantic/vector memory | | | | 🚫 until structured memory demonstrably insufficient |
| Booking/payment integration with studios | | | | 🚫 |
| Crowdsourced real-time crowd-level data | | | | 🚫 |
| SMS authentication | | | | 🚫 (cost) |
| Autonomous unsupervised calendar writes | | | | 🚫 (trust-breaking, never build) |

---

## Step 3 — Complete User Flows

### 3.1 Onboarding
1. Sign in with Google (Firebase Auth).
2. Consent screen: what data is used (location per-search, no continuous tracking; calendar only if later connected; preferences stored to personalize results). Link to delete-data control.
3. Location capture: current city (geocoded), or manual city entry if location permission denied.
4. Quick preference form (5–8 questions, all skippable):
   - Primary goals (fitness / focused work / both)
   - Preferred fitness activities (multi-select: gym, yoga, running, cycling, swimming, classes)
   - Budget band (per month or per class)
   - Max travel time/distance + preferred travel mode
   - Minimum rating threshold
   - Preferred work environment traits (quiet, has Wi-Fi, has outlets — flagged to user as "we'll show confidence on these")
   - Typical free time windows (rough — "mornings," "evenings," "weekends") — used later for weather/calendar suggestions
5. Confirmation screen summarizing captured preferences, editable inline.
6. Land on chat/home screen with a first proactive suggestion (e.g., top 3 gyms near them) to demonstrate value immediately.

Failure handling: if geocoding fails, ask for manual address/neighborhood entry; if the user skips all preference questions, proceed with defaults and ask preference questions inline the first time they're needed by a specific query.

### 3.2 Fitness discovery
1. User asks in chat ("find me a gym") or uses a structured search card.
2. Agent checks stored preferences; asks only for missing/relevant fields not already known (e.g., if budget is already saved, don't re-ask).
3. Agent geocodes location if not already resolved this session.
4. Agent calls Places search (nearby/text search) with category + radius, then selectively fetches Place Details (field-masked) only for a bounded shortlist (e.g., top 15 candidates by initial distance/rating) to control cost.
5. Deterministic scorer ranks candidates using weighted factors (distance, travel time, rating, review count, price signal, category match, preference match, weather relevance where applicable).
6. Agent generates natural-language explanation per top 3–5 results ("closest option under your budget, 4.6★ from 800+ reviews, 12 min walk").
7. Results rendered as cards + map pins. Each card shows data confidence (verified/estimated/unavailable) per attribute.
8. User can accept (save), reject (with optional reason), or ask to refine ("cheaper," "closer," "different activity").
9. Accept/reject is written to feedback store and feeds future preference weighting.

Missing-info handling: if the user hasn't set a budget and asks a budget-sensitive query, agent asks once, inline, then saves the answer.
Failed API handling: if Places API fails/times out, agent retries once with backoff; on second failure, tells the user plainly ("place search is temporarily unavailable, try again shortly") rather than fabricating results.

### 3.3 Running/walking route planning
1. User specifies (or agent asks for) starting point, distance/duration, run vs. walk, park preference, loop vs. point-to-point, time of day.
2. Agent geocodes start point (and end point if point-to-point).
3. Agent fetches weather for the requested/implied time window.
4. Agent requests route candidates via Routes API (walking mode) shaped around parks/lower-classification roads where possible; since Google Routes API doesn't natively optimize for "park preference," this is implemented as: generate candidate waypoints biased toward known park/green-space polygons (from Places "park" results in the area), then request routes through those waypoints, scored for closeness to target distance.
5. Deterministic scorer ranks candidates by: distance-to-target accuracy, estimated major-road exposure (via road data/heuristics), park coverage, estimated travel time, weather comfort score for the window, daylight availability (sunset time check).
6. Agent presents 1–3 route options on the map with explicit caveat language: "lower-traffic route based on available road and park data — not a safety guarantee."
7. User accepts a route, requests a different distance/preference, or asks for a different time window recommendation.

Failure handling: if no route can be generated near the target distance (e.g., very short/very long asks in an area with poor path density), agent explains the constraint rather than returning a poor-fit route silently.

### 3.4 Productive workspace discovery
1. User asks for a café/library/coworking space; agent gathers/uses saved preferences (Wi-Fi need, outlet need, noise tolerance, budget, duration of stay, indoor/outdoor).
2. Places search + selective Details fetch as in fitness flow.
3. Attribute resolution: hard facts (hours, price level, distance) come from Places API directly; soft attributes (quiet, has outlets, good for laptops) are derived only where Places/Google explicitly exposes them (e.g., "good for working" attribute where available) — otherwise labeled "unconfirmed, based on general reviews" or omitted with a note that this data isn't available for the venue.
4. Deterministic scoring + ranked cards + explanations, same pattern as fitness.
5. Accept/reject feedback captured.

### 3.5 Weather-aware scheduling
1. User asks "best time to run today" or similar, or this is triggered as a follow-up after a route/fitness selection.
2. Agent fetches hourly forecast (precipitation, temp, feels-like, wind, humidity, UV, sunrise/sunset; air quality if available) for the remaining hours of the day.
3. Agent checks calendar free/busy (only if calendar connected and permitted) to exclude occupied windows.
4. Deterministic comfort-scoring function ranks remaining hourly windows.
5. Agent recommends a specific window with plain-language reasoning ("5–6pm: low rain chance, 68°F, light wind, and you're free — best window today”).
6. If the user approves and calendar is connected, agent proposes a calendar event (title, time, location if applicable) and asks for explicit confirmation before creating it.

### 3.6 Saving preferences
Preferences are saved two ways: (1) explicitly, via onboarding/settings forms; (2) implicitly, via accept/reject actions, which adjust stored preference weights (e.g., repeatedly rejecting expensive options nudges budget sensitivity up) — implicit updates are always visible/editable in a "Why we think this" settings panel, never silent.

### 3.7 Approving calendar actions
Strict rule: no calendar write happens without a distinct user confirmation step per event. Flow: agent proposes event details → user sees an explicit "Add to calendar?" card with edit option → user confirms → backend creates the event → confirmation shown with an "undo/remove" option. Calendar connection itself is opt-in and revocable from settings at any time; revoking immediately stops all calendar reads/writes.

### 3.8 Handling missing information
Priority order: (1) use saved preference if present; (2) infer from conversation context if unambiguous; (3) ask the user one targeted question, not a batch; (4) if still unresolved after one ask, proceed with a clearly labeled default and let the user correct it via feedback rather than blocking the flow.

### 3.9 Handling failed API calls
General policy across all providers: one automatic retry with backoff for transient errors; circuit-breaker style short-lived "provider degraded" flag to avoid hammering a failing API within a session; user-facing message is honest and specific ("weather data is temporarily unavailable, so I can't recommend a time window right now") rather than silently degrading to guessed data. All provider failures are logged with enough context (provider, endpoint, params, error) for debugging without logging full PII unnecessarily.

---

## Step 4 — Agent Workflow (LangGraph)

### Design stance
Single coordinator agent, LangGraph `StateGraph`, checkpointed for persistence and pause/resume (calendar approval is a real interrupt, not a prompt trick). Claude is used only where judgment/language understanding is required; every deterministic step (ranking, scoring, retries, budget enforcement) is plain Python — this is the core "separate reasoning from facts" principle applied structurally.

### State object (conceptual shape)
```python
class AgentState(TypedDict):
    # conversation
    messages: list[BaseMessage]
    user_id: str
    session_id: str

    # intent & extraction
    intent: Literal["fitness", "workspace", "route", "weather", "general", "unclear"]
    extracted_preferences: dict          # this-turn extracted slots
    missing_fields: list[str]

    # resolved context
    resolved_location: Location | None
    saved_preferences: UserPreferences   # loaded from Firestore, merged with extracted

    # tool results (raw, provider-shaped)
    places_results: list[PlaceCandidate]
    route_candidates: list[RouteCandidate]
    weather_data: WeatherWindow | None
    calendar_freebusy: list[TimeSlot] | None

    # scoring/output
    scored_results: list[ScoredRecommendation]
    explanation: str | None

    # control
    pending_approval: ApprovalRequest | None
    tool_call_count: int
    tool_call_budget: int                # e.g. 8 per turn
    errors: list[ProviderError]
    retry_counts: dict[str, int]
```

### Nodes
| Node | Type | Responsibility |
|---|---|---|
| `understand_request` | Claude | Classify intent, extract explicit constraints from free text into structured slots. Structured output (function-calling schema), not free text. |
| `load_preferences` | Deterministic | Fetch `UserPreferences` from Firestore, merge with this-turn extraction (this-turn overrides saved, but doesn't persist until confirmed). |
| `check_missing_info` | Deterministic | Compare required fields for the intent against known/merged values; produce `missing_fields`. |
| `ask_user` | Claude (generation only) | If `missing_fields` non-empty, generate one targeted clarifying question; graph pauses (interrupt) for user reply. |
| `geocode_location` | Deterministic (tool) | Geocoding API call, cached by normalized query. |
| `search_places` | Deterministic (tool) | Places nearby/text search with field masks; bounded result count. |
| `fetch_place_details` | Deterministic (tool) | Selective Details fetch for shortlisted candidates only. |
| `fetch_route_data` | Deterministic (tool) | Routes API calls for candidate waypoints. |
| `fetch_weather` | Deterministic (tool) | Weather provider call for relevant window, cached per location/hour. |
| `fetch_calendar_freebusy` | Deterministic (tool) | Only if calendar connected + permitted; read-only. |
| `score_recommendations` | Deterministic | Explicit weighted-scoring function per domain (fitness/workspace/route/weather). No LLM involvement. |
| `generate_explanation` | Claude | Turns scored, structured results into a natural-language explanation per item — reasoning over given facts, not inventing new ones. |
| `request_user_approval` | Deterministic + interrupt | Used for calendar-event creation only; graph pauses until explicit confirm/reject. |
| `create_calendar_event` | Deterministic (tool) | Executes only after `request_user_approval` returns confirmed. |
| `save_preference` | Deterministic | Persists explicit/implicit preference updates to Firestore. |
| `save_feedback` | Deterministic | Persists accept/reject on a recommendation. |
| `handle_provider_error` | Deterministic | Central error node: decides retry vs. user-facing failure message based on `retry_counts` and error type. |
| `enforce_tool_budget` | Deterministic (graph guard) | Checked before each tool node; if `tool_call_count >= tool_call_budget`, short-circuits to a "narrow your request" response instead of looping. |

### Edges / control flow (text diagram)
```
START
  → understand_request
  → load_preferences
  → check_missing_info
      ├─ missing_fields non-empty → ask_user → [INTERRUPT: wait for user] → check_missing_info (loop, bounded)
      └─ complete → route_by_intent
                        ├─ fitness   → geocode_location → search_places → fetch_place_details → score_recommendations
                        ├─ workspace → geocode_location → search_places → fetch_place_details → score_recommendations
                        ├─ route     → geocode_location → fetch_weather → fetch_route_data → score_recommendations
                        └─ weather   → fetch_weather → (fetch_calendar_freebusy if connected) → score_recommendations
  → generate_explanation
  → present_results  → [INTERRUPT: wait for user action]
                           ├─ accept/reject → save_feedback → END (or loop back to refine)
                           ├─ "add to calendar" → request_user_approval → [INTERRUPT: confirm]
                           │                          ├─ confirmed → create_calendar_event → END
                           │                          └─ rejected → END
                           └─ refine query → understand_request (loop, bounded by tool_call_budget)

Any tool node → on error → handle_provider_error
                                ├─ retryable & retry_counts[node] < 1 → retry same node
                                └─ else → append user-facing error → present_results (degraded)

Before every tool node → enforce_tool_budget
                             ├─ under budget → proceed
                             └─ at/over budget → present_results (ask user to narrow scope)
```

### Claude vs. deterministic split (explicit)
**Claude handles:** intent classification, slot extraction from free text (structured output), generating clarifying questions, generating natural-language explanations of already-computed rankings, summarizing tradeoffs across options, disambiguating vague requests ("somewhere chill to work").

**Deterministic Python handles:** all scoring/ranking math, all provider API calls and their retries, missing-field detection, tool-call budget enforcement, approval-gate logic, persistence writes, caching, and any output claiming a fact (price, rating, distance, hours) — these are always passed through from provider data, never generated by the LLM.

### Retries, approval points, error states, persistence
- Retries: one automatic retry per tool node on transient failure (timeout/5xx), tracked in `retry_counts`; permanent failures (4xx/invalid input) do not retry.
- Approval points: only `create_calendar_event` requires human-in-the-loop confirmation as a hard gate (LangGraph interrupt) — modeled as a real pause/resume, not a prompt instruction, so it cannot be bypassed by a bad LLM turn.
- Error states: every tool node failure funnels through `handle_provider_error`, which decides retry vs. degrade-and-inform; the state's `errors` list is always surfaced to the frontend so the UI can show "weather data unavailable" banners honestly.
- Persistence: LangGraph checkpointer (e.g., backed by Firestore or a simple key-value store keyed by `session_id`) so a paused-for-approval or paused-for-clarification session survives a page reload or delay.
- Max tool-call limits: `tool_call_budget` defaults (e.g., 8 tool calls per user turn) enforced at `enforce_tool_budget`, preventing uncontrolled loops from a confused extraction or repeated retries from ballooning cost.

---

## Step 5 — System Architecture

### High-level architecture
```
┌─────────────┐      HTTPS       ┌──────────────────┐      ┌─────────────────────┐
│  Next.js    │ ───────────────► │  FastAPI backend  │ ───► │  LangGraph agent     │
│  (Vercel)   │ ◄─────────────── │  (Cloud Run)       │ ◄─── │  (in-process w/     │
│  Frontend   │   JSON / SSE     └──────────────────┘      │  Cloud Run service)  │
└─────────────┘                          │  │  │            └─────────────────────┘
      │                                   │  │  │                     │
      │ Firebase Auth (ID token)          │  │  │                     ▼
      ▼                                   │  │  │        ┌───────────────────────────┐
┌─────────────┐                           │  │  │        │ Provider abstraction layer  │
│  Firebase    │                          │  │  │        │ PlacesProvider / WeatherProvider
│  Auth        │                          │  │  │        │ RouteProvider / CalendarProvider
└─────────────┘                           │  │  │        │ LLMProvider (Claude)         │
                                            │  │  │        └───────────────────────────┘
                                            │  │  │                     │
                              ┌─────────────┘  │  └───────────┐         ▼
                              ▼                 ▼              ▼   ┌──────────────┐
                     ┌────────────┐   ┌────────────────┐  ┌───────────┐│ External APIs│
                     │ Firestore  │   │ Secret Manager  │  │  Google  ││ Maps/Places/  │
                     │ (data)     │   │ (API keys)      │  │  Calendar││ Routes/Weather│
                     └────────────┘   └────────────────┘  └───────────┘└──────────────┘
```

### Frontend ↔ backend flow
Browser loads Next.js app (Vercel) → user authenticates via Firebase Auth (Google sign-in) → frontend attaches Firebase ID token as a bearer token on every request to the FastAPI backend → backend verifies the token via Firebase Admin SDK on each request → authenticated `user_id` is used to scope all Firestore reads/writes and LangGraph session state. Chat/streaming responses use Server-Sent Events (or simple polling for MVP simplicity) so the UI can show incremental agent progress (e.g., "searching gyms near you…").

### Agent flow
FastAPI endpoint receives a chat/query request → loads or creates a LangGraph session (checkpointed by `session_id`) → invokes the graph → graph either completes and returns a structured result payload, or hits an interrupt (missing info / approval) and returns a "waiting for input" state to the frontend → frontend renders the appropriate prompt (clarifying question or approval card) → user's next action resumes the graph from the checkpoint.

### Database flow
FastAPI backend is the only component that talks to Firestore directly (frontend never touches Firestore directly in MVP, to keep authorization logic centralized and simple). Reads/writes go through a repository layer (`UserRepository`, `PreferenceRepository`, etc.) so Firestore specifics don't leak into agent/business logic.

### External API flow
All external calls (Places, Routes, Weather, Geocoding, Calendar) go through provider abstraction classes in the backend, never directly from graph nodes. Each provider implements caching (short-TTL for weather, longer for place details), field masking, and rate-limit handling internally, so swapping Google Weather for Open-Meteo, for example, means implementing one new class against the same `WeatherProvider` interface.

### Authentication flow
1. User signs in via Firebase Auth (Google OAuth) on the frontend.
2. Firebase issues an ID token to the client.
3. Client sends the token on every API call (`Authorization: Bearer <token>`).
4. FastAPI middleware verifies the token with Firebase Admin SDK, extracts `uid`, rejects unauthenticated/invalid requests before they reach any route handler.
5. Google Calendar access (phase 2) uses a separate OAuth consent flow with its own scoped, revocable token stored server-side (never exposed to the frontend), associated with the user's `uid`.

### Deployment flow
- Frontend: GitHub → GitHub Actions (lint/test/build) → Vercel deployment (preview per PR, production on merge to `main`).
- Backend: GitHub → GitHub Actions (lint/test) → build container → push to Google Artifact Registry → deploy to Cloud Run (staging on PR/merge to a staging branch, production on tagged release).
- Secrets: injected into Cloud Run from Google Secret Manager at deploy/runtime, never committed to source control; frontend build-time public config (Firebase client config) is safe to expose, distinct from server secrets.

### Custom domain hosting (how it actually connects)
**On the "which subdomain is cheaper" question: there's no cost difference.** A subdomain is just a DNS record (a `CNAME` or `A`/`AAAA` entry) added under a domain you already own — `app.`, `move.`, and `agent.` all cost the same (nothing beyond what you already pay for the domain itself; Vercel/Cloud Run don't charge per-subdomain). Pick based on clarity, not price. Recommendation: **`app.yourdomain.com`** for the frontend — it's the most immediately legible convention to a first-time visitor, and pairs cleanly with `api.yourdomain.com` for the backend.

You own the root domain (e.g., `mydomain.com`) at a registrar (Namecheap, Google Domains successor, Cloudflare, etc.). To host the app on a subdomain:
1. In Vercel, add the subdomain (e.g., `app.mydomain.com`) as a project domain.
2. Vercel gives you a DNS record to create — typically a `CNAME` record pointing `app` → `cname.vercel-dns.com` (exact target shown in Vercel's dashboard).
3. In your domain registrar's/DNS provider's DNS settings, add that CNAME record for the `app` host.
4. DNS propagates (minutes to a few hours); Vercel auto-provisions an SSL certificate for the subdomain once it verifies the record.
5. The backend (Cloud Run) can similarly be mapped to a subdomain (e.g., `api.mydomain.com`) via Cloud Run domain mapping, which also gives you a DNS record (usually a set of `A`/`AAAA` or `CNAME` records) to add at your DNS provider.
This means the root domain stays wherever it's registered; you're only adding DNS records that point specific subdomains at Vercel/Cloud Run — no need to move DNS hosting itself unless you want Cloudflare-style proxying/CDN in front, which is optional and not required for MVP.

### Data-security flow
- Firestore security rules restrict every document to `request.auth.uid == resource.data.user_id` (no cross-user reads).
- All external API keys live in Secret Manager, injected as environment variables at runtime, never in frontend code or source control.
- Calendar OAuth tokens (phase 2) stored server-side only, encrypted at rest by Firestore/Cloud infra defaults, with a user-facing revoke action that deletes the stored token and stops all calendar calls immediately.
- PII minimization: only store what's needed for personalization (preferences, accept/reject history, saved locations) — no raw continuous location tracking, no calendar content beyond free/busy + created-event metadata.

---

## Step 6 — Firestore Data Model

```
users/{userId}
  - email, displayName, photoUrl
  - createdAt, lastActiveAt
  - homeCity, homeLocation (geopoint-like {lat, lng})
  - onboardingCompleted: bool
  - calendarConnected: bool

users/{userId}/preferences/profile   (single doc)
  - activities: string[]                      // ["gym", "yoga", "running"]
  - budgetBand: { min, max, currency, period } // period: "month" | "class"
  - maxTravelMinutes: number
  - travelMode: "walk" | "bike" | "transit" | "drive"
  - minRating: number
  - importance: { affordability: 1-5, reviewCount: 1-5, distance: 1-5 }
  - workspaceNeeds: { wifi: bool, outlets: bool, quiet: bool, food: bool }
  - preferredWorkoutTimes: string[]            // ["morning", "evening"]
  - indoorOutdoorPreference: "indoor" | "outdoor" | "either"
  - accessibilityRequirements: string[]
  - updatedAt, updatedBy: "explicit" | "inferred"

users/{userId}/savedPlaces/{placeId}
  - placeId (Google Place ID), name, category
  - location {lat, lng}, address
  - savedAt, source: "fitness" | "workspace"
  - lastKnownRating, lastKnownPriceLevel
  - dataConfidence: { field: "verified"|"estimated"|"unavailable", ... }

users/{userId}/searchSessions/{sessionId}
  - createdAt, intent: "fitness"|"workspace"|"route"|"weather"
  - queryText, extractedPreferences (snapshot)
  - status: "completed" | "awaiting_input" | "awaiting_approval" | "failed"
  - langGraphCheckpointId  (pointer to persisted graph state)

users/{userId}/searchSessions/{sessionId}/recommendations/{recId}
  - rank, placeId or routeId
  - score, scoreBreakdown: { distance: x, rating: y, price: z, ... }
  - explanation (LLM-generated text)
  - dataConfidence map
  - userAction: "pending" | "accepted" | "rejected"
  - actionReason (optional, free text if rejected)
  - actedAt

routes/{routeId}
  - userId, createdAt
  - startLocation, endLocation (or null if loop)
  - distanceMeters, estimatedDurationSeconds
  - polyline (encoded)
  - parkCoverageScore, majorRoadExposureScore, elevationGainMeters (nullable)
  - weatherAtGeneration snapshot
  - caveatText: "lower-traffic route based on available road and park data"

weatherRecommendations/{recId}
  - userId, forLocation, forDate
  - hourlyWindows: [{ hour, precipProb, temp, feelsLike, wind, humidity, uvIndex, comfortScore }]
  - recommendedWindow: { start, end }
  - reasoning (LLM-generated)
  - calendarConflictsExcluded: bool

users/{userId}/calendarActions/{actionId}
  - proposedEvent: { title, start, end, location }
  - status: "proposed" | "confirmed" | "created" | "rejected" | "removed"
  - googleCalendarEventId (nullable until created)
  - proposedAt, confirmedAt

agentSessions/{sessionId}   // LangGraph checkpoint store
  - userId, state (serialized AgentState), updatedAt
  - toolCallCount, status

users/{userId}/feedback/{feedbackId}
  - relatedRecommendationId, relatedSessionId
  - action: "accepted" | "rejected"
  - reason (optional)
  - createdAt

apiCache/{cacheKey}   // shared, not per-user
  - provider: "places" | "weather" | "routes" | "geocoding"
  - requestHash, responsePayload
  - createdAt, expiresAt
```

Notes: `apiCache` is intentionally not per-user (place/weather/route data is not user-specific, so caching is shared to reduce cost). `dataConfidence` is stored as a map so the frontend can render per-field badges ("rating: verified," "wifi: unconfirmed") rather than a single blanket label.

---

## Step 7 — API Contracts (FastAPI)

All endpoints require `Authorization: Bearer <Firebase ID token>` unless noted. Errors follow a consistent shape: `{ "error": { "code": str, "message": str, "retryable": bool } }`.

### `POST /v1/onboarding`
Request:
```json
{
  "homeCity": "Austin, TX",
  "activities": ["gym", "running"],
  "budgetBand": {"min": 0, "max": 80, "currency": "USD", "period": "month"},
  "maxTravelMinutes": 20,
  "travelMode": "walk",
  "minRating": 4.0
}
```
Response `200`:
```json
{"status": "saved", "preferencesId": "profile"}
```
Errors: `400 invalid_preferences` (bad ranges), `401 unauthenticated`.

### `POST /v1/chat`
Starts or continues an agent session (new `sessionId` if omitted).
Request:
```json
{
  "sessionId": null,
  "message": "find me a yoga studio under $100/month within 15 min walk"
}
```
Response `200` (graph completed):
```json
{
  "sessionId": "sess_abc123",
  "status": "completed",
  "intent": "fitness",
  "recommendations": [
    {
      "rank": 1,
      "placeId": "ChIJ...",
      "name": "Riverside Yoga Co.",
      "score": 0.91,
      "scoreBreakdown": {"distance": 0.3, "rating": 0.25, "price": 0.2, "preferenceMatch": 0.16},
      "explanation": "Closest match under your $100 budget, 4.7★ from 340 reviews, 11 min walk.",
      "dataConfidence": {"price": "verified", "rating": "verified", "quietness": "unavailable"}
    }
  ]
}
```
Response `200` (awaiting clarification):
```json
{"sessionId": "sess_abc123", "status": "awaiting_input", "question": "What's your max travel time?"}
```
Response `200` (awaiting calendar approval):
```json
{"sessionId": "sess_abc123", "status": "awaiting_approval", "proposedEvent": {"title": "Yoga at Riverside", "start": "2026-07-23T18:00:00-05:00", "end": "2026-07-23T19:00:00-05:00", "location": "Riverside Yoga Co."}}
```
Errors: `422 tool_budget_exceeded`, `502 provider_unavailable` (with `retryable: true`), `401 unauthenticated`.

### `POST /v1/chat/{sessionId}/resume`
Resumes a paused session with user input (clarification answer or approval decision).
Request:
```json
{"answer": "15 minutes", "approved": null}
```
or
```json
{"answer": null, "approved": true}
```
Response: same shape as `/v1/chat`.

### `POST /v1/recommendations/{recommendationId}/feedback`
Request:
```json
{"action": "accepted"}
```
or
```json
{"action": "rejected", "reason": "too expensive"}
```
Response `200`: `{"status": "recorded"}`
Errors: `404 recommendation_not_found`, `401 unauthenticated`.

### `GET /v1/weather/recommendation?lat=&lng=&date=`
Response `200`:
```json
{
  "recommendedWindow": {"start": "17:00", "end": "18:00"},
  "reasoning": "Low rain probability and comfortable temperature; you're free after 5pm.",
  "hourlyWindows": [
    {"hour": "16:00", "precipProb": 0.4, "temp": 91, "comfortScore": 0.42},
    {"hour": "17:00", "precipProb": 0.05, "temp": 84, "comfortScore": 0.88}
  ]
}
```
Errors: `400 missing_location`, `502 weather_provider_unavailable`.

### `GET /v1/places/saved`
Returns the user's saved places. `200`: `{"places": [ ...SavedPlace ]}`.

### `DELETE /v1/user/data`
Deletes all stored preferences/history for the authenticated user (privacy control). `200`: `{"status": "deleted"}`.

### `POST /v1/calendar/connect` / `POST /v1/calendar/disconnect`
Initiates/revokes Google Calendar OAuth (phase 2). `200`: `{"status": "connected"}` / `{"status": "disconnected"}`.

---

## Step 8 — Project Folder Structure

```
relocation-copilot/
├── frontend/                          # Next.js app
│   ├── app/                           # App Router pages
│   │   ├── (onboarding)/
│   │   ├── chat/
│   │   ├── settings/
│   │   └── api/                       # thin proxy routes if needed
│   ├── components/
│   │   ├── chat/
│   │   ├── recommendation-cards/
│   │   ├── map/
│   │   ├── weather-timeline/
│   │   └── forms/
│   ├── lib/                           # firebase client, api client, hooks
│   ├── styles/
│   ├── public/
│   └── package.json
│
├── backend/                           # FastAPI app
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                       # routers: chat, onboarding, feedback, weather, calendar
│   │   ├── agent/                     # LangGraph workflow
│   │   │   ├── graph.py
│   │   │   ├── state.py
│   │   │   ├── nodes/
│   │   │   │   ├── understand_request.py
│   │   │   │   ├── check_missing_info.py
│   │   │   │   ├── score_recommendations.py
│   │   │   │   └── ...
│   │   │   └── prompts/               # Claude prompt templates
│   │   ├── tools/                     # LangGraph-callable tool wrappers
│   │   │   ├── places_tool.py
│   │   │   ├── weather_tool.py
│   │   │   ├── routes_tool.py
│   │   │   └── calendar_tool.py
│   │   ├── providers/                 # external service abstractions
│   │   │   ├── places_provider.py
│   │   │   ├── weather_provider.py
│   │   │   ├── route_provider.py
│   │   │   ├── calendar_provider.py
│   │   │   └── llm_provider.py
│   │   ├── scoring/                   # deterministic ranking logic
│   │   │   ├── fitness_scoring.py
│   │   │   ├── workspace_scoring.py
│   │   │   ├── route_scoring.py
│   │   │   └── weather_scoring.py
│   │   ├── models/                    # domain models (dataclasses/pydantic)
│   │   ├── schemas/                   # API request/response pydantic schemas
│   │   ├── services/                  # orchestration between repositories/providers
│   │   ├── db/
│   │   │   ├── firestore_client.py
│   │   │   └── repositories/
│   │   │       ├── user_repository.py
│   │   │       ├── preference_repository.py
│   │   │       └── feedback_repository.py
│   │   ├── auth/                      # Firebase token verification middleware
│   │   ├── core/                      # config, logging, rate limiting, caching
│   │   └── utils/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── fixtures/
│   ├── evaluations/                   # LangGraph/LLM eval scripts, prompt regression tests
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
│
├── infrastructure/
│   ├── cloud-run/                     # service configs
│   ├── firestore/                     # security rules, indexes
│   └── secrets/                       # (docs only — no actual secrets)
│
├── .github/
│   └── workflows/
│       ├── frontend-ci.yml
│       ├── backend-ci.yml
│       └── deploy.yml
│
├── docs/
│   ├── architecture.md
│   ├── decisions/                     # ADRs
│   └── api-contracts.md
│
└── README.md
```

---

## Step 9 — Implementation Roadmap

### Milestone 0 — Foundations
- **Goal:** Repo, auth, and empty-but-deployed skeleton end to end.
- **Features:** Firebase Auth sign-in, empty Next.js shell deployed to Vercel on subdomain, empty FastAPI deployed to Cloud Run, health-check endpoint, CI pipelines.
- **Tech:** Next.js, FastAPI, Firebase Auth, Vercel, Cloud Run, GitHub Actions.
- **Dependencies:** none.
- **Testing:** CI runs lint + a trivial test on both frontend/backend; manual check that sign-in works and an authenticated ping request round-trips.
- **Expected output:** `app.yourdomain.com` shows a sign-in screen; authenticated ping hits Cloud Run and returns 200.
- **Risks:** DNS propagation delays; Firebase project misconfiguration.
- **Completion criteria:** authenticated request from deployed frontend to deployed backend succeeds, verified via a real browser session, not just localhost.

### Milestone 1 — Preferences & onboarding
- **Goal:** Users can complete onboarding and preferences persist.
- **Features:** onboarding form, `/v1/onboarding` endpoint, Firestore `preferences` doc, settings page to edit preferences.
- **Tech:** FastAPI + Firestore repository layer, Firestore security rules.
- **Dependencies:** Milestone 0.
- **Testing:** unit tests on preference validation; integration test writing/reading a preferences doc scoped to a test user.
- **Expected output:** a signed-in user can complete onboarding and see saved preferences on reload.
- **Risks:** Firestore rule misconfiguration exposing cross-user data — test explicitly.
- **Completion criteria:** preferences persist across sessions; security rules verified to block cross-user reads.

### Milestone 2 — Provider abstractions & caching
- **Goal:** Working, cost-controlled integrations to Places, Geocoding, Weather, Routes — no agent yet.
- **Features:** `PlacesProvider`, `WeatherProvider`, `RouteProvider`, `GeocodingProvider` classes with field masks, shared `apiCache` Firestore collection, basic rate limiting.
- **Tech:** Google Maps Platform APIs including Google Weather API (see pricing rationale below), `apiCache` collection. `WeatherProvider` interface written so Open-Meteo could be swapped in later, but not implemented for MVP.
- **Dependencies:** Milestone 0.
- **Testing:** unit tests with mocked HTTP responses per provider; integration test hitting real APIs in a sandboxed/low-quota way; cache hit/miss tests.
- **Expected output:** backend can, given a query, return real gym/café/park results and real weather for a location, with caching verified (second identical call doesn't re-hit the external API).
- **Risks:** API cost surprises if field masks/caching aren't right before this milestone ships — treat this as a hard gate before agent work begins.
- **Completion criteria:** a manual script can fetch places + weather for a test location with visible cache reuse and no unmasked (full-field) Places requests.

### Milestone 3 — Deterministic scoring
- **Goal:** Ranking logic exists and is testable independent of any LLM.
- **Features:** `fitness_scoring`, `workspace_scoring`, `route_scoring`, `weather_scoring` modules with explicit, documented weights.
- **Tech:** pure Python, pydantic models for scored output.
- **Dependencies:** Milestone 2 (needs real provider data shapes to score against).
- **Testing:** unit tests with fixed inputs/expected score ordering (this is the most testable, highest-confidence part of the system — invest here).
- **Expected output:** given a fixed set of candidate places and a fixed preference profile, scoring produces a deterministic, explainable ranked list.
- **Risks:** overfitting weights to a small number of manually-checked examples; revisit after real usage data.
- **Completion criteria:** scoring functions have unit test coverage and documented weight rationale in `docs/decisions/`.

### Milestone 4 — LangGraph agent (fitness + workspace flows)
- **Goal:** End-to-end agent flow for fitness and workspace discovery, via chat.
- **Features:** `understand_request`, `check_missing_info`, `ask_user` (interrupt), search/score/explain nodes, tool-call budget enforcement, `/v1/chat` and `/v1/chat/{sessionId}/resume` endpoints.
- **Tech:** LangGraph, Claude (Anthropic API) with structured outputs, checkpointing (start with an in-memory or Firestore-backed checkpointer).
- **Dependencies:** Milestones 1–3.
- **Testing:** integration tests simulating multi-turn conversations (missing info → clarification → completion); LangSmith tracing enabled to inspect real runs during dev.
- **Expected output:** a user can type "find me a gym" in chat, get asked one clarifying question if needed, and receive ranked, explained results.
- **Risks:** LLM extraction errors causing wrong tool calls — mitigate with structured output schemas and validation before any tool call executes.
- **Completion criteria:** a scripted set of representative conversations (10–15) completes correctly end to end, traced in LangSmith.

### Milestone 5 — Frontend chat + recommendation UI
- **Goal:** Usable UI for the agent flow built in Milestone 4.
- **Features:** chat interface, recommendation cards (with confidence badges), map display of results, accept/reject actions.
- **Tech:** Next.js, Tailwind, Google Maps JavaScript API, `/v1/recommendations/{id}/feedback`.
- **Dependencies:** Milestone 4.
- **Testing:** component tests for cards; manual E2E pass of the full fitness/workspace flow in a real browser.
- **Expected output:** a non-technical person can complete a full search-to-decision flow in the UI without touching the API directly.
- **Risks:** map/API key exposure — ensure Maps JS key is domain-restricted.
- **Completion criteria:** a first-time user (internal test) can go from sign-in to an accepted recommendation without guidance.

### Milestone 6 — Route planning + weather-aware scheduling
- **Goal:** Add the remaining two MVP domains to the same agent.
- **Features:** route generation flow, weather "best time" flow, corresponding UI (route map overlay, weather timeline component).
- **Tech:** Routes API, Weather provider, new scoring modules already built in Milestone 3.
- **Dependencies:** Milestones 4–5.
- **Testing:** integration tests for route/weather conversation flows; manual check of caveat language on all route outputs.
- **Expected output:** users can request a 3-mile route or "best time to run today" and get a ranked, explained answer.
- **Risks:** route candidate generation quality in areas with sparse park data — document as a known MVP limitation, not silently hidden.
- **Completion criteria:** route and weather flows pass the same scripted-conversation test bar as Milestone 4.

### Milestone 7 — Feedback loop & preference learning (structured, non-ML)
- **Goal:** Accept/reject history visibly influences future results.
- **Features:** implicit preference weight adjustment based on `feedback` collection, "why we think this" settings panel showing inferred vs. explicit preferences.
- **Tech:** deterministic rule-based adjustment logic (not ML) in `PreferenceRepository`.
- **Dependencies:** Milestone 3–5 in production use for real feedback data to exist.
- **Testing:** unit tests on adjustment rules; before/after comparison on a test user's recommendation set.
- **Expected output:** a user who repeatedly rejects expensive options sees budget-sensitive ranking shift measurably.
- **Risks:** overcorrecting from small feedback samples — cap adjustment magnitude per event.
- **Completion criteria:** documented, testable adjustment rules; visible in settings UI.

### Milestone 8 — Calendar integration (Phase 2 gate)
- **Goal:** Optional, explicitly-approved calendar event creation.
- **Features:** Google Calendar OAuth connect/disconnect, free/busy read, event-proposal + approval interrupt, event creation.
- **Tech:** Google Calendar API, OAuth token storage (server-side, encrypted at rest), LangGraph interrupt for approval.
- **Dependencies:** Milestone 6 (weather scheduling flow needs to exist first).
- **Testing:** integration test verifying that no code path can create an event without a `confirmed: true` approval record; manual security review of token storage.
- **Expected output:** a user can connect calendar, get a scheduling suggestion, approve it, and see the real event appear in Google Calendar.
- **Risks:** highest-trust feature in the product — any bug here is reputationally severe; treat approval-gate testing as release-blocking.
- **Completion criteria:** approval gate has explicit automated test coverage proving unconfirmed proposals never call the create-event tool.

### Milestone 9 — Hardening, cost controls, and launch readiness
- **Goal:** Production-readiness pass before opening to real users beyond internal testing.
- **Features:** rate limiting per user, API budget alerts, Firestore security rule audit, PostHog/Firebase Analytics event tracking, data export/delete tooling, error monitoring.
- **Tech:** Google Secret Manager audit, PostHog or Firebase Analytics, Cloud Run scaling/quota review, LangSmith cost/latency dashboards.
- **Dependencies:** Milestones 0–8.
- **Testing:** load test at expected pilot-city usage levels; security review of auth/data-access paths.
- **Expected output:** a small pilot group (e.g., 20–50 users in 1–2 launch cities) can use the product without cost or trust incidents.
- **Risks:** unanticipated API cost spikes — budget alerts must exist before any public sharing of the app.
- **Completion criteria:** cost dashboards, analytics, and data-deletion controls all verified working; go/no-go checklist signed off before wider release.

---

## Decisions resolved

**1. Pilot cities: New York, Los Angeles, Boston.** Locked in Step 1/Step 9 above.

**2. Subdomain: `app.yourdomain.com`.** All subdomains cost the same — a subdomain is just a free DNS record on a domain you already own, not a billed resource. `app.` was chosen for clarity, not price. See Step 5 for the DNS setup mechanics.

**3. Weather provider: Google Weather API (not Open-Meteo) for MVP.** Researched both current pricing models:

| | Google Weather API | Open-Meteo |
|---|---|---|
| Free tier | 10,000 calls/month free | 10,000 calls/day free, **non-commercial use only** |
| Paid pricing | $0.15 per 1,000 calls beyond free tier (pay-as-you-go) | Free tier can't legally be used for a commercial product; commercial plans are fixed monthly subscriptions starting at a 1M-calls/month tier regardless of actual usage |
| Setup friction | Same Google Cloud project/billing account and API key you're already using for Places/Routes/Geocoding — one integration, one bill | Separate account, separate billing relationship, separate provider to monitor |
| Verdict | **Cheaper at MVP/pilot scale** (pay only for what you use, starting from $0) **and easier** (no new vendor, same auth pattern as the rest of Maps Platform) | Only cheaper at high, sustained volume where a flat subscription beats per-call pricing — not relevant until well past MVP |

This reverses the original placeholder recommendation to default to Open-Meteo — that assumed Google Weather API might require a procurement/allowlist delay, but it's self-serve with the same API key model as Places/Routes, so there's no setup lag to avoid. `WeatherProvider` stays an abstraction either way, so switching later is a contained change.

**4. LangGraph checkpointer: Firestore-backed from the start.** On "does Firestore require charges" — Firestore has two billing tiers, not a single paid plan:

- **Spark (free) plan:** 50,000 reads, 20,000 writes, and 20,000 deletes per day, plus 1 GiB of storage, at no cost, indefinitely (not a trial). This alone comfortably covers development and a 20–50 user pilot.
- **Blaze (pay-as-you-go) plan:** required once you exceed those daily quotas (or need Cloud Storage buckets, which as of Feb 2026 always require Blaze). Beyond the same free daily allowance, it's $0.06 per 100K reads, $0.18 per 100K writes, $0.02 per 100K deletes — usage-based, no fixed monthly fee. Cloud Run itself also requires the Blaze plan to be enabled (billing account linked) even though Cloud Run's own free tier covers light usage — so you'll need Blaze enabled by Milestone 0 regardless, but that doesn't mean you'll be charged; it just removes the artificial cap.

Given that, using Firestore as the LangGraph checkpoint store from Milestone 0 costs nothing extra at MVP scale (checkpoint writes are a small fraction of total read/write volume) and avoids a later migration from an in-memory checkpointer to a persistent one — which would otherwise become its own mid-project task.

---

All four open items are now resolved. Step 10 (implementation) can begin at Milestone 0, whenever you're ready.
