"""4 additional full courses to broaden the certification catalog."""
from models import Course, Module, Lesson, QuizQuestion


def _module(number, title, level, summary, lessons_data, duration_min=45):
    return Module(
        number=number, title=title, level=level, summary=summary, duration_min=duration_min,
        lessons=[Lesson(**l) for l in lessons_data],
    )


# ============================================================================
# COURSE 2 — Prompt Engineering Mastery
# ============================================================================
def build_prompt_engineering_course() -> Course:
    modules = [
        _module(1, "Foundations of Prompting", 1, "Why prompt engineering is a durable, high-leverage skill.", [
            {"title": "Prompting as a Discipline", "duration_min": 10, "content": "Prompt engineering is the craft of coaxing reliable, useful outputs from probabilistic systems. It is not going away — even as models improve, the value of a good prompt compounds. In enterprise settings, the same well-designed prompt saves thousands of hours across teams.", "key_takeaways": ["Prompting is a durable skill", "Compounds across teams", "Higher leverage than most 'AI training'"]},
            {"title": "Anatomy of a Prompt", "duration_min": 12, "content": "Every high-quality prompt has: (1) role, (2) task, (3) context, (4) format, (5) constraints, (6) examples. Master these six primitives and 80% of your work is done.", "key_takeaways": ["Six primitives cover most cases", "Role + task = the backbone", "Format constraints reduce hallucination"]},
            {"title": "Zero-Shot vs Few-Shot vs Chain-of-Thought", "duration_min": 10, "content": "Zero-shot: ask directly. Few-shot: provide 2-5 examples. Chain-of-thought: ask the model to reason step-by-step. Each has ideal use cases and cost profiles."},
        ]),
        _module(2, "Structured Output", 1, "Getting reliable JSON, tables, and schemas from LLMs.", [
            {"title": "Why Structure Matters", "duration_min": 10, "content": "Free-text output is a debugging nightmare in production. Structured output (JSON with a schema) turns LLMs into reliable API endpoints. Modern models support native structured mode via tools like OpenAI's `response_format`, Anthropic's tool calling, and Gemini's JSON mode."},
            {"title": "Schema Design Patterns", "duration_min": 12, "content": "Use Pydantic or JSON Schema. Keep schemas flat, name fields verbatim, add descriptions for every field. Enum types dramatically improve reliability."},
            {"title": "Handling Malformed Output", "duration_min": 8, "content": "Even structured mode fails. Always wrap parses in try/except, log the raw response, and retry with a corrective prompt."},
        ]),
        _module(3, "Role & Persona Design", 1, "Crafting effective system prompts.", [
            {"title": "The System Prompt is Half the Battle", "duration_min": 12, "content": "System prompts define the model's operating persona. A weak system prompt shows through in every user interaction. Invest 10x more time on the system prompt than any single user prompt."},
            {"title": "Persona Prompting Patterns", "duration_min": 10, "content": "'You are a Y professional who specializes in Z' outperforms generic prompts by 15-30% on domain benchmarks. Add authority anchors (years of experience, credentials) and boundaries (what the persona does NOT do)."},
            {"title": "Multi-Persona Prompts", "duration_min": 10, "content": "For complex tasks, define multiple internal personas the model rotates through: analyst, critic, synthesizer. This is the poor-person's multi-agent."},
        ]),
        _module(4, "Reasoning & Chain-of-Thought", 1, "Getting models to think before they speak.", [
            {"title": "CoT Fundamentals", "duration_min": 10, "content": "The classic 'Let's think step by step' pattern unlocks reasoning for many models. Modern reasoning models (o1, Claude 3.5 with extended thinking, Gemini Deep Think) do this internally."},
            {"title": "Self-Consistency", "duration_min": 12, "content": "Sample multiple CoT paths and take the majority vote. Costs 5-10x but dramatically improves accuracy on hard problems."},
            {"title": "Reflection & Self-Critique", "duration_min": 10, "content": "Ask the model to critique its own answer, then revise. Simple pattern; often better than reasoning models for cost-sensitive workloads."},
        ]),
        _module(5, "Testing & Evaluation Basics", 1, "Never ship a prompt without a test set.", [
            {"title": "The Golden Dataset", "duration_min": 12, "content": "Curate 50-200 representative inputs with expected outputs. Every prompt change gets scored against this dataset. Without one, you are shipping blind."},
            {"title": "Automated Grading", "duration_min": 10, "content": "Use LLM-as-judge to grade outputs on your rubric. Rotate judges (e.g., GPT-5 judging Claude outputs and vice versa) to guard against bias."},
            {"title": "Regression Prevention", "duration_min": 8, "content": "Wire grading into CI. Fail the build if any test drops more than 5% from baseline."},
        ]),
        # LEVEL 2 - Premium
        _module(6, "Advanced Structured Prompting", 2, "XML tags, delimiters, and format precision.", [
            {"title": "Why XML-Style Tags Win", "duration_min": 12, "content": "Claude in particular responds excellently to XML-style delimiters. `<instructions>...</instructions>` and `<context>...</context>` reduce ambiguity between different prompt sections.", "code_sample": "<role>You are a senior tax analyst.</role>\n<instructions>Compute the effective tax rate.</instructions>\n<data>{invoice_json}</data>\n<output_format>JSON with fields: rate, breakdown, notes</output_format>"},
            {"title": "Prompt Caching for Long Prompts", "duration_min": 10, "content": "Anthropic and OpenAI now support prompt caching — mark the static portion of your prompt as cacheable and pay only for the delta on subsequent calls. Can reduce cost by 90% on prompts with large context."},
            {"title": "Response Prefill Techniques", "duration_min": 10, "content": "Prefilling the assistant's response with '{' or '```json' locks the model into your desired format. Powerful, under-used technique."},
        ]),
        _module(7, "Prompting for Agents", 2, "Tool-use, function-calling, and multi-turn.", [
            {"title": "Tool Descriptions Are Prompts Too", "duration_min": 12, "content": "Every tool description in a function-calling schema is a mini-prompt. Rich descriptions of when to use (and not use) each tool improve tool-selection accuracy by 20-40%."},
            {"title": "Multi-Turn State Prompts", "duration_min": 10, "content": "Design the system prompt so the model always knows: current goal, past actions, available tools, and success criteria. State discipline prevents wandering agents."},
            {"title": "Guarding Against Over-Confidence", "duration_min": 10, "content": "Prompt agents to say 'I don't know' or 'I need to call a tool' rather than fabricate. Add explicit uncertainty phrases: 'If unsure, defer.'"},
        ]),
        _module(8, "Retrieval-Aware Prompting", 2, "Making RAG prompts robust.", [
            {"title": "Grounding Instructions", "duration_min": 12, "content": "Explicitly tell the model to only use provided context. 'Answer strictly from the context below. If the answer is not in the context, say \"I don't know\".'"},
            {"title": "Citation Enforcement", "duration_min": 10, "content": "Require citations for every factual claim. Post-process to verify citations exist and match. This one pattern eliminates 80% of hallucination complaints."},
            {"title": "Handling Conflicting Sources", "duration_min": 10, "content": "When retrieval returns contradictory information, prompt the model to name the conflict rather than pick a side silently."},
        ]),
        _module(9, "Prompt Injection & Defense", 2, "Attackers manipulate prompts too.", [
            {"title": "Direct vs Indirect Injection", "duration_min": 12, "content": "Direct: attacker types 'ignore previous instructions.' Indirect: attacker plants instructions in a document the agent later reads. Indirect is much harder to defend against."},
            {"title": "Defense Patterns", "duration_min": 12, "content": "Signed system prompts, quarantined executor pattern, output filters, allow-lists for tool actions. Belt AND suspenders."},
            {"title": "Testing for Robustness", "duration_min": 8, "content": "Maintain an adversarial test set of 30-50 known injection payloads. Test every prompt change against it."},
        ]),
        _module(10, "Prompt Versioning & Operations", 2, "Prompts are code. Treat them that way.", [
            {"title": "Prompt Registries", "duration_min": 10, "content": "LangSmith, PromptLayer, or a homegrown git-based registry. Every prompt has a version, an owner, and a changelog."},
            {"title": "A/B Testing Prompts", "duration_min": 12, "content": "Route 10% of production traffic to a challenger prompt and compare quality + cost + latency in real conditions."},
            {"title": "Rollback Discipline", "duration_min": 8, "content": "Every prompt change must be revertible in <5 minutes. Feature-flag prompts the same way you feature-flag code."},
        ]),
        # LEVEL 3 - Advanced/Certification
        _module(11, "Domain-Specific Prompting: Finance", 3, "Prompting patterns for banking and insurance.", [
            {"title": "Reasoning About Numbers", "duration_min": 12, "content": "LLMs are notoriously fragile with arithmetic. Always offload calculations to code interpreter tools or explicit CoT with step-by-step numeric reasoning."},
            {"title": "Compliance-Aware Prompts", "duration_min": 12, "content": "Every financial prompt should include: 'Do not make investment recommendations,' 'Cite authoritative sources,' 'Flag any regulatory concerns.'"},
            {"title": "Case Study: KYC Automation", "duration_min": 10, "content": "A tier-1 bank cut KYC processing from 40 minutes to 3 minutes using structured prompts + human review. Not full automation — augmentation."},
        ]),
        _module(12, "Domain-Specific Prompting: Healthcare", 3, "Clinical safety-first patterns.", [
            {"title": "The Safety Prefix Pattern", "duration_min": 10, "content": "Every clinical prompt starts with: 'You are assisting a licensed clinician. Do not provide direct medical advice to patients. Cite clinical guidelines by name.'"},
            {"title": "Structured Clinical Extraction", "duration_min": 15, "content": "Extract to SNOMED-CT or FHIR structures, not free text. Reduces downstream errors by 10x."},
            {"title": "Documentation Auto-Generation", "duration_min": 10, "content": "Ambient scribes are the killer app. Prompt patterns for SOAP notes, discharge summaries, and referral letters."},
        ]),
        _module(13, "Prompt Optimization Automation", 3, "Let AI optimize your prompts.", [
            {"title": "DSPy & Automated Prompt Search", "duration_min": 15, "content": "Stanford's DSPy framework treats prompts as parameters and optimizes them via gradient-free search. Often finds prompts humans wouldn't write."},
            {"title": "Meta-Prompting", "duration_min": 12, "content": "Use one LLM to write and iterate on prompts for another LLM. Recursive self-improvement of prompts."},
            {"title": "When to Automate vs. Handcraft", "duration_min": 10, "content": "Automate for well-defined tasks with clear metrics. Handcraft for high-stakes, low-volume, or novel domains."},
        ]),
        _module(14, "Multilingual & Cross-Cultural Prompting", 3, "One prompt to rule 47 markets.", [
            {"title": "Non-English Performance Gaps", "duration_min": 12, "content": "Most frontier models are English-centric. Non-English performance can drop 15-40%. Test in every language you deploy."},
            {"title": "Cultural Localization", "duration_min": 10, "content": "'Polite tone' means different things in Japan vs. Germany vs. Brazil. Localize the persona, not just the words."},
            {"title": "Translation-in-the-Loop", "duration_min": 10, "content": "Sometimes: translate input to English → process → translate output back. Costs more but improves consistency."},
        ]),
        _module(15, "Capstone: Design an Enterprise Prompt Library", 3, "Bring it all together.", [
            {"title": "Capstone Brief", "duration_min": 15, "content": "Design a versioned prompt library for a fictional insurance carrier: 20 prompts covering underwriting, claims, and customer support. Include tests and governance."},
            {"title": "Architecture Deliverable", "duration_min": 25, "content": "Document: taxonomy, versioning strategy, testing protocol, incident response, and ownership model."},
            {"title": "Executive Presentation", "duration_min": 20, "content": "Present to fictional CIO. Business case, guardrails, roadmap, ROI."},
        ]),
    ]

    quiz = [
        QuizQuestion(question="Which is NOT one of the six prompt primitives?", options=["Role", "Task", "Format", "Model temperature"], correct=[3], explanation="Model temperature is a decoding parameter, not a prompt primitive."),
        QuizQuestion(question="Prompt caching primarily reduces:", options=["Latency and cost for repeated static prompts", "Model accuracy", "Hallucination rate", "Context window size"], correct=[0], explanation="Prompt caching lets you pay only for the delta on subsequent calls, reducing cost and latency."),
        QuizQuestion(question="Which pattern is most effective for hallucination reduction in RAG?", options=["Higher temperature", "Enforced citations + 'answer only from context' instruction", "Longer prompts", "Random sampling"], correct=[1], explanation="Grounding + citations is the strongest defense against RAG hallucinations."),
        QuizQuestion(question="What is 'indirect prompt injection'?", type="mcq", options=["When an attacker types 'ignore previous instructions'", "When an attacker plants instructions in a document the agent later reads", "When the model prompts itself", "When the model rate-limits"], correct=[1], explanation="Indirect injection embeds attacker payloads in data sources the model consumes."),
        QuizQuestion(question="Self-consistency involves:", options=["Using the same prompt every time", "Sampling multiple CoT paths and taking the majority answer", "Fine-tuning the model", "Using a smaller model"], correct=[1], explanation="Self-consistency samples multiple reasoning paths and votes."),
        QuizQuestion(question="Prompt libraries should include (select all):", type="multi", options=["Version numbers", "Owners", "Test datasets", "Changelogs"], correct=[0, 1, 2, 3], explanation="All four are essential."),
        QuizQuestion(question="LLMs are notoriously fragile with:", options=["Text summarization", "Multi-step arithmetic without tools", "Style transfer", "Tone matching"], correct=[1], explanation="Numeric reasoning without a code tool remains a weakness."),
        QuizQuestion(question="The passing score for this certification is:", options=["50%", "60%", "65%", "75%"], correct=[2], explanation="65% across the ITHR certification catalog."),
        QuizQuestion(question="Which is a valid defense against prompt injection?", options=["Concatenating user input into system prompt", "Signed system prompts + quarantined executor pattern", "Ignoring the problem", "Disabling logs"], correct=[1], explanation="Defense-in-depth with signed prompts and executor isolation."),
        QuizQuestion(question="DSPy's core value proposition is:", options=["A new UI for prompts", "Treating prompts as parameters and optimizing them automatically", "A cloud host for prompts", "A model provider"], correct=[1], explanation="DSPy optimizes prompt+program parameters via gradient-free search."),
        QuizQuestion(question="Multilingual deployment best practices include (select all):", type="multi", options=["Test in every deployed language", "Localize the persona, not just words", "Consider translation-in-the-loop", "Assume English performance transfers"], correct=[0, 1, 2], explanation="Never assume English performance transfers directly."),
        QuizQuestion(question="Which prompt element MOST directly reduces hallucination in agent tool use?", type="scenario", options=["Longer system prompt", "Rich tool descriptions with 'when NOT to use' guidance", "Higher temperature", "Removing all tools"], correct=[1], explanation="Rich, negative-inclusive tool descriptions dramatically improve tool-selection accuracy."),
    ]

    return Course(
        slug="prompt-engineering-mastery",
        title="Prompt Engineering Mastery",
        subtitle="From zero-shot to structured reasoning",
        description="A rigorous 15-module program on the durable, high-leverage craft of prompting frontier LLMs. Covers structured output, agentic prompting, RAG grounding, injection defense, prompt operations, and domain-specific patterns for finance and healthcare. Includes a capstone project building an enterprise prompt library.",
        category="Prompt Engineering",
        industries=["Banking", "Healthcare", "Insurance", "Retail", "Professional Services", "Media"],
        difficulty="Intermediate",
        duration_hours=22,
        thumbnail_url="https://images.unsplash.com/photo-1655720031554-a929595ffad7?w=800&q=80",
        instructor="Maya Chen",
        prerequisites=["Basic Python literacy", "Prior exposure to any LLM API"],
        learning_objectives=[
            "Design robust prompts across zero-shot, few-shot, and chain-of-thought paradigms",
            "Ship structured JSON outputs reliably at scale",
            "Defend against direct and indirect prompt injection",
            "Operate a versioned enterprise prompt library",
            "Optimize prompts automatically with DSPy and meta-prompting",
        ],
        skills_gained=["Structured Prompting", "Chain-of-Thought", "Prompt Caching", "Injection Defense", "Prompt Operations", "DSPy", "Domain Prompt Design"],
        business_value="A well-engineered enterprise prompt library saves 200-400 engineering hours per business unit annually and cuts LLM cost by 30-60%.",
        modules=modules,
        quiz=quiz,
        passing_score=65,
        enrolled_count=24310,
        rating=4.85,
    )


# ============================================================================
# COURSE 3 — RAG for the Enterprise
# ============================================================================
def build_rag_course() -> Course:
    modules = [
        _module(1, "Why RAG?", 1, "The case for retrieval-augmented generation.", [
            {"title": "RAG vs. Fine-Tuning vs. Pure Prompting", "duration_min": 12, "content": "Decision tree: **new knowledge that changes over time** → RAG. **New skill or format** → fine-tune. **One-off task** → pure prompting. Most enterprise use cases sit squarely in RAG territory."},
            {"title": "The Business Case for RAG", "duration_min": 10, "content": "RAG cuts hallucinations by 60-80%, produces verifiable citations, adapts to fresh data without retraining, and is fully revocable — critical for GDPR right-to-forget."},
            {"title": "RAG Failure Modes", "duration_min": 8, "content": "Bad chunking, weak retrieval, context stuffing, no reranking, missing citations. Every one of these will bite you in production."},
        ]),
        _module(2, "Text Embeddings", 1, "How text becomes a vector.", [
            {"title": "Embedding Models 101", "duration_min": 12, "content": "Modern top-tier embeddings: Voyage 3, Cohere Embed v4, OpenAI text-embedding-3-large. Dimension counts range 512-3072. Higher isn't always better."},
            {"title": "Embedding Cost & Quality Trade-offs", "duration_min": 10, "content": "Voyage 3 lite gives 90% of the quality at 20% of the cost. Route embeddings by importance tier."},
            {"title": "Domain Adaptation", "duration_min": 10, "content": "Fine-tune embeddings on your corpus for 5-15% retrieval improvement. Cheaper than fine-tuning the generator."},
        ]),
        _module(3, "Chunking Strategy", 1, "Where the retrieval game is won or lost.", [
            {"title": "Chunk Size Trade-offs", "duration_min": 12, "content": "Small chunks: precise retrieval, weak context. Large chunks: rich context, imprecise retrieval. Most enterprise RAG runs 400-800 tokens with 10-15% overlap."},
            {"title": "Semantic Chunking", "duration_min": 12, "content": "Chunk by semantic boundaries (paragraphs, sentences with similarity thresholds) rather than fixed token counts. Consistently improves retrieval quality."},
            {"title": "Structured Document Chunking", "duration_min": 10, "content": "Legal contracts, financial reports, and technical specs have inherent structure. Chunk along these seams (sections, clauses, tables). Preserve metadata: page, section, source."},
        ]),
        _module(4, "Vector Databases", 1, "Storing and searching at scale.", [
            {"title": "The Vector DB Landscape", "duration_min": 12, "content": "Pinecone (managed), Weaviate (open + managed), Qdrant (open), pgvector (Postgres extension), Chroma (dev-friendly). Choice depends on scale, ops preference, and existing infra."},
            {"title": "Indexing Strategies", "duration_min": 12, "content": "HNSW for balanced perf/quality, IVF for large scale, exhaustive for small corpora. Understand recall@k trade-offs."},
            {"title": "Metadata Filtering", "duration_min": 8, "content": "Never search the whole vector space when you can pre-filter by metadata (tenant, doc_type, date). Massive perf win."},
        ]),
        _module(5, "First Working RAG (Hands-On)", 1, "Ship your first pipeline.", [
            {"title": "Environment Setup", "duration_min": 10, "content": "Python + LangChain + Chroma + OpenAI. Under 30 minutes to a working local RAG."},
            {"title": "Ingest → Chunk → Embed → Store", "duration_min": 15, "content": "The ingestion pipeline. Every enterprise RAG has one — most are janky. Get the fundamentals right.", "code_sample": "from langchain.text_splitter import RecursiveCharacterTextSplitter\nsplitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)\nchunks = splitter.split_documents(docs)"},
            {"title": "Query → Retrieve → Generate", "duration_min": 12, "content": "The runtime path. Cache aggressively. Log every retrieval for debugging."},
        ]),
        # LEVEL 2
        _module(6, "Hybrid Search (Vector + BM25)", 2, "Beyond pure semantic search.", [
            {"title": "Why Pure Vector Search Fails", "duration_min": 10, "content": "SKU numbers, error codes, and exact phrases are murder for pure vector search. Semantic similarity misses them entirely."},
            {"title": "BM25 Fundamentals", "duration_min": 12, "content": "Classical lexical scoring. Elasticsearch, OpenSearch, and Postgres full-text indexes all support it. Fast and exact."},
            {"title": "Reciprocal Rank Fusion (RRF)", "duration_min": 12, "content": "State-of-the-art way to combine vector and BM25 rankings. Simple math, big quality gain. All modern RAG systems use RRF."},
        ]),
        _module(7, "Reranking & Contextual Retrieval", 2, "Squeezing every drop of quality.", [
            {"title": "Rerankers 101", "duration_min": 12, "content": "Cohere Rerank v3, Voyage rerank-2. Take top 25-50 candidates, rerank to top 5. Cross-encoder attention makes rerankers 10x more accurate than pure embeddings."},
            {"title": "Anthropic's Contextual Retrieval", "duration_min": 15, "content": "Prepend an LLM-generated context summary to each chunk before embedding. Reduces failed retrievals by 49% in Anthropic's benchmarks."},
            {"title": "Combining Both", "duration_min": 8, "content": "Contextual embeddings + hybrid + reranker = the current SOTA stack. Push top-1 accuracy above 95% on most corpora."},
        ]),
        _module(8, "Advanced Retrieval Patterns", 2, "Multi-hop, HyDE, and query decomposition.", [
            {"title": "HyDE — Hypothetical Document Embeddings", "duration_min": 12, "content": "Generate a hypothetical answer with the LLM first, then use ITS embedding to search. Works well for open-ended queries."},
            {"title": "Multi-Hop RAG", "duration_min": 12, "content": "For questions requiring multiple retrievals ('What was Company X's revenue in the year they acquired Y?'), decompose the query and retrieve iteratively."},
            {"title": "Query Rewriting", "duration_min": 10, "content": "Users type sloppy queries. Rewrite with the LLM before retrieval: expand acronyms, add context, split compound questions."},
        ]),
        _module(9, "Long-Context vs. RAG", 2, "When to use each — or both.", [
            {"title": "Long-Context Models Change Nothing (Almost)", "duration_min": 12, "content": "Gemini 1.5 Pro's 2M-token window doesn't kill RAG. Cost, latency, and lost-in-the-middle failures still favor RAG for anything >200k tokens."},
            {"title": "Hybrid Long+RAG Architectures", "duration_min": 10, "content": "Retrieve the top 20 chunks, load into a long-context model, let the model 're-retrieve' internally. Best of both worlds."},
            {"title": "Cost Model Comparison", "duration_min": 8, "content": "Under 200k tokens: long context wins on simplicity. Above: RAG wins on cost, latency, and consistency."},
        ]),
        _module(10, "Evaluating RAG Systems", 2, "Measure what matters.", [
            {"title": "RAG Metrics That Matter", "duration_min": 12, "content": "Retrieval: precision@k, recall@k, MRR. Generation: faithfulness, answer relevance, context relevance. Don't optimize one at the expense of the others."},
            {"title": "RAGAS, TruLens & LLM-as-Judge", "duration_min": 12, "content": "Tools for automated RAG evaluation. Score every deploy against a fixed 100-500 item test set."},
            {"title": "Production Monitoring", "duration_min": 8, "content": "Log every retrieval → user rating. Feed thumbs-down cases into weekly quality reviews."},
        ]),
        # LEVEL 3
        _module(11, "Enterprise Data Ingestion", 3, "Getting data into your RAG system.", [
            {"title": "The Ingestion Zoo", "duration_min": 12, "content": "PDFs (with tables), Word docs, Confluence, SharePoint, Slack, email, Google Drive, SQL, S3. Every source needs a purpose-built connector."},
            {"title": "OCR & Layout-Aware Parsing", "duration_min": 15, "content": "Unstructured.io, LlamaParse, AWS Textract, Azure Document Intelligence. Layout-aware parsing preserves tables and columns — massively better than dumping to text."},
            {"title": "Incremental Sync", "duration_min": 10, "content": "Full-recrawl every hour will bankrupt you. Design incremental change-detection into every connector."},
        ]),
        _module(12, "Multi-Tenant & Access Control", 3, "RAG in enterprise means row-level security.", [
            {"title": "Tenant Isolation Patterns", "duration_min": 12, "content": "Separate namespaces, separate indexes, or metadata-filtered shared index. Trade-off: isolation vs. cost."},
            {"title": "Document-Level ACLs", "duration_min": 15, "content": "Users see search results only for documents they have permission to view. Filter at query time using each user's group memberships."},
            {"title": "Right-to-Forget", "duration_min": 10, "content": "GDPR Article 17. Every embedding must be locatable and deletable by data subject. Design ingestion metadata for this from day one."},
        ]),
        _module(13, "RAG for Regulated Industries", 3, "Banking, healthcare, government.", [
            {"title": "Audit Trails", "duration_min": 12, "content": "Every response must be traceable to the exact source chunks. Store the retrieval trace with a hash of the source at retrieval time."},
            {"title": "Explainability Requirements", "duration_min": 12, "content": "Model risk management (SR 11-7) requires that every automated decision be explainable. RAG citations satisfy most such requirements."},
            {"title": "Data Residency & Sovereign RAG", "duration_min": 10, "content": "EU data must stay in the EU. Design your vector store deployment topology accordingly."},
        ]),
        _module(14, "Cost Optimization at Scale", 3, "FinOps for RAG.", [
            {"title": "Model Cascading", "duration_min": 12, "content": "Route trivial queries to Haiku/Flash, escalate to Sonnet/Pro only when needed. Cuts cost 60-80%."},
            {"title": "Semantic Caching", "duration_min": 12, "content": "Cache responses to semantically similar queries. GPT-Cache, Portkey, LiteLLM all support it. Cache hit rates 30-60% in typical support workloads."},
            {"title": "Embedding Cost Governance", "duration_min": 10, "content": "Bulk embedding backfills can cost thousands. Batch, throttle, and budget-alert."},
        ]),
        _module(15, "Capstone: Design a Production RAG", 3, "Build and defend a full system.", [
            {"title": "Capstone Brief", "duration_min": 15, "content": "Design a RAG system for a fictional Fortune 500 asset manager: 10M documents, 5-year audit retention, multi-tenant, EU + US regions."},
            {"title": "Architecture Deliverable", "duration_min": 25, "content": "C4 architecture: ingestion, indexing, retrieval, generation, observability, security."},
            {"title": "Evaluation & FinOps Plan", "duration_min": 25, "content": "20-item golden set with LLM-as-judge. Monthly cost model. Rollout plan."},
        ]),
    ]

    quiz = [
        QuizQuestion(question="Which is the CORRECT choice when the goal is to add new knowledge that evolves over time?", options=["Fine-tune the model", "Use RAG", "Increase context window", "Retrain from scratch"], correct=[1], explanation="RAG is cheaper, fresher, and more auditable for evolving knowledge."),
        QuizQuestion(question="Reciprocal Rank Fusion is used to:", options=["Split documents", "Combine vector and BM25 rankings", "Fine-tune embeddings", "Compress prompts"], correct=[1], explanation="RRF combines multiple ranked lists into a single ranking."),
        QuizQuestion(question="Anthropic's Contextual Retrieval works by:", options=["Using bigger embeddings", "Prepending an LLM-generated summary to each chunk before embedding", "Using more models", "Removing chunks"], correct=[1], explanation="Contextual Retrieval enriches chunks with context before embedding."),
        QuizQuestion(question="Which retrieval failure is MOST likely with pure vector search?", options=["Semantic paraphrase", "Exact SKU / error-code lookup", "Concept clustering", "Topic modeling"], correct=[1], explanation="Exact lexical matches (SKUs, error codes) are BM25's strength, vector's weakness."),
        QuizQuestion(question="Which are RAG evaluation metrics that matter (select all)?", type="multi", options=["Faithfulness", "Answer relevance", "Context relevance", "Recall@k"], correct=[0, 1, 2, 3], explanation="All four are core RAG metrics."),
        QuizQuestion(question="Long-context models eliminate the need for RAG.", type="true_false", options=["True", "False"], correct=[1], explanation="Cost, latency, and lost-in-the-middle failures still favor RAG at scale."),
        QuizQuestion(question="Right-to-forget in RAG means:", options=["Users forget passwords", "Embeddings must be locatable and deletable per data subject", "Models forget training data", "Chunks disappear"], correct=[1], explanation="GDPR Article 17 requires embeddings to be locatable and deletable."),
        QuizQuestion(question="Semantic caching works because:", options=["Users ask identical questions", "Users often ask semantically similar questions", "Caches are free", "Vector databases are slow"], correct=[1], explanation="Semantic similarity between queries enables cache hits without exact matches."),
        QuizQuestion(question="What is HyDE?", options=["A vector database", "Hypothetical Document Embeddings — generate an answer, embed IT for search", "A reranker", "A prompt technique"], correct=[1], explanation="HyDE generates a hypothetical answer and embeds it for search."),
        QuizQuestion(question="Passing score for the ITHR certification?", options=["50%", "65%", "70%", "80%"], correct=[1], explanation="65% is the ITHR standard."),
        QuizQuestion(question="Layout-aware parsing matters for:", type="multi", options=["Tables", "Multi-column layouts", "PDFs", "Financial reports"], correct=[0, 1, 2, 3], explanation="All of the above benefit from layout-aware parsing."),
        QuizQuestion(question="Scenario: You need a RAG that must never hallucinate citations. What is the FIRST design decision?", type="scenario", options=["Use the biggest model", "Enforce citation validation post-generation (reject responses whose citations don't match retrieved chunks)", "Higher temperature", "Skip reranking"], correct=[1], explanation="Post-generation citation validation is the strongest hallucination defense."),
    ]

    return Course(
        slug="rag-enterprise",
        title="Retrieval-Augmented Generation for the Enterprise",
        subtitle="Vector databases, hybrid search, reranking, and production RAG",
        description="A comprehensive 15-module certification course on designing, building, and operating RAG systems at enterprise scale. Covers embeddings, chunking, vector databases, hybrid search, reranking, contextual retrieval, multi-tenant access control, regulated-industry patterns, and cost optimization. Includes a full capstone project.",
        category="Retrieval Augmented Generation",
        industries=["Banking", "Healthcare", "Insurance", "Government", "Professional Services"],
        difficulty="Intermediate",
        duration_hours=24,
        thumbnail_url="https://images.unsplash.com/photo-1526379095098-d400fd0bf935?w=800&q=80",
        instructor="Dr. Priya Nair",
        prerequisites=["Python proficiency", "Familiarity with any LLM API", "Basic understanding of embeddings"],
        learning_objectives=[
            "Architect production-grade RAG systems for regulated and non-regulated enterprises",
            "Master hybrid search, reranking, and contextual retrieval",
            "Implement multi-tenant access control and audit trails",
            "Design for right-to-forget and data residency",
            "Optimize cost via cascading and semantic caching",
        ],
        skills_gained=["Vector Databases", "Hybrid Search", "Reranking", "Contextual Retrieval", "RAG Evaluation", "Multi-Tenant RAG", "FinOps for AI"],
        business_value="Enterprises with mature RAG programs cite 3-5x faster knowledge worker productivity and 60% reduction in policy-lookup escalations.",
        modules=modules,
        quiz=quiz,
        passing_score=65,
        enrolled_count=12450,
        rating=4.8,
    )


# ============================================================================
# COURSE 4 — Multi-Agent Systems in Production
# ============================================================================
def build_multi_agent_course() -> Course:
    modules = [
        _module(1, "The Case for Multi-Agent", 1, "When one agent is not enough.", [
            {"title": "Single vs. Multi-Agent Decision", "duration_min": 12, "content": "Not every problem needs multiple agents. Multi-agent shines when tasks decompose naturally, when specialization improves quality, or when parallelism matters. Otherwise, a single tool-using agent wins."},
            {"title": "Real-World Multi-Agent Deployments", "duration_min": 10, "content": "Financial close automation, research report generation, complex customer support, security incident response. All show 30-60% cycle-time improvement over single-agent alternatives."},
            {"title": "The Cost of Complexity", "duration_min": 10, "content": "Multi-agent systems are harder to debug, test, and cost-model. Only adopt when the value clearly exceeds the operational overhead."},
        ]),
        _module(2, "Orchestration Patterns", 1, "Supervisor, peer-to-peer, hierarchical.", [
            {"title": "The Supervisor Pattern", "duration_min": 12, "content": "One planner-agent decomposes goals and delegates to executor-agents. Most common enterprise pattern. Easy to audit, easy to reason about."},
            {"title": "Peer-to-Peer Collaboration", "duration_min": 12, "content": "Agents negotiate directly (CrewAI style). Higher creativity but harder to constrain. Best for open-ended research and content."},
            {"title": "Hierarchical & Blackboard", "duration_min": 10, "content": "Hierarchical: nested supervisors. Blackboard: shared memory space all agents read/write. Choose based on task structure."},
        ]),
        _module(3, "Frameworks Landscape", 1, "LangGraph, CrewAI, AutoGen, OpenAI Swarm.", [
            {"title": "LangGraph — State Machines for Agents", "duration_min": 12, "content": "Deterministic graph of nodes and edges. Best for auditable, resumable enterprise workflows. Steep learning curve."},
            {"title": "CrewAI — Role-Based Collaboration", "duration_min": 12, "content": "Model agents as roles with goals and backstories. Excellent for research and content generation. Less deterministic."},
            {"title": "AutoGen & OpenAI Swarm", "duration_min": 10, "content": "AutoGen: conversation-first orchestration. Swarm: lightweight handoff patterns from OpenAI. Choose based on team preferences and use case."},
        ]),
        _module(4, "Agent Communication", 1, "How agents talk.", [
            {"title": "Message-Passing Fundamentals", "duration_min": 10, "content": "Every multi-agent system is at heart a message-passing system. Structure messages carefully: sender, recipient, task, context, expected output."},
            {"title": "Google's A2A Protocol", "duration_min": 15, "content": "The emerging standard for cross-vendor agent interoperability. Key primitives: skills, tasks, artifacts. Positions agents as first-class network citizens."},
            {"title": "Handoff & Delegation Patterns", "duration_min": 10, "content": "When one agent's job is done, it must cleanly hand off state to the next. Bad handoffs cause the majority of production failures."},
        ]),
        _module(5, "First Multi-Agent System (Hands-On)", 1, "Build a research crew.", [
            {"title": "Environment & Framework Setup", "duration_min": 10, "content": "Python + CrewAI + Emergent LLM key. Under 45 minutes to a working local research crew."},
            {"title": "Defining Roles", "duration_min": 15, "content": "Research Analyst, Fact-Checker, Report Writer. Each with distinct goals, backstories, and tools.", "code_sample": "analyst = Agent(role='Research Analyst', goal='Find relevant sources', backstory='PhD in library science', tools=[search_tool])\nwriter = Agent(role='Report Writer', goal='Synthesize into a briefing', tools=[])"},
            {"title": "Sequencing the Crew", "duration_min": 12, "content": "Define tasks and their execution order. Verify each agent produces the artifact the next agent needs."},
        ]),
        # LEVEL 2
        _module(6, "State Management", 2, "Keeping agents on the same page.", [
            {"title": "Shared vs. Isolated Memory", "duration_min": 12, "content": "Shared: all agents read the same context. Isolated: each has its own memory, hand off deliberately. Isolated is safer in production."},
            {"title": "Persistent State", "duration_min": 10, "content": "For long-running workflows (days, weeks), persist state to a database. LangGraph checkpointing is the reference implementation."},
            {"title": "Optimistic Concurrency", "duration_min": 10, "content": "When multiple agents can update the same state, use version numbers and last-writer-wins-with-reconciliation."},
        ]),
        _module(7, "Coordination & Conflict Resolution", 2, "When agents disagree.", [
            {"title": "The Arbiter Pattern", "duration_min": 12, "content": "For disagreements, invoke a stronger LLM as arbiter. Cost: 1 extra call. Benefit: prevents deadlock and reduces silent errors."},
            {"title": "Timeout & Budget Enforcement", "duration_min": 12, "content": "Every agent gets a cost budget and time budget. Exceeding either terminates gracefully. Without this, agents run forever."},
            {"title": "Handling Loops", "duration_min": 10, "content": "Agents love to loop. Detect via repeated tool calls or repeated states. Force-terminate and escalate to human."},
        ]),
        _module(8, "Tool Design for Multi-Agent", 2, "Sharing tools safely.", [
            {"title": "Shared Tool Pools", "duration_min": 10, "content": "Multiple agents call the same tool. Design for idempotency and concurrency."},
            {"title": "Per-Agent Tool Allowlists", "duration_min": 12, "content": "Least privilege: each agent only gets the tools it needs. Prevents scope creep and reduces attack surface."},
            {"title": "Tool Result Sharing", "duration_min": 10, "content": "When Agent A calls a tool, should Agent B see the result? Depends on the pattern. Default to no — explicit sharing only."},
        ]),
        _module(9, "Multi-Agent Evaluation", 2, "Testing systems, not just agents.", [
            {"title": "End-to-End Golden Sets", "duration_min": 12, "content": "Evaluate at the system level, not the individual agent level. Users don't care which agent got which piece right."},
            {"title": "Trace-Level Debugging", "duration_min": 12, "content": "LangSmith, Braintrust, Arize. Every agent step is a span. Diagnose where quality broke."},
            {"title": "A/B Testing Agent Configurations", "duration_min": 8, "content": "Route 10% of traffic through a challenger configuration (different orchestration, different models). Compare quality and cost."},
        ]),
        _module(10, "Safety & Alignment", 2, "Keeping agent crews within bounds.", [
            {"title": "Safety Rails per Agent", "duration_min": 12, "content": "Each agent has its own set of guardrails. The system as a whole has an outer guardrail (approval gates, kill switches)."},
            {"title": "Approval Gates", "duration_min": 12, "content": "For high-stakes actions (payments, external emails, system changes), require human approval. Design the UX for fast approval."},
            {"title": "Emergent Behavior", "duration_min": 10, "content": "Multi-agent systems can produce behaviors not present in any single agent. Monitor for surprises. Log liberally."},
        ]),
        # LEVEL 3
        _module(11, "Multi-Agent for Financial Services", 3, "Automating month-end close and beyond.", [
            {"title": "The Financial Close Crew", "duration_min": 15, "content": "5-agent crew: ledger, reconciliation, variance analysis, narrative, review. Reduces month-end close from 8 days to 8 hours in real deployments."},
            {"title": "Compliance-Aware Orchestration", "duration_min": 12, "content": "SR 11-7 model risk management extends to multi-agent systems. Every agent decision must be traceable and explainable."},
            {"title": "Fraud Detection Crews", "duration_min": 10, "content": "Signal collector → pattern detector → risk scorer → escalation router. Reduces false positives by 40%."},
        ]),
        _module(12, "Multi-Agent for Customer Support", 3, "Deflection at scale.", [
            {"title": "The Tiered Support Crew", "duration_min": 15, "content": "Triage agent → knowledge agent → action agent → escalation agent. Handles 60-80% of tickets without human touch."},
            {"title": "Voice-First Multi-Agent", "duration_min": 12, "content": "Real-time voice adds latency constraints. Design for sub-second handoffs. Use streaming everywhere."},
            {"title": "Sentiment & Escalation", "duration_min": 10, "content": "Dedicated sentiment agent monitors every turn. Auto-escalates when frustration detected."},
        ]),
        _module(13, "Multi-Agent Operations", 3, "Deploying at scale.", [
            {"title": "Serving Architecture", "duration_min": 12, "content": "Every agent as a service? A monolith? Somewhere in between? For most enterprises, start monolithic and split when scale demands."},
            {"title": "Observability", "duration_min": 15, "content": "OpenTelemetry traces for every agent step. Custom metrics per agent: cost, latency, quality, tool-call count."},
            {"title": "Rollback & Kill Switches", "duration_min": 10, "content": "Every multi-agent deployment needs a global kill switch and per-agent rollback. Test both quarterly."},
        ]),
        _module(14, "Emerging Patterns & Standards", 3, "Where the field is heading.", [
            {"title": "MCP for Multi-Agent", "duration_min": 12, "content": "Model Context Protocol lets multiple agents share the same tool infrastructure. Reduces integration cost dramatically."},
            {"title": "Agent Marketplaces", "duration_min": 12, "content": "Salesforce Agentforce, Microsoft Agent Store. Enterprises will assemble crews from vendor-supplied agents. Prepare your integration story."},
            {"title": "Autonomous Enterprise Vision", "duration_min": 10, "content": "The 5-year view: entire departmental workflows run by agent crews with humans as approvers. Prepare governance now."},
        ]),
        _module(15, "Capstone: Design a Production Multi-Agent System", 3, "Build the whole stack.", [
            {"title": "Capstone Brief", "duration_min": 15, "content": "Choose one: automated financial close, tiered customer support, or clinical intake triage. Design end-to-end."},
            {"title": "Architecture Deliverable", "duration_min": 25, "content": "Diagram: agents, tools, memory, orchestration, observability, guardrails. Justify every choice."},
            {"title": "Executive Presentation", "duration_min": 25, "content": "10-slide deck: business case, architecture, ROI, roadmap, risks. Present to a fictional COO."},
        ]),
    ]

    quiz = [
        QuizQuestion(question="Multi-agent is MOST appropriate when:", options=["Tasks decompose naturally into specialized roles", "You have a single well-defined task", "You want to save cost", "You want simplicity"], correct=[0], explanation="Natural decomposition and specialization are the strongest signals for multi-agent."),
        QuizQuestion(question="The Supervisor pattern involves:", options=["Peer agents", "A central agent that delegates to executors", "Random agent selection", "No orchestration"], correct=[1], explanation="A supervisor decomposes goals and delegates."),
        QuizQuestion(question="LangGraph's key advantage is:", options=["Cheap models", "Deterministic, resumable state machines", "Voice support", "Image generation"], correct=[1], explanation="LangGraph brings deterministic state machines to LLM workflows."),
        QuizQuestion(question="A2A stands for:", options=["Agent to Application", "Agent to Agent (Google's interoperability protocol)", "Assistant to Assistant", "API to Application"], correct=[1], explanation="A2A is Google's standard for agent-to-agent interoperability."),
        QuizQuestion(question="Which are essential guardrails for production multi-agent (select all)?", type="multi", options=["Cost budget per agent", "Time budget per agent", "Loop detection", "Approval gates for high-stakes actions"], correct=[0, 1, 2, 3], explanation="All four are essential."),
        QuizQuestion(question="The Arbiter pattern is used to:", options=["Save cost", "Resolve disagreements between agents", "Speed up execution", "Reduce agents"], correct=[1], explanation="An arbiter LLM resolves conflicts."),
        QuizQuestion(question="Emergent behavior in multi-agent systems is:", options=["Always positive", "Behaviors not present in any single agent — must be monitored", "Cosmetic", "Impossible"], correct=[1], explanation="Emergent behavior is real and must be monitored."),
        QuizQuestion(question="Passing score for this certification:", options=["50%", "65%", "70%", "80%"], correct=[1], explanation="65% ITHR standard."),
        QuizQuestion(question="Financial close crews typically achieve:", options=["No improvement", "30-90% cycle time reduction", "Cost increase", "Regulation failure"], correct=[1], explanation="Real deployments show major cycle time reductions."),
        QuizQuestion(question="Per-agent tool allowlists are an example of:", options=["Waste", "Least privilege / defense in depth", "Cost optimization only", "Compliance theater"], correct=[1], explanation="Least privilege reduces attack surface."),
        QuizQuestion(question="Multi-agent frameworks in modern use include (select all):", type="multi", options=["LangGraph", "CrewAI", "AutoGen", "OpenAI Swarm"], correct=[0, 1, 2, 3], explanation="All four are actively used in enterprises."),
        QuizQuestion(question="Scenario: An agent crew is stuck in a loop calling the same tool. What is the CORRECT response?", type="scenario", options=["Add more agents", "Detect the loop, force-terminate, escalate to human", "Increase the model temperature", "Restart the whole system"], correct=[1], explanation="Detect + terminate + escalate is the disciplined pattern."),
    ]

    return Course(
        slug="multi-agent-systems",
        title="Multi-Agent Systems in Production",
        subtitle="CrewAI, LangGraph, A2A, and enterprise orchestration",
        description="A comprehensive 15-module program on designing, building, and operating multi-agent systems in production. Covers orchestration patterns, framework selection, state management, safety, evaluation, and industry-specific deployment patterns for financial services, customer support, and healthcare. Includes a hands-on capstone.",
        category="Multi-Agent Systems",
        industries=["Banking", "Insurance", "Retail", "Healthcare", "Logistics", "Professional Services"],
        difficulty="Advanced",
        duration_hours=26,
        thumbnail_url="https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=800&q=80",
        instructor="Rahul Bansal",
        prerequisites=["Prior single-agent development experience", "Python + async/await proficiency"],
        learning_objectives=[
            "Choose between single-agent, multi-agent, and hybrid architectures",
            "Implement supervisor, peer-to-peer, and hierarchical orchestration",
            "Design robust state management and handoff protocols",
            "Deploy safely with cost budgets, timeouts, and approval gates",
            "Evaluate multi-agent systems end-to-end",
        ],
        skills_gained=["LangGraph", "CrewAI", "AutoGen", "A2A Protocol", "Orchestration", "Agent Observability", "Safety Rails"],
        business_value="Well-designed multi-agent systems cut cycle time by 30-70% in claims processing, financial close, and complex customer support workflows.",
        modules=modules,
        quiz=quiz,
        passing_score=65,
        enrolled_count=6870,
        rating=4.85,
    )


# ============================================================================
# COURSE 5 — AI Governance, Risk & Compliance
# ============================================================================
def build_ai_governance_course() -> Course:
    modules = [
        _module(1, "The GRC Landscape 2026", 1, "Why governance is now board-level.", [
            {"title": "From Nice-to-Have to Board Mandate", "duration_min": 12, "content": "AI governance moved from ML researcher curiosity to board-mandated function in under 24 months. Every Fortune 500 now has (or is hiring) a Head of AI Governance. This course prepares you for that role."},
            {"title": "Scope of AI GRC", "duration_min": 10, "content": "Model risk, data risk, third-party risk, operational risk, reputational risk, regulatory risk. AI touches every quadrant."},
            {"title": "The Business Case for Governance", "duration_min": 8, "content": "Companies with mature AI governance ship AI products 2x faster because approval friction is systematized rather than ad-hoc. Governance is an accelerator, not a brake."},
        ]),
        _module(2, "EU AI Act in Depth", 1, "The world's first comprehensive AI regulation.", [
            {"title": "Risk-Tier Framework", "duration_min": 12, "content": "Prohibited, high-risk, limited-risk, minimal-risk. Most enterprise AI systems land in high-risk. Understand which tier you're in — the requirements differ dramatically."},
            {"title": "Obligations for Deployers", "duration_min": 15, "content": "Even if you didn't build the model, if you deploy it in a high-risk use case, you inherit obligations: risk management, data governance, transparency, human oversight, robustness testing."},
            {"title": "Timeline & Enforcement", "duration_min": 10, "content": "The Act is in force. General-purpose AI obligations, high-risk conformity assessments, and enforcement have staggered dates. Miss them at 7% of global revenue."},
        ]),
        _module(3, "NIST AI Risk Management Framework", 1, "The US voluntary standard.", [
            {"title": "The GOVERN-MAP-MEASURE-MANAGE Loop", "duration_min": 12, "content": "The four functions of the AI RMF. Every enterprise governance program organizes around this."},
            {"title": "Applying the RMF", "duration_min": 12, "content": "Concrete artifacts: model cards, data sheets, risk registers, control matrices. NIST provides templates."},
            {"title": "Sector Overlays", "duration_min": 10, "content": "Financial services (SR 11-7), healthcare (FDA guidance), and government contractors (FedRAMP) all layer additional requirements on the RMF."},
        ]),
        _module(4, "ISO/IEC 42001 AI Management Systems", 1, "The first international AI standard.", [
            {"title": "Structure of the Standard", "duration_min": 12, "content": "Plan-Do-Check-Act discipline applied to AI. Familiar territory for anyone with ISO 27001 or 9001 experience."},
            {"title": "Certification Path", "duration_min": 15, "content": "Third-party audits, non-conformity findings, corrective actions. Certification takes 12-18 months for most organizations from a cold start."},
            {"title": "The Business Value of ISO 42001", "duration_min": 10, "content": "Increasingly a procurement gate. If you sell to Fortune 500, 42001 will be on your buyer's checklist within 18 months."},
        ]),
        _module(5, "Model & Data Risk Basics", 1, "The building blocks.", [
            {"title": "Model Risk Categories", "duration_min": 12, "content": "Accuracy, bias, robustness, security, privacy. Every model gets a risk profile across all five."},
            {"title": "Data Risk Categories", "duration_min": 12, "content": "Provenance, quality, drift, bias, legal basis. Every training and inference dataset needs a data sheet."},
            {"title": "Risk Registers", "duration_min": 10, "content": "Central log of every identified risk, owner, mitigation, and status. Auditors will ask for this."},
        ]),
        # LEVEL 2
        _module(6, "Model Cards, Data Sheets & System Cards", 2, "Documentation that satisfies auditors.", [
            {"title": "Model Card Anatomy", "duration_min": 12, "content": "Intended use, out-of-scope use, training data, performance across subgroups, ethical considerations, versions. Google's Model Card Toolkit and Hugging Face's model cards are the practical references."},
            {"title": "Data Sheets", "duration_min": 12, "content": "Purpose, collection process, consent basis, distribution across attributes, known biases. Especially important for training data."},
            {"title": "System Cards & Emergent Behavior", "duration_min": 8, "content": "For compound systems (RAG + agents + tools), a system card captures behaviors that no single component card would show."},
        ]),
        _module(7, "Bias Testing & Mitigation", 2, "The hardest part of GRC.", [
            {"title": "Bias Definitions", "duration_min": 12, "content": "Statistical parity, equalized odds, calibration. Different fairness definitions can be mutually incompatible. Choose deliberately."},
            {"title": "Testing Tools", "duration_min": 12, "content": "IBM AI Fairness 360, Google What-If Tool, Fairlearn. Real-world tools with real-world limitations."},
            {"title": "Mitigation Techniques", "duration_min": 10, "content": "Pre-processing (rebalancing data), in-processing (fairness-aware training), post-processing (calibration). Each has ideal contexts."},
        ]),
        _module(8, "Privacy & Data Protection", 2, "GDPR, CCPA, and beyond.", [
            {"title": "GDPR Article 22 & Automated Decisions", "duration_min": 12, "content": "Solely automated decisions with legal or significant effects have specific rights: explanation, contest, human review. Design AI systems accordingly."},
            {"title": "PII Handling in LLM Systems", "duration_min": 12, "content": "Data loss prevention, prompt-level redaction, output filtering. Model training on PII creates permanent leakage risk."},
            {"title": "Right-to-Forget in AI Systems", "duration_min": 10, "content": "GDPR Article 17. Embeddings, vector stores, fine-tuned models — all must support deletion of specific data subjects. Design this in from day one."},
        ]),
        _module(9, "Human Oversight & Accountability", 2, "Who owns AI decisions?", [
            {"title": "Oversight Models", "duration_min": 12, "content": "Human-in-the-loop, human-on-the-loop, human-in-command. Risk tier dictates which model applies."},
            {"title": "Accountability Structures", "duration_min": 12, "content": "Model owner, deployer, data steward, and business sponsor — each has specific accountability. Document via a RACI."},
            {"title": "Incident Response", "duration_min": 10, "content": "AI incident response is analogous to cybersecurity incident response. Runbooks, kill switches, post-mortems."},
        ]),
        _module(10, "Auditing AI Systems", 2, "External and internal.", [
            {"title": "Internal Audit Function", "duration_min": 12, "content": "The 3rd line of defense. Independent, board-reporting, empowered to challenge model owners."},
            {"title": "External Audits", "duration_min": 12, "content": "ISO 42001 certification, SOC 2 for AI, NYC LL 144 bias audits. Prepare for at least one within 18 months."},
            {"title": "Audit Trails", "duration_min": 10, "content": "Every AI decision, its inputs, model version, and outcome — logged, immutable, retention 7+ years."},
        ]),
        # LEVEL 3
        _module(11, "Governance for Generative AI", 3, "New risks the frameworks weren't built for.", [
            {"title": "Copyright & Training Data", "duration_min": 15, "content": "Open lawsuits and evolving case law. Content licensing has become the biggest gen-AI legal risk."},
            {"title": "Hallucination as a Governance Issue", "duration_min": 12, "content": "Reasonable-user standard: a system that hallucinates in high-stakes contexts is defective under product liability law."},
            {"title": "Deepfakes, Impersonation & Misuse", "duration_min": 10, "content": "Voice cloning, image synthesis, and impersonation are governance issues even for benign products."},
        ]),
        _module(12, "Governance for Agentic AI", 3, "The autonomy problem.", [
            {"title": "Bounded Autonomy", "duration_min": 15, "content": "Agents that take actions in the world require explicit scope, budget, and blast-radius controls. Design these in — do not retrofit."},
            {"title": "Multi-Agent Governance", "duration_min": 12, "content": "Governance in multi-agent systems is a system-level property, not an agent-level property. Design accordingly."},
            {"title": "Tool-Use Governance", "duration_min": 10, "content": "Every tool an agent can call is a potential blast radius. Allow-list tools per agent, log every call, alert on anomalies."},
        ]),
        _module(13, "Sector-Specific Overlays", 3, "Banking, healthcare, government.", [
            {"title": "SR 11-7 for Banks", "duration_min": 15, "content": "Model risk management from the Federal Reserve. Extends fully to AI models. Model validation, ongoing monitoring, effective challenge."},
            {"title": "FDA AI/ML Guidance", "duration_min": 12, "content": "For medical AI, FDA's software-as-medical-device framework applies. Predetermined change control plans allow continuous model updates."},
            {"title": "Government & Public Sector", "duration_min": 10, "content": "OMB M-24-10, FedRAMP High, and agency-specific AI plans. Documentation burden is heavy — start early."},
        ]),
        _module(14, "Building the Governance Function", 3, "Org design and ops.", [
            {"title": "The AI Governance Committee", "duration_min": 12, "content": "Cross-functional: legal, risk, security, engineering, product. Meets biweekly. Has veto rights over high-risk deployments."},
            {"title": "Roles & Hiring", "duration_min": 12, "content": "Head of AI Governance, Model Risk Lead, AI Ethicist, AI Compliance Officer. Salary ranges, org placement, reporting lines."},
            {"title": "Vendor & Third-Party Governance", "duration_min": 10, "content": "Every AI vendor you use is your risk. SOC 2, ISO 42001, data processing addenda — demand them."},
        ]),
        _module(15, "Capstone: Design a Governance Program", 3, "Board-level deliverable.", [
            {"title": "Capstone Brief", "duration_min": 15, "content": "Choose one: Fortune 500 bank, mid-size healthcare system, or federal agency. Design their end-to-end AI governance program."},
            {"title": "Deliverable 1: Policy Charter", "duration_min": 20, "content": "Board-approved policy: scope, risk tiering, approval process, oversight, accountability, incident response."},
            {"title": "Deliverable 2: Board Presentation", "duration_min": 25, "content": "Present to a fictional board Audit Committee. 12-slide deck. Executive question handling."},
        ]),
    ]

    quiz = [
        QuizQuestion(question="The EU AI Act classifies systems into how many risk tiers?", options=["2", "3", "4", "5"], correct=[2], explanation="Prohibited, high-risk, limited-risk, minimal-risk = 4 tiers."),
        QuizQuestion(question="NIST AI RMF functions are:", options=["Identify-Protect-Detect-Respond", "Govern-Map-Measure-Manage", "Plan-Do-Check-Act", "Prevent-Detect-Correct"], correct=[1], explanation="Govern-Map-Measure-Manage is the AI RMF loop."),
        QuizQuestion(question="ISO 42001 is:", options=["A US law", "The first international AI management system standard", "A model card format", "A vendor tool"], correct=[1], explanation="ISO/IEC 42001 is the first international AI management system standard."),
        QuizQuestion(question="GDPR Article 22 addresses:", options=["Right to be forgotten", "Solely automated decisions with legal or significant effects", "Data minimization", "Consent"], correct=[1], explanation="Article 22 governs automated decision-making."),
        QuizQuestion(question="Which are typical roles in an AI governance function (select all)?", type="multi", options=["Head of AI Governance", "Model Risk Lead", "AI Ethicist", "AI Compliance Officer"], correct=[0, 1, 2, 3], explanation="All four are increasingly common."),
        QuizQuestion(question="SR 11-7 originates from:", options=["The EU", "The US Federal Reserve", "China", "The UK"], correct=[1], explanation="SR 11-7 is Federal Reserve model risk management guidance."),
        QuizQuestion(question="Bias mitigation techniques include (select all):", type="multi", options=["Pre-processing (data rebalancing)", "In-processing (fairness-aware training)", "Post-processing (calibration)", "Ignoring bias"], correct=[0, 1, 2], explanation="Three legitimate techniques; ignoring is not one."),
        QuizQuestion(question="Passing score for the ITHR certification:", options=["50%", "65%", "75%", "85%"], correct=[1], explanation="65% is the ITHR standard."),
        QuizQuestion(question="A system card is:", options=["A financial ledger", "Documentation for a compound AI system capturing emergent behaviors", "A hardware spec", "A user manual"], correct=[1], explanation="System cards document compound-system properties."),
        QuizQuestion(question="Agent governance requires:", type="multi", options=["Bounded autonomy", "Cost budgets", "Blast-radius controls", "Tool allow-lists"], correct=[0, 1, 2, 3], explanation="All four are essential."),
        QuizQuestion(question="The 3rd line of defense refers to:", options=["Firewall", "Internal audit function (independent, board-reporting)", "Firewalls again", "External vendors"], correct=[1], explanation="The 3rd line of defense is independent internal audit."),
        QuizQuestion(question="Scenario: Your AI vendor cannot produce a SOC 2 report. The CORRECT governance response is:", type="scenario", options=["Approve anyway", "Reject or require compensating controls with legal sign-off", "Ignore vendor risk", "Assume it's fine"], correct=[1], explanation="Vendor risk requires either SOC 2 or documented compensating controls."),
    ]

    return Course(
        slug="ai-governance-compliance",
        title="AI Governance, Risk & Compliance",
        subtitle="EU AI Act, NIST AI RMF, ISO 42001, and enterprise governance operations",
        description="A rigorous 15-module program preparing risk, compliance, and product leaders to build and operate enterprise AI governance functions. Covers the EU AI Act in depth, NIST AI RMF, ISO 42001, model cards, bias testing, privacy, human oversight, generative and agentic AI governance, and sector-specific overlays. Board-ready capstone.",
        category="AI Governance",
        industries=["Banking", "Insurance", "Healthcare", "Government", "Pharmaceutical", "Professional Services"],
        difficulty="Enterprise Leader",
        duration_hours=22,
        thumbnail_url="https://images.pexels.com/photos/7108207/pexels-photo-7108207.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
        instructor="Judith Ackerman, JD",
        prerequisites=["Familiarity with enterprise risk management", "Basic AI/ML literacy"],
        learning_objectives=[
            "Navigate the EU AI Act, NIST AI RMF, and ISO 42001",
            "Design model cards, data sheets, and system cards",
            "Implement bias testing and mitigation",
            "Structure human oversight and accountability",
            "Build the governance function: committee, roles, processes, vendor oversight",
        ],
        skills_gained=["EU AI Act", "NIST AI RMF", "ISO 42001", "Model Cards", "Bias Testing", "AI Auditing", "Governance Ops"],
        business_value="Mature AI governance functions cut deployment friction 60%, insurance premiums 20-30%, and regulatory findings by 70%. Increasingly a procurement prerequisite.",
        modules=modules,
        quiz=quiz,
        passing_score=65,
        enrolled_count=4520,
        rating=4.9,
    )
