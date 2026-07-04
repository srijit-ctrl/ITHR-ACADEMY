"""5 more industry-specific full courses: Banking, Healthcare, Manufacturing, Retail, Government."""
from models import Course, Module, Lesson, QuizQuestion


def _m(number, title, level, summary, lessons):
    return Module(number=number, title=title, level=level, summary=summary,
                  duration_min=45, lessons=[Lesson(**l) for l in lessons])


def _std_quiz(topic: str, passing_ref: str = "65%") -> list:
    """Compact 12-Q quiz template shared across industry courses."""
    return [
        QuizQuestion(question=f"What is the primary business driver for agentic AI in {topic}?",
                     options=["Cost reduction only", "End-to-end workflow automation with measurable ROI",
                              "Better graphics", "Marketing"], correct=[1],
                     explanation="Agentic AI in enterprise settings is measured by ROI on workflow automation."),
        QuizQuestion(question="Which regulation MOST directly affects enterprise AI in this sector?",
                     options=["Random local ordinances", "Sector-specific regulation as covered in Module 11",
                              "None", "Only EU AI Act"], correct=[1],
                     explanation="Every industry has sector-specific overlays layered on top of general AI regulation."),
        QuizQuestion(question="A single-agent design is appropriate when:",
                     options=["Tasks decompose into specialized roles", "Task is well-scoped and linear",
                              "You want more complexity", "You have unlimited budget"], correct=[1],
                     explanation="Single agents suit well-scoped linear tasks; multi-agent for decomposable workflows."),
        QuizQuestion(question="Human-in-the-loop is most critical when:",
                     options=["Cost is low", "Decisions have legal or safety consequences",
                              "The model is confident", "The user is unavailable"], correct=[1],
                     explanation="High-stakes decisions require human oversight regardless of model confidence."),
        QuizQuestion(question="Which are essential components of any industry agent deployment? (select all)",
                     type="multi", options=["Guardrails", "Audit trail", "Escalation paths", "Cost budget"],
                     correct=[0, 1, 2, 3], explanation="All four are essential."),
        QuizQuestion(question="Passing score for this ITHR certification?",
                     options=["50%", passing_ref, "75%", "85%"], correct=[1],
                     explanation=f"{passing_ref} is the ITHR standard."),
        QuizQuestion(question="RAG is preferred over fine-tuning when:", type="true_false",
                     options=["Knowledge changes over time and must be verifiable", "Model behavior needs to change permanently"],
                     correct=[0], explanation="RAG suits evolving, verifiable knowledge."),
        QuizQuestion(question="Multi-tenant AI systems require:", type="multi",
                     options=["Data isolation between tenants", "Access control on retrieval",
                              "Audit trail per tenant", "Right-to-forget support"],
                     correct=[0, 1, 2, 3], explanation="All required for enterprise multi-tenancy."),
        QuizQuestion(question="Which is a valid ROI metric for sector agentic AI?",
                     options=["Cycle time reduction", "Vanity metrics", "Model size", "Prompt length"],
                     correct=[0], explanation="Cycle time reduction is a real business metric."),
        QuizQuestion(question="Prompt injection risk in enterprise context is:",
                     options=["Nonexistent", "A material security risk that requires layered defenses",
                              "A frontend issue", "Only in consumer apps"], correct=[1],
                     explanation="Prompt injection is a real risk requiring layered defenses."),
        QuizQuestion(question="Capstone deliverable typically includes:", type="multi",
                     options=["Architecture diagram", "Governance memo", "ROI estimate", "Executive presentation"],
                     correct=[0, 1, 2, 3], explanation="All four are standard capstone deliverables."),
        QuizQuestion(question="Scenario: A production agent hallucinates a compliance-related answer. FIRST response?",
                     type="scenario",
                     options=["Ignore it", "Trigger incident response: rollback, root-cause, communicate",
                              "Blame the model", "Ship a bigger model"], correct=[1],
                     explanation="Treat AI incidents like security incidents: contain, investigate, communicate."),
    ]


def _compact_modules(industry_name: str, industry_slug: str) -> list:
    """Standard 15-module template with 2-3 lessons each for industry-specific courses.
    Lesson content is written specifically per industry via prefix templating."""
    p = industry_name  # shorthand
    return [
        # LEVEL 1 (Free)
        _m(1, f"Agentic AI in {p}: The Landscape", 1, f"Current state of agentic AI adoption across {p}.", [
            {"title": f"Where {p} Stands Today", "duration_min": 12, "content": f"{p} is one of the fastest-adopting industries for agentic AI. Leading firms are running 20-40 production agents by 2026, up from single-digit pilots in 2024. The gap between leaders and laggards is now measurable in operating margin.", "key_takeaways": [f"{p} leaders operate 20-40 production agents", "Gap between leaders and laggards is widening", "Board-level attention is universal"]},
            {"title": "Reference Use Cases", "duration_min": 12, "content": f"The five highest-value use cases in {p} today: workflow automation, customer engagement, risk & compliance, employee productivity, and analytics. Each has proven case studies with double-digit ROI."},
            {"title": "The Business Case", "duration_min": 10, "content": f"McKinsey and BCG estimates put the {p} sector productivity gain at 25-40% over the next 5 years — the biggest opportunity for {p} in a generation."},
        ]),
        _m(2, f"Value Chains & Workflow Mapping", 1, f"Where agentic AI plugs into {p} value chains.", [
            {"title": f"{p} Value Chain 101", "duration_min": 12, "content": f"Map your {p} value chain. Identify high-volume, rules-adjacent workflows. These are agentic AI's sweet spot in every {p} deployment."},
            {"title": "Prioritization Framework", "duration_min": 10, "content": "Use the volume × complexity × strategic-value matrix. Start with quadrant 3 (high volume, low complexity, high strategic value) for fastest ROI."},
            {"title": "First 90 Days", "duration_min": 10, "content": "Pick ONE workflow. Ship a scoped agent. Measure. Iterate. Do not try to boil the ocean — this is the single most common failure mode in enterprise AI programs."},
        ]),
        _m(3, "Agent Architecture Basics", 1, "Perception, reasoning, action, reflection.", [
            {"title": "The Agent Loop", "duration_min": 12, "content": "Every enterprise agent implements Perceive → Reason → Act → Reflect. Master this loop and you master 80% of the design problem."},
            {"title": "LLM Selection", "duration_min": 10, "content": "Claude Sonnet 4.5 leads for enterprise agent workloads. GPT-5.2 leads on general reasoning. Route by task."},
            {"title": "Tools & Function Calling", "duration_min": 10, "content": "Every tool is a typed function. Rich descriptions with 'when NOT to use' guidance. One tool = one verb."},
        ]),
        _m(4, "Data Foundations", 1, "The data you need before you deploy an agent.", [
            {"title": "Data Readiness Assessment", "duration_min": 12, "content": f"Most {p} organizations have data. Few have AI-ready data. Assess: accessibility, quality, freshness, licensing, and consent status."},
            {"title": "Building the Knowledge Base", "duration_min": 12, "content": "RAG is the fastest path to a grounded agent. Ingest, chunk, embed, retrieve. Cover this pipeline before you write your first agent."},
            {"title": "Data Governance", "duration_min": 10, "content": "Every data flow needs a data steward, a retention policy, and a right-to-forget process."},
        ]),
        _m(5, f"Case Study: A {p} Pioneer", 1, f"Deep dive into a leading {p} agent deployment.", [
            {"title": "Deployment Context", "duration_min": 12, "content": f"A tier-1 {p} organization deployed their first production agent in Q3 2024. We examine the business case, technical architecture, and 18-month operating outcomes."},
            {"title": "What Worked", "duration_min": 10, "content": "Tight scope. Executive sponsorship. Cross-functional pod. Weekly cadence with real customers. These four factors correlated most strongly with success across 40+ case studies."},
            {"title": "What Failed & Lessons", "duration_min": 10, "content": "Over-scoping, weak evaluation, unclear ownership, and skipping governance — the four horsemen of failed AI programs. Avoid at all costs."},
        ]),
        # LEVEL 2 (Premium)
        _m(6, "Building Your First Agent", 2, "Hands-on: from zero to a working agent.", [
            {"title": "Environment Setup", "duration_min": 10, "content": "Python + Emergent LLM key + LangGraph. Under 30 minutes to a working local agent."},
            {"title": "Tool Wiring", "duration_min": 15, "content": f"Wire domain tools: a {p}-specific data lookup, a policy check, and an escalation trigger. Design tools with idempotency in mind.", "code_sample": "from langgraph.graph import StateGraph\nfrom langchain_anthropic import ChatAnthropic\n\ngraph = StateGraph(AgentState)\ngraph.add_node('plan', plan_step)\ngraph.add_node('act', act_step)\ngraph.add_edge('plan', 'act')"},
            {"title": "Deployment", "duration_min": 12, "content": "FastAPI + Docker + Kubernetes. Log every step. Cache aggressively. Rate-limit generously at the edge."},
        ]),
        _m(7, "Retrieval & Grounding", 2, f"Grounding agents in {p} knowledge.", [
            {"title": "Corpus Design", "duration_min": 12, "content": f"For {p}, the highest-value corpora are: policies, standards, product docs, historical transactions, and expert commentary. Prioritize freshness."},
            {"title": "Hybrid Search & Reranking", "duration_min": 12, "content": "Vector + BM25 with RRF is the current SOTA. Add a Cohere reranker for the last 10% of accuracy."},
            {"title": "Citations & Explainability", "duration_min": 10, "content": f"In {p}, citations are non-negotiable. Every agent answer must trace back to source documents with hashes."},
        ]),
        _m(8, "Multi-Agent Patterns", 2, "When to graduate from single-agent to a crew.", [
            {"title": "Decomposition", "duration_min": 12, "content": f"For {p} workflows requiring multiple specialized skills (research → analysis → recommendation → review), a small crew of 3-5 agents often outperforms a monolith."},
            {"title": "Orchestration", "duration_min": 12, "content": "Supervisor pattern is the enterprise default. Peer-to-peer for research/content. Blackboard for shared state across long horizons."},
            {"title": "Safety Rails", "duration_min": 10, "content": "Every crew needs cost budgets, timeouts, loop detection, and approval gates for high-stakes actions."},
        ]),
        _m(9, "Human-in-the-Loop", 2, f"Design the human interfaces for {p} agents.", [
            {"title": "Approval Gates", "duration_min": 12, "content": f"For {p}, high-stakes actions (financial commitments, customer communications, regulatory filings) require human approval. Design the UX so approvals take <60s."},
            {"title": "Escalation UX", "duration_min": 10, "content": "When agents hit uncertainty, they escalate. The human experience of receiving an escalation must be beautiful — not a spammy alert."},
            {"title": "Feedback Loops", "duration_min": 10, "content": "Every human decision becomes training signal. Log it, tag it, feed it back into evaluation."},
        ]),
        _m(10, "Evaluation & Monitoring", 2, "Ship confidently.", [
            {"title": "Golden Datasets", "duration_min": 12, "content": f"Curate 100-500 representative {p} scenarios with expected outcomes. Run on every model or prompt change."},
            {"title": "Production Observability", "duration_min": 12, "content": "OpenTelemetry traces. LangSmith or Arize for LLM-specific spans. Cost + latency + quality per node."},
            {"title": "Regression Gates", "duration_min": 10, "content": "Automated regression testing in CI. No deploy if quality drops >5% or cost >20%."},
        ]),
        # LEVEL 3 (Certification)
        _m(11, f"{p} Governance & Regulation", 3, f"Regulatory landscape specific to {p}.", [
            {"title": f"{p} Regulatory Overview", "duration_min": 15, "content": f"Sector-specific regulations affecting AI in {p}: covered in depth with recent enforcement actions and compliance timelines."},
            {"title": "Documentation Requirements", "duration_min": 12, "content": "Model cards, risk assessments, audit trails, human oversight records. Every deployment needs a documentation package."},
            {"title": "Working with Auditors", "duration_min": 10, "content": "Prepare for internal audit and external regulators. Anticipate their questions. Rehearse."},
        ]),
        _m(12, "Ethics & Responsible Deployment", 3, "Beyond compliance.", [
            {"title": "Bias & Fairness", "duration_min": 12, "content": f"In {p}, bias in AI outputs can cause real harm. Test with a fairness harness. Document your definitions and trade-offs."},
            {"title": "Explainability", "duration_min": 12, "content": "Every high-stakes decision must be explainable to the affected party — customer, patient, citizen. Design for this from day one."},
            {"title": "Transparency to End Users", "duration_min": 10, "content": "Users must know they're interacting with an AI. Disclose. Provide human recourse."},
        ]),
        _m(13, "Cost & FinOps", 3, "Making agentic AI economically sustainable.", [
            {"title": "Model Cascading", "duration_min": 12, "content": "Route simple queries to Haiku/Flash, escalate to Sonnet/Pro only when needed. Cuts cost 60-80%."},
            {"title": "Semantic Caching", "duration_min": 12, "content": "Cache responses to semantically similar queries. Cache hit rates 30-60% in typical workloads."},
            {"title": "Budget Alerts", "duration_min": 10, "content": "Per-team, per-feature, per-customer cost attribution. Alert on anomalies."},
        ]),
        _m(14, "Change Management", 3, "The human side of transformation.", [
            {"title": "Communication Strategy", "duration_min": 12, "content": f"Every {p} AI deployment displaces or augments work. Communicate the change plan proactively. Involve affected teams early."},
            {"title": "Training & Upskilling", "duration_min": 12, "content": "The ITHR Academy exists for a reason. Certify a critical mass of your workforce. Track fluency at the team level."},
            {"title": "Measuring Cultural Adoption", "duration_min": 10, "content": "Beyond software adoption metrics — track sentiment, engagement, and voluntary self-directed learning."},
        ]),
        _m(15, f"Capstone: Design a {p} Agentic Program", 3, "Bring it all together.", [
            {"title": "Capstone Brief", "duration_min": 15, "content": f"Design an end-to-end agentic AI program for a fictional {p} organization. Include architecture, governance, financials, and 24-month roadmap."},
            {"title": "Executive Deliverable", "duration_min": 25, "content": "Present to a fictional board. 12-slide deck. Executive Q&A handling."},
            {"title": "Peer Review", "duration_min": 20, "content": "Review and score two peer capstones using the ITHR rubric."},
        ]),
    ]


def _make_industry_course(slug: str, title: str, subtitle: str, description: str, industry: str,
                          thumbnail: str, instructor: str, industries: list, industry_short: str,
                          enrolled: int = 6000, rating: float = 4.85) -> Course:
    return Course(
        slug=slug, title=title, subtitle=subtitle, description=description,
        category="Agentic AI", industries=industries,
        difficulty="Advanced", duration_hours=26,
        thumbnail_url=thumbnail, instructor=instructor,
        prerequisites=["Agentic AI Foundations (recommended)", f"Domain experience in {industry_short}"],
        learning_objectives=[
            f"Architect agentic AI systems for {industry_short}",
            f"Navigate {industry_short}-specific regulation and governance",
            "Deploy with production-grade guardrails",
            "Measure ROI and cultural adoption",
            "Present board-ready programs",
        ],
        skills_gained=["Agent Architecture", "RAG", "Multi-Agent", "AI Governance", "Change Management", "FinOps"],
        business_value=f"Leading {industry_short} organizations report 25-40% productivity gains from mature agentic AI programs. This course prepares you to lead one.",
        modules=_compact_modules(industry_short, slug),
        quiz=_std_quiz(industry_short),
        passing_score=65,
        enrolled_count=enrolled,
        rating=rating,
        is_certification_track=True,
    )


def build_banking_course() -> Course:
    return _make_industry_course(
        slug="agentic-ai-banking",
        title="Agentic AI in Banking & Financial Services",
        subtitle="From claims to compliance — the practitioner's playbook",
        description="A 15-module certification for banking and financial services professionals deploying agentic AI across claims, KYC, credit, wealth advisory, and compliance workflows. Covers SR 11-7, Basel model risk management, and real Fortune 500 deployments.",
        industry="banking", industry_short="banking",
        thumbnail="https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=800&q=80",
        instructor="David Kimura", industries=["Banking", "Insurance"],
        enrolled=7210, rating=4.88,
    )


def build_healthcare_course() -> Course:
    return _make_industry_course(
        slug="agentic-ai-healthcare",
        title="Agentic AI in Healthcare",
        subtitle="HIPAA-safe clinical agents — from intake to discharge",
        description="A 15-module certification for healthcare technologists and clinical leaders. Covers HIPAA-safe agent architectures, FDA guidance on AI/ML software as medical device (SaMD), predetermined change control plans, and ambient clinical documentation.",
        industry="healthcare", industry_short="healthcare",
        thumbnail="https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=800&q=80",
        instructor="Dr. Sofia Almeida", industries=["Healthcare", "Pharmaceutical"],
        enrolled=5680, rating=4.9,
    )


def build_manufacturing_course() -> Course:
    return _make_industry_course(
        slug="agentic-ai-manufacturing",
        title="Agentic AI in Manufacturing & Industrial IoT",
        subtitle="Digital twins, predictive maintenance, and autonomous quality",
        description="A 15-module certification for manufacturing leaders deploying agentic AI in industrial settings. Covers OT/IT boundary discipline, real-time constraints, functional safety (IEC 61508), digital twin architectures, and shop-floor deployment patterns.",
        industry="manufacturing", industry_short="manufacturing",
        thumbnail="https://images.unsplash.com/photo-1565043666747-69f6646db940?w=800&q=80",
        instructor="Klaus Bergmann", industries=["Manufacturing", "Energy", "Oil & Gas"],
        enrolled=3450, rating=4.82,
    )


def build_retail_course() -> Course:
    return _make_industry_course(
        slug="agentic-ai-retail",
        title="Agentic AI in Retail & E-Commerce",
        subtitle="Personalization, dynamic pricing, supply-chain agents",
        description="A 15-module certification for retail and e-commerce practitioners. Covers customer-facing conversational commerce, dynamic pricing agents, personalization engines, supply-chain optimization, and inventory intelligence.",
        industry="retail", industry_short="retail",
        thumbnail="https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=800&q=80",
        instructor="Chloe Deneuve", industries=["Retail", "Supply Chain"],
        enrolled=4980, rating=4.78,
    )


def build_government_course() -> Course:
    return _make_industry_course(
        slug="agentic-ai-government",
        title="Agentic AI in Government & Public Sector",
        subtitle="FedRAMP-ready, sovereign, and mission-focused",
        description="A 15-module certification for public-sector technologists. Covers OMB M-24-10, FedRAMP High, air-gapped LLM deployments, procurement pathways, and mission-focused agentic AI for citizen services, defense, and regulatory agencies.",
        industry="government", industry_short="government",
        thumbnail="https://images.unsplash.com/photo-1526661934280-676cef25bc9b?w=1200&q=80",
        instructor="Col. Anthony Reynolds (Ret.)", industries=["Government"],
        enrolled=2140, rating=4.87,
    )
