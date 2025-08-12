# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from src.prompts.planner_model import StepType

from .types import State
from .nodes import (
    coordinator_node,
    planner_node,
    reporter_node,
    research_team_node,
    researcher_node,
    coder_node,
    human_feedback_node,
    background_investigation_node,
)
from .data_nodes import data_analysis_node
from .intelligent_router import (
    intelligent_router_node,
    data_analysis_workflow_node,
    traditional_research_workflow_node,
    hybrid_workflow_node
)
from .hybrid_workflow import (
    hybrid_planner_node,
    hybrid_executor_node,
    hybrid_coordinator_node
)


def continue_to_running_research_team(state: State):
    """Enhanced routing logic for traditional research workflow."""
    current_plan = state.get("current_plan")
    if not current_plan or not current_plan.steps:
        return "planner"

    if all(step.execution_res for step in current_plan.steps):
        return "planner"

    # Find first incomplete step
    incomplete_step = None
    for step in current_plan.steps:
        if not step.execution_res:
            incomplete_step = step
            break

    if not incomplete_step:
        return "planner"

    if incomplete_step.step_type == StepType.RESEARCH:
        return "researcher"
    if incomplete_step.step_type == StepType.PROCESSING:
        return "coder"
    if incomplete_step.step_type == StepType.DATA_ANALYSIS:
        return "data_analyst"
    return "planner"


def continue_to_hybrid_execution(state: State):
    """Routing logic for hybrid workflow execution."""
    current_plan = state.get("current_plan")
    if not current_plan or not current_plan.steps:
        return "hybrid_planner"

    # Check if all steps are completed
    if all(step.execution_res for step in current_plan.steps):
        return "reporter"  # Use reporter instead of report_writing

    # Find first incomplete step
    incomplete_step = None
    for step in current_plan.steps:
        if not step.execution_res:
            incomplete_step = step
            break

    if not incomplete_step:
        return "reporter"

    # Route based on step type
    if incomplete_step.step_type == StepType.RESEARCH:
        return "researcher"
    elif incomplete_step.step_type == StepType.PROCESSING:
        # Check if this is a synthesis/integration step
        if any(keyword in incomplete_step.description.lower() 
               for keyword in ["整合", "综合", "结合", "汇总"]):
            return "hybrid_coordinator"
        else:
            return "coder"
    elif incomplete_step.step_type == StepType.DATA_ANALYSIS:
        return "data_analyst"
    else:
        return "coder"


def get_return_destination(state: State):
    """Determine where agents should return based on workflow type."""
    workflow_type = state.get("workflow_type", "traditional_research")
    
    if workflow_type == "hybrid":
        return "hybrid_executor"
    else:
        return "research_team"


def _build_base_graph():
    """Build and return the enhanced state graph with intelligent routing."""
    builder = StateGraph(State)
    
    # Entry point
    builder.add_edge(START, "coordinator")
    
    # Core nodes
    builder.add_node("coordinator", coordinator_node)
    
    # Intelligent routing system
    builder.add_node("intelligent_router", intelligent_router_node)
    
    # Workflow-specific nodes
    builder.add_node("data_analysis_workflow", data_analysis_workflow_node)
    builder.add_node("traditional_research_workflow", traditional_research_workflow_node)
    builder.add_node("hybrid_workflow", hybrid_workflow_node)
    
    # Traditional DeerFlow nodes
    builder.add_node("background_investigator", background_investigation_node)
    builder.add_node("planner", planner_node)
    builder.add_node("research_team", research_team_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("coder", coder_node)
    builder.add_node("data_analyst", data_analysis_node)
    builder.add_node("human_feedback", human_feedback_node)
    
    # Hybrid workflow nodes
    builder.add_node("hybrid_planner", hybrid_planner_node)
    builder.add_node("hybrid_executor", hybrid_executor_node)
    builder.add_node("hybrid_coordinator", hybrid_coordinator_node)
    
    # Reporter node
    builder.add_node("reporter", reporter_node)
    
    # Main routing flow
    builder.add_edge("coordinator", "intelligent_router")
    
    # Router to workflow connections - using conditional edges for proper routing
    builder.add_conditional_edges(
        "intelligent_router",
        lambda state: state.get("intent_classification", {}).get("workflow_type", "research"),
        {
            "data_analysis": "data_analysis_workflow",
            "research": "traditional_research_workflow", 
            "hybrid": "hybrid_workflow"
        }
    )
    
    # Workflow-specific routing
    builder.add_edge("traditional_research_workflow", "background_investigator")
    builder.add_edge("hybrid_workflow", "hybrid_planner")
    
    # Traditional research flow
    builder.add_edge("background_investigator", "planner")
    builder.add_conditional_edges(
        "research_team",
        continue_to_running_research_team,
        ["planner", "researcher", "coder", "data_analyst"],
    )
    
    # Hybrid workflow execution
    builder.add_conditional_edges(
        "hybrid_executor",
        continue_to_hybrid_execution,
        ["researcher", "coder", "data_analyst", "hybrid_coordinator", "reporter"]
    )
    
    # Dynamic return paths based on workflow type
    builder.add_conditional_edges(
        "researcher",
        get_return_destination,
        ["research_team", "hybrid_executor"]
    )
    
    builder.add_conditional_edges(
        "coder", 
        get_return_destination,
        ["research_team", "hybrid_executor"]
    )
    
    builder.add_conditional_edges(
        "data_analyst",
        get_return_destination, 
        ["research_team", "hybrid_executor"]
    )
    
    # Hybrid workflow return paths
    builder.add_edge("hybrid_coordinator", "hybrid_executor")
    
    # Reporting flows
    builder.add_edge("data_analysis_workflow", "reporter")  # Direct data analysis
    builder.add_edge("planner", "reporter")                # Traditional research complete
    
    # Final output
    builder.add_edge("reporter", END)
    
    return builder


def build_graph_with_memory():
    """Build and return the agent workflow graph with memory."""
    # use persistent memory to save conversation history
    # TODO: be compatible with SQLite / PostgreSQL
    memory = MemorySaver()

    # build state graph
    builder = _build_base_graph()
    return builder.compile(checkpointer=memory)


def build_graph():
    """Build and return the agent workflow graph without memory."""
    # build state graph
    builder = _build_base_graph()
    return builder.compile()


graph = build_graph()
