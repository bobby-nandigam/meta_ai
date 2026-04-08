#!/usr/bin/env python3
"""
Baseline Inference Script for Autonomous Work OS
Uses OpenAI API to evaluate agent performance
Credentials read from HF_TOKEN environment variable
"""

import os
import json
import sys
from typing import Dict, List
from datetime import datetime

from openai import OpenAI
from pydantic import BaseModel

# Import environment and models
from environments.openenv import (
    AutonomousWorkOSEnv, Observation, Action, Reward, 
    TaskType
)

# Environment variables
API_BASE_URL = os.getenv("API_BASE_URL", "https://api-inference.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    raise ValueError(
        "HF_TOKEN not found. Please set HF_TOKEN environment variable"
    )


class BaselineConfig(BaseModel):
    """Configuration for baseline evaluation"""
    model_name: str = MODEL_NAME
    api_base_url: str = API_BASE_URL
    temperature: float = 0.3
    max_tokens: int = 500
    num_episodes: int = 3
    timeout_seconds: int = 30


class InferenceClient:
    """Client for calling LLM inference via OpenAI"""
    
    def __init__(self, api_key: str = None, api_base: str = None, model: str = None):
        """Initialize OpenAI client"""
        self.api_key = api_key or HF_TOKEN
        self.api_base = api_base or API_BASE_URL
        self.model = model or MODEL_NAME
        
        if not self.api_key:
            raise ValueError("API key is required")
        
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_base)
    
    def call_model(self, prompt: str) -> str:
        """Call inference model via OpenAI client"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
                timeout=30
            )
            return response.choices[0].message.content
        except Exception as e:
            sys.stdout.write(f"STEP Inference call failed: {e}\n")
            sys.stdout.flush()
            raise


class AutonomousAgent:
    """
    Baseline agent that uses LLM reasoning to solve tasks
    Uses few-shot prompting to guide decision-making
    """
    
    def __init__(self, inference_client: InferenceClient):
        self.client = inference_client
        self.action_history = []
    
    def decide_action(self, observation: Observation) -> Action:
        """
        Decide next action based on observation
        Uses LLM reasoning for intelligent decision-making
        """
        prompt = self._build_decision_prompt(observation)
        
        sys.stdout.write(f"STEP Agent thinking at step {observation.step_number}\n")
        sys.stdout.flush()
        
        # Call LLM for decision
        response = self.client.call_model(prompt)
        
        # Parse response into action
        action = self._parse_action_response(response, observation)
        
        self.action_history.append({
            "step": observation.step_number,
            "action": action.action_type,
            "confidence": action.confidence
        })
        
        return action
    
    def _build_decision_prompt(self, observation: Observation) -> str:
        """Build few-shot prompt for decision-making"""
        
        task_type = observation.task_type.value
        
        if task_type == "email_triage":
            return self._email_triage_prompt(observation)
        elif task_type == "code_review":
            return self._code_review_prompt(observation)
        elif task_type == "data_cleaning":
            return self._data_cleaning_prompt(observation)
        else:
            return ""
    
    def _email_triage_prompt(self, observation: Observation) -> str:
        """Few-shot prompt for email triage"""
        return f"""
You are an AI agent for email automation. Analyze the email below and decide the action.

Current Email:
{json.dumps(observation.current_state.get('current_email', {}), indent=2)}

Context: {observation.context}
Available Actions: {observation.available_actions}

## Few-Shot Examples:

Example 1:
Email: From: ceo@meta.com, Subject: "Urgent: Board meeting"
Decision: {{"action_type": "classify_email", "confidence": 0.95, "category": "work_critical"}}

Example 2:
Email: From: friend@personal.com, Subject: "Let's catch up"
Decision: {{"action_type": "classify_email", "confidence": 0.90, "category": "personal"}}

Example 3:
Email: From: spam@vendor.com, Subject: "CLICK HERE: Amazing offer!!!"
Decision: {{"action_type": "classify_email", "confidence": 0.98, "category": "spam"}}

Now analyze the current email and respond with JSON only:
{{
  "action_type": "classify_email",
  "category": "[work_critical|work_routine|personal|spam]",
  "confidence": [0.0-1.0],
  "reasoning": "brief explanation"
}}
"""
    
    def _code_review_prompt(self, observation: Observation) -> str:
        """Few-shot prompt for code review"""
        return f"""
You are an AI code reviewer. Analyze the code change and identify issues.

PR: {observation.current_state.get('current_pr')}
Code Diff:
{observation.current_state.get('code_snippet', '')}

Available Actions: {observation.available_actions}

## Few-Shot Examples:

Example 1: Missing type hints
Issue: Function parameters lack type annotations
Decision: {{"action_type": "detect_style_issue", "description": "Missing type hints"}}

Example 2: Security vulnerability
Issue: Hardcoded credentials in code
Decision: {{"action_type": "flag_security", "description": "Hardcoded API key"}}

Now analyze and respond with JSON:
{{
  "action_type": "[detect_style_issue|flag_bug|flag_security|suggest_improvement|approve_pr]",
  "description": "detailed finding",
  "confidence": [0.0-1.0],
  "severity": "[low|medium|high]"
}}
"""
    
    def _data_cleaning_prompt(self, observation: Observation) -> str:
        """Few-shot prompt for data cleaning"""
        return f"""
You are a data quality engineer. Analyze the dataset and decide cleaning action.

Dataset State:
{json.dumps(observation.current_state, indent=2)}

Issues Detected:
{json.dumps(observation.current_state.get('issues', {}), indent=2)}

Available Actions: {observation.available_actions}

## Few-Shot Examples:

Example 1: Duplicate rows
Issue: ID 5 and 50 have identical data
Decision: {{"action_type": "remove_duplicate", "record_id": "5"}}

Example 2: Missing values
Issue: Email field is NULL in 12 records
Decision: {{"action_type": "fill_missing", "field": "email", "strategy": "placeholder"}}

Now analyze and respond with JSON:
{{
  "action_type": "[remove_duplicate|fill_missing|remove_outlier|reformat_field|validate_constraints|complete_cleaning]",
  "target_records": "which records to affect",
  "strategy": "approach to take",
  "confidence": [0.0-1.0]
}}
"""
    
    def _parse_action_response(self, response: str, observation: Observation) -> Action:
        """Parse LLM response into Action object"""
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                action_json = response[json_start:json_end]
                action_data = json.loads(action_json)
            else:
                action_data = {}
            
            # Map to valid actions for task
            action_type = action_data.get('action_type')
            if action_type not in observation.available_actions:
                action_type = observation.available_actions[0]
            
            return Action(
                action_type=action_type,
                parameters=action_data.get('parameters', {}),
                agent_reasoning=action_data.get('reasoning', ''),
                confidence=float(action_data.get('confidence', 0.5))
            )
            
        except Exception as e:
            logger.error(f"Failed to parse action: {e}")
            # Fallback to first available action
            return Action(
                action_type=observation.available_actions[0],
                parameters={},
                agent_reasoning="Fallback action due to parsing error",
                confidence=0.3
            )


def evaluate_task(
    task_type: str, 
    inference_client: InferenceClient,
    num_episodes: int = 3
) -> Dict[str, float]:
    """
    Evaluate agent performance on a specific task
    
    Returns:
        scores: Dict with episode scores and average
    """
    
    sys.stdout.write(f"\nSTART Evaluating task: {task_type}\n")
    sys.stdout.flush()
    
    agent = AutonomousAgent(inference_client)
    episode_scores = []
    
    for episode in range(num_episodes):
        sys.stdout.write(f"STEP Episode {episode + 1}/{num_episodes}\n")
        sys.stdout.flush()
        
        # Initialize environment
        env = AutonomousWorkOSEnv(task_type=task_type)
        observation = env.reset()
        
        done = False
        step_count = 0
        max_steps = 20
        
        while not done and step_count < max_steps:
            # Agent decides action
            action = agent.decide_action(observation)
            sys.stdout.write(f"STEP Action: {action.action_type} (confidence: {action.confidence:.2f})\n")
            sys.stdout.flush()
            
            # Execute action
            observation, reward, done, info = env.step(action)
            
            sys.stdout.write(f"STEP Reward: {reward.immediate_reward:.3f} | "
                       f"Trajectory: {reward.trajectory_reward:.3f}\n")
            sys.stdout.flush()
            
            step_count += 1
        
        # Grade episode
        score = env.grade()
        episode_scores.append(score)
        sys.stdout.write(f"STEP Episode {episode + 1} Final Score: {score:.4f}\n")
        sys.stdout.flush()
    
    # Compute statistics
    avg_score = sum(episode_scores) / len(episode_scores)
    max_score = max(episode_scores)
    min_score = min(episode_scores)
    
    sys.stdout.write(f"END Task {task_type} completed - Average Score: {avg_score:.4f}\n")
    sys.stdout.flush()
    
    return {
        "task_type": task_type,
        "num_episodes": num_episodes,
        "scores": episode_scores,
        "average": avg_score,
        "max": max_score,
        "min": min_score,
        "std_dev": (sum((s - avg_score) ** 2 for s in episode_scores) / len(episode_scores)) ** 0.5
    }


def main():
    """Main evaluation loop"""
    
    sys.stdout.write("START Autonomous Work OS Baseline Evaluation\n")
    sys.stdout.flush()
    sys.stdout.write(f"STEP Timestamp: {datetime.now().isoformat()}\n")
    sys.stdout.flush()
    
    config = BaselineConfig()
    sys.stdout.write(f"STEP Configuration: model={config.model_name}, api_base={config.api_base_url}\n")
    sys.stdout.flush()
    
    # Initialize inference client
    try:
        client = InferenceClient()
        sys.stdout.write("STEP Inference client initialized with HF_TOKEN\n")
        sys.stdout.flush()
    except ValueError as e:
        sys.stdout.write(f"STEP Failed to initialize client: {e}\n")
        sys.stdout.flush()
        return
    
    # Evaluate all tasks
    all_results = {
        "timestamp": datetime.now().isoformat(),
        "config": config.dict(),
        "task_results": []
    }
    
    task_types = ["email_triage", "code_review", "data_cleaning"]
    
    for task_type in task_types:
        try:
            result = evaluate_task(
                task_type=task_type,
                inference_client=client,
                num_episodes=config.num_episodes
            )
            all_results["task_results"].append(result)
            
        except Exception as e:
            sys.stdout.write(f"STEP Task evaluation failed for {task_type}: {e}\n")
            sys.stdout.flush()
            all_results["task_results"].append({
                "task_type": task_type,
                "error": str(e)
            })
    
    # Aggregate results
    all_results["summary"] = {
        "overall_average": (
            sum(r["average"] for r in all_results["task_results"] 
                if "average" in r) / 
            len([r for r in all_results["task_results"] if "average" in r])
        ),
        "difficulty_levels": {
            "easy": 0.0,  # Email triage
            "medium": 0.0,  # Code review
            "hard": 0.0  # Data cleaning
        }
    }
    
    # Print results
    sys.stdout.write("\n" + "="*60 + "\n")
    sys.stdout.write("BASELINE EVALUATION RESULTS\n")
    sys.stdout.write("="*60 + "\n")
    sys.stdout.flush()
    
    for result in all_results["task_results"]:
        if "error" in result:
            sys.stdout.write(f"\n{result['task_type']}: ERROR\n")
            sys.stdout.write(f"  {result['error']}\n")
        else:
            sys.stdout.write(f"\n{result['task_type']}:\n")
            sys.stdout.write(f"  Episodes: {result['num_episodes']}\n")
            sys.stdout.write(f"  Average Score: {result['average']:.4f}\n")
            sys.stdout.write(f"  Max Score: {result['max']:.4f}\n")
            sys.stdout.write(f"  Min Score: {result['min']:.4f}\n")
            sys.stdout.write(f"  Std Dev: {result['std_dev']:.4f}\n")
        sys.stdout.flush()
    
    sys.stdout.write(f"\nOverall Average: {all_results['summary']['overall_average']:.4f}\n")
    sys.stdout.write("="*60 + "\n")
    sys.stdout.flush()
    
    # Save results
    results_file = "evaluation_results.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)
    sys.stdout.write(f"STEP Results saved to {results_file}\n")
    sys.stdout.flush()
    
    sys.stdout.write("END Evaluation complete\n")
    sys.stdout.flush()
    
    return all_results

if __name__ == "__main__":
    main()
