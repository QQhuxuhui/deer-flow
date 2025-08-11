"""
Graph Utility Functions for DeerFlow

Provides common utility functions for graph operations and state management.
"""

from typing import Optional
from langchain_core.runnables import RunnableConfig
from src.config.configuration import Configuration
from .types import State


def get_current_step(state: State) -> Optional[str]:
    """
    Get the current step from the state.
    
    Args:
        state: The current state of the graph
        
    Returns:
        Current step identifier or None if not available
    """
    current_plan = state.get("current_plan")
    if not current_plan or not hasattr(current_plan, 'steps'):
        return None
        
    # Find the current step being executed
    for step in current_plan.steps:
        if not getattr(step, 'execution_res', None):
            return getattr(step, 'step_type', None)
            
    return None


def get_configuration(config: RunnableConfig) -> Configuration:
    """
    Get DeerFlow configuration from RunnableConfig.
    
    Args:
        config: LangChain RunnableConfig object
        
    Returns:
        DeerFlow Configuration instance
    """
    return Configuration.from_runnable_config(config)


def update_step_result(state: State, step_result: str) -> State:
    """
    Update the execution result for the current step.
    
    Args:
        state: Current state
        step_result: Result of step execution
        
    Returns:
        Updated state
    """
    current_plan = state.get("current_plan")
    if current_plan and hasattr(current_plan, 'steps'):
        for step in current_plan.steps:
            if not getattr(step, 'execution_res', None):
                step.execution_res = step_result
                break
    
    return state