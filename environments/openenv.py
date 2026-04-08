"""
OpenEnv-compliant Autonomous Work OS Environment
Implements three real-world tasks with graders and reward functions
"""

from typing import Any, Dict, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field, validator
import json
from abc import ABC, abstractmethod
from datetime import datetime
import random


# ==================== OBSERVATION & ACTION MODELS ====================

class TaskType(str, Enum):
    """Supported task types"""
    EMAIL_TRIAGE = "email_triage"
    CODE_REVIEW = "code_review"  
    DATA_CLEANING = "data_cleaning"


class Observation(BaseModel):
    """Observation from environment - what the agent sees"""
    task_id: str
    task_type: TaskType
    step_number: int
    current_state: Dict[str, Any]  # Task-specific state
    available_actions: list  # Valid actions in current state
    context: str  # Human-readable description
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task-001",
                "task_type": "email_triage",
                "step_number": 0,
                "current_state": {
                    "unread_count": 487,
                    "emails": [
                        {
                            "id": "email-001",
                            "from": "boss@meta.com",
                            "subject": "Urgent: Q1 Planning",
                            "preview": "Need your input on strategy...",
                            "timestamp": "2024-01-15T09:30:00Z"
                        }
                    ]
                },
                "available_actions": ["classify_email", "fetch_next_email", "complete_task"],
                "context": "Email triage task: 487 unread emails in inbox"
            }
        }


class Action(BaseModel):
    """Action taken by agent"""
    action_type: str  # "classify_email", "move_email", "review_code", etc.
    parameters: Dict[str, Any]  # Action-specific parameters
    agent_reasoning: str  # Why did agent take this action?
    confidence: float = Field(ge=0.0, le=1.0)

    class Config:
        json_schema_extra = {
            "example": {
                "action_type": "classify_email",
                "parameters": {
                    "email_id": "email-001",
                    "category": "work_critical",
                    "folder": "inbox"
                },
                "agent_reasoning": "Email from boss with urgent keywords",
                "confidence": 0.94
            }
        }


class Reward(BaseModel):
    """Reward signal"""
    immediate_reward: float  # -1.0 to 1.0
    reward_components: Dict[str, float]  # Breakdown of reward
    trajectory_reward: float = 0.0  # Cumulative reward so far
    done: bool = False  # Episode termination
    info: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "immediate_reward": 0.85,
                "reward_components": {
                    "accuracy": 0.9,
                    "efficiency": 0.8,
                    "safety": 1.0,
                    "constraint_violation": 0.0
                },
                "trajectory_reward": 5.2,
                "done": False
            }
        }


# ==================== TASK IMPLEMENTATIONS ====================

class Task(ABC):
    """Base class for all tasks"""

    def __init__(self, task_id: str, difficulty: str):
        self.task_id = task_id
        self.difficulty = difficulty  # "easy", "medium", "hard"
        self.step_count = 0
        self.max_steps = 20
        self.trajectory_reward = 0.0
        self.history = []
        self.ground_truth = {}

    @abstractmethod
    def reset(self) -> Observation:
        """Reset task and return initial observation"""
        pass

    @abstractmethod
    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict]:
        """Execute action and return (observation, reward, done, info)"""
        pass

    @abstractmethod
    def grade(self) -> float:
        """Return score 0.0-1.0 for task completion"""
        pass


class EmailTriageTask(Task):
    """
    EASY TASK: Email triage and classification
    
    Agent must:
    1. Classify emails into categories (work_critical, work_routine, personal, spam)
    2. Move emails to correct folders
    3. Suggest responses to routine emails
    
    Success metrics:
    - Classification accuracy > 90%
    - No critical emails marked as spam
    - Process efficiently (< 30 steps)
    """

    def __init__(self, task_id: str = "email_triage_001"):
        super().__init__(task_id, difficulty="easy")
        
        # Generate synthetic emails
        self.emails = self._generate_emails()
        self.processed_emails = []
        self.current_email_idx = 0
        self.classifications = {}  # email_id -> predicted_class
        
        # Ground truth labels for grading
        self.ground_truth = {
            "email-001": "work_critical",
            "email-002": "work_routine",
            "email-003": "personal",
            "email-004": "spam",
            "email-005": "work_critical",
            "email-006": "work_routine",
        }

    def reset(self) -> Observation:
        """Initialize email triage task"""
        self.step_count = 0
        self.trajectory_reward = 0.0
        self.processed_emails = []
        self.current_email_idx = 0
        self.classifications = {}
        
        return Observation(
            task_id=self.task_id,
            task_type=TaskType.EMAIL_TRIAGE,
            step_number=0,
            current_state={
                "total_emails": len(self.emails),
                "unread_count": len(self.emails),
                "current_email": self.emails[0] if self.emails else None,
                "processed_count": 0
            },
            available_actions=["classify_email", "fetch_next_email", "complete_task"],
            context=f"Email triage: {len(self.emails)} unread emails to process"
        )

    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict]:
        """Process email action"""
        self.step_count += 1
        reward_info = {
            "accuracy": 0.0,
            "efficiency": 1.0,
            "safety": 1.0,
            "constraint_violation": 0.0
        }
        
        done = False
        next_observation = self._get_observation()

        if action.action_type == "classify_email":
            email_id = action.parameters.get("email_id")
            predicted_class = action.parameters.get("category")
            
            if email_id in self.ground_truth:
                correct = predicted_class == self.ground_truth[email_id]
                reward_info["accuracy"] = 1.0 if correct else 0.0
                self.classifications[email_id] = predicted_class
                self.processed_emails.append(email_id)
            
            # Move to next email
            if self.current_email_idx < len(self.emails) - 1:
                self.current_email_idx += 1
            
        elif action.action_type == "complete_task":
            done = True
            # No more emails to process
            
        # Compute reward
        accuracy = sum(self.classifications[eid] == self.ground_truth[eid] 
                      for eid in self.classifications if eid in self.ground_truth) / max(1, len(self.classifications))
        
        efficiency = max(0, 1.0 - self.step_count / self.max_steps)
        
        reward_info["accuracy"] = accuracy
        reward_info["efficiency"] = efficiency
        
        immediate_reward = (
            accuracy * 0.6 +
            efficiency * 0.3 +
            reward_info["safety"] * 0.1
        )
        
        self.trajectory_reward += immediate_reward
        
        return (
            next_observation,
            Reward(
                immediate_reward=immediate_reward,
                reward_components=reward_info,
                trajectory_reward=self.trajectory_reward,
                done=done
            ),
            done,
            {"action": action.action_type, "step": self.step_count}
        )

    def grade(self) -> float:
        """Grade email triage performance"""
        if not self.classifications:
            return 0.0
        
        # Accuracy component (60%)
        correct = sum(self.classifications[eid] == self.ground_truth[eid]
                     for eid in self.classifications if eid in self.ground_truth)
        accuracy_score = (correct / len(self.classifications)) * 0.6
        
        # Efficiency component (20%)
        efficiency_score = max(0, 1.0 - self.step_count / self.max_steps) * 0.2
        
        # Coverage component (20%)
        coverage_score = (len(self.classifications) / len(self.ground_truth)) * 0.2
        
        return accuracy_score + efficiency_score + coverage_score

    def _generate_emails(self) -> list:
        """Create synthetic emails for testing"""
        return [
            {
                "id": "email-001",
                "from": "ceo@meta.com",
                "subject": "Urgent: Board meeting in 1 hour",
                "body": "Need your report on Q1 metrics ASAP",
                "timestamp": "2024-01-15T09:30:00Z"
            },
            {
                "id": "email-002",
                "from": "colleague@meta.com",
                "subject": "FYI: Meeting notes attached",
                "body": "Here are the notes from today's standup",
                "timestamp": "2024-01-15T09:15:00Z"
            },
            {
                "id": "email-003",
                "from": "friend@personal.com",
                "subject": "Let's catch up this weekend",
                "body": "Want to grab coffee on Saturday?",
                "timestamp": "2024-01-15T08:45:00Z"
            },
            {
                "id": "email-004",
                "from": "spam@vendor.com",
                "subject": "CLICK HERE: Amazing offer!!!",
                "body": "Buy now and get 50% off...",
                "timestamp": "2024-01-15T08:00:00Z"
            },
            {
                "id": "email-005",
                "from": "manager@meta.com",
                "subject": "Action required: Code review deadline TODAY",
                "body": "PR #4521 needs approval before EOD",
                "timestamp": "2024-01-15T09:00:00Z"
            },
            {
                "id": "email-006",
                "from": "noreply@meta.com",
                "subject": "Your weekly digest",
                "body": "Here's what happened in your teams this week",
                "timestamp": "2024-01-14T18:00:00Z"
            }
        ]

    def _get_observation(self) -> Observation:
        """Get current observation"""
        if self.current_email_idx < len(self.emails):
            current = self.emails[self.current_email_idx]
        else:
            current = None
        
        return Observation(
            task_id=self.task_id,
            task_type=TaskType.EMAIL_TRIAGE,
            step_number=self.step_count,
            current_state={
                "total_emails": len(self.emails),
                "processed_count": len(self.processed_emails),
                "current_email": current,
                "classifications_so_far": self.classifications
            },
            available_actions=["classify_email", "fetch_next_email", "complete_task"],
            context=f"Processed {len(self.processed_emails)}/{len(self.emails)} emails"
        )


class CodeReviewTask(Task):
    """
    MEDIUM TASK: Automated code review
    
    Agent must:
    1. Identify style violations
    2. Spot potential bugs/security issues
    3. Suggest improvements
    4. Assess overall quality
    
    Success metrics:
    - F1 score on issue detection > 0.85
    - No false positives on critical issues
    - Reasonable efficiency
    """

    def __init__(self, task_id: str = "code_review_001"):
        super().__init__(task_id, difficulty="medium")
        
        self.code_samples = self._generate_code_samples()
        self.current_sample_idx = 0
        self.issues_found = []  # Detected issues
        self.max_steps = 15

        self.ground_truth = {
            "pr-001": {
                "style_issues": 3,
                "bugs": 1,
                "security": 0,
                "improvements": 2
            },
            "pr-002": {
                "style_issues": 1,
                "bugs": 0,
                "security": 1,
                "improvements": 1
            }
        }

    def reset(self) -> Observation:
        """Initialize code review task"""
        self.step_count = 0
        self.trajectory_reward = 0.0
        self.issues_found = []
        self.current_sample_idx = 0
        
        return Observation(
            task_id=self.task_id,
            task_type=TaskType.CODE_REVIEW,
            step_number=0,
            current_state={
                "total_prs": len(self.code_samples),
                "current_pr": self.code_samples[0]["id"],
                "code_snippet": self.code_samples[0]["code"],
                "changes": self.code_samples[0]["changes"]
            },
            available_actions=["detect_style_issue", "flag_bug", "flag_security",
                             "suggest_improvement", "approve_pr", "complete_review"],
            context="Code review: Analyze pull requests for issues"
        )

    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict]:
        """Process code review action"""
        self.step_count += 1
        
        reward_info = {
            "precision": 0.0,
            "recall": 0.0,
            "efficiency": 1.0,
            "false_positives": 0.0
        }
        
        done = False
        current_pr = self.code_samples[self.current_sample_idx]["id"]
        expected = self.ground_truth.get(current_pr, {})

        if action.action_type in ["detect_style_issue", "flag_bug", "flag_security", "suggest_improvement"]:
            issue = {
                "type": action.action_type,
                "description": action.parameters.get("description", ""),
                "confidence": action.confidence
            }
            self.issues_found.append(issue)
            
            # Simple grading: is this a real issue?
            issue_type_map = {
                "detect_style_issue": "style_issues",
                "flag_bug": "bugs",
                "flag_security": "security",
                "suggest_improvement": "improvements"
            }
            
            issue_category = issue_type_map[action.action_type]
            expected_count = expected.get(issue_category, 0)
            
            if expected_count > 0:
                reward_info["precision"] = 0.8  # Simplified
                reward_info["recall"] = 0.9

        elif action.action_type == "complete_review":
            done = True

        # Compute reward
        immediate_reward = (
            reward_info.get("precision", 0.0) * 0.4 +
            reward_info.get("recall", 0.0) * 0.4 +
            max(0, 1.0 - self.step_count / self.max_steps) * 0.2
        )
        
        self.trajectory_reward += immediate_reward

        next_obs = Observation(
            task_id=self.task_id,
            task_type=TaskType.CODE_REVIEW,
            step_number=self.step_count,
            current_state={
                "current_pr": current_pr,
                "issues_detected": len(self.issues_found),
                "step": self.step_count
            },
            available_actions=["detect_style_issue", "flag_bug", "flag_security",
                             "suggest_improvement", "approve_pr", "complete_review"],
            context=f"Detected {len(self.issues_found)} issues so far"
        )

        return (
            next_obs,
            Reward(
                immediate_reward=immediate_reward,
                reward_components=reward_info,
                trajectory_reward=self.trajectory_reward,
                done=done
            ),
            done,
            {"action": action.action_type, "issues_found": len(self.issues_found)}
        )

    def grade(self) -> float:
        """Grade code review performance"""
        if not self.issues_found:
            return 0.0
        
        current_pr = self.code_samples[self.current_sample_idx]["id"]
        expected = self.ground_truth.get(current_pr, {})
        total_expected = sum(expected.values())
        
        # Simplified scoring
        accuracy = min(1.0, len(self.issues_found) / max(1, total_expected))
        efficiency = max(0, 1.0 - self.step_count / self.max_steps)
        
        return accuracy * 0.7 + efficiency * 0.3

    def _generate_code_samples(self) -> list:
        return [
            {
                "id": "pr-001",
                "title": "Optimize email classifier",
                "code": """
def classify_email(email, model):
    text = email['body']
    tokens = text.split(' ')  # TODO: use proper tokenizer
    features = extract_features(tokens)
    logits = model(features)
    return logits
""",
                "changes": "+15 -8 lines"
            },
            {
                "id": "pr-002",
                "title": "Add user authentication",
                "code": """
async def authenticate_user(username: str, password: str):
    user = db.query(User).filter_by(username=username).first()
    if user and check_password(password, user.password_hash):
        return create_token(user.id)
    raise AuthError("Invalid credentials")
""",
                "changes": "+20 -0 lines"
            }
        ]


class DataCleaningTask(Task):
    """
    HARD TASK: Data cleaning and standardization
    
    Agent must:
    1. Identify data quality issues (missing values, duplicates, outliers)
    2. Apply appropriate cleaning strategies
    3. Maintain data integrity constraints
    4. Achieve target quality metrics
    
    Success metrics:
    - Data quality score > 0.92
    - No loss of critical information
    - Proper handling of edge cases
    """

    def __init__(self, task_id: str = "data_cleaning_001"):
        super().__init__(task_id, difficulty="hard")
        
        self.dataset = self._generate_dataset()
        self.cleaned_records = 0
        self.actions_taken = []
        self.max_steps = 25

        self.ground_truth = {
            "total_records": 100,
            "duplicates": 5,
            "missing_values": 12,
            "outliers": 3,
            "invalid_format": 8
        }

    def reset(self) -> Observation:
        """Initialize data cleaning task"""
        self.step_count = 0
        self.trajectory_reward = 0.0
        self.cleaned_records = 0
        self.actions_taken = []
        
        data_quality = self._assess_quality()
        
        return Observation(
            task_id=self.task_id,
            task_type=TaskType.DATA_CLEANING,
            step_number=0,
            current_state={
                "total_records": len(self.dataset),
                "quality_score": data_quality,
                "issues": self._detect_issues()
            },
            available_actions=["remove_duplicate", "fill_missing", "remove_outlier",
                             "reformat_field", "validate_constraints", "complete_cleaning"],
            context=f"Data cleaning: {len(self.dataset)} records, quality score {data_quality:.2f}"
        )

    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict]:
        """Process cleaning action"""
        self.step_count += 1
        
        reward_info = {
            "quality_improvement": 0.0,
            "data_integrity": 1.0,
            "efficiency": 1.0
        }
        
        done = False

        if action.action_type == "remove_duplicate":
            # Simulate removing duplicates
            self.cleaned_records += 1
            reward_info["quality_improvement"] = 0.05
            
        elif action.action_type == "fill_missing":
            self.cleaned_records += 1
            reward_info["quality_improvement"] = 0.03
            
        elif action.action_type == "remove_outlier":
            self.cleaned_records += 1
            reward_info["quality_improvement"] = 0.04
            
        elif action.action_type == "reformat_field":
            self.cleaned_records += 1
            reward_info["quality_improvement"] = 0.02
            
        elif action.action_type == "complete_cleaning":
            done = True

        self.actions_taken.append(action.action_type)
        
        # Compute reward
        efficiency = max(0, 1.0 - self.step_count / self.max_steps)
        
        immediate_reward = (
            reward_info["quality_improvement"] * 0.5 +
            reward_info["data_integrity"] * 0.3 +
            efficiency * 0.2
        )
        
        self.trajectory_reward += immediate_reward

        next_quality = self._assess_quality()
        
        next_obs = Observation(
            task_id=self.task_id,
            task_type=TaskType.DATA_CLEANING,
            step_number=self.step_count,
            current_state={
                "total_records": len(self.dataset),
                "quality_score": next_quality,
                "cleaned_count": self.cleaned_records
            },
            available_actions=["remove_duplicate", "fill_missing", "remove_outlier",
                             "reformat_field", "validate_constraints", "complete_cleaning"],
            context=f"Quality: {next_quality:.2f}, Cleaned: {self.cleaned_records}"
        )

        return (
            next_obs,
            Reward(
                immediate_reward=immediate_reward,
                reward_components=reward_info,
                trajectory_reward=self.trajectory_reward,
                done=done
            ),
            done,
            {"cleaned": self.cleaned_records, "quality": next_quality}
        )

    def grade(self) -> float:
        """Grade data cleaning quality"""
        final_quality = self._assess_quality()
        efficiency = max(0, 1.0 - self.step_count / self.max_steps)
        
        return final_quality * 0.8 + efficiency * 0.2

    def _generate_dataset(self) -> list:
        """Create synthetic dataset with quality issues"""
        records = []
        for i in range(100):
            record = {
                "id": i,
                "name": f"user_{i}",
                "email": f"user{i}@example.com",
                "age": 25 + (i % 50),
                "country": ["US", "UK", "CA", "DE"][i % 4]
            }
            records.append(record)
        
        # Add quality issues
        # Duplicates (indices 5-9)
        for i in range(5, 10):
            records.append(records[i].copy())
        
        # Missing values
        for i in [15, 27, 38, 42, 51, 63, 74, 85, 91, 96]:
            if i < len(records):
                records[i]["email"] = None
        
        return records

    def _assess_quality(self) -> float:
        """Calculate data quality score 0.0-1.0"""
        # Simplified quality calculation
        base_quality = 0.65 + (self.cleaned_records / 50) * 0.35
        return min(1.0, base_quality)

    def _detect_issues(self) -> Dict[str, int]:
        """Identify data quality problems"""
        return {
            "duplicates": self.ground_truth["duplicates"],
            "missing_values": self.ground_truth["missing_values"],
            "outliers": self.ground_truth["outliers"],
            "invalid_format": self.ground_truth["invalid_format"]
        }


# ==================== OPENENV ENVIRONMENT ====================

class AutonomousWorkOSEnv:
    """
    OpenEnv-compliant Autonomous Work OS Environment
    
    Task: Given real-world workflows (email triage, code review, data cleaning),
    agents must autonomously execute complex tasks with minimal human supervision.
    
    Difficulty progression:
    - Easy (Email): Single classification task
    - Medium (Code Review): Multi-issue detection
    - Hard (Data Cleaning): Complex multi-step process with constraints
    """

    def __init__(self, task_type: str = "email_triage"):
        """Initialize environment with specified task"""
        
        self.task_type = task_type
        
        if task_type == "email_triage":
            self.task = EmailTriageTask()
        elif task_type == "code_review":
            self.task = CodeReviewTask()
        elif task_type == "data_cleaning":
            self.task = DataCleaningTask()
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    def reset(self) -> Observation:
        """Reset environment and return initial observation"""
        return self.task.reset()
    
    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict[str, Any]]:
        """
        Execute one step of environment
        
        Args:
            action: Agent's chosen action
            
        Returns:
            observation: Current state
            reward: Reward signal
            done: Episode termination flag
            info: Additional info for debugging
        """
        observation, reward, done, info = self.task.step(action)
        
        return observation, reward, done, info
    
    def state(self) -> Dict[str, Any]:
        """Return current environment state"""
        return {
            "task_id": self.task.task_id,
            "task_type": self.task_type,
            "step_count": self.task.step_count,
            "trajectory_reward": self.task.trajectory_reward,
            "history": self.task.history
        }
    
    def grade(self) -> float:
        """Get final reward for completed task (0.0-1.0)"""
        return self.task.grade()


"""
OpenEnv Specification Compliance:

1. Typed Models ✓
   - Observation: TaskID, ActionSpace, State (Dict)
   - Action: ActionType, Parameters, Confidence
   - Reward: Immediate + Trajectory + Done flag

2. Interface Implementation ✓
   - step(action) → (observation, reward, done, info)
   - reset() → observation
   - state() → current_state_dict
   - grade() → float (0.0-1.0)

3. Three Tasks ✓
   - Email Triage (EASY)
   - Code Review (MEDIUM)
   - Data Cleaning (HARD)

4.Meaningful Rewards ✓
   - Immediate rewards for progress
   - Trajectory rewards accumulate
   - Penalties for inefficiency and errors
   - Task-specific grading function

5. Real-World Tasks ✓
   - Email automation (Meta/Gmail use case)
   - Code review (GitHub/internal repos)
   - Data cleaning (Data ML pipelines)
"""
