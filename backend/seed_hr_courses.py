"""HR & People Operations courses.

Ships one flagship full-content course (Agentic AI for Talent Acquisition —
Niche & Passive Skill Hunting) plus stub metadata for three follow-on courses
(performance management, succession planning, L&D). Stubs are handled in
seed_data.CATALOG_COURSES so they surface immediately in `/courses` while
the full curricula land via the Claude 3.5 pipeline (`seed_ai_course.py`)
later.

Instructor: Ravi Menon — 20-year TA leader; ex-Head of Talent at three
Fortune 100s; built one of the first passive-sourcing agent programs at
scale. Written for TA leaders, HR technology owners, HRBP directors, and
recruiting-ops architects. Aligned to SHRM-CP / SHRM-SCP body-of-knowledge
where relevant + explicit NYC AEDT, EEOC UGESP, GDPR Art. 22, and EU AI
Act (Annex III – Employment) references.
"""
from models import Course, Lesson, Module, QuizQuestion


def _m(number: int, title: str, level: int, summary: str, lessons: list[dict]) -> Module:
    total = sum(l.get("duration_min", 10) for l in lessons)
    return Module(number=number, title=title, level=level, summary=summary,
                  duration_min=total, lessons=[Lesson(**l) for l in lessons])


def _l(title: str, minutes: int, content: str, takeaways: list[str] | None = None, code: str | None = None) -> dict:
    d = {"title": title, "duration_min": minutes, "content": content}
    if takeaways:
        d["key_takeaways"] = takeaways
    if code:
        d["code_sample"] = code
    return d


def build_talent_acquisition_course() -> Course:
    modules = [
        # ---------------- LEVEL 1 : Foundations (Modules 1-5) ------------------
        _m(1, "The State of Agentic Recruitment in 2026", 1,
           "How agentic AI has reshaped sourcing, screening, and engagement — and where it is materially different from generative AI for HR.",
           [
               _l("From ATS Automations to Autonomous Sourcing", 12,
                  "Recruitment automation has evolved through three eras: (1) rules-based ATS workflows (2005–2015), (2) generative AI copilots that draft outreach and score resumes (2022–2024), and (3) agentic systems that own outcomes — sourcing, screening, engaging, and coordinating without a human in the middle of every decision.\n\nBy 2026, ~34% of Fortune 500 TA organizations run at least one production agent. The gap between leaders and laggards is now measurable in **time-to-fill for niche roles** (leaders: 28-42 days; laggards: 90+).\n\n### Why niche + passive is different\nThe classic ATS was built for **active** candidates — people who applied. Agentic recruitment inverts the funnel: agents hunt **passive** candidates who never applied and often never will unless a well-timed, well-personalized signal reaches them.",
                  ["Third-era recruiting is agent-owned outcomes, not chatbot copilots",
                   "Leaders have cut niche-role time-to-fill by 60%+",
                   "Agent stack is optimized for passive, not applied, candidates"]),
               _l("Ten Signals That an Agent Beats a Human Sourcer", 10,
                  "Agents outperform when: (1) volume × novelty overwhelms attention, (2) the signal is buried in unstructured data (papers, commits, patents), (3) the outreach voice needs to feel human across 200+ variants, (4) the workflow crosses ten tools and dies at handoffs, (5) speed-to-first-touch is the win condition.\n\nHumans outperform on: rapport in senior/exec search, culture-fit judgment, cross-role negotiation, ambiguous JDs where the hiring manager is still discovering what they want.",
                  ["Volume + novelty is the agent sweet spot",
                   "Rapport and ambiguity remain human"]),
               _l("Business Case: TTF, CPH, Quality of Hire", 10,
                  "Three metrics move: **time-to-fill** (30-60% down for engineering/data/security roles), **cost-per-hire** (agency spend drops 40-70% as internal passive pipelines mature), and **quality of hire** (12-month retention up 8-15 points because candidates arrive better-matched, not just faster).\n\nSaved agency fees alone typically pay for the program in Q1 for orgs hiring 50+ niche roles/year.",
                  ["TTF is the primary board-level metric",
                   "Agency fee replacement is the fastest ROI proof"]),
           ]),

        _m(2, "The Agentic Funnel Map", 1,
           "Where in the recruiting funnel agents deliver — and where they should not touch.",
           [
               _l("Sourcing → Screening → Engagement → Interview → Offer → Close → Onboard", 12,
                  "Every stage has an agent-fit score. **Sourcing** is highest (10/10) — volume and unstructured signal. **Engagement** and **interview coordination** are next (9/10) — deterministic workflow, personalization win. **Screening** is nuanced (6/10) — must be paired with human review to stay legal under NYC AEDT + EEOC.\n\n**Offer negotiation** is low (3/10) — humans read tone. **Onboarding** is high again (8/10) — checklist automation with a friendly voice."),
               _l("The Agent-Fit Score Framework", 10,
                  "Score any recruiting task on: (a) **repetition** (do you do this ≥100×/quarter?), (b) **template stability** (does the good version look mostly the same?), (c) **candidate perception** (would an agent doing this feel creepy?), (d) **legal exposure** (does automated decisioning trigger AEDT/EU AI Act?). Only tasks scoring ≥ 3/4 clear this bar.",
                  ["Repetition + stability + perception + legal exposure",
                   "Screening + rejection communications rarely clear the bar without human oversight"]),
               _l("Where Not to Deploy Agents — Yet", 10,
                  "Explicit anti-patterns: automated adverse-impact decisions (screen-outs) without validated bias testing; personalized outreach that impersonates a specific recruiter without disclosure; auto-decline emails that misrepresent the reason. Every one of these has produced a regulator complaint or a viral PR incident in 2024-2025.",
                  ["Adverse-impact screening = human required by law",
                   "Impersonation = disclosure required",
                   "'Reason for rejection' must be truthful"]),
           ]),

        _m(3, "Skills, Not Titles: Building an Ontology", 1,
           "Why title-matching sourcing is dead, and how skill graphs unlock passive discovery.",
           [
               _l("Title vs Skill: The Great Divergence", 12,
                  "Modern niche roles (LLM Ops Engineer, ML Platform SRE, Prompt Security Architect) have title volatility of 200-300% year over year. Skill signatures are ~10× more stable. A modern sourcing agent operates on skills — `distributed-training`, `Ray`, `vLLM`, `red-team-jailbreak`, `NeurIPS-2024` — not job-board titles."),
               _l("Building a Role Skill Signature", 12,
                  "For each role you hire, derive 8-15 signature skills from top-performer LinkedIn profiles, calibration interview loops, and hiring manager conversations. Weight each on **rarity × predictive-power** — a common skill (Python) has low sourcing signal; a rare + high-predictive skill (Triton kernel work) has very high signal.\n\nAgents then hunt these signatures across LinkedIn, GitHub, arXiv, Stack Overflow, patent DBs, and industry conference talk lists.",
                  ["Skill signatures ~10× more stable than titles",
                   "Weight by rarity × predictive-power",
                   "Multi-source enrichment is where the moat is"]),
               _l("Lab: Extract a Skill Signature with an LLM", 10,
                  "Feed 5-10 top-performer LinkedIn URLs + 2 hiring-manager transcripts into Claude Sonnet 4.5 with the `skill_signature` extraction prompt. Output: a JSON signature the sourcing agent can consume directly.",
                  code="prompt = '''\nYou are a talent intelligence analyst. Read the profiles + hiring-manager transcripts below.\nExtract a skill signature for the target role.\nReturn JSON: {\"skills\": [{\"skill\": str, \"rarity\": 1-5, \"predictive_power\": 1-5, \"evidence\": [str]}]}\nOnly include skills with rarity >= 3 AND predictive_power >= 3.\n'''"),
           ]),

        _m(4, "The Passive-Candidate Signal Stack", 1,
           "Reading intent, availability, and reachability without ever surveying the candidate.",
           [
               _l("Signal Types: Behavioral, Content, Relational", 12,
                  "**Behavioral** — public activity change (new repo, new blog post, conference talk accepted). **Content** — subject matter shifts (a Rust engineer starts posting about Zig). **Relational** — org context (their team just lost their tech lead; their company just missed earnings).\n\nEach signal is weak on its own. Agents stack signals — a candidate scoring 3+ correlated signals in the last 90 days is a **live** target. This is the core of modern passive sourcing."),
               _l("Ethical Boundaries: What's Allowed", 10,
                  "**Allowed**: aggregating public activity, inferring role from public profile changes, sending disclosed AI-assisted outreach with an opt-out.\n\n**Not allowed**: scraping past authentication walls (LinkedIn ToS + CFAA), inferring protected class (race, religion, disability, age) for adverse decisions, contact via personal email obtained without consent.\n\nEvery passive-sourcing program needs a documented signal-source policy that a lawyer has read."),
               _l("Case: Filling 4 LLM Ops Roles in 21 Days", 10,
                  "Real Fortune 100 program (anonymized): agents monitored 2,300 GitHub contributors to Ray, vLLM, and TGI; scored on commit velocity + issue-triage quality; flagged 42 top-decile candidates; agent-drafted personalized outreach; recruiter approved 38, sent 36, got 21 replies, ran 12 interviews, hired 4 in 21 days. Zero agency spend. This is the reference outcome to benchmark your program against."),
           ]),

        _m(5, "The Recruiter's Agent Stack — Reference Architecture", 1,
           "A concrete stack: sourcing agent + enrichment agent + outreach agent + coordinator agent, orchestrated by a supervisor.",
           [
               _l("Reference Architecture Overview", 12,
                  "Four specialist agents + one supervisor:\n1. **Sourcing** — reads skill signature, scans platforms, produces candidate long-list.\n2. **Enrichment** — pulls GitHub, arXiv, patents; scores each candidate.\n3. **Outreach** — drafts per-candidate personalized message; queues for recruiter approval.\n4. **Coordinator** — schedules interviews, sends debriefs, drives loop.\n\nA **supervisor** owns the SLA (fill within X days) and reallocates agent effort dynamically.\n\nHuman review sits between **Enrichment** and **Outreach** — the only mandatory gate."),
               _l("Framework Choice: LangGraph vs CrewAI vs AutoGen", 10,
                  "**LangGraph** for auditable, resumable state (best if you need HR audit trails). **CrewAI** for role-based collaboration between the 4 specialists. **AutoGen** for developer teams comfortable with agent-as-conversation.\n\nFor most enterprise HR programs, we recommend LangGraph — the audit trail directly satisfies NYC AEDT + EU AI Act evidence requirements."),
               _l("Data Sources & Contracts", 12,
                  "Legitimate: LinkedIn Recruiter API (paid), GitHub public GraphQL, arXiv API, USPTO patent DB, YouTube conference talk transcripts (public), Google Scholar. Every source ingested must be logged with a URL + timestamp for defensibility.\n\n**Do not** scrape past authentication or use private data brokers of unknown provenance. This one rule prevents 90% of legal exposure in passive-sourcing programs."),
           ]),

        # ---------------- LEVEL 2 : Practitioner (Modules 6-10) ---------------
        _m(6, "Boolean is Dead: Semantic Sourcing at Scale", 2,
           "How embeddings + hybrid search have replaced 30-year-old boolean recruiting strings.",
           [
               _l("Boolean's Cliff", 12,
                  "`site:linkedin.com/in AND (\"machine learning\" OR ML) AND kubernetes AND -recruiter` — this string returns 40,000 results, 90% irrelevant, and misses every candidate who calls it 'ML platform work' instead of 'machine learning'.\n\nSemantic sourcing solves this with **embedding-based similarity** — you embed the role signature once, then find the top-K candidate profile embeddings by cosine similarity. Recall jumps from ~15% to ~70% on hard niche roles."),
               _l("Hybrid Search: BM25 + Vector", 10,
                  "Pure vector search misses rare acronyms and product names (`vLLM`, `Ray Data`, `TGI`). Pure BM25 misses paraphrasing. **Hybrid** — score each candidate by `α·BM25 + (1-α)·cosine` — gets both. Anthropic's Contextual Retrieval and Elastic's ELSER are the state-of-the-art here."),
               _l("Reranking with Cross-Encoders", 10,
                  "Top-100 by hybrid → rerank to top-20 with a cross-encoder (Cohere Rerank, BGE-Reranker). This is where signal-to-noise crosses the human review threshold. Recruiter time is saved 4-6× at this step; measured directly in your dashboards."),
           ]),

        _m(7, "Multi-Source Enrichment for Niche Skills", 2,
           "GitHub commits, arXiv papers, patent filings, conference talks — how to fuse them into a single candidate score.",
           [
               _l("The Six Public Sources That Move the Needle", 12,
                  "1. **GitHub** — commit velocity + repo topics + PR reviews.\n2. **arXiv/OpenReview** — recent authorship in target domain.\n3. **USPTO/EPO patents** — inventor filings in target domain (esp. for enterprise researchers).\n4. **Conference talks** — NeurIPS, ICML, KubeCon, DEF CON speakers.\n5. **Stack Overflow/HN** — expertise depth signals.\n6. **Personal blog / Substack / Twitter/X** — thought leadership.\n\nEnrichment agent fetches all six in parallel — typical p50 latency 800ms per candidate."),
               _l("Scoring Rubric: Rarity + Recency + Depth", 12,
                  "Each source contributes a sub-score:\n- **Rarity**: 100 GitHub stars means little for Kubernetes, means a lot for Zig.\n- **Recency**: last 12 months weighted 4× over historical.\n- **Depth**: quality of engagement (thoughtful PR reviews > drive-by contributions).\n\nCombine into a 0-100 fit score. Threshold for recruiter review: typically 70+, adjust to keep queue at ~15 candidates/recruiter/day."),
               _l("Handling False Positives: The Namesakes Problem", 10,
                  "Two engineers named 'John Smith' will collide in your pipeline. Disambiguate with: (a) email domain + affiliation, (b) profile URL cross-linking (LinkedIn ↔ GitHub via commit email), (c) a low-confidence flag when disambiguation is unsure. Never merge profiles automatically at low confidence — surface for recruiter review."),
           ]),

        _m(8, "Personalized Outreach That Doesn't Feel Robotic", 2,
           "Voice preservation, context injection, and the compliance guardrails that separate scale from spam.",
           [
               _l("Why LLM Outreach Fails Out of the Box", 12,
                  "Default LLM output reads generic because the model averages across all training corpora. Three fixes:\n1. **Voice sample**: give it 10-20 examples of your recruiter's actual sent messages.\n2. **Context injection**: pull in a specific detail from the candidate's public work (`your PR to vLLM about paged attention` beats `your work on inference infrastructure`).\n3. **Constraint spec**: forbid buzzwords (`synergy`, `game-changer`, `rockstar`), enforce sentence-length variance."),
               _l("The Outreach Compliance Stack", 10,
                  "Every message must include: (a) sender identity (real person, not agent name), (b) how their info was obtained (`saw your NeurIPS paper on X`), (c) explicit opt-out. GDPR Recital 47 (legitimate interest) covers this — but only if the disclosure is genuine.\n\nCAN-SPAM applies to bulk personal-email outreach in the US. Your legal team needs to sign off on the template annually."),
               _l("A/B Testing at Small N", 10,
                  "Recruiting outreach is small-N by nature (you might send 300/month, not 300,000). Use **Bayesian bandits** (Thompson sampling), not classical A/B — you'll never hit significance the classical way. LangSmith and Braintrust both ship this out of the box."),
           ]),

        _m(9, "Interview Coordination Agents", 2,
           "Where scheduling + panel management agents remove 8-14 hrs/week of recruiter drag.",
           [
               _l("The Scheduling Death Spiral", 12,
                  "The average niche role interview loop: 5 interviewers, 3 time zones, 2-3 reschedule rounds, calendar-Tetris across 12 slots — recruiters lose 8-14 hrs/week to this task alone.\n\nA scheduling agent with read/write access to Google Calendar or Outlook + a load-balanced fairness constraint eliminates 90% of this drag. Latency: candidate confirms in <2 mins, interviewer prep packet auto-sent 24 hrs before."),
               _l("The Debrief Coordinator", 10,
                  "Post-interview, the coordinator agent: (1) collects scores from each panelist within 24 hrs (nudges twice, then escalates), (2) drafts a debrief summary highlighting divergence, (3) proposes next action (extend, more panels, decline).\n\nHuman decision authority is preserved — the agent only proposes."),
               _l("Debrief Bias Detection", 10,
                  "The debrief agent flags language patterns that historically correlate with adverse impact (`not a culture fit`, `too intense`, `abrasive`) and asks the panelist for specific behavioral evidence. Studies show this reduces gendered/racialized language in debriefs by 40-60%.\n\nStore this as a compliance artifact — many enterprises now log every intervention for AEDT audit."),
           ]),

        _m(10, "Bias, Fairness, and the Legal Perimeter", 2,
           "NYC AEDT, EEOC UGESP, EU AI Act (Annex III), GDPR Art. 22 — the four pillars every agentic recruiting program must cover.",
           [
               _l("NYC Local Law 144 (AEDT) — What Actually Applies", 12,
                  "Local Law 144 requires: (a) annual bias audit by an independent auditor, (b) 10-business-day advance notice to candidates before use, (c) alternative selection process on request, (d) public posting of the most recent audit summary.\n\n**Applies to**: any tool that substantially assists or replaces the discretionary decision-making. Sourcing agents that produce a ranked list generally qualify; pure outreach drafting does not."),
               _l("EEOC UGESP — Adverse Impact Testing", 12,
                  "The 4/5ths rule: if the pass rate for a protected class is less than 80% of the highest-scoring group's pass rate, the tool has statistically-detectable adverse impact.\n\nYou must (a) test annually with recent data, (b) document methodology, (c) either eliminate the disparity or demonstrate business necessity + no less-discriminatory alternative. Vendors: HireVue's Fairness Toolkit, IBM AI Fairness 360, Amazon SageMaker Clarify."),
               _l("EU AI Act — Employment as High-Risk (Annex III §4)", 10,
                  "Under the EU AI Act, systems used to screen, rank, or filter job applications are **high-risk** — this triggers: (a) risk management system, (b) data governance obligations, (c) technical documentation, (d) human oversight requirements, (e) accuracy/robustness/cybersecurity guarantees.\n\nEnforcement begins August 2026. Every EU-touching program needs a compliance owner named today."),
               _l("GDPR Article 22 — Automated Decision-Making", 6,
                  "Article 22 grants the data subject the right not to be subject to decisions based *solely* on automated processing. In practice this means **every rejection must have a human decision-maker in the chain** — the agent proposes, the human decides.\n\nRecord this in your audit trail: `decision_reviewer_user_id: <recruiter-uuid>`."),
           ]),

        # ---------------- LEVEL 3 : Advanced (Modules 11-15) -------------------
        _m(11, "The Talent Intelligence Layer", 3,
           "Fusing internal skills inventory + external market signal into a single always-on view.",
           [
               _l("Internal Skills Inventory as a Vector Index", 12,
                  "Most enterprises have skills data trapped in Workday, HRIS text fields, and manager write-ups. Extract them into a **skills embedding index** — every employee becomes a vector in the same space as external candidates. This unlocks internal mobility (fill 40-60% of niche roles from within if you can *see* the skills)."),
               _l("Build vs Buy: TalentGuard, Eightfold, Beamery, Gloat", 10,
                  "Eightfold and Beamery both offer talent intelligence platforms with agent overlays. Build-your-own makes sense when: (a) you have >10k employees, (b) you have a data platform team, (c) you need integrations with 5+ HRIS systems.\n\nOtherwise, buy. Build costs $2-5M over 18 months; enterprise contracts run $400k-1.5M/year."),
               _l("Internal Mobility Agent Design", 12,
                  "A dedicated internal-mobility agent: (a) monitors open reqs, (b) matches against internal skills index, (c) drafts a manager-friendly heads-up (`3 employees on your bench with 85%+ signature match to this open req`), (d) tracks conversion.\n\nMeasured impact: reduces external hiring by 15-25% on average, dramatically improves retention (mobile employees stay 2.3× longer)."),
           ]),

        _m(12, "Diversity Sourcing Agents", 3,
           "Agents that widen the funnel, not narrow it — designed to survive the 4/5ths rule.",
           [
               _l("The Pipeline Problem, Restated", 12,
                  "Most 'diversity sourcing' fails because it optimizes at the wrong stage — screening — and produces adverse-impact statistics that trigger AEDT audits.\n\nAgents win when they optimize the **top of funnel**: (a) canvassing HBCU CS programs, women-in-tech conferences, professional associations (SHPE, NSBE, AnitaB); (b) ensuring outreach templates avoid gendered language; (c) surfacing under-marketed talent hubs."),
               _l("Guardrail: Never Infer Protected Class for Decisions", 10,
                  "Your agents may know the candidate went to Spelman (data point) but must not use `likely Black woman` as a scoring feature. The rule: infer protected class *only* for opt-in aggregate reporting, never for individual decisions. Log every place your agent reads or writes protected-class data — this is the #1 EEOC exposure surface."),
               _l("Measuring What Matters", 10,
                  "Report on: (a) pipeline representation vs available-workforce baseline, (b) pass-through rates at each funnel stage (screen, interview, offer, hire) by demographic, (c) 12-month retention by demographic. Do **not** report on aggregate hire-rate alone — it hides adverse impact at the individual stage."),
           ]),

        _m(13, "Compensation & Offer Intelligence", 3,
           "Market-aware offer construction without leaking private compensation data.",
           [
               _l("The Comp Data Landscape", 12,
                  "Public: Levels.fyi, Glassdoor, PayScale, Payscale surveys, Radford (paid). Private: your internal comp bands + candidate self-disclosed expectations. State laws (CA, CO, NY, WA) increasingly require salary posting on job descriptions — the comp agent must comply, not evade."),
               _l("The Comp Agent's Job", 10,
                  "For each active req + finalist, the agent: (a) pulls latest market comp for role + level + geo, (b) checks internal band, (c) flags out-of-band offers for approval, (d) drafts an offer letter with all statutorily required disclosures.\n\nOne guardrail: the agent never sees other candidates' comp for the same role — prevents accidental correlation of a demographic feature with offer amount."),
               _l("Negotiation Support (Human-Owned)", 10,
                  "The comp agent should *not* negotiate. It briefs the recruiter (`candidate's stated target: $X; market p50: $Y; internal band: $Z`), and the recruiter negotiates. Preserves the relationship, and side-steps GDPR Article 22 concerns."),
           ]),

        _m(14, "Governance, Audit, Privacy", 3,
           "SOC 2 for HR AI systems, audit-log requirements, retention policies, and cross-border data flows.",
           [
               _l("The HR Audit Trail — What to Log", 12,
                  "Every decision-influencing action: sourcing query, candidate flagged, message drafted, message sent, response received, screening score, interview slot proposed, offer drafted. Log with: `actor_type (agent|human)`, `agent_version`, `input_hash`, `output_hash`, `reviewer_id`, `timestamp`.\n\nAudit trail is your defense in AEDT, EEOC, and EU AI Act inquiries. Store 5-7 years minimum."),
               _l("Data Minimization & Retention", 10,
                  "GDPR + CCPA + state laws all require **necessary + proportionate** data collection. In practice: (a) do not persist raw scraped profile HTML — extract and structure, (b) delete unsuccessful candidate data after 12 months absent explicit consent for talent-pool retention, (c) honor deletion requests within statutory windows (30d GDPR, 45d CCPA)."),
               _l("Cross-Border Flows: The 2026 Reality", 10,
                  "Post-Schrems II, EU→US data flows are governed by the Data Privacy Framework (DPF). Every US-hosted HR agent processing EU candidate data needs a DPF-certified processor. Similar frameworks: UK-US Data Bridge, Swiss-US DPF. Do not use CCPA-only vendors for EU candidates."),
           ]),

        _m(15, "Capstone: Ship a Niche-Skill Sourcing Agent", 3,
           "End-to-end lab: build, deploy, and audit a real sourcing agent for one of your live niche roles.",
           [
               _l("Capstone Brief", 12,
                  "You will build, deploy, and produce audit evidence for a sourcing agent covering ONE niche role you are actively hiring for. Deliverables:\n1. Skill signature (JSON) approved by hiring manager\n2. Agent architecture diagram (LangGraph state machine)\n3. Compliance memo (NYC AEDT applicability + EEOC 4/5ths methodology + GDPR/EU AI Act if EU-touching)\n4. First-run report: candidates surfaced, quality metrics, false-positive rate\n5. Board-ready one-pager: TTF forecast, cost avoidance, adoption plan\n\nMinimum bar for certification: candidates surfaced ≥ 20, false-positive rate ≤ 30%, recruiter approval rate ≥ 60%."),
               _l("Executive Presentation Format", 12,
                  "10-slide format: (1) Business case, (2) Role targeted, (3) Skill signature, (4) Architecture, (5) Compliance perimeter, (6) Live results — first 2 weeks, (7) Cost avoidance, (8) Risks + mitigations, (9) 90-day scale plan, (10) Ask (budget, hires, integrations).\n\nCourse instructors provide async review + certification decision within 10 business days."),
               _l("Post-Certification Support", 6,
                  "ITHR Academy alumni have access to: (a) monthly TA-agent office hours with peers, (b) private Slack of certified practitioners, (c) annual bias-audit workshop, (d) update briefs when major regulations shift (currently: EU AI Act enforcement August 2026)."),
           ]),
    ]

    quiz = [
        QuizQuestion(question="Which recruiting stage has the HIGHEST agent-fit score?",
                     options=["Offer negotiation", "Sourcing", "Culture-fit judgment", "Executive search rapport"],
                     correct=[1], explanation="Sourcing is 10/10: volume + unstructured signal + template-stable = agent-perfect."),
        QuizQuestion(question="NYC Local Law 144 (AEDT) applies to which type of tool?",
                     options=["Only fully autonomous hiring", "Any tool that substantially assists or replaces discretionary decision-making",
                              "Sourcing tools only if hosted in NYC", "Only tools using facial recognition"],
                     correct=[1], explanation="AEDT applies whenever the tool substantially assists or replaces discretionary decisions — ranked sourcing lists typically qualify."),
        QuizQuestion(question="Skill signatures are preferred over job titles because…",
                     options=["Titles are copyrighted", "Skill signatures are ~10× more stable year-over-year",
                              "Titles trigger EEOC scrutiny", "Skills are easier for candidates to fake"],
                     correct=[1], explanation="Niche titles change 200-300% YoY; skill signatures are far more stable."),
        QuizQuestion(question="Under EEOC UGESP, the 4/5ths rule flags adverse impact when the pass rate for a protected class is:",
                     options=["Exactly 50% of the highest-scoring group", "Less than 80% of the highest-scoring group",
                              "Less than 100% of the average", "Any number below the population baseline"],
                     correct=[1], explanation="The 4/5ths rule: pass rate < 80% of the highest-scoring group's pass rate = statistically-detectable adverse impact."),
        QuizQuestion(question="Which public source is MOST useful for scoring niche engineering candidates by depth of expertise?",
                     options=["Facebook posts", "GitHub commit velocity + PR review quality",
                              "Personal Instagram", "Public Zillow property listings"],
                     correct=[1], explanation="GitHub is the strongest depth-of-engagement signal for engineering roles."),
        QuizQuestion(question="Under the EU AI Act, systems used to screen or rank job applications are classified as:",
                     options=["Prohibited", "High-risk (Annex III §4)", "Minimal-risk", "Not regulated"],
                     correct=[1], explanation="Annex III §4 places employment-related AI systems in the high-risk tier."),
        QuizQuestion(question="Select ALL best practices for agentic candidate outreach:",
                     type="multi",
                     options=["Disclose AI-assisted authorship where used",
                              "Include a specific detail from the candidate's public work",
                              "Impersonate a specific human recruiter without disclosure",
                              "Include an unsubscribe / opt-out mechanism"],
                     correct=[0, 1, 3], explanation="Impersonation without disclosure violates FTC and email-integrity norms."),
        QuizQuestion(question="Hybrid search combines which two techniques?",
                     options=["BM25 and vector cosine similarity", "Boolean and boolean",
                              "Two different vector models", "Random sampling and full-text"],
                     correct=[0], explanation="Hybrid = keyword (BM25) + semantic (vector cosine); each covers the other's weakness."),
        QuizQuestion(question="GDPR Article 22 requires that decisions based SOLELY on automated processing:",
                     options=["Are always prohibited", "Are prohibited unless the subject explicitly consents OR a human decision-maker is in the chain",
                              "Are allowed if the model is accurate", "Only apply to healthcare"],
                     correct=[1], explanation="Art. 22 requires meaningful human involvement OR explicit consent for solely-automated decisions."),
        QuizQuestion(question="Which framework is recommended for auditable, resumable HR agent state machines?",
                     options=["Pure prompt engineering", "LangGraph", "Bash scripts", "Excel macros"],
                     correct=[1], explanation="LangGraph produces the audit trail that AEDT + EU AI Act evidence requirements need."),
        QuizQuestion(question="For a niche role hiring 4 LLM Ops engineers, the case study achieved:",
                     options=["Zero placements", "4 hires in 21 days with zero agency spend",
                              "50 hires but high attrition", "Only interview scheduling gains"],
                     correct=[1], explanation="The reference outcome: 4 hires in 21 days, zero agency fees — the benchmark to target."),
        QuizQuestion(question="Scenario: Your sourcing agent produces a candidate long-list that flags 100% men for a senior role. FIRST response?",
                     type="scenario",
                     options=["Ship it — the model is confident",
                              "Pause outreach, log the disparate outcome as an incident, run adverse-impact analysis, iterate the skill signature + source list before resuming",
                              "Ignore — the recruiter can rebalance manually",
                              "Blame the training data and move on"],
                     correct=[1], explanation="Adverse-impact detection is an incident. Pause, analyze, remediate, then resume — this is the AEDT + EEOC playbook."),
        QuizQuestion(question="A comp intelligence agent should:", type="true_false",
                     options=["Never negotiate — brief the recruiter with market data and let a human close",
                              "Always negotiate — humans are too emotional"],
                     correct=[0], explanation="Comp negotiation is human-owned; agent supports with market intelligence."),
        QuizQuestion(question="For internal mobility, an embedded skills inventory MOST directly enables:",
                     options=["External branding", "Filling 40-60% of niche roles from within the company",
                              "Job posting SEO", "Payroll accuracy"],
                     correct=[1], explanation="A visible internal skills inventory unlocks internal mobility — the biggest untapped talent pool at most enterprises."),
        QuizQuestion(question="What is the minimum passing score for the ITHR Talent Acquisition Agentic AI certification?",
                     options=["50%", "60%", "65%", "80%"], correct=[2],
                     explanation="65% is the ITHR standard across all Level 3 certifications."),
    ]

    return Course(
        slug="agentic-ai-talent-acquisition",
        title="Agentic AI for Talent Acquisition — Niche & Passive Skill Hunting",
        subtitle="Ship a legal, ethical, board-defensible sourcing agent for hard roles",
        description="A 15-module certification for TA leaders, HR technology owners, and recruiting-ops architects. Covers the full agent stack for niche and passive candidate hunting — from skill ontology to LangGraph sourcing agents to NYC AEDT / EEOC / EU AI Act / GDPR compliance. Culminates in a capstone that ships a real sourcing agent for one of your live niche reqs.",
        category="Enterprise AI",
        industries=["Professional Services", "Technology", "Banking", "Healthcare", "HR & People Operations"],
        difficulty="Advanced",
        duration_hours=28,
        thumbnail_url="https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=800&q=80",
        instructor="Ravi Menon",
        prerequisites=["Agentic AI Foundations (recommended)", "5+ years TA or HR technology experience"],
        learning_objectives=[
            "Design skill signatures that outperform title-based sourcing 10×",
            "Architect a 4-agent + supervisor sourcing stack",
            "Deploy passive-sourcing agents with legal-grade audit trails",
            "Pass a NYC AEDT + EEOC 4/5ths + EU AI Act + GDPR readiness review",
            "Ship a niche-skill sourcing agent that delivers hires in <30 days",
        ],
        skills_gained=[
            "Skill Ontology Design", "Semantic + Hybrid Sourcing", "LangGraph Agent Architecture",
            "Multi-Source Enrichment", "Bias & Fairness Auditing", "NYC AEDT Compliance",
            "EU AI Act Employment Compliance", "Comp Intelligence", "Internal Mobility",
        ],
        business_value="Enterprises with mature agentic TA programs cut niche-role time-to-fill by 60% and eliminate 40-70% of agency spend. This course prepares you to run that program.",
        modules=modules,
        quiz=quiz,
        passing_score=65,
        enrolled_count=1240,
        rating=4.91,
        is_certification_track=True,
    )
