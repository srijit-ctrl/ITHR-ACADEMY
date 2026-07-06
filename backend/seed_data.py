"""Seed data: 1 full course with 15 modules + 20+ catalog metadata courses."""
from models import Course, Module, Lesson, QuizQuestion


# ============================================================================
# FULL COURSE: "Agentic AI Foundations for the Enterprise"
# ============================================================================

def build_full_course() -> Course:
    modules = []

    # LEVEL 1 (FREE) - Modules 1-5
    modules.append(Module(number=1, title="What is Agentic AI?", level=1, duration_min=45, summary="Understand the fundamental shift from generative AI to autonomous agentic systems.", lessons=[
        Lesson(title="From Chatbots to Autonomous Agents", duration_min=12,
               content="Agentic AI represents a paradigm shift beyond generative AI. Where GPT-style models respond, agentic systems **act**. They perceive, reason, plan, execute, and reflect — closing the loop between intent and outcome.\n\n### The Four Pillars of Agentic AI\n1. **Perception** — ingest signals from documents, APIs, sensors, users\n2. **Reasoning** — decompose goals into sub-goals\n3. **Action** — invoke tools, APIs, and other agents\n4. **Reflection** — evaluate results and self-correct\n\nEnterprises are moving from productivity assistants to *digital coworkers* that own outcomes end-to-end.",
               key_takeaways=["Agentic AI acts, not just answers", "Loop: Perceive → Reason → Act → Reflect", "Enterprise value is outcome ownership, not task assistance"]),
        Lesson(title="The Business Case for Agentic AI", duration_min=10,
               content="McKinsey estimates $4.4T in annual productivity from generative AI. Agentic AI multiplies that by shifting from **assisted work** to **automated work**. Fortune 500 pilots in 2025 saw 30-70% cycle-time reduction in claims processing, procurement, and customer support.",
               key_takeaways=["ROI horizon: 3-9 months for well-scoped agents", "Highest value in high-volume, rules-adjacent workflows"]),
        Lesson(title="Landmark Case Studies", duration_min=12,
               content="**Klarna** replaced 700 support agents with a single AI agent handling 2.3M conversations. **Anthropic's Claude** now writes 50% of code shipped at leading startups. **Salesforce Agentforce** processes 1M+ enterprise decisions daily.",
               key_takeaways=["Support, coding, and back-office are today's sweet spots", "Human-in-the-loop remains essential for high-stakes decisions"]),
        Lesson(title="Common Misconceptions", duration_min=8,
               content="Agentic AI is not AGI. It is not fully autonomous. It is not risk-free. Successful deployments treat agents as **constrained specialists** operating inside guardrails — not as general employees.",
               key_takeaways=["Constrain scope aggressively", "Guardrails > raw capability"]),
        Lesson(title="Module Wrap-Up & Reflection", duration_min=5,
               content="You now understand what makes an AI system 'agentic' and why enterprises are investing heavily. In the next module we'll break down the anatomy of an agent.",
               key_takeaways=["Agentic ≠ generative", "Business value comes from bounded autonomy"]),
    ]))

    modules.append(Module(number=2, title="Anatomy of an AI Agent", level=1, duration_min=50, summary="Deconstruct the core components: LLM, tools, memory, planner, executor.", lessons=[
        Lesson(title="The Agent Loop", duration_min=12, content="Every agent implements a variant of the ReAct loop: **Reason → Act → Observe → Reflect**. The LLM is the reasoning engine, tools are its hands, memory is its context.",
               code_sample="while not done:\n    thought = llm.reason(state, goal)\n    action = llm.choose_tool(thought)\n    observation = tools.execute(action)\n    state = memory.update(observation)\n    done = llm.evaluate(state, goal)"),
        Lesson(title="Tools & Function Calling", duration_min=10, content="Tools are typed functions the LLM can invoke. Modern models (Claude Sonnet 4.5, GPT-5, Gemini 3) support parallel tool calls, allowing agents to fan out queries."),
        Lesson(title="Memory Systems", duration_min=10, content="Short-term (conversation buffer), episodic (session recap), semantic (vector store), procedural (learned skills). Enterprise agents need all four."),
        Lesson(title="Planners & Executors", duration_min=10, content="Planner LLM decomposes goals into a DAG of steps; executor(s) run each step. Separation of concerns dramatically improves reliability."),
        Lesson(title="Guardrails & Policies", duration_min=8, content="Input validation, output filters, PII redaction, action allowlists, and human approval gates keep agents safe in production."),
    ]))

    modules.append(Module(number=3, title="The Agent Development Stack", level=1, duration_min=55, summary="Survey LangChain, CrewAI, AutoGen, LlamaIndex, and the MCP ecosystem.", lessons=[
        Lesson(title="LangChain & LangGraph", duration_min=12, content="LangGraph brings deterministic state machines to LLM workflows. Best for auditable, resumable agents."),
        Lesson(title="CrewAI & Multi-Agent Frameworks", duration_min=10, content="CrewAI models agents as roles collaborating on shared goals. Ideal for research, content, and analysis pipelines."),
        Lesson(title="AutoGen & Conversation-First Agents", duration_min=10, content="Microsoft AutoGen frames orchestration as agent conversations. Excellent for developer tooling."),
        Lesson(title="Model Context Protocol (MCP)", duration_min=13, content="Anthropic's MCP is the emerging USB-C of AI — a standard way to expose tools, resources, and prompts to any model.",
               code_sample="# MCP tool definition\n@mcp.tool()\ndef get_customer_orders(customer_id: str) -> list:\n    '''Fetches recent orders for a given customer.'''\n    return db.orders.find({'customer_id': customer_id})"),
        Lesson(title="Choosing Your Stack", duration_min=10, content="Decision matrix: audit needs → LangGraph; role-based collab → CrewAI; developer agents → AutoGen; retrieval-heavy → LlamaIndex."),
    ]))

    modules.append(Module(number=4, title="LLMs Powering Agents", level=1, duration_min=45, summary="Compare frontier models — GPT-5, Claude Sonnet 4.5, Gemini 3, and open-weight alternatives.", lessons=[
        Lesson(title="Frontier Model Landscape 2026", duration_min=12, content="**Claude Sonnet 4.5** leads coding + long-horizon agents. **GPT-5.2** leads general reasoning. **Gemini 3 Pro** excels at multimodal + massive context (2M+ tokens)."),
        Lesson(title="Cost, Latency, Quality Trade-offs", duration_min=10, content="Route trivial calls to Haiku/Flash/mini models; escalate to Sonnet/Opus/Pro only when reasoning is needed. Multi-model routing cuts costs 60-80%."),
        Lesson(title="Open-Weight Models", duration_min=10, content="Llama 4, Mistral Large 3, and Qwen 3 close the gap for on-prem/regulated deployments."),
        Lesson(title="Fine-Tuning vs. Prompting vs. RAG", duration_min=8, content="Decision tree: **new behavior** → fine-tune; **new knowledge** → RAG; **new format** → prompt."),
        Lesson(title="Benchmarks that Actually Matter", duration_min=5, content="For enterprise agents: SWE-Bench, TAU-bench, τ-bench — not MMLU."),
    ]))

    modules.append(Module(number=5, title="Your First Agent (Hands-On)", level=1, duration_min=60, summary="Build a research agent that answers questions with citations.", lessons=[
        Lesson(title="Setting Up Your Environment", duration_min=10, content="Install the Emergent Integrations library, get an API key, spin up a Python virtualenv."),
        Lesson(title="Wiring the LLM", duration_min=12, content="Instantiate a chat client, configure the model, add a system prompt that defines the agent's role.",
               code_sample="from emergentintegrations.llm.chat import LlmChat, UserMessage\n\nchat = LlmChat(\n    api_key=os.environ['EMERGENT_LLM_KEY'],\n    session_id='research-agent-1',\n    system_message='You are a citation-first research analyst.',\n).with_model('anthropic', 'claude-sonnet-4-5-20250929')"),
        Lesson(title="Adding Web Search as a Tool", duration_min=15, content="Wrap a search API as a tool the LLM can invoke. The agent decides when to search vs answer from parametric memory."),
        Lesson(title="Adding Citation Guardrails", duration_min=13, content="Enforce that every factual claim links to a source URL. Reject responses that fail this contract."),
        Lesson(title="Deploying to Production", duration_min=10, content="Wrap in a FastAPI endpoint, add logging + rate limiting, ship behind auth."),
    ]))

    # LEVEL 2 (PREMIUM) - Modules 6-10
    modules.append(Module(number=6, title="Retrieval-Augmented Generation (RAG)", level=2, duration_min=55, summary="Ground agents in your enterprise data with modern RAG.", lessons=[
        Lesson(title="Why RAG Beats Fine-Tuning for Knowledge", duration_min=10, content="RAG is cheaper, fresher, auditable, and revocable. Fine-tuning bakes knowledge into weights — hard to update, impossible to fully forget."),
        Lesson(title="Vector Databases 101", duration_min=12, content="Compare Pinecone, Weaviate, Qdrant, pgvector. Chunking strategies. Embedding model selection (Voyage 3, Cohere Embed v4, OpenAI text-embedding-3-large)."),
        Lesson(title="Hybrid Search (Vector + BM25)", duration_min=10, content="Pure vector search misses exact matches (SKU numbers, error codes). Hybrid ranking with reciprocal rank fusion is state of the art."),
        Lesson(title="Reranking & Contextual Retrieval", duration_min=13, content="Anthropic's Contextual Retrieval + Cohere Rerank v3 push top-1 accuracy above 95% for most corpora."),
        Lesson(title="Evaluating RAG Systems", duration_min=10, content="RAGAS, TruLens, and custom LLM-as-judge harnesses. Track precision@k, faithfulness, answer relevance."),
    ]))

    modules.append(Module(number=7, title="Multi-Agent Systems", level=2, duration_min=60, summary="Design systems where multiple specialized agents collaborate.", lessons=[
        Lesson(title="When to Use Multi-Agent", duration_min=10, content="Not always! Single agents with tools often outperform. Use multi-agent when tasks decompose cleanly into parallel roles."),
        Lesson(title="Orchestration Patterns", duration_min=15, content="Supervisor pattern, peer-to-peer, hierarchical, blackboard. Each has failure modes to know."),
        Lesson(title="A2A: The Agent-to-Agent Protocol", duration_min=10, content="Google's A2A protocol standardizes cross-vendor agent interoperability. Key primitives: skills, tasks, artifacts."),
        Lesson(title="Handling Agent Conflict & Deadlock", duration_min=15, content="Timeout policies, arbiter agents, and cost budgets prevent runaway loops."),
        Lesson(title="Case Study: Automated Financial Close", duration_min=10, content="A 5-agent crew (ledger, reconciliation, variance, narrative, review) cuts month-end close from 8 days to 8 hours."),
    ]))

    modules.append(Module(number=8, title="Agent Memory & State", level=2, duration_min=50, summary="Give agents persistent, semantic, and procedural memory.", lessons=[
        Lesson(title="Memory Architecture Overview", duration_min=10, content="Working memory (context window), episodic (session summaries), semantic (vector store), procedural (fine-tuned skills)."),
        Lesson(title="Building Semantic Memory with Vector Stores", duration_min=12, content="Store observations as embeddings; retrieve top-k on each turn. Add TTL and importance weighting."),
        Lesson(title="Episodic Memory & Summarization", duration_min=10, content="Rolling summaries of past sessions preserve long-horizon context without exploding token cost."),
        Lesson(title="Procedural Memory (Skill Libraries)", duration_min=10, content="Voyager-style skill libraries let agents accumulate and reuse learned procedures."),
        Lesson(title="Privacy & Right-to-Forget", duration_min=8, content="Design memory with GDPR Article 17 in mind — memories must be locatable and deletable."),
    ]))

    modules.append(Module(number=9, title="Tool Use & Function Calling Mastery", level=2, duration_min=55, summary="Advanced patterns: parallel calls, streaming tools, retries.", lessons=[
        Lesson(title="Tool Design Principles", duration_min=12, content="One tool = one verb. Rich docstrings. Typed args. Idempotency where possible."),
        Lesson(title="Parallel Tool Execution", duration_min=10, content="Modern models call tools in parallel — design tools to be safely concurrent."),
        Lesson(title="Streaming & Long-Running Tools", duration_min=10, content="Return progress events, not just final results. Users tolerate 30s of a streaming answer; they abandon 30s of silence."),
        Lesson(title="Retries, Timeouts, and Fallbacks", duration_min=13, content="Every external call fails eventually. Build exponential backoff, circuit breakers, and graceful degradation into every tool."),
        Lesson(title="Testing Tools with LLM-as-Judge", duration_min=10, content="Use a stronger model to grade tool call quality across a fixed test suite."),
    ]))

    modules.append(Module(number=10, title="Evaluation & Observability", level=2, duration_min=55, summary="Measure agent quality in production.", lessons=[
        Lesson(title="Why Traditional Testing Fails", duration_min=10, content="Non-determinism breaks unit tests. You need statistical evaluation."),
        Lesson(title="Golden Datasets & Regression Suites", duration_min=12, content="Curate 100-500 representative tasks with expected outcomes. Run on every model or prompt change."),
        Lesson(title="LLM-as-Judge Patterns", duration_min=10, content="Use a frontier model to grade outputs on rubrics. Guard against judge bias with rotation."),
        Lesson(title="Tracing with LangSmith / Arize / Braintrust", duration_min=13, content="Distributed traces for every agent call. Latency, cost, quality per node."),
        Lesson(title="Production Feedback Loops", duration_min=10, content="Thumbs-up/down, escalation logs, and RLHF-style continuous improvement."),
    ]))

    # LEVEL 3 (ADVANCED / CERTIFICATION) - Modules 11-15
    modules.append(Module(number=11, title="Enterprise AI Governance", level=3, duration_min=60, summary="EU AI Act, NIST AI RMF, ISO 42001 — what enterprises must comply with.", lessons=[
        Lesson(title="Regulatory Landscape 2026", duration_min=12, content="EU AI Act (in force), Colorado AI Act, NYC LL 144, China Interim Measures. High-risk systems face conformity assessments."),
        Lesson(title="NIST AI Risk Management Framework", duration_min=10, content="Govern → Map → Measure → Manage. The de facto standard for US federal contractors."),
        Lesson(title="ISO/IEC 42001 AI Management Systems", duration_min=10, content="First international standard for AI management systems. Certification path for enterprises."),
        Lesson(title="Building an AI Governance Committee", duration_min=15, content="Charter, cadence, veto rights, and cross-functional composition (legal, risk, security, product, engineering)."),
        Lesson(title="Documentation Requirements", duration_min=13, content="Model cards, data sheets, risk assessments, audit logs, human oversight records."),
    ]))

    modules.append(Module(number=12, title="AI Security & Adversarial Robustness", level=3, duration_min=55, summary="Prompt injection, data exfiltration, model inversion.", lessons=[
        Lesson(title="OWASP Top 10 for LLMs", duration_min=12, content="Prompt injection, insecure output, training data poisoning, model DoS, supply chain, sensitive info disclosure, insecure plugin design, excessive agency, overreliance, model theft."),
        Lesson(title="Prompt Injection Defense-in-Depth", duration_min=13, content="Signed system prompts, dual LLM patterns, content-filtering guardrails, and executor sandboxing."),
        Lesson(title="Preventing Data Exfiltration via Tools", duration_min=10, content="Tool allowlists per persona, egress filtering, DLP integration."),
        Lesson(title="Red-Teaming AI Agents", duration_min=10, content="Structured adversarial testing. Anthropic's Responsible Scaling Policy as a template."),
        Lesson(title="Incident Response for AI Systems", duration_min=10, content="Rollback plans, kill switches, and post-mortems."),
    ]))

    modules.append(Module(number=13, title="Deploying Agents at Scale", level=3, duration_min=65, summary="Kubernetes, GPU pooling, request routing, cost control.", lessons=[
        Lesson(title="Deployment Topologies", duration_min=12, content="Managed API (OpenAI, Anthropic), self-hosted (vLLM, TGI), hybrid routing."),
        Lesson(title="LLM Gateways & Routing", duration_min=13, content="LiteLLM, Portkey, Kong AI Gateway. Semantic caching, retry, cost caps."),
        Lesson(title="Kubernetes for AI Workloads", duration_min=15, content="KServe, Kubeflow, Ray Serve. GPU node pools with autoscaling."),
        Lesson(title="Observability Stack", duration_min=10, content="OpenTelemetry + Prometheus + Grafana. Custom metrics: TTFT, tokens/sec, cost/req."),
        Lesson(title="FinOps for AI", duration_min=15, content="Cost attribution by team, feature, and customer. Budget alerts. Model cascading to control spend."),
    ]))

    modules.append(Module(number=14, title="Agentic AI in Regulated Industries", level=3, duration_min=60, summary="Healthcare, finance, government — sector-specific patterns.", lessons=[
        Lesson(title="Banking & Insurance", duration_min=15, content="Model risk management (SR 11-7, PRA SS1/23), explainability requirements, fair lending compliance."),
        Lesson(title="Healthcare & Life Sciences", duration_min=15, content="HIPAA-safe agents, FDA guidance on AI/ML SaMD, clinical validation studies."),
        Lesson(title="Government & Defense", duration_min=12, content="OMB M-24-10, FedRAMP High, air-gapped LLM deployments."),
        Lesson(title="Manufacturing & Industrial", duration_min=10, content="OT/IT boundary, real-time constraints, functional safety (IEC 61508)."),
        Lesson(title="Cross-Border Data & Sovereign AI", duration_min=8, content="Data residency, EU-US Data Privacy Framework, sovereign LLM strategies."),
    ]))

    modules.append(Module(number=15, title="Capstone: Design a Production Agentic System", level=3, duration_min=90, summary="Synthesize everything: architect, build, evaluate, and present.", lessons=[
        Lesson(title="Capstone Brief", duration_min=15, content="Choose one: customer support triage agent, financial close crew, clinical intake summarizer, or procurement negotiator. Design the full system."),
        Lesson(title="Architecture Deliverable", duration_min=20, content="Produce a C4 architecture diagram covering agents, tools, memory, gateway, observability, and governance."),
        Lesson(title="Evaluation Harness", duration_min=20, content="Build a 20-item golden set with LLM-as-judge scoring. Report precision, recall, cost."),
        Lesson(title="Risk & Governance Memo", duration_min=15, content="One-page memo covering regulatory scope, top 3 risks, and mitigations."),
        Lesson(title="Executive Presentation", duration_min=20, content="10-slide deck to a fictional CEO. Business case, architecture, ROI, roadmap."),
    ]))

    quiz = [
        QuizQuestion(question="Which of the following best distinguishes agentic AI from generative AI?",
                     type="mcq",
                     options=["Agentic AI uses larger models",
                              "Agentic AI perceives, reasons, acts, and reflects to achieve goals autonomously",
                              "Agentic AI is always multimodal",
                              "Agentic AI runs on-premises only"],
                     correct=[1],
                     explanation="Agentic AI closes the loop between intent and outcome by taking actions, not just generating text."),
        QuizQuestion(question="Which pattern is MOST appropriate for auditable, resumable enterprise workflows?",
                     options=["Free-form CrewAI", "LangGraph deterministic state machine", "Single-prompt zero-shot", "Fine-tuned monolithic model"],
                     correct=[1],
                     explanation="LangGraph's state-machine model provides deterministic transitions and resumability, critical for enterprise auditability."),
        QuizQuestion(question="What are typical components of an agent's memory system? (select all that apply)",
                     type="multi",
                     options=["Short-term / working memory", "Episodic memory (session summaries)", "Semantic memory (vector store)", "Procedural memory (skill libraries)"],
                     correct=[0, 1, 2, 3],
                     explanation="All four are recognized memory tiers in modern agent architectures."),
        QuizQuestion(question="RAG is generally preferred over fine-tuning when the goal is to add new knowledge that changes over time.",
                     type="true_false", options=["True", "False"], correct=[0],
                     explanation="RAG is cheaper, fresher, and more auditable for knowledge that evolves."),
        QuizQuestion(question="Which regulation most directly governs high-risk AI systems in the European Union?",
                     options=["GDPR", "EU AI Act", "NIS2 Directive", "Digital Services Act"], correct=[1],
                     explanation="The EU AI Act (in force since 2024) classifies and regulates AI systems by risk tier."),
        QuizQuestion(question="Which of the following is a prompt-injection defense pattern?",
                     options=["Concatenating user input directly into system prompts",
                              "Dual-LLM pattern with a privileged planner and a quarantined executor",
                              "Using only one large model",
                              "Disabling logging to reduce attack surface"], correct=[1],
                     explanation="The dual-LLM pattern isolates untrusted content from privileged reasoning."),
        QuizQuestion(question="What does MCP stand for in the agentic AI ecosystem?",
                     options=["Model Compute Platform", "Model Context Protocol", "Multi-Component Pipeline", "Managed Cloud Provider"], correct=[1],
                     explanation="Anthropic's Model Context Protocol standardizes how agents connect to tools and data."),
        QuizQuestion(question="Which evaluation technique is best suited to grading open-ended agent outputs?",
                     options=["Exact string match", "BLEU score", "LLM-as-judge with a rubric", "Regex assertions"], correct=[2],
                     explanation="LLM-as-judge with well-designed rubrics is the industry-standard technique for open-ended evaluation."),
        QuizQuestion(question="A supervisor-executor multi-agent pattern is most useful when: ",
                     options=["Tasks are trivially parallelizable and homogeneous",
                              "A central agent must decompose work and delegate to specialists",
                              "Only one tool is available",
                              "Regulatory compliance forbids delegation"], correct=[1],
                     explanation="Supervisor patterns fit well when a planner must coordinate specialized executors."),
        QuizQuestion(question="What is the minimum passing score for the Agentic AI Foundations certification?",
                     options=["50%", "60%", "65%", "80%"], correct=[2],
                     explanation="The passing score is 65% for the Foundations tier."),
        QuizQuestion(question="Which of the following are recognized best practices for tool design? (select all that apply)",
                     type="multi",
                     options=["One tool = one verb", "Rich docstrings and typed arguments", "Idempotent behavior where possible", "Silent failure on error"],
                     correct=[0, 1, 2],
                     explanation="Tools should have clear names, rich metadata, and be predictable — silent failure is an anti-pattern."),
        QuizQuestion(question="Scenario: Your enterprise agent must access customer PII across borders. What is the FIRST governance consideration?",
                     type="scenario",
                     options=["Latency optimization",
                              "Data residency & sovereign AI compliance (GDPR, DPF)",
                              "Model temperature settings",
                              "Choice of programming language"],
                     correct=[1],
                     explanation="Cross-border PII triggers residency and privacy regulations that must be addressed before any other design decision."),
    ]

    return Course(
        slug="agentic-ai-foundations",
        title="Agentic AI Foundations for the Enterprise",
        subtitle="From Chatbots to Autonomous Digital Coworkers",
        description="A comprehensive 15-module certification course designed to transform business leaders, architects, and practitioners into fluent operators of agentic AI systems. Built around real enterprise deployments across banking, healthcare, manufacturing, and public sector. Includes hands-on labs, a capstone project, and a proctor-ready certification exam.",
        category="Agentic AI",
        industries=["Banking", "Healthcare", "Manufacturing", "Retail", "Insurance", "Government"],
        difficulty="Intermediate",
        duration_hours=28,
        thumbnail_url="https://images.unsplash.com/photo-1644088379091-d574269d422f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1OTV8MHwxfHNlYXJjaHw0fHxhYnN0cmFjdCUyMGdlb21ldHJpYyUyMGRhdGElMjBhcnR8ZW58MHx8fHwxNzgzMTUyNTU1fDA&ixlib=rb-4.1.0&q=85",
        hero_url="https://images.unsplash.com/photo-1526314114033-349ef6f72220?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODl8MHwxfHNlYXJjaHwzfHxtb2Rlcm4lMjBhcmNoaXRlY3R1cmFsJTIwbGlicmFyeXxlbnwwfHx8fDE3ODMxNTI1NTV8MA&ixlib=rb-4.1.0&q=85",
        instructor="Dr. Aditi Rao & Marcus Blackwood",
        prerequisites=["Basic Python literacy (helpful, not required)", "Familiarity with cloud services (AWS/Azure/GCP)"],
        learning_objectives=[
            "Explain the agentic AI paradigm and its business case to executives",
            "Architect single-agent and multi-agent systems using modern frameworks",
            "Implement RAG, memory, and tool-use with production-grade guardrails",
            "Evaluate and monitor agents using LLM-as-judge and observability platforms",
            "Navigate the EU AI Act, NIST AI RMF, and ISO 42001 for compliance",
            "Design and defend a capstone agentic system to executive stakeholders",
        ],
        skills_gained=["Agent Architecture", "LangGraph", "CrewAI", "RAG", "Vector Databases", "Prompt Engineering", "AI Governance", "AI Security", "Evaluation Harnesses", "MCP Protocol"],
        business_value="Enterprises that certify a critical mass of AI-fluent talent achieve 2.3x higher ROI on AI initiatives (McKinsey 2025). This course accelerates that talent readiness.",
        modules=modules,
        quiz=quiz,
        passing_score=65,
        enrolled_count=18420,
        rating=4.9,
    )


# ============================================================================
# CATALOG METADATA (20+ additional courses, no lesson bodies)
# ============================================================================

CATALOG_COURSES = [
    {"slug": "generative-ai-executives", "title": "Generative AI for Executives", "subtitle": "A 90-minute strategy briefing for the C-suite", "category": "Enterprise AI", "industries": ["Professional Services", "Banking"], "difficulty": "Enterprise Leader", "duration_hours": 4, "thumbnail_url": "https://images.unsplash.com/photo-1643228995868-bf698f67d053?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1OTV8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMGdlb21ldHJpYyUyMGRhdGElMjBhcnR8ZW58MHx8fHwxNzgzMTUyNTU1fDA&ixlib=rb-4.1.0&q=85", "instructor": "Prof. Elena Vasquez", "enrolled_count": 5210, "rating": 4.8},
    {"slug": "llm-architecture-deep-dive", "title": "Large Language Model Architecture Deep Dive", "subtitle": "Transformers, MoE, and beyond", "category": "Large Language Models", "industries": ["Technology", "Research"], "difficulty": "Advanced", "duration_hours": 32, "thumbnail_url": "https://images.unsplash.com/photo-1642132652075-2b0b7cfc0f45?w=800&q=80", "instructor": "Dr. Kenji Sato", "enrolled_count": 8940, "rating": 4.9},
    {"slug": "prompt-engineering-mastery", "title": "Prompt Engineering Mastery", "subtitle": "From zero-shot to structured reasoning", "category": "Prompt Engineering", "industries": ["Media", "Professional Services"], "difficulty": "Intermediate", "duration_hours": 18, "thumbnail_url": "https://images.unsplash.com/photo-1655720031554-a929595ffad7?w=800&q=80", "instructor": "Maya Chen", "enrolled_count": 24310, "rating": 4.7},
    {"slug": "multi-agent-systems", "title": "Multi-Agent Systems in Production", "subtitle": "CrewAI, AutoGen, and A2A protocol", "category": "Multi-Agent Systems", "industries": ["Banking", "Logistics"], "difficulty": "Advanced", "duration_hours": 26, "thumbnail_url": "https://images.unsplash.com/photo-1673526759327-2f7b9a9b0e14?w=800&q=80", "instructor": "Rahul Bansal", "enrolled_count": 6870, "rating": 4.85},
    {"slug": "rag-enterprise", "title": "Retrieval-Augmented Generation for the Enterprise", "subtitle": "Vector DBs, hybrid search, and reranking", "category": "Retrieval Augmented Generation", "industries": ["Banking", "Healthcare", "Insurance"], "difficulty": "Intermediate", "duration_hours": 22, "thumbnail_url": "https://images.unsplash.com/photo-1592305863326-6c2e6d5c4b8b?w=800&q=80", "instructor": "Dr. Priya Nair", "enrolled_count": 12450, "rating": 4.8},
    {"slug": "ai-governance-compliance", "title": "AI Governance, Risk & Compliance", "subtitle": "EU AI Act, NIST AI RMF, ISO 42001", "category": "AI Governance", "industries": ["Banking", "Insurance", "Government"], "difficulty": "Enterprise Leader", "duration_hours": 20, "thumbnail_url": "https://images.pexels.com/photos/7108207/pexels-photo-7108207.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940", "instructor": "Judith Ackerman, JD", "enrolled_count": 4520, "rating": 4.9},
    {"slug": "ai-security-red-team", "title": "AI Security & Red Teaming", "subtitle": "Prompt injection, jailbreaks, and defense-in-depth", "category": "AI Security", "industries": ["Banking", "Government", "Technology"], "difficulty": "Advanced", "duration_hours": 24, "thumbnail_url": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800&q=80", "instructor": "Aleksei Volkov", "enrolled_count": 3890, "rating": 4.85},
    {"slug": "agentic-ai-banking", "title": "Agentic AI in Banking & Financial Services", "subtitle": "From claims to compliance", "category": "Agentic AI", "industries": ["Banking", "Insurance"], "difficulty": "Advanced", "duration_hours": 30, "thumbnail_url": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=800&q=80", "instructor": "David Kimura", "enrolled_count": 7210, "rating": 4.88},
    {"slug": "agentic-ai-healthcare", "title": "Agentic AI in Healthcare", "subtitle": "HIPAA-safe clinical agents", "category": "Agentic AI", "industries": ["Healthcare", "Pharmaceutical"], "difficulty": "Advanced", "duration_hours": 28, "thumbnail_url": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=800&q=80", "instructor": "Dr. Sofia Almeida", "enrolled_count": 5680, "rating": 4.9},
    {"slug": "agentic-ai-manufacturing", "title": "Agentic AI in Manufacturing & Industrial IoT", "subtitle": "Digital twins and predictive maintenance agents", "category": "Agentic AI", "industries": ["Manufacturing", "Energy", "Oil & Gas"], "difficulty": "Advanced", "duration_hours": 26, "thumbnail_url": "https://images.unsplash.com/photo-1565043666747-69f6646db940?w=800&q=80", "instructor": "Klaus Bergmann", "enrolled_count": 3450, "rating": 4.82},
    {"slug": "agentic-ai-retail", "title": "Agentic AI in Retail & E-Commerce", "subtitle": "Personalization, pricing, and supply chain agents", "category": "Agentic AI", "industries": ["Retail", "Supply Chain"], "difficulty": "Intermediate", "duration_hours": 22, "thumbnail_url": "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=800&q=80", "instructor": "Chloe Deneuve", "enrolled_count": 4980, "rating": 4.78},
    {"slug": "agentic-ai-hospitality", "title": "Agentic AI in Hospitality & Travel", "subtitle": "Concierge agents and dynamic pricing", "category": "Agentic AI", "industries": ["Hospitality", "Travel"], "difficulty": "Intermediate", "duration_hours": 18, "thumbnail_url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&q=80", "instructor": "Isabella Rossi", "enrolled_count": 2670, "rating": 4.75},
    {"slug": "ai-product-management", "title": "AI Product Management", "subtitle": "Ship AI products that customers love", "category": "AI Product Management", "industries": ["Technology", "Professional Services"], "difficulty": "Intermediate", "duration_hours": 20, "thumbnail_url": "https://images.unsplash.com/photo-1552664730-d307ca884978?w=800&q=80", "instructor": "James Okonkwo", "enrolled_count": 9820, "rating": 4.86},
    {"slug": "ai-architecture-enterprise", "title": "Enterprise AI Architecture", "subtitle": "Reference architectures for Fortune 500", "category": "AI Architecture", "industries": ["Banking", "Insurance", "Telecommunications"], "difficulty": "Architect", "duration_hours": 32, "thumbnail_url": "https://images.pexels.com/photos/31656148/pexels-photo-31656148.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940", "instructor": "Ana Martínez", "enrolled_count": 3210, "rating": 4.92},
    {"slug": "vector-databases", "title": "Vector Databases & Knowledge Graphs", "subtitle": "Pinecone, Weaviate, Qdrant, Neo4j", "category": "Vector Databases", "industries": ["Technology"], "difficulty": "Intermediate", "duration_hours": 16, "thumbnail_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80", "instructor": "Marcus Blackwood", "enrolled_count": 6540, "rating": 4.8},
    {"slug": "fine-tuning-llms", "title": "Fine-Tuning & Model Adaptation", "subtitle": "LoRA, QLoRA, and RLHF at scale", "category": "Fine Tuning", "industries": ["Technology", "Research"], "difficulty": "Advanced", "duration_hours": 24, "thumbnail_url": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800&q=80", "instructor": "Dr. Chen Wei", "enrolled_count": 4120, "rating": 4.87},
    {"slug": "ai-devops-mlops", "title": "AI DevOps & MLOps", "subtitle": "CI/CD for LLM applications", "category": "AI DevOps", "industries": ["Technology", "Telecommunications"], "difficulty": "Advanced", "duration_hours": 22, "thumbnail_url": "https://images.unsplash.com/photo-1667372393119-3d4c48d07fc9?w=800&q=80", "instructor": "Fatima Al-Rashid", "enrolled_count": 5340, "rating": 4.83},
    {"slug": "ai-change-management", "title": "AI Change Management for Leaders", "subtitle": "Leading AI transformation across the workforce", "category": "AI Change Management", "industries": ["Professional Services", "Manufacturing", "Retail"], "difficulty": "CXO", "duration_hours": 12, "thumbnail_url": "https://images.pexels.com/photos/7698712/pexels-photo-7698712.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940", "instructor": "Lord William Ashcroft", "enrolled_count": 2890, "rating": 4.91},
    {"slug": "responsible-ai", "title": "Responsible AI & Ethics", "subtitle": "Bias, fairness, and accountability", "category": "Responsible AI", "industries": ["Government", "Healthcare", "Education"], "difficulty": "Intermediate", "duration_hours": 16, "thumbnail_url": "https://images.unsplash.com/photo-1573164713988-8665fc963095?w=800&q=80", "instructor": "Dr. Amara Okafor", "enrolled_count": 7680, "rating": 4.86},
    {"slug": "chief-ai-officer-track", "title": "Chief AI Officer Executive Track", "subtitle": "The definitive CAIO leadership program", "category": "AI Strategy", "industries": ["Banking", "Insurance", "Manufacturing", "Retail"], "difficulty": "CXO", "duration_hours": 40, "thumbnail_url": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=800&q=80", "instructor": "Multiple Faculty", "enrolled_count": 1240, "rating": 4.95},
    {"slug": "mcp-a2a-protocols", "title": "MCP & A2A Protocol Deep Dive", "subtitle": "Standards for interoperable agents", "category": "MCP", "industries": ["Technology"], "difficulty": "Advanced", "duration_hours": 14, "thumbnail_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80", "instructor": "Marcus Blackwood", "enrolled_count": 3420, "rating": 4.88},
    {"slug": "ai-observability", "title": "AI Observability & Evaluation", "subtitle": "LangSmith, Arize, and evaluation harnesses", "category": "AI Observability", "industries": ["Technology"], "difficulty": "Advanced", "duration_hours": 18, "thumbnail_url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&q=80", "instructor": "Nathan Reilly", "enrolled_count": 4560, "rating": 4.84},
    # ---- HR & People Operations track (iter-32) ----
    {"slug": "agentic-ai-talent-acquisition", "title": "Agentic AI for Talent Acquisition — Niche & Passive Skill Hunting", "subtitle": "Ship a legal, ethical, board-defensible sourcing agent for hard roles", "category": "Enterprise AI", "industries": ["Professional Services", "Technology", "Banking", "Healthcare", "HR & People Operations"], "difficulty": "Advanced", "duration_hours": 28, "thumbnail_url": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=800&q=80", "instructor": "Ravi Menon", "enrolled_count": 1240, "rating": 4.91},
    {"slug": "agentic-ai-performance-management", "title": "AI-Augmented Performance Management", "subtitle": "From annual reviews to continuous, evidence-based coaching", "category": "Enterprise AI", "industries": ["HR & People Operations", "Professional Services", "Technology"], "difficulty": "Intermediate", "duration_hours": 18, "thumbnail_url": "https://images.unsplash.com/photo-1552664730-d307ca884978?w=800&q=80", "instructor": "Dr. Ayesha Karim", "enrolled_count": 780, "rating": 4.82},
    {"slug": "agentic-ai-succession-planning", "title": "Succession Planning with Predictive Talent Intelligence", "subtitle": "Model the leadership bench 24 months before you need it", "category": "Enterprise AI", "industries": ["HR & People Operations", "Banking", "Manufacturing", "Professional Services"], "difficulty": "Advanced", "duration_hours": 22, "thumbnail_url": "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=800&q=80", "instructor": "Mira Sundaram", "enrolled_count": 640, "rating": 4.89},
    {"slug": "agentic-ai-learning-development", "title": "Agentic AI for L&D and Skills-Gap Closure", "subtitle": "Adaptive learning paths, cohort agents, and skills-inventory intelligence", "category": "Enterprise AI", "industries": ["HR & People Operations", "Education", "Technology"], "difficulty": "Intermediate", "duration_hours": 20, "thumbnail_url": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=800&q=80", "instructor": "Dr. Fenwick Cole", "enrolled_count": 920, "rating": 4.86},
]


INDUSTRIES = [
    "Manufacturing", "Healthcare", "Hospitality", "Retail", "Real Estate", "Education",
    "Construction", "Government", "Banking", "Insurance", "Logistics", "Supply Chain",
    "Oil & Gas", "Telecommunications", "Energy", "Pharmaceutical", "Aviation", "Travel",
    "Media", "Professional Services", "Technology", "Research", "HR & People Operations",
]

CATEGORIES = [
    "AI Fundamentals", "Generative AI", "Large Language Models", "Prompt Engineering",
    "Agentic AI", "AI Agents", "Multi-Agent Systems", "Retrieval Augmented Generation",
    "MCP", "AI Governance", "Responsible AI", "AI Security", "Enterprise AI",
    "AI Strategy", "AI Product Management", "AI Architecture", "Vector Databases",
    "Fine Tuning", "AI DevOps", "AI Observability", "AI Change Management",
]

CERTIFICATION_PATHS = [
    {"slug": "agentic-ai-foundation", "title": "Agentic AI Foundation", "level": 1, "description": "Entry-level credential for professionals beginning their agentic AI journey."},
    {"slug": "agentic-ai-practitioner", "title": "Agentic AI Practitioner", "level": 2, "description": "Hands-on credential for those building production agents."},
    {"slug": "agentic-ai-professional", "title": "Agentic AI Professional", "level": 3, "description": "Advanced credential requiring capstone project."},
    {"slug": "agentic-ai-specialist", "title": "Agentic AI Specialist", "level": 4, "description": "Domain-focused credential (banking, healthcare, etc.)."},
    {"slug": "agentic-ai-expert", "title": "Agentic AI Expert", "level": 5, "description": "Senior technical credential."},
    {"slug": "agentic-ai-architect", "title": "Agentic AI Architect", "level": 6, "description": "System design credential."},
    {"slug": "enterprise-ai-leader", "title": "Enterprise AI Leader", "level": 7, "description": "Executive credential for AI transformation leaders."},
    {"slug": "chief-ai-officer", "title": "Chief AI Officer Track", "level": 8, "description": "The definitive CAIO credential."},
]
