# CLAUDE.md — ShikshaPulse (AI Foundation Hackathon)

Persistent project memory. Read this first in any new session.

## 1. What this is
**ShikshaPulse** is a district/block education diagnostic and accountable-action platform built for the **AI Foundation Hackathon**. The judges need a **fully working end-to-end demo**, and AI must be central and visible.

**Problem statement (from the user).** Block and district education officers cannot easily access, join or interpret assessment and monitoring data:
- Data sits in separate files (NAS/assessment, state attendance portal, UDISE+ infrastructure, teacher vacancy), with different keys and a different format each year.
- Collating it takes 3–4 days, plus another week for a 3-year trend.

**Scenario (from the user).** Mr. Chan, a District Education Officer, sees his district near the bottom of the state on foundational numeracy, with no explanation.
- Romi, a Block Education Officer, blames election duty, vaguely.
- Remedial blocks get picked by instinct ("let's target Poti and Sinda").
- Nobody owns the follow-up actions.

**Our pitch:** `Data → Diagnosis → Decision → Action → Accountability → Outcome`. ShikshaPulse is a decision-and-action layer on top of UDISE+/VSK/NDEAR, not a replacement portal.

**Approved plan:** `C:\Users\Yash Naik\.claude\plans\pasted-content-id-7d30-this-is-snoopy-giraffe.md` (v2). It includes the team's review points:
- scenario-driven synthetic data
- source adapters
- eval suite
- lineage and comparability
- strict Evidence Guard
- implementation vs learning outcomes tracked separately
- Scenario Lab
- deployment path

## 2. Hard rules / user preferences
- **LLM must be free tier.** Use any OpenAI-compatible endpoint (Gemini default, Groq, Ollama), configured in `backend/.env` (`LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, optional `LLM_API_KEY_FALLBACK`). With no key, the deterministic engine answers through the same tools and guard. **Never commit `.env`.**
- **All data is SYNTHETIC.** Never present it as government data. Banners are shown in the UI and in every generated file.
- **Findings are associations, never causal claims.** Label each one *observed fact / associated signal / open question*. The guard softens causal wording.
- **No hard-coded block outcomes in analytics.** Randomised eval scenarios enforce this.
- After changing analytics, keep `python -m eval` (47/47) and `pytest` (33+) passing.
- **Real-life usefulness without added complexity (user request, 2026-10-27).** Remember who the actual users are: DEOs, BEOs, CRCs, headmasters and teachers in villages. New features must stay simple for them.
- **UI (latest user request, 2026-10-26):**
  - No blue or purple; avoid an "AI-generated" look (no gradients, no sparkle icons, no generic pill soup).
  - Use an intelligent, crafted civic design.
  - Fully multilingual for village teachers who may not know English.
  - ⓘ info icons with descriptions wherever applicable.
- Charts: follow the dataviz skill. Run `validate_palette.js`; one axis only; direct labels; status colours always paired with an icon and a label.

## 3. Run / test
```
.\start.ps1                      # Windows one-command (venv, npm, build, serve on :8000)
cd backend; .venv\Scripts\python -m uvicorn app.main:app --port 8000   # serves API + frontend/dist
cd frontend; npm run dev         # dev UI :5173 (proxies /api)
cd frontend; npm run build       # tsc -b && vite build  (the backend serves dist/)
cd backend; .venv\Scripts\python -m pytest -q tests
cd backend; .venv\Scripts\python -m eval        # writes eval/report.md + report.json (~2 min)
cd backend; .venv\Scripts\python -m scenario_lab generate demo_district_a [--seed N --missing 0.1]
```
- Set `PYTHONIOENCODING=utf-8` when printing from Python on Windows (cp1252 crashes on "→" and Devanagari).
- To reset demo state: stop the server, delete `backend/data/warehouse.db*` (and `data/scenarios/demo_district_a` if the YAML changed). On startup the server generates the scenario, ingests it and seeds simulated actions (`runtime.bootstrap`).
- Tool gotchas:
  - Bash heredocs containing nested quotes and Python triple-quoted `\\` broke several times; prefer the Write/Edit tools for multi-line code.
  - The Playwright skill lives at `C:/Users/Yash Naik/.claude/skills/playwright` (`node run.js <script>`). Put scripts in `C:/Users/YASHNA~1/AppData/Local/Temp/`.
  - Screenshots go to `screenshots/` (git-ignored).
- The demo date is pinned: `config.yaml demo_today: 2025-10-20` (deadlines and overdue status). `actions.service._now()` uses it.

## 4. Architecture (files)
```
backend/
  config.yaml              mode demo|department, adapters, matching/diagnosis thresholds, demo_today
  app/config.py db.py      settings (env SHIKSHAPULSE_DB overrides warehouse path); SQLAlchemy/SQLite; db.version() cache key
  app/runtime.py           active scenario, ingest JOBS (thread), PREVIEWS, bootstrap()
  app/auth.py              PERSONAS, HMAC token, can_view / can_list_schools / clamp_school_scope, audit()
  app/sources/             base.RawDataset/SourceAdapter, readers (header detection, banner skip, year/kind hints),
                           synthetic_files, upload, udise_api + state_portal (stubs documenting access requirements)
  app/ingest/              schema (CANONICAL synonyms, REQUIRED, WIDE_MONTH), mapper (dictionary→fuzzy→profile→LLM),
                           normalise (years, wide→long, %/fraction, raw marks→% with scale tag, Y/N, dates),
                           matcher (UDISE code → normalised name → village token → fuzzy; else review queue),
                           dedupe, pipeline (run_ingest full rebuild, preview, summary, resolve_review; ingest_runs table)
  app/analytics/           derive (attendance_annual, panel, comparability_flags), common (panel cache, agg, METRICS,
                           MIN_MONTHS=6, comparable instrument), trends (trend/breakdown/overview/tiles/school_profile),
                           diagnose (pooled first-difference OLS + within-unit r → HIGH/MEDIUM/CONFLICTING/INSUFFICIENT;
                           verdicts; unresolved items with `kind`; children_reasons with reason_items), expected (Ridge,
                           GroupKFold by block, OOF residuals, pattern persistent|emerging, model_card), peers (kNN,
                           election_only, other_districts=True default), radar (multi-flag, not a ranking), quality
                           (completeness, confidence, warning_items), context (timeline, review_order with reason_items)
  app/actions/             interventions.yaml (keyed by trigger; implementation + learning indicators), service (create,
                           status workflow open→in_progress→awaiting_verification→verified|closed_not_implemented,
                           measurements, outcome_status, overdue, seed_demo_actions with is_simulated=1)
  app/ai/                  llm (OpenAI-compatible client), tools (12 vetted tools incl. get_school, early_warning; no raw SQL),
                           evidence (EvidenceStore E1..), guard (numbers/citations/labels/causal lint EN+HI/unresolved),
                           assistant (tool loop ≤4 steps, 1 retry with guard feedback, then fallback),
                           phrases.py (6-language phrase tables: en hi mr bn ta te), templates (router + compose using
                           phrases), drafter (AI action drafts), brief (meeting brief + reportlab PDF, English fonts)
  app/api/routes.py        all /api endpoints;  app/main.py serves frontend/dist as SPA
  scenario_lab/            generator.py (structural model COEF; effects vacancy_rise, attendance_decline, election_disruption,
                           infra_gap(4 facilities), improvement, unexplained_decline, insufficient_evidence,
                           methodology_change), messify.py (per-year formats, banner, name variants, dupes, missing months),
                           scenarios/demo_district_a.yaml + test_random_a/b + test_overlap_c (randomised)
  eval/__main__.py         full evaluation against expected.json
  tests/                   conftest (isolated warehouse), test_ingest, test_analytics_ai (incl. scripted-LLM loop test)
frontend/src/
  api.ts state.tsx types.ts   AppProvider: user, meta, unit, ask panel, lang; useFocusBlock()
  components/ui.tsx Layout.tsx AskPanel.tsx DraftActions.tsx
  components/EarlyWarning.tsx Smart.tsx   i18n/en.ts hi mr bn ta te + extra.ts (Phase 4 strings)
  pages/ Login CommandCenter Why Block Peers Radar Actions DataStudio Brief Lab About MySchool
         Visits Review ReportCard Guide
  public/ manifest.webmanifest icon.svg sw.js (PWA)
```

## 5. Demo story (verified against the live system)
Demo scenario `demo_district_a`: about 1,168 schools, 20 blocks, 4 districts, years 2022-23 → 2024-25.

**Devgarh** (Mr. Chan's district) is **4th of 4** districts; numeracy is 61.3 → 54.6 (−6.7 pp).

| Block | What the evidence shows |
|---|---|
| **Poti** | Maths vacancy 9.8% → 44.7% (HIGH). Numeracy −13.6. Election peers in other districts changed −5.1 to −2.5 (median −3.7). |
| **Sinda** | Student attendance −14.8 pp in migration months (HIGH). Persistent gap of −7.5 pp vs expectation. |
| **Kerwa** | −15.2 pp, UNEXPLAINED. Residual −16.5, an *emerging* gap. The Instinct-vs-Evidence top pick. |
| **Dabra** | INSUFFICIENT_EVIDENCE (attendance and teacher files missing). |
| **Manasa** | NON_COMPARABLE (SLAS, marks out of 50, coverage 41%). |
| **Chitrangi** | Overlapping effects; its infrastructure signal is masked (known, reported miss). |

Other facts used in the demo:
- **Ingest:** 13 files in about 5.5 s; 535 duplicates removed; 1,269 rows matched by name; 26 review groups (96 rows).
- **Ask** "Why did numeracy fall in my district?" returns *Numbers verified against source calculations (34/34)*.
- **Personas:**
  - `state-spd` (Dr. Meera Iyer)
  - `deo-devgarh` (Mr. Chan)
  - `beo-poti` (Romi), `beo-sinda` (Arjun Patel), `beo-kerwa` (Kavita Rao)
  - `hm-poti-1` (Sunita Verma, headmaster)
  - `teacher-poti-1` (Shanti Devi, teacher; simple "My school" view)
  - `crc-kerwa-1` (Meena Kumari, Cluster Resource Coordinator; role block, scope Kerwa, `crc: True`; home page is School visits)
- **Seeded simulated actions:** Ranjhi improved; Bhanpur implemented with no change; Kerwa not implemented; Poti overdue; Sinda in progress.

## 6. Evaluation status (last run 2026-10-26)
47/47 checks pass:
- school-match precision 0.995–1.0, recall 0.92–0.95
- signal recall 0.86–1.0, with 0 false flags per block
- status accuracy 1.0
- held-out R² 0.55–0.70
- guard adversarial cases 6/6; fallback answers grounded 9/9
- data-confidence score falls monotonically as missing data rises (99 → 94 → 88)

## 7. UI redesign + multilingual + accessibility (DONE 2026-10-26)

**User's request:**
- The UI "looked AI generated"; use an intelligent, crafted design.
- Make it multilingual for village teachers who don't know English.
- Add ⓘ info icons with descriptions.
- No purple or blue.

**What exists now:**
- **Palette:**
  - tokens in `frontend/src/index.css` `@theme`: forest `#1e4d36` primary, paper `#f4efe5`, surface `#fffdf8`, saffron `#dd8f22` accent, brick `#b4432a` critical, mustard `#8a5a0b` warning
  - chart series: green `#1f7a4a` + saffron `#dd8f22` (validated, CVD ΔE 16.4); use at most 2 series, with dashes or labels for the second
  - diverging change scale: brick ↔ green with a warm-gray midpoint, always shown with signed numbers
  - sequential `SEQ`: green ramp
  - helpers live in `components/ui.tsx` (`C`, `divergingColor`, `SEQ`)
  - **never reintroduce blue/purple, gradients or sparkle icons**
- **Fonts:** `@fontsource/mukta` (Latin + Devanagari) and Noto Sans Tamil / Telugu / Bengali. `--font-ui` switches per language (`i18n/index.ts fontFor`).
- **i18n:**
  - `frontend/src/i18n/en.ts` is the master (~370 keys); `hi`, `mr`, `bn`, `ta`, `te` are `Partial<Dict>` and fall back to en
  - read strings through `useApp().t(key, vars)` with `{var}` interpolation
  - `lang` is persisted in localStorage `sp_lang`; the Login page shows a language-first picker until one is chosen
  - **every new UI string must be added to en.ts and to all 5 other dictionaries**
  - backend free text is localised on the frontend from structured codes: `reason_items`, unresolved `kind`, `warning_items`, `data_gap_keys`, intervention keys `iv.*`, flags `r.*` / `ri.*`, verdicts `v.*` / `vr.*`, classes `cls.*` / `clsi.*`
  - hooks: `useReasonText`, `useOpenQuestionText`, `useWarningText`, `useActionTitle`
  - action titles are stored in English and displayed through `iv.<intervention_key>`
- **Backend languages:**
  - `app/ai/phrases.py` holds 6-language phrase tables
  - `templates.py` has a multilingual keyword router and `compose(results, lang)`, which also handles the `get_school` tool
  - `assistant.ask` accepts `en hi mr bn ta te`; LLM language rule from `phrases.LANG_NAMES`
  - the guard softens causal words in en/hi/mr/bn/ta/te
  - Tamil gotcha: "கேளுங்கள்" means both listen and ask; the listen label uses "ஒலியாகக் கேளுங்கள்"
- **Accessibility:**
  - `speech.ts` provides `useSpeaker` (speechSynthesis) and `useListener` (SpeechRecognition)
  - `<Speak>` button on pages and answers; mic in the Ask panel
  - text-size control A / A+ / A++ (root font 16/18/20 px, `sp_size`)
  - `<InfoTip>` ⓘ and `<HelpStrip k="help.*">` (collapsible, remembered per page)
- **Teacher view:**
  - persona `teacher-poti-1` (Shanti Devi, role headmaster, `teacher: true`)
  - headmaster/teacher roles get a reduced nav and `pages/MySchool.tsx` as home, backed by `GET /api/my-school`
- **Live LLM:** a Gemini key is now configured in `backend/.env` (never print or commit it). Live answers pass the guard; on intermittent 503s the client retries twice, then the deterministic engine answers.
- **Verified:**
  - Playwright walkthroughs in hi, ta, te and en with 0 console errors (scripts `pw-i18n.js` and `pw-fix.js` in Temp; screenshots in `screenshots/v2/`)
  - pytest 20/20
  - eval 47/47

**Possible next steps:**
- Native-speaker review of translations.
- Localise persona titles.
- PDF brief currently uses English fonts only; recommend the browser print for Indic text.
- Gujarati / Kannada / Odia dictionaries.

## 7b. Field features — Phase 4 (DONE 2026-10-27)
The user chose: **CRC visit form, Smarter actions, Early warning, Review mode + report card.**

| Feature | Backend | Frontend |
|---|---|---|
| **Early warning.** Compares the last 3 months with the same months last year. Alert kinds: `attendance_drop` (≥8 pp in ≥10% of schools), `teacher_dip` (<80%), `teacher_dip_multi` (3 or more blocks merged into one alert), `missing_reports`. Also lists the top schools by drop. | `analytics/early_warning.py`, `GET /api/early-warning`, AI tool `early_warning` (router keyword "warning") | `components/EarlyWarning.tsx` on Overview and Block |
| **CRC school visits.** 6-item maths-classroom checklist; yes=2 / partly=1 / no=0, scaled to /100. Works offline: the queue lives in localStorage `sp_visit_queue`, sync is idempotent on `client_id`, and sync runs on the `online` event. Visit results feed Why? as `field_observations` and remove `gap_observation`. | `app/visits.py` (`visits` table, `record`, `summary`, `seed_demo_visits`), `GET/POST /api/visits` (single or `{"visits":[...]}`), `/api/visits/checklist`, `/api/schools` | `pages/Visits.tsx` (`useVisitSync`); for CRC users "/" is Visits and "/overview" is the dashboard |
| **Smarter actions.** (a) Track record: how the same intervention went elsewhere (uses, implemented, improved, average change). (b) Teacher-sharing pairs for vacancies: the donor has 2+ working maths teachers and a load ≤60% of the block median; same cluster preferred; 2 days a week. | `actions.service.track_record`, `analytics/redistribution.py`, `/api/track-record`, `/api/redistribution`; the drafter attaches both | `components/Smart.tsx` (`TrackRecordLine`, `PairList`, `SharingCard`) in DraftActions and Block |
| **Review meeting mode.** 6-step stepper (standing → early warnings → follow-ups → blocks → decisions that become tasks → wrap up and brief). | existing endpoints + `POST /actions` | `pages/Review.tsx` (`/review`, arrow keys) |
| **School report card.** One printable page for parents and SMC meetings, with a WhatsApp share link (wa.me), a Speak button and tips chosen by flags. | `/api/my-school?udise=` | `pages/ReportCard.tsx` (`/report-card/:udise`), linked from MySchool and Block SchoolModal |
| **PWA / offline.** | — | `public/manifest.webmanifest`, `icon.svg`, `sw.js` (network-first shell; never caches `/api`), registered in production only |

More details:
- **Simulated demo data** (all `is_simulated`):
  - visits: Kerwa (low materials and level grouping), Poti (teacher absent; time on maths), Bhanpur (good practice)
  - action history for the track record: Ujjaini, Khilchipur, Badnagar, Sironj (Sironj not implemented)
- **LLM time budgets:**
  - `assistant.TIME_BUDGET_S=35`, `CALL_TIMEOUT_S=20`; below 4 s left it raises `TimeoutError` and the deterministic engine answers
  - `llm.chat(..., timeout=)` uses `max_retries=1`
  - drafter rationale timeout 8 s; mapper timeout 12 s
  - Gemini 503s previously blocked Ask for 30 s or more
- **New strings** live in `frontend/src/i18n/extra.ts` (enX, hiX, …), merged in `i18n/index.ts`. Backend phrase tables `ITEM`, `FIELD` and `EW` are in `phrases.py`.
- **Verified 2026-10-27:**
  - pytest 26/26 (new `tests/test_field_features.py`)
  - eval 47/47
  - Playwright `pw-new.js` (8 steps) and `pw-i18n.js` (15 steps), 0 errors; screenshots in `screenshots/v3/`

## 7c. Fallback API key + no empty screens (DONE 2026-10-27)
**User request:** "check everything which might not have data and add wherever needed" + "add another fallback gemini api key… if the primary key is rate limited it will shift to the fallback key and try again".

- **Key rotation** (`app/ai/llm.py`):
  - keys = `LLM_API_KEY` (primary) then `LLM_API_KEY_FALLBACK`. The user adds the fallback key value themselves; `.env` has an empty slot. Never print either key.
  - On HTTP 429 / 401 / 403 / 5xx, the same request is retried on the next key. The failed key rests (429: 60 s, 401/403: 600 s, else 20 s), and healthy keys are tried first.
  - Non-last keys use SDK `max_retries=0` (fail fast); the last key keeps the normal retries. Other errors (400, timeouts) do not switch.
  - `status()` adds `keys_configured`, `active_key`, `key_switches`. Tests: `tests/test_llm_keys.py` (fake clients, no network).
- **Empty-data sweep:**
  - Tools: `sp_sweep.py` (API, all 25 units) and `pw-empty.js` (every page × persona × Devgarh block) in Temp.
  - Gaps fixed:
    - visits existed for only 3 blocks → `seed_demo_visits` now seeds every block (story blocks keep their hand-set profiles; others get 4–6 visits shaped by their maths vacancy and teacher attendance)
    - 11 blocks had no tasks → `actions.service._seed_field_actions` adds one current task per block from its own diagnosis (Dabra/Manasa → `data_completion`)
    - "Waiting for verification" column was always empty → Poti teacher-sharing task (Romi) awaiting verification
    - headmaster/teacher/report cards had no tasks → school-level tasks for Belner (Sunita: `remedial_catchup`; Shanti: `parent_engagement`) and a Poti `fln_remedial` task listing the flagged schools
    - CRC Meena owns a Kerwa `classroom_observation` task covering the visited schools
    - brief/Ask had no next steps for no-signal blocks → `step_monitor` / `step_compare` (6 languages)
  - Visits are now seeded **before** actions (runtime), since the Kerwa task lists the visited schools.
  - Actions now carry `unit_name` (school name for school-level tasks); `useActionTitle` uses it.
  - `/my-school?udise=` only adds owner-matched tasks for the user's own school (an officer's unrelated tasks no longer appear on other report cards).
- **Intentional gaps (do not "fill"):** Manasa nulls (non-comparable), Dabra nulls (missing files), "—" for a block's distance to itself, schools with no flags showing "No open tasks".
- **Verified:** pytest 30/30, eval 47/47, `pw-new.js` 8/8, `pw-i18n.js` 15/15, 0 console errors.

## 7d. Who sees what — role-specific vs shared data (DONE 2026-10-27)
User asked: some parts show the same data to everyone; should they? Compared every page per persona (`pw-common.js` → `common.json` in Temp).
- **Shared on purpose:**
  - How we check / About, Scenario Lab, the 13 source files: one state-wide dataset.
  - Block-level aggregates and peers for benchmarking (`can_view` allows them).
  - CRC Meena and BEO Kerwa see the same Why/Radar: same block.
  - DEO's block pages open on Kerwa, same as BEO Kerwa: same unit.
  - Headmaster and teacher share one school (Belner): realistic.
- **Fixed (were wrongly shared):**
  - Tasks: `actions.service.in_scope` (state all; DEO own district; BEO own block; school staff tasks at or listing their school; owners always) and `can_update` (owner, creator-in-scope, officers in scope except CRCs, headmaster for own-school tasks; teachers only their own).
    - Enforced in `/actions` (+ `can_update` flag), `/actions/{id}`, status / measurement / evidence (403), `/my-school`, `brief.py`, and the AI tool `t_actions`. Before, anyone could move any task.
  - Match-review queue (`_review_in_scope` in routes): state all, DEO own district, BEO own block, CRC/school none; resolve is checked too. Before, a BEO could resolve records statewide.
  - MySchool: "Your tasks" (`can_update`, with buttons) vs "Other work at your school" (read-only, owner named). The headmaster and teacher pages differ now.
  - Task drawer shows "Only {o} or the responsible officer can update this task" when `can_update === false`.
  - Ask suggestions per role: state "in the state", district "my district", block/CRC "my block" + peers vs own block (`ask.s1b`, `ask.s1st`, `ask.s3b`), headmaster "my school".
  - State focus block (`useFocusBlock`): the most affected block of the most affected district (Chitrangi), not alphabetical Alot.
  - Overview tiles mark the officer's own block (ring) / district ("Your area").
- Tests: `tests/test_scoping.py` (3). pytest 33/33, eval 47/47, pw-new 8/8, pw-i18n 15/15.

## 7e. Deployment readiness (DONE 2026-10-27)
- **Host decision:** a single Docker container on Render free (`render.yaml`, `Dockerfile`, `.dockerignore`), or Hugging Face Spaces (Docker). Not Vercel:
  - deps are about 457 MB installed, close to Vercel's 500 MB Python limit
  - the app needs a writable SQLite file, background ingest threads and in-memory job state
  - a Vercel + Render split adds CORS and a second URL for nothing, because the backend serves `frontend/dist`
- **Dockerfile:**
  - node:24-slim builds the frontend, then python:3.12-slim
  - the demo warehouse is built at image build (`runtime.bootstrap()` with `LLM_DISABLED=1`; no secrets in the image)
  - runs as uid 1000; `PORT` env; `PUBLIC_DEMO=1`
- **`PUBLIC_DEMO=1`** (`config.public_demo()`, exposed in `/api/meta`):
  - blocks `/lab/generate` and `/ingest/run` with adapter ≠ `synthetic_files` (403)
  - the Lab page explains this (`lab.publicOff`, 6 languages)
  - uploads are capped at 15 MB always (`MAX_UPLOAD_MB`, 413)
- **Requirements pinned** to the tested versions.
- `backend/eval/report.json` is no longer git-ignored: the How-we-check page needs it.
- **Must set on the host:** `APP_SECRET` (the default is a known string), `LLM_API_KEY`, optional `LLM_API_KEY_FALLBACK`.
- **Verified:**
  - simulated container: build step 40 s, cold start 4.9 s, peak RSS about 300 MB (fresh start + heavy pages + PDF + rebuild)
  - problem-statement checklist `sp_ps_check.py` (Temp) 15/15
  - pytest 33/33, eval 47/47, pw-new 8/8, pw-i18n 15/15
  - Docker itself was not available locally, so the image build is untested here
- **Free-tier notes:** Render sleeps after 15 idle minutes (about 1 min wake) and has an ephemeral disk (restart resets the demo).

## 7f. In-app Guide (DONE 2026-10-27)
User asked for a guide that gives users the whole context: what the app is, every feature, and why each exists. The team-facing write-up stays in `PROJECT_EXPLAINED.md`; this guide is for app users and judges.
- **Page:**
  - `pages/Guide.tsx` at `/guide`, in both route sets; in every menu (officer, CRC, school) next to "How we check"; a "Guide" button in the top bar on every page
  - a one-time "New here?" note (`GuideNudge` in Layout, localStorage `sp_guide_seen`)
- **Sections:**
  - In one minute, plus a 6-step journey (Data → Why → Decide → Act → Check → Result)
  - **Start here**: the user's own role card highlighted, then the other roles
  - Problem → what ShikshaPulse does (4 pairs)
  - **Every feature with "What it does" + "Why it is there"** (17 items, grouped Understand / Act / For schools / Data & trust / On every page). The "Open" button appears only where that role can go: state/district 14, BEO 12, CRC 8, school 5.
  - Can I trust what I see? (4 points)
  - Listen reads the intro + the user's own steps
- **Strings:**
  - `i18n/guide.ts` (enG … teG, merged in `i18n/index.ts`)
  - page names come in through placeholders `{home} {why} {block} {peers} {visits} {actions} {review} {mySchool} {instinct} {ask} {reportCard} {started} {done} {listen}`, filled from the real menu and button labels (quoted), so the guide always matches the menu in every language
  - when renaming a menu item, the guide follows automatically
- **Verified:** `pw-guide.js` (Temp), 6 personas × 6 languages: no untranslated keys, no unfilled placeholders, Open buttons navigate, the note shows once. pw-new 8/8, pw-i18n 15/15, 0 errors.

## 7g. Mobile responsive (DONE 2026-10-27)
User asked for a mobile-friendly UI without disturbing the desktop layout.
- **Rule: desktop classes stay as they were, now under `lg:` (≥1024 px). Mobile styles are the unprefixed or `sm:` classes.**
  - Verified by pixel comparison of 18 desktop pages (`pw-resp.js` with `MODE=baseline` / `MODE=after` in Temp; screenshots in `screenshots/resp/`)
  - result: identical apart from data changes and 1/255 anti-aliasing at card corners
- **Layout.tsx:**
  - below lg the sidebar is a slide-in drawer (☰, backdrop, ✕; closes on navigation)
  - compact mobile header with menu, name, Guide and Ask icons, then language and text size, then the demo-data label
  - the mobile header is rendered only when `useIsDesktop()` (matchMedia ≥1024 px) is false, so the desktop DOM has no hidden duplicate controls; tests select "the first language select" and broke when it existed
- **index.css `@media (max-width: 1023.98px)`:**
  - `main .grid > * { min-width: 0 }` (charts and long words stay on screen)
  - `main table { display:block; overflow-x:auto }` (wide tables scroll inside their card)
  - smaller `.h-page`
- **Per-page:**
  - CommandCenter: attention rows and instinct rows become name | change | tag with reasons on their own line; tiles use 3 columns on phones
  - Radar: school rows stack the metrics under the name
  - Why: React Flow `minZoom` 0.25 so the graph fits a phone
  - Login and the language screen: padding, headline size, min-w-0
- **Audit:** `MODE=mobile` (390×844, measures sideways overflow) gave 0 px on all 18 pages; `MODE=mobiletall` gives tall screenshots for visual review.
- `c.menu` key added in 6 languages.
- **Note:** `pw-new.js` creates a review-meeting task and a CRC visit on every run. Reset the local DB after repeated runs (stop the server, delete `backend/data/warehouse.db*`).

## 8. Lessons / bugs already fixed (don't regress)
- **Guard number regex:**
  - `NUM_RE` must parse "66.7/100" as 66.7, "45টি" as 45, and "1,16,800" as 116800 (commas are thousands separators and are stripped)
  - it ignores IDs such as E12, years, and "Grade 3"
  - the earlier bug skipped numbers before "/" and mis-split decimals
- Every number in a template must exist in the evidence data. For field observations this means `minutes_threshold: 30`.
- Playwright selectors break when the UI copy changes ("Where problems overlap" became "Which problems appear together"). When a step fails, check the copy before suspecting the app.
- React effects must not return values: `useEffect(() => { el.scrollIntoView(...) })` needs braces, because `scrollIntoView` returns a Promise in new Chrome and crashed the app ("destroy_ is not a function").
- Recharts: give dots an explicit `fill`, and keep 0 inside the bar-chart axis domain (`domain` functions) so bars start at zero.
- React Flow edges: draw them from the outcome (source, bottom) to the signals (target, top) to avoid looping edges.
- The block-level pages use `useFocusBlock()` and must NOT change the global unit silently.
- Outcome numbers come from `agg(..., comparable_only=True)` everywhere (trend = diagnose = peers), so screens stay consistent.
- Peers default to `other_districts=True`, which matches Mr. Chan's question ("similar blocks in other districts").
- The guard counts every number. Add any constant used in a template (e.g. 2, 3, 6, 100) to the evidence data, and include school names in the evidence, because names contain digits ("… Kharpada 2").
- Verdict STABLE applies when |Δ| < 4 pp; UNEXPLAINED applies when the explained share is under 25%.
- Infrastructure effect strength is `facilities_lost: 4`. A weaker planted effect is undetectable, which is honest.
- Ingest seconds are persisted in the `ingest_runs` table so Data Studio can show them.

## 9. Memory
The auto-memory index is at `C:\Users\Yash Naik\.claude\projects\c--Users-Yash-Naik-OneDrive-Desktop-AI-FOUNDATION-CLAUDE\memory\` (`shikshapulse-hackathon.md`).
