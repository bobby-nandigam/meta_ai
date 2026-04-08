"""
Base Agent classes and orchestration framework
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import asyncio
import logging
from datetime import datetime
import json

from ..core.models import (
    Agent, Decision, ExecutionResult, ReviewResult,
    ExecutionPlan, ExecutionStep, AgentType, TaskStatus,
    AuditLog, LearningSignal, TaskSpec
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agent types"""
    
    def __init__(self, agent_id: str, agent_type: AgentType, name: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.name = name
        self.status = "idle"
        self.processed_tasks = 0
        self.error_rate = 0.0
        self.last_heartbeat = datetime.now()
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent's primary responsibility"""
        pass
    
    async def heartbeat(self):
        """Signal that agent is alive"""
        self.last_heartbeat = datetime.now()
    
    def update_metrics(self, success: bool):
        """Update performance metrics"""
        self.processed_tasks += 1
        if not success:
            self.error_rate = (self.error_rate * (self.processed_tasks - 1) + 1.0) / self.processed_tasks


class PlannerAgent(BaseAgent):
    """Decomposes tasks into execution plans"""
    
    def __init__(self, agent_id: str, llm_client):
        super().__init__(agent_id, AgentType.PLANNER, "Planner")
        self.llm = llm_client
    
    async def execute(self, task_spec: Dict[str, Any]) -> ExecutionPlan:
        """
        Takes a high-level task and returns a detailed execution plan
        
        Args:
            task_spec: User-provided task description
            
        Returns:
            ExecutionPlan with decomposed steps
        """
        logger.info(f"Planning task: {task_spec.get('title')}")
        
        # Generate plan using LLM reasoning
        prompt = self._build_planning_prompt(task_spec)
        plan_json = await self.llm.generate(
            prompt=prompt,
            temperature=0.3,  # Low temperature for deterministic planning
            max_tokens=2000
        )
        
        # Parse and structure plan
        plan = self._parse_plan_output(plan_json, task_spec)
        
        self.update_metrics(success=True)
        return plan
    
    def _build_planning_prompt(self, task_spec: Dict[str, Any]) -> str:
        """Generate planning prompt for LLM"""
        return f"""
You are a task planning agent for an AI automation system.

Task: {task_spec.get('title')}
Description: {task_spec.get('description')}
Domain: {task_spec.get('domain')}
Constraints: {task_spec.get('constraints', [])}
Priority: {task_spec.get('priority', 5)}/10

Generate a detailed execution plan in JSON format with:
1. Decomposed steps (ordered list)
2. For each step: action_type, tool_name, function_name, parameters
3. Dependencies between steps
4. Estimated duration and cost
5. Risk assessment

Output pure JSON only.
"""
    
    def _parse_plan_output(self, plan_json: str, task_spec: Dict) -> ExecutionPlan:
        """Parse LLM output into ExecutionPlan"""
        try:
            plan_data = json.loads(plan_json)
            
            # Create execution plan
            return ExecutionPlan(
                task_id=task_spec['task_id'],
                steps=[ExecutionStep(**step) for step in plan_data.get('steps', [])],
                estimated_duration=plan_data.get('estimated_duration', 60),
                estimated_cost=plan_data.get('estimated_cost', 0.1),
                risk_level=plan_data.get('risk_level', 'medium'),
                reasoning=plan_data.get('reasoning', '')
            )
        except Exception as e:
            logger.error(f"Failed to parse plan: {e}")
            # Return minimal plan
            return ExecutionPlan(
                task_id=task_spec['task_id'],
                steps=[],
                estimated_duration=60,
                estimated_cost=0.1
            )


class ExecutorAgent(BaseAgent):
    """Executes individual actions using tools"""
    
    def __init__(self, agent_id: str, tool_registry):
        super().__init__(agent_id, AgentType.EXECUTOR, "Executor")
        self.tool_registry = tool_registry
    
    async def execute(self, step: ExecutionStep) -> ExecutionResult:
        """
        Execute a single step using available tools
        
        Args:
            step: Execution step to perform
            
        Returns:
            ExecutionResult with outcome
        """
        logger.info(f"Executing step {step.step_id}: {step.action_type}")
        
        start_time = datetime.now()
        retry_count = 0
        
        while retry_count <= step.retries:
            try:
                # Get appropriate tool
                tool = self.tool_registry.get_tool(step.tool_name)
                
                # Execute function
                result = await tool.call(
                    function_name=step.function_name,
                    parameters=step.parameters,
                    timeout=step.timeout_seconds
                )
                
                # Success
                duration = (datetime.now() - start_time).total_seconds()
                self.update_metrics(success=True)
                
                return ExecutionResult(
                    step_id=step.step_id,
                    task_id=step.plan_id,  # derived from step
                    status=TaskStatus.COMPLETED,
                    output=result,
                    duration_seconds=duration,
                    retry_count=retry_count
                )
                
            except Exception as e:
                retry_count += 1
                logger.warning(f"Attempt {retry_count} failed for {step.step_id}: {e}")
                
                if retry_count <= step.retries:
                    # Exponential backoff
                    await asyncio.sleep(2 ** retry_count)
                else:
                    # All retries exhausted
                    duration = (datetime.now() - start_time).total_seconds()
                    self.update_metrics(success=False)
                    
                    return ExecutionResult(
                        step_id=step.step_id,
                        task_id=step.plan_id,
                        status=TaskStatus.FAILED,
                        error=str(e),
                        error_type=self._classify_error(e),
                        duration_seconds=duration,
                        retry_count=retry_count
                    )
    
    def _classify_error(self, error: Exception) -> str:
        """Classify error type for handling"""
        error_str = str(error).lower()
        if "rate" in error_str:
            return "ratelimit"
        elif "auth" in error_str or "permission" in error_str:
            return "auth"
        elif "timeout" in error_str:
            return "timeout"
        else:
            return "data_error"


class ReviewerAgent(BaseAgent):
    """Validates execution quality and safety"""
    
    def __init__(self, agent_id: str, safety_checker):
        super().__init__(agent_id, AgentType.REVIEWER, "Reviewer")
        self.safety_checker = safety_checker
    
    async def execute(self, decision: Decision) -> ReviewResult:
        """
        Review a decision for safety and quality
        
        Args:
            decision: Decision to review
            
        Returns:
            ReviewResult with approval/rejection
        """
        logger.info(f"Reviewing decision {decision.decision_id}")
        
        # Run safety checks
        safety_checks = await self.safety_checker.run_all_checks(decision)
        
        # Compute confidence
        confidence = self._compute_confidence(decision, safety_checks)
        
        # Determine if escalation needed
        requires_escalation = self._should_escalate(confidence, safety_checks)
        
        return ReviewResult(
            decision_id=decision.decision_id,
            approved=confidence > 0.7,
            confidence=confidence,
            safety_checks=safety_checks,
            policy_violations=self._check_policies(decision),
            explanation=self._generate_explanation(confidence, safety_checks),
            requires_escalation=requires_escalation
        )
    
    def _compute_confidence(self, decision: Decision, safety_checks: Dict[str, bool]) -> float:
        """Compute overall confidence score"""
        # Base confidence from decision
        base = decision.confidence * 0.6
        
        # Safety check score
        passed = sum(1 for v in safety_checks.values() if v)
        safety_score = (passed / len(safety_checks)) * 0.4
        
        return base + safety_score
    
    def _should_escalate(self, confidence: float, safety_checks: Dict) -> bool:
        """Check if human escalation is needed"""
        if confidence < 0.7:
            return True
        if any(not v for v in safety_checks.values()):
            return True
        return False
    
    def _check_policies(self, decision: Decision) -> List[str]:
        """Check for policy violations"""
        violations = []
        # TODO: Implement policy checks
        return violations
    
    def _generate_explanation(self, confidence: float, safety_checks: Dict) -> str:
        """Generate human-readable explanation"""
        if confidence > 0.9:
            return "Very high confidence - approved"
        elif confidence > 0.7:
            return "Good confidence - approved with monitoring"
        else:
            return "Low confidence - requires escalation"


class MemoryAgent(BaseAgent):
    """Manages user context and learning"""
    
    def __init__(self, agent_id: str, vector_db, cache_store):
        super().__init__(agent_id, AgentType.MEMORY, "Memory")
        self.vector_db = vector_db
        self.cache = cache_store
    
    async def execute(self, user_id: str, query: str) -> Dict[str, Any]:
        """Retrieve relevant context for a user"""
        
        # 1. Check cache first
        cached = await self.cache.get(f"user_context:{user_id}")
        if cached:
            return cached
        
        # 2. Search vector database for similar memories
        results = await self.vector_db.similarity_search(
            query=query,
            top_k=5,
            filter={"user_id": user_id}
        )
        
        # 3. Compile context from results
        context = {
            "user_id": user_id,
            "similar_cases": [r['metadata'] for r in results],
            "recommendations": self._generate_recommendations(results)
        }
        
        # 4. Cache for next 1 hour
        await self.cache.set(f"user_context:{user_id}", context, ttl=3600)
        
        return context
    
    async def learn(self, learning_signal: LearningSignal):
        """Store new learning signal for model improvement"""
        
        # Create embedding for semantic storage
        embedding = await self._embed(learning_signal.input_features)
        
        # Store in vector DB
        await self.vector_db.upsert({
            "user_id": learning_signal.user_id,
            "embedding": embedding,
            "metadata": {
                "input": learning_signal.input_features,
                "outcome": learning_signal.actual_outcome,
                "reward": learning_signal.reward,
                "timestamp": learning_signal.timestamp
            }
        })
        
        logger.info(f"Learned from signal: {learning_signal.signal_id}")
    
    async def _embed(self, data: Dict) -> List[float]:
        """Generate embedding for data"""
        # TODO: Call embedding service
        return [0.0] * 384  # Sentence-Transformers dimension


class MonitorAgent(BaseAgent):
    """Monitors system health and optimization"""
    
    def __init__(self, agent_id: str, metrics_store):
        super().__init__(agent_id, AgentType.MONITOR, "Monitor")
        self.metrics = metrics_store
    
    async def execute(self) -> Dict[str, Any]:
        """Check system health"""
        
        health_report = {
            "timestamp": datetime.now(),
            "status": "healthy",
            "task_queue_depth": await self.metrics.get("queue_depth"),
            "avg_latency_ms": await self.metrics.get("avg_latency"),
            "error_rate": await self.metrics.get("error_rate"),
            "active_agents": await self.metrics.get("active_agents"),
            "alerts": []
        }
        
        # Check thresholds
        if health_report["task_queue_depth"] > 5000:
            health_report["alerts"].append("High task queue depth")
            health_report["status"] = "warning"
        
        if health_report["error_rate"] > 0.05:
            health_report["alerts"].append("High error rate")
            health_report["status"] = "warning"
        
        return health_report


# ==================== Orchestrator ====================

class Orchestrator:
    """Coordinates all agents"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.message_bus = MessageBus()
    
    def register_agent(self, agent: BaseAgent):
        """Register an agent"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.name}")
    
    async def submit_task(self, task_spec: Dict[str, Any]):
        """Submit a task for processing"""
        await self.task_queue.put(task_spec)
        logger.info(f"Task submitted: {task_spec.get('task_id')}")
    
    async def process_tasks(self):
        """Main orchestration loop"""
        while True:
            task = await self.task_queue.get()
            
            try:
                # 1. Planning phase
                planner = self._get_agent(AgentType.PLANNER)
                plan = await planner.execute(task)
                self.message_bus.publish("plan_created", plan)
                
                # 2. Execution phase
                for step in plan.steps:
                    executor = self._get_agent(AgentType.EXECUTOR)
                    result = await executor.execute(step)
                    self.message_bus.publish("step_completed", result)
                
                # 3. Review phase
                reviewer = self._get_agent(AgentType.REVIEWER)
                # Review each decision
                
                logger.info(f"Task {task['task_id']} completed")
                
            except Exception as e:
                logger.error(f"Task processing failed: {e}")
            
            finally:
                self.task_queue.task_done()
    
    def _get_agent(self, agent_type: AgentType) -> BaseAgent:
        """Get an agent of specific type"""
        for agent in self.agents.values():
            if agent.agent_type == agent_type and agent.status == "idle":
                return agent
        raise RuntimeError(f"No available agent of type {agent_type}")


class MessageBus:
    """Event-driven message passing between agents"""
    
    def __init__(self):
        self.subscribers: Dict[str, List] = {}
    
    def subscribe(self, event_type: str, callback):
        """Subscribe to event"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
    
    def publish(self, event_type: str, data: Any):
        """Publish event"""
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                asyncio.create_task(callback(data))
