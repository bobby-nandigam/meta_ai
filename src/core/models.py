"""
Core data models using Pydantic - properly typed and validated.
"""
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, validator
import uuid


class TaskStatus(str, Enum):
    """Task lifecycle states"""
    CREATED = "created"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class AgentType(str, Enum):
    """Types of agents in the system"""
    PLANNER = "planner"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    MEMORY = "memory"
    MONITOR = "monitor"


class ActionType(str, Enum):
    """Types of executable actions"""
    EMAIL_CLASSIFY = "email_classify"
    EMAIL_MOVE = "email_move"
    EMAIL_REPLY = "email_reply"
    CODE_REVIEW = "code_review"
    DATA_QUERY = "data_query"
    ESCALATE = "escalate"
    LEARN = "learn"


class ConfidenceLevel(float):
    """Confidence score 0.0-1.0"""
    def __new__(cls, value: float):
        if not 0.0 <= value <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return float(value)


# ==================== Task Models ====================

class TaskSpec(BaseModel):
    """User's high-level task specification"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    domain: str  # "email", "code_review", "data_cleaning", etc.
    priority: int = Field(default=5, ge=1, le=10)  # 1-10
    context: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    deadline: Optional[datetime] = None
    user_id: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task-001",
                "title": "Triage email inbox",
                "description": "Classify and organize 500+ unread emails",
                "domain": "email",
                "priority": 8,
                "constraints": ["No deletion", "Keep internal only"]
            }
        }


class ExecutionPlan(BaseModel):
    """Decomposed plan from Planner Agent"""
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    steps: List["ExecutionStep"] = Field(default_factory=list)
    estimated_duration: float  # seconds
    estimated_cost: float  # USD
    risk_level: str = "medium"  # low, medium, high
    confidence: ConfidenceLevel = 0.8
    reasoning: str  # Why this plan?
    created_at: datetime = Field(default_factory=datetime.now)


class ExecutionStep(BaseModel):
    """Single executable step"""
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    order: int
    action_type: ActionType
    tool_name: str  # "email_classifier", "code_reviewer", etc.
    function_name: str  # "classify", "review", etc.
    parameters: Dict[str, Any]
    dependencies: List[int] = Field(default_factory=list)  # step orders it depends on
    timeout_seconds: int = 30
    retries: int = 3
    rollback_strategy: Optional[str] = None


# ==================== Agent Models ====================

class Agent(BaseModel):
    """Agent instance"""
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    agent_type: AgentType
    status: str = "idle"  # idle, busy, error, offline
    role: str  # "executor_email", "reviewer", etc.
    permissions: List[str] = Field(default_factory=list)
    last_heartbeat: datetime = Field(default_factory=datetime.now)
    processed_tasks: int = 0
    error_rate: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== Decision Models ====================

class Decision(BaseModel):
    """Agent decision with reasoning and confidence"""
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    step_id: str
    task_id: str
    action: str  # What to do
    parameters: Dict[str, Any]  # How to do it
    confidence: ConfidenceLevel
    reasoning: str  # Why this decision?
    input_summary: str  # What was analyzed
    similar_cases: List[Dict[str, Any]] = Field(default_factory=list)  # Historical matches
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    applied_rules: List[str] = Field(default_factory=list)
    requires_escalation: bool = False
    escalation_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "decision_id": "dec-001",
                "agent_id": "agent-02",
                "action": "MOVE_EMAIL",
                "parameters": {"folder": "work_critical", "email_id": "123"},
                "confidence": 0.92,
                "reasoning": "Email from boss with urgent keywords"
            }
        }


class ReviewResult(BaseModel):
    """Reviewer Agent's validation"""
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str
    approved: bool
    confidence: ConfidenceLevel
    safety_checks: Dict[str, bool]  # {"no_pii_leaked": True, ...}
    policy_violations: List[str] = Field(default_factory=list)
    explanation: str
    suggested_modifications: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ExecutionResult(BaseModel):
    """Result of executing a step"""
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_id: str
    task_id: str
    status: TaskStatus
    output: Dict[str, Any]
    error: Optional[str] = None
    error_type: Optional[str] = None  # "ratelimit", "auth", "data_error"
    duration_seconds: float
    retry_count: int = 0
    human_override: bool = False
    human_override_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


# ==================== Feedback & Learning ====================

class UserFeedback(BaseModel):
    """User's feedback on AI decision"""
    feedback_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str
    user_id: str
    feedback_type: str  # "approved", "rejected", "modified"
    original_decision: Dict[str, Any]
    modified_decision: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class LearningSignal(BaseModel):
    """Data for model improvement"""
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    input_features: Dict[str, Any]
    predicted_action: str
    predicted_confidence: ConfidenceLevel
    actual_outcome: str  # "success", "failure", "user_rejected"
    outcome_confidence: ConfidenceLevel = 1.0
    reward: float  # -1.0 to 1.0
    timestamp: datetime = Field(default_factory=datetime.now)


# ==================== Memory Models ====================

class MemoryEntry(BaseModel):
    """Stored in vector database"""
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    content: str  # Text to embed
    embedding: Optional[List[float]] = None  # Vector embedding
    entry_type: str  # "user_preference", "decision_pattern", "email_context"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    success_rate: float = 0.5  # How often was this pattern successful?
    frequency: int = 1  # How often observed?
    last_updated: datetime = Field(default_factory=datetime.now)


class UserProfile(BaseModel):
    """Learned user preferences"""
    user_id: str
    preferences: Dict[str, Any] = Field(default_factory=dict)
    behavior_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    priority_rules: Dict[str, int] = Field(default_factory=dict)
    trusted_senders: List[str] = Field(default_factory=list)
    escalation_triggers: List[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.now)


# ==================== Audit & Governance ====================

class AuditLog(BaseModel):
    """Immutable action log"""
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    agent_id: str
    action: str
    task_id: str
    decision_id: str
    input_summary: str
    reasoning: str
    outcome: str  # "success", "failure"
    outcome_details: Dict[str, Any] = Field(default_factory=dict)
    user_override: bool = False
    user_feedback: Optional[str] = None
    confidence_score: ConfidenceLevel
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "agent-02",
                "action": "CLASSIFY_EMAIL",
                "task_id": "task-001",
                "confidence_score": 0.92,
                "outcome": "success"
            }
        }


# Models with nested references
ExecutionPlan.update_forward_refs()
