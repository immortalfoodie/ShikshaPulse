# ShikshaPulse — The Complete Project Explanation

> One document that explains everything we built: the problem, the solution, every feature, how the AI works, how the analytics work, the architecture, how we tested it, and how it could be deployed for real.
>
> **All data in the demo is synthetic.** No real schools, children or officers.

---

## Contents
1. [The problem statement](#1-the-problem-statement)
2. [The scenario, line by line](#2-the-scenario-line-by-line)
3. [Our solution in one paragraph](#3-our-solution-in-one-paragraph)
4. [Who uses it (personas)](#4-who-uses-it-personas)
5. [Features, page by page](#5-features-page-by-page)
6. [How the AI is used — and kept honest](#6-how-the-ai-is-used--and-kept-honest)
7. [How the analytics work](#7-how-the-analytics-work)
8. [The data pipeline](#8-the-data-pipeline)
9. [Synthetic data and the Scenario Lab](#9-synthetic-data-and-the-scenario-lab)
10. [How we proved it works (evaluation)](#10-how-we-proved-it-works-evaluation)
11. [Architecture](#11-architecture)
12. [Data model](#12-data-model)
13. [API reference](#13-api-reference)
14. [Languages, accessibility and design](#14-languages-accessibility-and-design)
15. [Security, privacy and governance](#15-security-privacy-and-governance)
16. [Path to real deployment](#16-path-to-real-deployment)
17. [The 5-minute demo script](#17-the-5-minute-demo-script)
18. [Questions judges may ask (with answers)](#18-questions-judges-may-ask-with-answers)
19. [Limitations (said honestly)](#19-limitations-said-honestly)
20. [Repository map and how to run](#20-repository-map-and-how-to-run)
21. [Glossary](#21-glossary)

---

## 1. The problem statement

> **Block and district level education officers need support in use of education assessment and monitoring data to take necessary actions.**
> - Officials face challenges in easily accessing data, deriving insights and understanding what necessary actions are needed to address gaps.
> - Data is collected at multiple levels with limited systems to collate, and generate a clear overall view.
> - Officials are often unaware what actions are planned in response to data findings and who is executing them, which reduces accountability for improving education delivery.

The problem breaks down into three gaps:

| Gap | What it means in practice |
|---|---|
| **Access & insight** | An officer sees a score but not *why* it changed or *what to do*. |
| **Collation** | Assessment, attendance, UDISE+ facilities and teacher posts live in separate files and formats, with different keys. |
| **Accountability** | Even when action is decided, nobody tracks who owns it, whether it happened, or whether it worked. |

---

## 2. The scenario, line by line

The scenario we were given is a story about Mr. Chan, a District Education Officer, and Romi, a Block Education Officer. Every sentence in it maps to a feature.

| What the scenario says | What ShikshaPulse does |
|---|---|
| "The survey told Mr. Chan his district is near the bottom of the state… It did not tell him anything else." | **Overview** shows the rank (*"4 of 4 districts"*) and immediately offers **"Why did it change?"** |
| "Has attendance dropped? Is it infrastructure, vacancy?" | The **Why? engine** tests each factor (attendance, teacher attendance, maths vacancy, facilities) and grades the evidence. |
| "We do not have this information collected… UDISE+ by school code, attendance by month, assessment separate. Nothing joins. 3 to 4 days." | **Data Studio** reads messy files, maps columns with AI help, matches schools by UDISE code and builds the warehouse in **about 6 seconds**. |
| "Pull the last 3 years… each year in its own file and format… another week." | The pipeline normalises all three years automatically. The **trend chart** answers *"have we fallen or were we always here?"* |
| "My own district's trend is not readily available for me." | The trend is the first chart on the Overview. |
| Romi: "It was an election year… could be possible the results dropped." | **Election duty** appears as *context* (teacher-days lost), never as a proven cause. |
| "I wonder how similar blocks in other districts do during the election period." | The **Peer Benchmark** compares similar election-affected blocks *in other districts*. |
| "I wish I had guidance on how to proceed." | **Suggested next steps**, the **Intervention Radar** and **AI-drafted tasks** from an intervention library. |
| "Let's target Poti and Sinda for now." | **Instinct vs Evidence** lets him pick blocks, then shows what the data says. Here it points to **Kerwa**, which he missed. |
| "Remedial effort rests on the officer's instinct about which blocks are weakest." | Evidence-based review order, with the reason for each position. |
| "No clear responsibility set for the actions." | The **Action Room** gives every task an owner, deadline, proof of work, verification, result tracking and audit trail. |

---

## 3. Our solution in one paragraph

**ShikshaPulse** is a district and block education *decision-and-action* platform. It does five things in sequence:

1. It takes the files departments already have (assessment, attendance, UDISE+, teacher posts), even when they are messy and inconsistent, and joins them into one three-year record keyed on the UDISE school code, in seconds.
2. It explains **what changed, where, and what it is linked to**, grading every piece of evidence and refusing to claim causes the data cannot prove.
3. It compares each block with **fair peers**: similar blocks, and similar *election-affected* blocks.
4. It compares each block with **what its own conditions predict**.
5. It turns findings into **owned, dated, verified tasks** and measures whether they worked.

An AI assistant answers questions in **six Indian languages**. Every number it states is checked against the data before the user sees it.

**Pitch line:** `Data → Understand → Decide → Act → Follow up → Result`. We sit *on top of* UDISE+ / VSK / NDEAR as a decision layer; we are not another silo.

---

## 4. Who uses it (personas)

The demo has eight sign-in personas. Access is scoped by role.

| Persona | Role | Sees | Typical use |
|---|---|---|---|
| Dr. Meera Iyer | State Project Director | Whole state | Compare districts, audit log |
| **Mr. Chan** | District Education Officer, Devgarh | Own district in detail; other areas as aggregates | Diagnose, assign tasks, verify |
| **Romi** | Block Education Officer, Poti | Own block in detail | Do assigned tasks, upload proof |
| Arjun Patel / Kavita Rao | BEOs of Sinda / Kerwa | Own block | Same as Romi |
| Sunita Verma | Headmaster | Own school | "My school" view |
| **Shanti Devi** | Teacher | Own school (simple view) | Big cards, listen aloud, one-tap task updates |
| **Meena Kumari** | Cluster Resource Coordinator (CRC), Kerwa | Schools of her block | Fills the school-visit checklist on her phone, even offline; does assigned tasks |

**What is shared and what is personal.**

Shared with everyone, on purpose:
- The same state-wide source files.
- Block averages, so any officer can compare their area with others. Their own block or district is marked "Your area".
- The "How we check" page.

Personal, depending on the role:
- **Tasks.** Officers see tasks in their own district or block. School staff see tasks at their school, or tasks that list their school. Only the owner, the officer who set the task, or the officer responsible for that area can update it. A CRC updates only their own tasks. A teacher updates only their own; a headmaster also updates tasks set for their school. Everyone else sees a read-only line saying who can update it.
- **Unmatched school records.** Each officer checks these only for their own area, because they know those schools.
- **Ask suggestions.** They fit the person: "my block", "my district", "the state" or "my school".
- **Headmaster and teacher pages.** Each shows "Your tasks" with buttons, and "Other work at your school" as read-only.

---

## 5. Features, page by page

> **In-app Guide.** Users and judges get a plain-language version of this section inside the app, under **Guide** (`/guide`). It is available in all six languages and puts the reader's own role first, with each feature's purpose and an Open button. A one-time "New here?" note points first-time visitors to it.

Every page has a collapsible **"How to use this page"** strip and ⓘ explanations, and works in all six languages.

### 5.1 Language picker (first screen)
- Six large tiles, each in its own script with a greeting.
- The choice is remembered and can be changed any time from the top bar.

### 5.2 Overview
- **Rank banner:** *"Basic maths: 4 of 4 districts in the state"*.
- **Six KPI cards:** numeracy, literacy, student attendance, teacher attendance, empty maths posts, facilities. Each shows the latest value, the 3-year change with an arrow and a sign, the state average, a sparkline and an ⓘ definition.
- **Trend chart:** *"Have we fallen, or were we always here?"* The unit is shown against the state, using comparable tests only.
- **Areas needing attention, with reasons.** This is explicitly *not a ranking*: each block lists what the evidence says about it, e.g. *"Empty maths posts +34.9 pts (strong signal)"*.
- **Instinct vs Evidence.** The officer picks the blocks they would target. The system then shows an evidence-based order, flags any block they missed (Kerwa) and explains why.
- **Block tiles map:** every block coloured by change (green = better, brick = worse; striped = test changed, not comparable). Click a tile to open that block.
- **Tasks summary** (total / overdue / improved) and a **data confidence** score with warnings.
- **Listen** reads the headline aloud.

### 5.3 Why did it change? (diagnosis)
- **Verdict banner**, one of:
  - *matches tracked factors*
  - *partly explained*
  - *not explained*
  - *not enough data*
  - *not comparable*
  - *stable*
- **Evidence graph.** The result sits at the top. Below it are linked factors, coloured by evidence strength, plus *background* events such as election duty. Below those are dashed *open questions* and *data gaps*.
- **Click any factor** to see: before / now / change, the estimated share of the change, the school-level link (r), data coverage, the source files used, where it changed most (chart), and the most affected schools.
- **Disruption timeline:** monthly student and teacher attendance, with election months shaded.

### 5.4 Block report
- KPI cards for the block.
- **Fair comparison (expected vs actual):** what score the block's *conditions alone* predict, compared with its actual score. It is classified as one of:
  - *doing worse than its conditions predict*, split into **emerging** (new) or **persistent** (long-standing)
  - *held back by difficult conditions*
  - *doing better than predicted*
  - *as predicted*

  A bar chart shows how each condition raises or lowers the expected score.
- **Which schools to visit first:** schools with 2+ problems. Click one for a 3-year profile and full **data lineage** (which file and row every number came from).

### 5.5 Compare with similar blocks (peers)
- Finds the five most similar blocks using baseline characteristics.
- Filters: *only blocks with election duty*, *only other districts*.
- Sentence summary: *"5 similar blocks changed by −5.1 to −2.5 pts (middle value −3.7). Poti changed by −13.6 pts — 9.9 pts below the middle."*
- Interpretation: *"Blocks with similar election duty did not fall this much, so the election alone does not match the full change."*

### 5.6 Schools needing support (Intervention Radar)
- Lists schools where **several independent problems occur together**:
  - low maths score
  - maths fell 10+ points
  - attendance fell 8+ points
  - maths posts empty
  - facilities missing
  - teacher attendance below 80%
- Each rule has an ⓘ explanation. **Missing data is shown separately and never counted against a school.**
- An overlap matrix shows which problems appear together.
- Tick schools, then **Plan tasks** to get suggested interventions.

### 5.7 Action Room
- A kanban board: *To do → In progress → Overdue → Waiting for verification → Closed (result tracked)*.
- **AI-drafted tasks** come from an intervention library based on the evidence, e.g. *temporary maths teacher redistribution* for vacancy. The officer edits the owner and deadline and assigns it. **Nothing is ordered automatically.**
- Each task tracks two things separately:
  - **Was it done?** (implementation), e.g. teacher posts filled versus the target
  - **Did learning improve?** (outcome), compared against the baseline recorded when the task was created
- Outcome states:
  - *not started*
  - *in progress*
  - *overdue (escalated)*
  - *not done*
  - *done · waiting for results*
  - *done · results improved*
  - *done · no improvement yet*
- Proof upload, verification by the assigning officer, and a full history.
- **Demo history** (clearly labelled "demo history"):
  - Ranjhi: done, improved
  - Bhanpur: done, no change yet
  - Kerwa: never done
  - Poti: overdue
  - Sinda: in progress

### 5.8 My school (headmasters and teachers)
- A greeting, then four large cards in plain words: maths, children attending, maths teachers, facilities. Each compares with the block average.
- **Where your school needs help:** red cards, each with an explanation.
- **Your tasks:** big buttons *"I have started"* and *"Done — send for checking"*.
- **Listen to this page** and **Ask about my school**.

### 5.9 Data Studio
1. **Choose a source.** Demo files, department upload, or the locked official connectors (UDISE+ API, state portal), which show what access they need.
2. **Files received.** Click any file to see it exactly as it arrived.
3. **Check how columns were understood.** Every column is shown with its mapping method and confidence (dictionary / fuzzy / profile / AI / manual), and can be overridden.
4. **Build the 3-year record.** A live progress log and timer.

After the build:
- **Before/after strip:** *"By hand: 3–4 days + 1 week → ShikshaPulse: ~6 s"*, plus files joined, rows in and out, duplicates removed, rows matched by name, and records needing a person to check.
- **Records to check:** uncertain school matches with candidate schools. Pick one or mark *no match*; every decision is logged.
- **Data quality:** completeness per source per year, comparability warnings, and per-file lineage (mapping version, transformations).

### 5.10 Meeting brief
- A one-page review brief: summary (AI-written and number-checked), 3-year trend, where the change is, similar blocks, schools needing support, tasks and owners, decisions for the meeting, and limits of the data.
- In any language. **Print** or **Download PDF**.

### 5.11 Ask a question (AI assistant)
- Available on every page. Type or **speak** in any of the six languages.
- Each answer shows:
  - a summary and findings, each labelled **Measured fact / Linked signal / Open question**
  - **evidence chips** (E1, E2…) that open the exact data
  - suggested next steps
  - a **"Numbers checked against the data (n/n)"** badge
  - which data tools were used
- **Listen** reads the answer aloud.

### 5.12 Scenario Lab (internal) and How we check (trust)
- **Scenario Lab:** regenerate synthetic data with chosen messiness (missing months, duplicates, misspelt names) and see the planted ground truth.
- **How we check:** the live evaluation report (47 checks), how the answer checker works, the model card, data sources and deployment path, data tiers and privacy controls, and the language and accessibility notes.

### 5.13 Early warnings (on Overview and Block report)
Assessments come once a year, so by the time results show a fall, a whole year is lost. Attendance data arrives every month. Early warning compares **the last 3 months with the same 3 months last year**. Comparing the same months also cancels out seasonal effects such as harvest or migration months.

Alerts:
- **Attendance fell:** children's attendance dropped by 8 points or more in at least 10% of a block's schools. The alert gives the number of schools, the average drop and the months. It is marked high when a quarter or more of the schools are affected.
- **Teacher attendance dip:** a block's teacher attendance fell below 80%. When three or more blocks dip in the same months (for example, during election duty), they appear as **one** alert that lists the blocks, rather than a pile of separate alerts.
- **Reports missing:** schools that stopped sending attendance. Silence is treated as a warning sign, not hidden.

The schools with the largest drops are listed, so a CRC can visit them first. Each alert names its threshold and months. Users can also ask about alerts in any language, e.g. "Any early warnings this month?".

### 5.14 School visits (for CRCs, works offline)
Data files cannot show what happens inside a classroom. That is exactly why Kerwa was an "open question". Cluster Resource Coordinators already visit schools; this gives them a simple form to record what they see.

**The 6 questions**, each answered with a big **Yes / Partly / No** button:
1. Is a maths teacher present and teaching?
2. Are teaching materials (beads, sticks, cards) used?
3. Are children grouped by their level?
4. Do children solve problems themselves?
5. Does the teacher check each child's understanding?
6. Does maths get 30 minutes or more today?

The CRC can also record the number of children present and enrolled, and add a note.

**How it works:**
- **Score:** Yes = 2, Partly = 1, No = 0, scaled to 0–100.
- **No network needed.** The visit is saved on the phone (*"Saved on this phone — waiting to be sent"*) and sent automatically when the signal returns. Each visit has a unique id, so sending twice never creates duplicates.
- **Summary on the page:** the block's average visit score, the **weakest practices** (the share of visits answering *yes* for each question) and the recent visits.
- **Visits feed the Why? page.** Once a block has 3 or more visits, Why? shows a *From school visits* card and adds a node to the evidence graph. "No classroom observations" is then removed from the data gaps. Visits are shown as **field observations**, kept separate from test-score evidence.
- For a CRC, *School visits* is the home page. The dashboard is one tap away.
- The app can be **installed on the phone's home screen** (PWA).

### 5.15 Smarter task drafts: track record and teacher sharing
- **Past results.** Each drafted task shows how the same kind of task went elsewhere: *"Used 3 time(s): 1 improved, 1 no change yet, 1 not done · average change +4.1 pts"*. This helps officers choose actions that have worked, not just ones that sound right. The demo history is simulated and badged.
- **Teacher sharing options** appear in the Block report and in drafts for maths vacancies. Each is a concrete pair: a school with a vacant maths post and a nearby school that can share a maths teacher 2 days a week.
  - The donor school has at least 2 working maths teachers.
  - Its pupils per maths teacher are no more than 60% of the block median.
  - Same-cluster schools are preferred.
  - This turns "redistribute teachers" into a decision the BEO can sign today.

### 5.16 Review meeting mode
Monthly review meetings often drift. *Review meeting* walks the DEO through **6 steps**, one screen at a time (arrow keys work too):
1. **Where we stand:** rank, trend and change.
2. **Early warnings.**
3. **Tasks to follow up:** tasks that are overdue or waiting for verification.
4. **Blocks needing attention:** the evidence-based order, with reasons.
5. **Decisions:** type a decision, pick an owner and a deadline, then press *Add decision*. It becomes a task in the Action Room immediately.
6. **Wrap up:** a summary and a link to the meeting brief.

### 5.17 School report card (for parents and the SMC)
- **One printable page per school**, in plain words and the chosen language. It covers maths over three years, attendance, teachers, where the school needs help, and *what is being done* (open tasks).
- **How parents can help:** tips chosen from the school's own flags. Examples: *"Send your child to school every day — even in harvest and festival months"* and *"Ask your child to count, add and share things at home — 10 minutes a day helps."*
- **Listen** (read aloud), **Print**, and **Share on WhatsApp**, which opens WhatsApp with a short text summary.
- Open it from *My school* (headmaster or teacher), or from any school in the Block report.

---

## 6. How the AI is used — and kept honest

### Where AI is used

| Place | What the AI does | Safeguard |
|---|---|---|
| **Column mapping** | Resolves messy headers (e.g. `BLK`, `MAT_SCORE`) using headers plus sample values | Layered: dictionary → fuzzy → value profiling → **LLM**. Each column shows its method and confidence; the officer can override |
| **School matching** | Normalises names (`Govt. P.S.` = `Government Primary School`) and fuzzy-matches by village name | Below the confidence threshold or ambiguous → **human review queue** |
| **Why? engine** | Statistical evidence grading (Section 7) | Labelled as association. Low coverage → "not enough data" |
| **Fair comparison** | Machine-learning model predicts the score from conditions | Never uses past or current scores as inputs; tested on blocks it never saw |
| **Peers** | Nearest-neighbour similarity | Shows a range and a median, not a verdict |
| **Assistant** | An LLM chooses from **12 vetted analytics tools**, then writes a structured answer | **Evidence Guard** (below) |
| **Task drafting** | Picks interventions for detected signals, and attaches the track record and teacher-sharing pairs. The LLM writes the reason | Numbers must match the evidence, causal words are softened, and the officer decides |
| **Early warning** | Compares the same months year on year in monthly data; the assistant answers questions about it in any language | Every alert shows its threshold; the guard checks the numbers in answers |
| **Field observations** | CRC checklist results join the Why? evidence | Needs 3+ visits; labelled as observations |
| **Meeting brief** | The assistant writes the summary | Same guard |

### How an answer is produced
```
Question (any language, typed or spoken)
   │
   ▼
LLM chooses tools  ──►  get_overview / get_trend / where_did_it_change / diagnose /
(max 4 steps)           expected_vs_actual / find_peers / intervention_radar /
                        find_schools_with / list_actions / data_quality / get_school
   │                    (no raw SQL — only vetted, permission-scoped functions)
   ▼
Every tool result is stored as citable evidence: E1, E2, …
   │
   ▼
LLM writes JSON: summary + findings (label, text, evidence ids, period) + next steps
   │
   ▼
EVIDENCE GUARD checks it ──► fails? one retry with the guard's feedback
   │                                └─► fails again? deterministic engine answers
   ▼
Answer shown with "Numbers checked against the data (19/19)"
```

### The Evidence Guard (`backend/app/ai/guard.py`)
1. **Numbers:** every number in the answer must match a value in the tool outputs (rounding tolerance allowed).
2. **Citations:** every finding must cite real evidence ids and a reporting period.
3. **Labels:** each finding must be *observed fact*, *associated signal* or *unresolved question*. A finding citing a signal cannot be presented as a fact; the guard relabels it.
4. **No causal claims:** words like "caused", "due to", "because of", "led to", "के कारण", "मुळे", "কারণে", "காரணமாக" and "కారణంగా" are rewritten to associative wording, because our data is observational.
5. **Honesty:** if the evidence contains insufficient, conflicting or unexplained items, the answer must show them. The guard adds any the model left out, and says so.

The badge certifies **numbers and citations**, not that every interpretation is proven.

### The LLM itself
- **Free tier**, through any OpenAI-compatible endpoint. The default is **Google Gemini 2.5 Flash**; Groq Llama-3.3-70B and local Ollama also work. It is configured in `backend/.env`.
- **No key, no internet, or API down** → the **deterministic engine** answers. It uses the same tools and the same guard, with answers written from phrase tables in all six languages. **The demo never breaks.**
- Live Gemini has been verified: answers passed the guard (e.g. 19/19 numbers). The guard also softened the model's own "due to election duty" to "alongside election duty".

---

## 7. How the analytics work

Each method is explained first in plain words, then technically.

### 7.1 Comparable trend
- **Plain:** we only compare scores from the same kind of test. If a block switched tests (Manasa switched to a test marked out of 50), we flag it and stop its trend instead of showing a fake drop.
- **Technical:**
  - The "standard instrument" is the most common (assessment type, scale) in the baseline year.
  - Averages are weighted by students assessed.
  - `comparability_flags` record any instrument change (≥50% of schools changed) or coverage drop (≥25 points).

### 7.2 The Why? engine (`analytics/diagnose.py`)
- **Plain:** for each factor we ask three questions.
  1. *Did it change a lot?*
  2. *Did the schools where it changed more also see bigger changes in learning?*
  3. *Do enough schools have the data?*

  We grade the factor from the answers, and say clearly what is still unexplained.
- **Technical:**
  - For each school, compute the change between the baseline year and the latest year in the outcome and in each factor.
  - **Pooled first-difference regression** across the state: Δscore ~ Δattendance + Δteacher attendance + Δmaths vacancy + Δfacilities. This gives "points of score per point of factor".
  - **Contribution** of a factor in a unit = coefficient × the unit's factor change.
  - **Within-unit association r** = correlation, across the unit's schools, between factor change and score change.
  - **Classification:**
    - **HIGH:** contribution ≥ 2.5 pts, same direction as the outcome, and r ≥ 0.25
    - **MEDIUM:** smaller contribution, or a moderate contribution concentrated in the affected schools (r ≥ 0.3)
    - **CONFLICTING:** large contribution but r in the opposite direction
    - **INSUFFICIENT EVIDENCE:** under 60% of schools have the data in both years
    - **CONTEXT:** events such as election duty (teacher-days lost)
  - **Unresolved remainder:** outcome change minus the explained contributions. If it is ≥ 4 pts and at least half the change, it becomes an open question.
  - **Verdict:** STABLE (|change| < 4 pts), UNEXPLAINED (explained share under 25%), PARTIALLY_EXPLAINED, EXPLAINED_BY_ASSOCIATED_SIGNALS, INSUFFICIENT_EVIDENCE (2+ factors missing) or NON_COMPARABLE.
  - At **district/state level**, child blocks that are unexplained, insufficient or non-comparable stay visible as open questions (e.g. *"Kerwa: a 15.2 pts fall that tracked factors do not explain"*).

### 7.3 Fair comparison — Expected vs Actual (`analytics/expected.py`)
- **Plain:** a model learns how much conditions (attendance, teachers, facilities, village or town, school size) usually affect scores. It then says what score this block "should" have. A block far below that line needs a closer look at teaching; a block that is low *and* in line with its conditions needs resources, not blame.
- **Technical:**
  - **Ridge regression** on school-years.
  - Features: student attendance, teacher attendance, maths vacancy, facilities index, rural, log(enrolment).
  - **No current or lagged outcome is ever a feature** (asserted in code).
  - **Cross-fitted with GroupKFold by block:** every prediction comes from a model that never saw that block.
  - Held-out R² ≈ 0.55–0.70; mean error ≈ 5 points.
  - Residual = actual − expected.
  - **Pattern:** *emerging* if the gap widened by 4+ pts since the baseline, otherwise *persistent*.
  - Contributions per feature = coefficient × (block value − state mean).

### 7.4 Peer benchmark (`analytics/peers.py`)
- **Plain:** find blocks that *started* in a similar place and see how they changed over the same years.
- **Technical:**
  - **k-nearest neighbours** on standardised baseline-year features: number of schools, enrolment, rural share, baseline numeracy, baseline vacancy, baseline attendance, baseline facilities.
  - Default filters: *other districts only* and, optionally, *election-affected only* (≥10 teacher-days lost).
  - Reports the peer range, the median, and the unit's gap from the median.

### 7.5 Intervention Radar (`analytics/radar.py`)
- Six rule-based flags per school in the latest year. A school is listed when it has at least *N* flags (default 2); 3+ flags means *priority support*.
- Missing data is listed separately and never counted as a flag. Explicitly not a ranking.

### 7.6 Data quality (`analytics/quality.py`)
- **Completeness:** for each source (assessment, attendance months, teacher posts, facilities) and each year.
- **Confidence** = weighted completeness, taking the weaker of the two comparison years, × (1 − share of records still in review).
- Attendance from fewer than 6 of 10 months is treated as missing, not as a value.

### 7.7 Evidence-based review order (`analytics/context.py`)
- Orders a district's blocks by a combination of: size of fall, gap below expected, and share of schools with 3+ problems. Each position comes with its reasons. This powers *Instinct vs Evidence*.

### 7.8 Early warning (`analytics/early_warning.py`)
- **Window:** the latest 3 months of monthly attendance, compared school by school with the same calendar months a year earlier.
- **Attendance drop:** at least 10% of a block's schools fell by 8 points or more. It is marked high severity when 25% or more of the schools are affected.
- **Teacher dip:** block teacher attendance below 80% in the window. Three or more blocks merge into one `teacher_dip_multi` alert.
- **Missing reports:** schools with no rows in the window.
- **Tested:** the scenario's planted attendance decline is detected (`tests/test_field_features.py`).

### 7.9 Field observations (`app/visits.py`)
- Checklist answers score yes = 2, partly = 1, no = 0, scaled to /100.
- A practice's percentage is the share of visits that answered *yes*.
- A block summary needs at least 3 visits; a school summary needs 1. Below that, nothing is shown, so a single visit is never over-read.

### 7.10 Teacher sharing and track record
- **`analytics/redistribution.py`**
  - Receivers are schools with a vacant maths post.
  - Donors have 2 or more working maths teachers, and a load (pupils per maths teacher) of at most 60% of the block median.
  - Same-cluster pairs rank first. A donor is suggested at most twice.
- **`actions/service.track_record`**
  - For an intervention, counts past uses, implemented vs not implemented, and improved vs no change.
  - Reports the average change in the learning indicator, with examples.

---

## 8. The data pipeline

```
Files exactly as departments send them (CSV / Excel, any year's format)
  │
  ▼  1. READ        banner/title rows skipped, header row detected, year guessed from file name
  ▼  2. DETECT      which kind of file (assessment / attendance / teachers / UDISE+ / calendar)
  ▼  3. MAP         columns → standard fields: dictionary → fuzzy → value profiling → LLM (officer can override)
  ▼  4. NORMALISE   years ("AY 2023", "2024_25" → "2024-25"); wide month columns → long rows;
  │                 fractions → %; raw marks (out of 50) → % with scale tag; Y/N/1/0 → 1/0; mixed dates
  ▼  5. DEDUPE      exact duplicates and same-school-same-period duplicates
  ▼  6. MATCH       UDISE code → normalised name → village-name rule → fuzzy name
  │                 uncertain or ambiguous → REVIEW QUEUE (never guessed silently)
  ▼  7. STORE       warehouse tables, each row carrying source file, source row, provenance tier and match method
  ▼  8. DERIVE      annual attendance (records which months), school-year panel, comparability flags
  ▼
Analytics, AI assistant and reports
```

Demo run: **13 files, 38,629 rows in → 50,566 rows out, 1,168 schools × 3 years, 535 duplicates removed, 1,269 rows matched by name, 26 uncertain groups (96 rows) sent to review, about 6 seconds.**

---

## 9. Synthetic data and the Scenario Lab

We could not use real school or child data, and we did not want to fake "real" data. So we built a **Scenario Lab** (`backend/scenario_lab/`) that generates realistic data with **known ground truth**.

- **Structural model:** each school's numeracy is generated from attendance, maths vacancy, facilities, rurality, teacher-days lost, school and block effects, and noise. Base rates are loosely calibrated to published NAS 2021 / UDISE+ ranges.
- **Effects planted per block:**
  - maths vacancy rise
  - attendance decline (migration months)
  - election disruption
  - facility gaps
  - improvement
  - unexplained decline
  - insufficient evidence (data missing)
  - methodology change (new test)
- **Messy files:**
  - each year has different column names and formats (xlsx/csv, wide/long)
  - year formats vary
  - fractions appear in place of percentages
  - raw marks appear in place of percentages
  - misspelt school names without codes
  - missing months, duplicates and blank cells
  - every file carries a *SYNTHETIC — NOT GOVERNMENT DATA* banner
- **expected.json** is written for every scenario: which blocks should show which signals, the true school match for every misspelt name, and which year pairs are not comparable.
- **Demo scenario** `demo_district_a`: 4 districts, 20 blocks, ~1,168 schools, 2022-23 → 2024-25.

| Block | Planted story | What ShikshaPulse finds |
|---|---|---|
| **Poti** | Maths vacancy rises | Vacancy 9.8% → 44.7%, **strong signal**; numeracy −13.6 |
| **Sinda** | Migration-season attendance fall | Attendance −14.8 pts, **strong signal**; persistent gap vs expected |
| **Kerwa** | Decline with no tracked cause | −15.2 pts, **not explained**; 16.5 pts below expected; *emerging* |
| **Dabra** | Decline with attendance and teacher data missing | **Not enough data** |
| **Manasa** | Switched to a different test | **Not comparable** |
| **Chitrangi** | Vacancy + attendance + facilities together | Vacancy and attendance detected; the smaller facilities effect is masked (reported honestly) |
| Alot, Isagarh, Nagda… | Election duty | Small falls (−3 to −5); peers for Poti's comparison |
| Ranjhi, Khilchipur, Ujjaini | Improvement | Correctly shown as improving |

- **Three randomised test scenarios** place effects on **random block names** with different messiness, so nothing in the analytics can rely on hard-coded names.

---

## 10. How we proved it works (evaluation)

`python -m eval` runs the full pipeline on all four scenarios in isolated warehouses and scores the results against the ground truth. Latest result: **47 / 47 checks passed.**

| Check | Result |
|---|---|
| School-match precision (auto-matched names that are correct) | 0.995 – 1.0 |
| School-match recall (misspelt names matched automatically) | 0.92 – 0.95 |
| Planted signal detection recall | 0.86 – 1.0 |
| False worrying flags on blocks without that problem | **0 per block** |
| Block status accuracy (insufficient / not comparable / unexplained / stable / improving) | 1.0 |
| Decline detection | ≥ 0.9 |
| Methodology changes flagged | all |
| Fair-comparison model held-out R² (block-grouped) | 0.55 – 0.70 |
| No outcome leakage into model features | true |
| Unexplained declines classed as "worse than conditions predict" | all |
| Election peer filter respected | all |
| Guard catches adversarial answers (invented number, causal claim, missing citation, fake evidence id, signal labelled as fact, omitted open question) | 6 / 6 |
| Offline answers fully grounded | 9 / 9 |
| Data confidence falls as missing data rises | 99 → 94 → 88 ✓ |

**Unit tests** (`pytest`, 33 tests) cover:
- year, month and percentage normalisation
- name normalisation and matcher precision
- all files mapping without missing fields
- planted signals detected
- no leakage, peer filter
- guard behaviour, including Hindi causal softening
- grounded answers in **all six languages**
- school-level answers
- a **scripted-LLM test**: the model invents a number, the guard rejects it, and the retry passes
- early warning detects the planted attendance drop
- offline visit batches are idempotent and feed the diagnosis
- teacher-sharing pairs are valid; the track record has the right shape
- early-warning and field-observation answers are grounded in all six languages

**Browser tests (Playwright):**
- the full demo flow with zero console or API errors: sign in, compare with evidence, diagnose, compare peers, plan and assign a task to Romi, Romi submits, Mr. Chan verifies, re-ingest, Hindi, PDF
- multilingual walkthroughs in Hindi, Tamil, Telugu and English

---

## 11. Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                               React frontend (Vite + TypeScript)                      │
│  Language picker · Overview · Why? · Block · Peers · Radar · Action Room · My school   │
│  Data Studio · Meeting brief · Scenario Lab · How we check · Ask panel (voice, listen) │
│  i18n (6 languages) · Tailwind design system · Recharts · React Flow · TanStack Query  │
└───────────────────────────────────────────┬──────────────────────────────────────────┘
                                            │ JSON over /api (signed session token)
┌───────────────────────────────────────────▼──────────────────────────────────────────┐
│                                   FastAPI backend                                     │
│  auth & scoping · audit log · routes                                                  │
│ ┌──────────────┐  ┌───────────────┐  ┌─────────────────┐  ┌────────────────────────┐ │
│ │ Source        │→ │ Ingestion      │→ │ Warehouse        │→ │ Analytics               │ │
│ │ adapters      │  │ map · normalise│  │ SQLite via       │  │ trends · diagnose ·     │ │
│ │ demo files ·  │  │ dedupe · match │  │ SQLAlchemy       │  │ expected (Ridge) ·      │ │
│ │ upload ·      │  │ lineage ·      │  │ (Postgres-ready) │  │ peers (kNN) · radar ·   │ │
│ │ UDISE+ API*  │  │ review queue   │  │ provenance/row   │  │ quality · context       │ │
│ │ state portal*│  └───────────────┘  └─────────────────┘  └───────────┬────────────┘ │
│ └──────────────┘                                                       │              │
│ ┌──────────────────────────────┐   ┌──────────────────────────────────▼────────────┐ │
│ │ Action Room                    │   │ AI layer                                       │ │
│ │ intervention library · tasks · │   │ LLM client (Gemini/Groq/Ollama) · 12 tools ·   │ │
│ │ implementation vs learning ·   │   │ evidence store · Evidence Guard · assistant ·  │ │
│ │ verification · audit           │   │ 6-language offline engine · drafter · brief    │ │
│ └──────────────────────────────┘   └────────────────────────────────────────────────┘ │
│  * stubs that document required authorisation; not called in the demo                  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### Technology choices and why

| Layer | Choice | Why |
|---|---|---|
| Backend | Python, FastAPI | Fast to build, a strong data and ML ecosystem |
| Data | pandas, NumPy | Reshaping and joining messy tables |
| Matching | rapidfuzz | Fast fuzzy string matching |
| ML | scikit-learn (Ridge, GroupKFold), NumPy least squares | Explainable models with proper validation |
| Storage | SQLite through SQLAlchemy | Zero setup for the demo; the same code points at Postgres |
| LLM | `openai` SDK against OpenAI-compatible endpoints | One client for Gemini, Groq and Ollama; free tiers |
| PDF | reportlab | Server-side brief |
| Frontend | React 19, Vite, TypeScript | Fast, typed UI |
| Styling | Tailwind CSS v4 with custom tokens | One design system |
| Charts | Recharts; React Flow for the evidence graph | Interactive, accessible charts |
| Fonts | Mukta, Noto Sans Tamil/Telugu/Bengali | Correct rendering of Indian scripts |
| Speech | Browser Web Speech API | Read-aloud and voice input with no extra service |

---

## 12. Data model

**Fact tables** (each row also carries `_source_file`, `_source_row`, `_provenance`, `_match_method`, `_match_conf`):

| Table | Grain | Key columns |
|---|---|---|
| `schools` | school | udise_code, name, district, block, cluster, management, rural, provenance |
| `udise_year` | school × year | enrolment, Grade 3 enrolment, 6 facilities, infra_index |
| `assessments` | school × year × subject | assessment_type, scoring_scale, score_raw, score_pct, students_assessed |
| `attendance_monthly` | school × month | student %, teacher %, days open |
| `teacher_snapshot` | school × year × subject | sanctioned, working, vacant, snapshot date |
| `context_events` | block × event | event, start, end, teacher-days lost, source |

**Derived tables:**

| Table | Contents |
|---|---|
| `attendance_annual` | Yearly attendance, with the months used |
| `panel` | One row per school-year with every indicator; the analytics table |
| `comparability_flags` | Unit, years, reason |

**Pipeline bookkeeping:** `ingest_files` (per-file mapping, versions, transformations, counts), `ingest_runs` (timing), `match_review` (uncertain matches with candidates).

**Action Room tables:**

| Table | Contents |
|---|---|
| `issues` | The problem a task responds to |
| `actions` | Owner, deadline, priority, status, verifier, proof, simulated flag |
| `indicator_measurements` | Implementation and learning: baseline, target, value, dates |
| `action_updates` | Task history |
| `audit_log` | System-wide log |

---

## 13. API reference

All endpoints are under `/api` and need a session token, except `personas`, `login` and `health`.

| Area | Endpoints |
|---|---|
| Auth | `GET /personas`, `POST /login`, `GET /me`, `GET /meta` |
| Analytics | `GET /overview`, `/trend`, `/breakdown`, `/children-reasons`, `/diagnose`, `/expected`, `/expected/model`, `/expected/ranking`, `/peers`, `/radar`, `/radar/matrix`, `/school/{udise}`, `/my-school`, `/tiles`, `/context`, `/review-order`, `/quality` |
| Data Studio | `GET /ingest/sources`, `GET /ingest/raw`, `POST /ingest/upload`, `DELETE /ingest/upload`, `POST /ingest/preview`, `POST /ingest/run`, `GET /ingest/jobs/{id}`, `GET /ingest/summary`, `GET /ingest/review`, `POST /ingest/review/{id}`, `POST /ingest/review-bulk`, `GET /lineage` |
| Action Room | `GET /interventions`, `GET /owners`, `GET /actions`, `GET /actions/{id}`, `POST /actions`, `POST /actions/draft`, `POST /actions/{id}/status`, `POST /actions/{id}/measurement`, `POST /actions/{id}/evidence`, `GET /audit` |
| Field | `GET /early-warning`, `GET /schools`, `GET /visits/checklist`, `GET /visits`, `POST /visits` (one visit or a `{"visits": [...]}` batch, idempotent on `client_id`), `GET /redistribution`, `GET /track-record` |
| AI | `POST /ask` (question, lang), `GET /brief`, `GET /brief.pdf`, `GET /llm/status` |
| Lab & trust | `GET /lab/scenarios`, `POST /lab/generate`, `GET /lab/expected`, `GET /eval/report` |

The interactive API docs are at `http://localhost:8000/docs`.

---

## 14. Languages, accessibility and design

### Six languages, end to end
- English, हिन्दी, मराठी, বাংলা, தமிழ், తెలుగు.
- **Interface:** every label, button, ⓘ explanation, chart caption, verdict, reason, warning and task title comes from dictionaries (`frontend/src/i18n/*.ts`, ~370 strings each).
- **Backend sentences** are not translated as free text. The backend sends **structured codes** (e.g. `{kind: "signal", factor: "maths_vacancy", change: 34.9}`), and the frontend writes the sentence in the user's language. That keeps every language exact and consistent.
- **AI answers:** the LLM is told to answer in the chosen language. The **offline engine has its own phrase tables in all six languages**, so a teacher gets an answer in Tamil even with no internet AI.
- Translations are machine-assisted and should be checked by native speakers before official use. The app says this openly.

### Accessibility for village users
- **Read-aloud** (🔊) on page summaries, answers, the meeting brief and the whole "My school" page, in the chosen language.
- **Voice questions** (🎤) where the browser supports speech recognition.
- **Text size** A / A+ / A++, large touch targets, keyboard focus outlines.
- **Plain-language "My school" view** with big numbers and one-tap actions.
- Colour is never the only signal; arrows, signs and words are always present.

### Design system
- Warm civic palette: forest green, saffron, brick and mustard on a paper background. **No blue, no purple, no gradients.**
- Chart colours are validated for colour-blindness (green `#1f7a4a` / saffron `#dd8f22`). The change scale is brick ↔ green with a neutral midpoint.
- Calm surfaces: thin borders, modest rounding, reasons shown as short bullet lists instead of badge clutter.
- Branding: a slate with a rising saffron line ("learning moving up").

---

## 15. Security, privacy and governance

- **Role-based, row-level scoping:**
  - state sees everything
  - a district officer sees school detail only in their district
  - a block officer sees school detail only in their block
  - a headmaster or teacher sees only their school
  - aggregates are shared for benchmarking
- **Signed session tokens** (HMAC).
- **Audit log** of logins, uploads, ingests, match decisions, task changes, PDF downloads and AI questions.
- **Record-level lineage:** every number traces to file, row, mapping version and match method.
- **Provenance tier on every row:** `synthetic_demo`, `department_uploaded` or `verified_official`. Synthetic data is bannered everywhere.
- **No student-level data** in this build; school-level aggregates only.
- **AI safety:**
  - the LLM never touches the database directly, only vetted tools
  - outputs are checked by the Evidence Guard
  - no causal claims
  - insufficient evidence is always disclosed
- **Before any real data:** encryption at rest and in transit, a retention policy, aggregation by default, and a review against India's **DPDP Rules 2025**.

---

## 16. Path to real deployment

| Step | What changes | What stays the same |
|---|---|---|
| **1. Pilot with department uploads** | Switch `config.yaml` to `mode: department`; officers upload real files in Data Studio | All analytics, AI and UI |
| **2. Official connectors** | Enable the UDISE+ API and state attendance/HR portal adapters after registration or an MoU | Same pipeline, now with `verified_official` provenance |
| **3. Scale** | SQLite → Postgres (SQLAlchemy already used); scheduled monthly refresh | Code |
| **4. Integrate, don't replace** | Feed findings and tasks to Vidya Samiksha Kendra (VSK) dashboards; follow NDEAR interoperability | ShikshaPulse stays the decision-and-action layer |

We do **not** assume public systems expose every field we need. For example, subject-wise teacher vacancy and monthly attendance are usually *not* in UDISE+. Each connector stub lists its required authorisation, fields, history and refresh frequency.

---

## 17. The 5-minute demo script

1. **Choose a language** (start in English or Hindi), then sign in as **Mr. Chan**.
2. **Overview:** *"Devgarh is 4th of 4 districts; numeracy fell 6.7 points in three years — this is a fall, not a long-standing level."*
3. **Data Studio:** read and match the 13 messy files, then build the record. *"By hand this took 3–4 days plus a week. Here: about 6 seconds. 26 uncertain names are waiting for a person — nothing is guessed."*
4. **Your choice vs the evidence:** pick Poti and Sinda. *"The evidence also points to Kerwa — the steepest fall, 16.5 points below what its conditions predict, and not explained by any tracked factor."*
5. **Why did it change?** Poti shows empty maths posts (strong signal), Sinda attendance (strong signal). Election duty is *background*; Kerwa is an *open question*. Click a box to show the evidence.
6. **Compare blocks** (Poti, election only): *"Similar election-hit blocks in other districts fell only 2.5–5 points; Poti fell 13.6. The election alone doesn't explain it."*
7. **Schools needing support → Plan tasks:** assign *temporary maths teacher redistribution* to **Romi** with a deadline.
8. **Switch user → Romi:** record the work, add proof, send for verification. **Switch back → Mr. Chan verifies.** Show the history: improved / no change yet / never done / overdue.
9. **Ask a question** in Hindi or Tamil, by voice: show the answer, the evidence chips and *"Numbers checked (n/n)"*. Press **Listen**.
10. **Switch user → Shanti Devi (teacher):** the "My school" page in Telugu or Hindi, read aloud, with one-tap task buttons.
11. **Meeting brief → PDF**, then **How we check:** 47/47 automated checks.

**If there are 2 more minutes, show the field features:**

12. **Overview → Early warnings.** *"This shows up months before the next assessment would."*
13. **Sign in as Meena Kumari (CRC).** Turn Wi-Fi off, fill in the 6-question visit and save: *"Saved on this phone"*. Turn Wi-Fi on and the visit syncs by itself.
14. **Why? → Kerwa.** The *From school visits* card shows that level grouping and teaching materials are rarely seen. *"The open question now has a lead from the field."*
15. **Block → Poti.** Show the teacher-sharing pairs. *Plan tasks* shows the past results of each intervention.
16. **Review meeting.** Step through it and add a decision; it becomes a task for Meena Kumari.
17. **School report card.** Print it, or share it on WhatsApp for the parents' meeting.

---

## 18. Questions judges may ask (with answers)

**Q: Isn't this just a dashboard?**
No. A dashboard shows numbers. ShikshaPulse also:
- joins messy files automatically
- explains *why*, with graded evidence
- compares fair peers and expected performance
- turns findings into owned tasks
- checks whether the tasks worked

**Q: How do you avoid the AI making things up?**
- The LLM can only call 12 vetted analytics tools; it never writes SQL.
- Every number it writes is checked against the tool outputs. Every finding must cite evidence.
- Causal words are softened, and missing evidence must be shown.
- If the answer fails twice, a rule-based engine answers instead.
- We tested this with adversarial answers: 6/6 caught.

**Q: Correlation isn't causation — how do you handle that?**
- We never claim causes. Findings are labelled *measured fact*, *linked signal* or *open question*.
- Election duty is shown as *background*.
- Unexplained parts are explicitly *open questions* that need classroom visits.

**Q: Your data is synthetic — how do we know it would work on real data?**
- The Scenario Lab plants known effects and messiness, so we can *measure* whether the system finds them. That isn't possible with real data, which has no ground truth.
- We test on randomised scenarios with random block names: 47/47 checks pass.
- Real files go through the same pipeline, via Data Studio upload.

**Q: Why is the expected-vs-actual comparison fair?**
- It predicts from conditions only, never from past scores.
- It is validated on blocks the model never saw (held-out R² 0.55–0.70).
- It separates "held back by conditions" (needs resources) from "doing worse than conditions predict" (needs a look at teaching), and new gaps from old ones.

**Q: What if a school name doesn't match?**
It goes to *Records to check* with candidate schools. A person decides, and the decision is logged. Auto-match precision is 0.995–1.0.

**Q: What if there's no internet or the AI is down?**
Everything still works. The offline engine answers in all six languages, with the same guard.

**Q: How would a teacher who doesn't read English use it?**
- They choose their language on the first screen.
- The "My school" page uses big numbers and plain words.
- They can press Listen to hear the page, ask by voice, and update tasks with one tap.

**Q: Who would actually use this in a village?**
- **CRCs:** a 6-tap visit form that works without a network.
- **Teachers and headmasters:** a "My school" page in their own language, which can be read aloud.
- **Parents and SMCs:** a one-page report card, shared on WhatsApp.
- **BEOs and DEOs:** early warnings, a guided review meeting, and tasks with owners.

None of it needs English or a laptop.

**Q: Assessments are once a year — how is this useful month to month?**
Early warnings use monthly attendance, compared with the same months last year. CRC visits add what is happening in the classroom. Both are refreshed far more often than assessments.

**Q: How do you know an action works?**
Implementation and learning outcomes are tracked separately. Every new draft shows that intervention's track record from earlier tasks. Over time, this shows which actions work in the district.

**Q: What about privacy?**
- No child-level data. Role-based scoping. An audit log of every action. Provenance on every row.
- DPDP Rules 2025 review before real data.

**Q: How does it fit existing government systems?**
It consumes UDISE+, state portals and department files, and can feed VSK. It is a layer on top, not a replacement.

---

## 19. Limitations (said honestly)

- **Associations, not causes:** the data is observational and school-level. Classroom practice enters only through CRC visit checklists, and these are simulated in the demo. Without enough visits, unexplained declines remain open questions.
- **Offline support** covers the visit form only. The dashboards need a connection.
- **Teacher-sharing pairs** do not know distances. Same-cluster pairs are preferred as a stand-in, and the BEO makes the final call.
- **Track records** in the demo come from simulated history. They become meaningful as real tasks are closed.
- **Synthetic data:** loosely calibrated to published ranges; not real measurements.
- **One known miss:** in Chitrangi, three overlapping effects mask the smaller facilities signal.
- **Translations** are machine-assisted and need native-speaker review.
- **Read-aloud** depends on the device having a voice for the language (Hindi is common on Windows; Tamil and Telugu voices are more common on Android). **Voice input** depends on browser support (works best in Chrome).
- **The downloadable PDF** uses English fonts. For Indian-language briefs, use the page's Print button.
- **Gemini's free tier** sometimes returns "busy" errors; the system retries, then falls back to the offline engine.

---

## 20. Repository map and how to run

```
AI FOUNDATION CLAUDE/
├── README.md                 quick start, demo script, evaluation summary
├── PROJECT_EXPLAINED.md      this document
├── CLAUDE.md                 working notes for continuing development
├── start.ps1 / start.sh      one-command install + build + run
├── backend/
│   ├── config.yaml           mode (demo|department), thresholds, demo date
│   ├── .env(.example)        LLM provider + key (never commit .env)
│   ├── app/
│   │   ├── main.py           FastAPI app; serves the built frontend
│   │   ├── api/routes.py     all endpoints
│   │   ├── auth.py           personas, tokens, scoping, audit
│   │   ├── sources/          adapters: demo files, upload, UDISE+ & state-portal stubs
│   │   ├── ingest/           schema, AI column mapper, normaliser, matcher, dedupe, pipeline
│   │   ├── analytics/        derive, trends, diagnose, expected, peers, radar, quality, context,
│   │   │                     early_warning, redistribution (teacher sharing)
│   │   ├── actions/          intervention library (YAML) + Action Room service + track record
│   │   ├── visits.py         CRC school-visit checklist (offline batch sync)
│   │   └── ai/               llm client, tools, evidence, guard, assistant, phrases (6 langs),
│   │                         templates (offline engine), drafter, brief (+PDF)
│   ├── scenario_lab/         generator, messy-file writer, scenarios/*.yaml
│   ├── eval/                 evaluation suite → report.md / report.json
│   └── tests/                pytest
└── frontend/src/
    ├── i18n/                 en (master) + hi, mr, bn, ta, te; extra.ts (field-feature strings)
    ├── speech.ts             read-aloud + voice input
    ├── state.tsx api.ts types.ts
    ├── components/           Layout, AskPanel, DraftActions, EarlyWarning, Smart, ui (InfoTip, HelpStrip, Speak…)
    └── pages/                Login, CommandCenter, Why, Block, Peers, Radar, Actions, MySchool,
                              DataStudio, Brief, Lab, About, Visits, Review, ReportCard
frontend/public/              PWA manifest, icon, service worker
```

**Run:**
```powershell
.\start.ps1        # Windows — then open http://localhost:8000
```

**Test:**
```powershell
cd backend
.venv\Scripts\python -m pytest -q          # 33 unit tests
.venv\Scripts\python -m eval               # 47 evaluation checks against ground truth
```

**Use a free LLM:** put a Gemini key in `backend/.env` (`LLM_API_KEY=…`) and restart. Optionally add a second key as `LLM_API_KEY_FALLBACK=…`: when the first key is rate-limited, over quota or rejected, the same question is retried on the second key automatically. Without any key, the offline engine answers.

---

## 21. Glossary

| Term | Meaning |
|---|---|
| **UDISE+** | Unified District Information System for Education Plus. National school database; every school has an 11-digit UDISE code |
| **NAS** | National Achievement Survey (learning assessment) |
| **FLN** | Foundational Literacy and Numeracy |
| **SLAS** | State Learning Achievement Survey |
| **BEO / DEO** | Block / District Education Officer |
| **VSK** | Vidya Samiksha Kendra, the government's education monitoring and command centres |
| **NDEAR** | National Digital Education Architecture (interoperability framework) |
| **SMC** | School Management Committee |
| **CRC** | Cluster Resource Coordinator: visits and supports a cluster of schools |
| **PWA** | Progressive Web App: a website that can be installed on a phone and works partly offline |
| **Early warning** | An alert from monthly data, compared with the same months last year |
| **DPDP Rules 2025** | Rules under India's Digital Personal Data Protection Act |
| **pts / pp** | Percentage points (e.g. 61.3% → 54.6% is −6.7 points) |
| **Signal** | A factor that changed together with learning: a link, not proof of cause |
| **Open question** | Something the data cannot answer yet |
| **Residual / gap vs expected** | Actual score minus the score predicted from conditions |
| **Provenance tier** | Where a row of data came from: synthetic demo, department upload, or verified official |
| **Lineage** | The trail from a number back to its file, row and processing steps |
| **Evidence Guard** | The checker that verifies every AI answer before it is shown |
| **Deterministic engine** | The rule-based answer writer used when no LLM is available |
