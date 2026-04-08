# Autonomous Work OS - Visual Architecture Guide

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                        USER INTERFACE LAYER                                 │
│              (Dashboard, Task Monitor, Override Controls)                   │
│                                                                             │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        REQUEST PROCESSING                                  │
│          ┌──────────────────────────────────────────────────────┐          │
│          │  Task Request (Email, Code Review, Data Cleaning)   │          │
│          │  Constraints: No deletion, Confidential, etc.       │          │
│          └──────────────────────────────────────────────────────┘          │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
                    ▼                                 ▼
    ┌───────────────────────────┐      ┌───────────────────────────┐
    │  PLANNER AGENT            │      │  ORCHESTRATOR             │
    │  ├─ Decompose task        │      │  ├─ Route messages       │
    │  ├─ Generate plan         │      │  ├─ Coordinate agents    │
    │  ├─ Estimate cost/risk    │      │  └─ Manage workflow      │
    │  └─ LLM reasoning         │      └───────────────────────────┘
    └───────────────────────────┘
                    │
                    │ ExecutionPlan
                    │ (decomposed steps)
                    │
                    ▼
    ┌──────────────────────────────────────────────────────┐
    │  EXECUTOR AGENTS (5-10 parallel)                     │
    │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
    │  │  Executor-1  │  │  Executor-2  │  │ Executor-N │ │
    │  │ ┌──────────┐ │  │ ┌──────────┐ │  │┌──────────┐│ │
    │  │ │Tool Mgmt │ │  │ │Tool Mgmt │ │  ││Tool Mgmt ││ │
    │  │ │Retries   │ │  │ │Retries   │ │  ││Retries  ││ │
    │  │ └──────────┘ │  │ └──────────┘ │  │└──────────┘│ │
    │  └──────────────┘  └──────────────┘  └────────────┘ │
    └───────┬──────────────────────────────────────────────┘
            │ ExecutionResults
            │
            ▼
    ┌──────────────────────────┐
    │  REVIEWER AGENT          │
    │  ├─ Validate decisions   │
    │  ├─ Safety checks        │
    │  ├─ Confidence scoring   │
    │  └─ Escalation logic     │
    └────────┬─────────────────┘
             │
             ├─ High confidence?
             │  └──► Execute
             │
             ├─ Medium confidence?
             │  └──► Human review
             │
             └─ Low confidence?
                └──► Escalate & Wait
```

---

## Agent Communication Flow

```
┌─────────────────────────────────────────────────────┐
│          MESSAGE BUS (Event-Driven)                │
│   ┌────────────────────────────────────────────┐  │
│   │  Topics: Plan, Step, Result, Decision      │  │
│   │  Subscribers: All agents listening         │  │
│   └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
        ▲            ▲            ▲            ▲
        │            │            │            │
        │            │            │            │
    ┌───┴────┐   ┌───┴────┐   ┌───┴────┐   ┌───┴────┐
    │Planner │   │ Exec   │   │Reviewer│   │ Memory │
    │ Agent  │   │ Agent  │   │ Agent  │   │ Agent  │
    └────────┘   └────────┘   └────────┘   └────────┘
```

---

## ML Intelligence Layer

```
┌──────────────────────────────────────────────────────────┐
│             ML MODELS & INFERENCE                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  TASK-SPECIFIC MODELS:                                  │
│  ┌──────────────┐  ┌────────────┐  ┌───────────────┐  │
│  │ LLM (Claude) │  │ Classifier │  │  Embeddings   │  │
│  │  (Reasoning) │  │(Email,Code)│  │(Semantic MM)  │  │
│  └──────────────┘  └────────────┘  └───────────────┘  │
│                                                          │
│  SUPPORTING MODELS:                                     │
│  ┌──────────────┐  ┌────────────┐  ┌───────────────┐  │
│  │   Ranker     │  │  Anomaly   │  │  NER/NLP      │  │
│  │ (Prioritize) │  │ Detection  │  │(Entity Ext.)  │  │
│  └──────────────┘  └────────────┘  └───────────────┘  │
│                                                          │
│  FEEDBACK LOOP:                                         │
│  Outcomes → User Feedback → Update Weights             │
│  Detection of Data Drift → Retrain Trigger            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Memory System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   MEMORY SYSTEMS                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌────────────────────┐      ┌──────────────────────┐ │
│  │  SHORT-TERM        │      │   LONG-TERM          │ │
│  │  (In-Memory)       │      │   (Persistent)       │ │
│  │  ┌──────────────┐  │      │  ┌────────────────┐ │ │
│  │  │ Redis Cache  │  │      │  │ Vector DB      │ │ │
│  │  ├─ Session     │  │      │  │ ┌────────────┐ │ │ │
│  │  │ Context      │  │      │  │ │ Embedding  │ │ │ │
│  │  ├─ Agent State │  │      │  │ │ (Sentence  │ │ │ │
│  │  │              │  │      │  │ │ Transformer) │ │ │
│  │  ├─ TTL: 1h     │  │      │  │ └────────────┘ │ │ │
│  │  └──────────────┘  │      │  │ ┌────────────┐ │ │ │
│  └────────────────────┘      │  │ │ Metadata   │ │ │ │
│                               │  │ │ (Success   │ │ │ │
│                               │  │ │  rate,    │ │ │ │
│                               │  │ │  patterns) │ │ │ │
│                               │  │ └────────────┘ │ │ │
│                               │  └────────────────┘ │ │
│                               │                      │ │
│                               │  ┌────────────────┐ │ │
│                               │  │ PostgreSQL     │ │ │
│                               │  │ ├─ Audit Logs  │ │ │
│                               │  │ ├─ Decisions   │ │ │
│                               │  │ └─ Feedback    │ │ │
│                               │  └────────────────┘ │ │
│                               └──────────────────────┘ │
│                                                         │
│  LEARNING CYCLE:                                       │
│  Behavior Pattern → Embedding → Similarity Search    │
│  → Recommendation → User Feedback → Update           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Action/Execution Layer

```
┌────────────────────────────────────────────────────────┐
│            TOOL REGISTRY & MANAGEMENT                 │
├────────────────────────────────────────────────────────┤
│                                                        │
│  EMAIL TOOLS:                                         │
│  ├─ classify_email() → ML model                       │
│  ├─ move_email() → Gmail API                          │
│  ├─ reply_email() → LLM generation + send             │
│  └─ search_email() → Gmail search API                 │
│                                                        │
│  CODE TOOLS:                                          │
│  ├─ analyze_code() → CodeBERT/CodeT5                  │
│  ├─ get_pr_diff() → GitHub API                        │
│  ├─ post_comment() → GitHub API                       │
│  └─ suggest_fix() → LLM generation                    │
│                                                        │
│  DATA TOOLS:                                          │
│  ├─ query_database() → SQL executor                   │
│  ├─ detect_outliers() → Isolation Forest              │
│  ├─ remove_duplicates() → Pandas/SQL                  │
│  └─ validate_schema() → Custom validators             │
│                                                        │
│  EXECUTION WRAPPER:                                   │
│  ┌──────────────────────────────────────────────┐    │
│  │ try:                                         │    │
│  │   result = tool.execute(func, params, to=30)│    │
│  │ except RateLimitError:                       │    │
│  │   sleep(exp_backoff())                       │    │
│  │   retry()                                    │    │
│  │ except AuthError:                            │    │
│  │   escalate()                                 │    │
│  │ except DataError:                            │    │
│  │   rollback_and_notify()                      │    │
│  └──────────────────────────────────────────────┘    │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## Safety & Governance

```
┌────────────────────────────────────────────────────┐
│     SAFETY & GOVERNANCE LAYER                      │
├────────────────────────────────────────────────────┤
│                                                    │
│  CONFIDENCE-BASED ESCALATION:                    │
│                                                    │
│  Score ≥ 0.9 ──────► AUTO-EXECUTE                │
│                      Log & Monitor                │
│                                                    │
│  Score 0.7-0.9 ────► HUMAN REVIEW                │
│                      Wait for approval            │
│                                                    │
│  Score < 0.7 ───────► ESCALATE                   │
│                       High-priority human review  │
│                                                    │
│  ─────────────────────────────────────────────   │
│                                                    │
│  POLICY ENFORCEMENT:                              │
│  ┌──────────────────────────────────────────┐   │
│  │ if action == "delete":                  │   │
│  │   if not policy.allows_delete():        │   │
│  │     escalate("Policy violation")        │   │
│  │                                          │   │
│  │ if data_contains_pii():                 │   │
│  │   mask_in_logs()                        │   │
│  │   escalate("PII detected")              │   │
│  └──────────────────────────────────────────┘   │
│                                                    │
│  AUDIT LOG:                                       │
│  ┌──────────────────────────────────────────┐   │
│  │ {                                        │   │
│  │   "agent_id": "executor-02",            │   │
│  │   "action": "CLASSIFY_EMAIL",           │   │
│  │   "confidence": 0.92,                   │   │
│  │   "timestamp": "2024-01-15T10:30:00Z",  │   │
│  │   "result": "success",                  │   │
│  │   "user_override": false                │   │
│  │ }                                        │   │
│  └──────────────────────────────────────────┘   │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## OpenEnv Task Structure

```
┌──────────────────────────────────────────────────────┐
│        OPENENV ENVIRONMENT INTERFACE                 │
├──────────────────────────────────────────────────────┤
│                                                      │
│  RESET() ────────────────────────────────────────► │
│              Returns Initial Observation            │
│              ┌────────────────────────────────┐    │
│              │ Observation {                 │    │
│              │  task_id: str                 │    │
│              │  step: int                    │    │
│              │  state: Dict                  │    │
│              │  actions: List[Action]        │    │
│              │  context: str                 │    │
│              │ }                             │    │
│              └────────────────────────────────┘    │
│                          │                          │
│                          │ Agent responds with     │
│                          │ Action                  │
│                          ▼                          │
│  STEP(action) ──────────────────────────────────► │
│              ┌───────────────────────────────┐    │
│              │ Returns (obs, reward, done)   │    │
│              │                               │    │
│              │ Reward {                      │    │
│              │  immediate: float             │    │
│              │  trajectory: float            │    │
│              │  components: Dict             │    │
│              │  done: bool                   │    │
│              │ }                             │    │
│              └───────────────────────────────┘    │
│                          │                          │
│                          │ Repeat until done       │
│                          ▼                          │
│  GRADE() ────────────────────────────────────────► │
│              Returns Score: 0.0-1.0               │
│              Based on final performance           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## Scalability Architecture

```
┌─────────────────────────────────────────────────────────┐
│              KUBERNETES DEPLOYMENT                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Load Balancer                                          │
│  └─ Distributes requests to API servers               │
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │  API Service (1-3 replicas)                      │ │
│  │  ├─ Receives task requests                       │ │
│  │  └─ Routes to broker                             │ │
│  └──────────────────────────────────────────────────┘ │
│                        │                                │
│                        ▼                                │
│  ┌──────────────────────────────────────────────────┐ │
│  │  Message Broker (RabbitMQ/Kafka)                 │ │
│  │  ├─ planning-queue (1 worker)                    │ │
│  │  ├─ execution-queue (5-10 workers, autoscale)   │ │
│  │  ├─ review-queue (2-3 workers)                  │ │
│  │  └─ escalation-queue (high priority)            │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ Planner     │  │ Executor-1  │  │ Executor-N  │   │
│  │ Service     │  │ Service     │  │ Service     │   │
│  │ (1 replica) │  │ (1-10       │  │ (Horizontal │   │
│  │             │  │ replicas,   │  │  Autoscaling)  │
│  │             │  │ autoscale)  │  │             │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │  Data Layer                                      │ │
│  │  ├─ Redis (cache, session state)                │ │
│  │  ├─ PostgreSQL (audit logs, decisions)          │ │
│  │  ├─ Pinecone (vector embeddings)                │ │
│  │  └─ S3 (model checkpoints, data)                │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │  Monitoring                                      │ │
│  │  ├─ Prometheus (metrics)                        │ │
│  │  ├─ Grafana (dashboards)                        │ │
│  │  └─ Datadog (full observability)                │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Data Flow: Email Triage Example

```
USER REQUEST
    │
    │ "Triage 500 emails"
    │
    ▼
PLANNER AGENT
    │ Decomposes into:
    │ 1. Fetch emails
    │ 2. Classify
    │ 3. Move
    │ 4. Respond
    │ 5. Update metadata
    │
    ▼
EXECUTOR AGENTS (parallel)
    │ Fetch: 487 emails ✓
    │       │
    │       ├─ Gmail API.list_unread()
    │       │
    │ Classify: 487 → 4 categories ✓
    │       │
    │       ├─ Email Classifier (DistilBERT)
    │       │  ├─ Input: email text
    │       │  └─ Output: confidence scores
    │       │
    │ Move: 460 emails ✓
    │       │
    │       ├─ Gmail API.move_to_folder()
    │       │
    │ Respond: 120 suggestions ✓
    │       │
    │       └─ ResponseGenerator (Claude)
    │          ├─ Input: email + category
    │          └─ Output: draft response
    │
    ▼
MEMORY AGENT
    │
    ├─ Store embeddings of processed emails
    ├─ Update user preferences
    ├─ Note patterns (sender_reputation, time)
    │
    ▼
REVIEWER AGENT
    │
    ├─ No critical → spam? ✓
    ├─ Accuracy matches history? ✓
    ├─ All constraints met? ✓
    │
    ├─ Confidence: 0.92
    │
    ▼
OUTPUT
    │
    └─ 487 emails processed
       Accuracy: 94.2%
       Time: 12.4 seconds
       Result: ✓ APPROVED & EXECUTED
```

---

## Model Stack

```
┌─────────────────────────────────────────────────────┐
│         MODEL SELECTION BY TASK                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  EMAIL TRIAGE:                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │ Input: Email text + metadata                │ │
│  │ Model: DistilBERT (fine-tuned)              │ │
│  │ Output: 4-way classification                │ │
│  │ Latency: ~50ms per email                    │ │
│  │ Confidence: 0.9+ (good)                     │ │
│  └──────────────────────────────────────────────┘ │
│                                                     │
│  CODE REVIEW:                                      │
│  ┌──────────────────────────────────────────────┐ │
│  │ Input: Code diff                            │ │
│  │ Models:                                     │ │
│  │  1. CodeBERT (semantic understanding)      │ │
│  │  2. Linter (style violations)              │ │
│  │  3. SAST scanner (security)                │ │
│  │  4. Claude (reasoning & suggestions)       │ │
│  │ Output: Issue list + severity              │ │
│  │ Latency: ~200ms per PR                     │ │
│  └──────────────────────────────────────────────┘ │
│                                                     │
│  DATA CLEANING:                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │ Input: Dataset                              │ │
│  │ Models:                                     │ │
│  │  1. Isolation Forest (outlier detection)   │ │
│  │  2. Duplicate detection (exact + fuzzy)    │ │
│  │  3. Schema validation                      │ │
│  │  4. Missing value imputation               │ │
│  │ Output: Quality score                      │ │
│  │ Latency: ~100ms per 100 records            │ │
│  └──────────────────────────────────────────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Decision Flow with Confidence Scoring

```
DECISION MADE
    │
    ├─ Confidence: 0.92
    │
    ─────────────────────────────────────────────────
    
    If Score ≥ 0.9:
    │
    ├──► ✓ APPROVED
    │    ├─ Log action
    │    ├─ Execute immediately
    │    └─ Monitor for issues
    │
    └─────────────────────────────────────────────────
    
    If Score 0.7-0.89:
    │
    ├──► ⚠️  MONITOR
    │    ├─ Log action
    │    ├─ Execute with caution
    │    └─ Human can override
    │
    └─────────────────────────────────────────────────
    
    If Score < 0.7:
    │
    ├──► 🔴 ESCALATE
    │    ├─ Add to human review queue
    │    ├─ Explain decision to human
    │    ├─ Wait for approval
    │    └─ Execute after approval OR
    │        Reject and replanning
    │
    └─────────────────────────────────────────────────
```

---

**This visual guide complements the detailed documentation in ARCHITECTURE.md**
