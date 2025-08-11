"""
Data Analysis Node for DeerFlow Graph Integration

Provides data analysis capabilities as a specialized node in DeerFlow's StateGraph.
Handles data analysis steps by delegating to the data analysis supervisor.
"""

from typing import Literal, Optional
from langchain_core.runnables import RunnableConfig
from langgraph.graph import Command

from src.config.configuration import Configuration
from src.agents.data_supervisor import create_data_supervisor
from src.graph.types import State
from src.graph.utils import get_current_step, get_configuration


async def data_analysis_node(
    state: State, config: RunnableConfig
) -> Command[Literal["research_team", "human_feedback", "report_writing"]]:
    """
    Data Analysis Node - Handle structured data analysis tasks.
    
    This node is triggered when the planner identifies a step that requires:
    - Database queries and data extraction
    - Statistical analysis and data processing  
    - Domain knowledge from telecom churn analytics
    - Data visualization and chart generation
    
    Args:
        state: Current graph state
        config: Runnable configuration
        
    Returns:
        Command with updated state and next node destination
    """
    try:
        # Get current step and configuration
        current_step = get_current_step(state)
        deer_config = get_configuration(config)
        
        # Check if this is a data analysis step
        if current_step.step_type != "data_analysis":
            # Not a data analysis step, continue to research team
            return Command(goto="research_team")
        
        # Create data analysis supervisor
        data_supervisor = create_data_supervisor(deer_config)
        
        # Prepare input for data supervisor
        analysis_input = {
            "messages": [
                {
                    "role": "user", 
                    "content": f"数据分析任务: {current_step.description}\n\n"
                               f"任务标题: {current_step.title}\n\n"
                               f"请根据这个任务需求，协调合适的专家完成数据分析工作。"
                }
            ]
        }
        
        # Execute data analysis
        result = await data_supervisor.ainvoke(analysis_input, config)
        
        # Extract analysis results
        if result and "messages" in result:
            # Get the final message content
            final_message = result["messages"][-1]
            analysis_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
            
            # Update state with analysis results
            updated_observations = state.get("observations", []) + [
                f"数据分析完成 - {current_step.title}: {analysis_content}"
            ]
            
            # Store detailed results for reporting
            data_analysis_results = {
                "step_id": current_step.title,
                "analysis_type": "data_analysis", 
                "content": analysis_content,
                "supervisor_result": result
            }
            
            return Command(
                update={
                    "observations": updated_observations,
                    "data_analysis_results": data_analysis_results
                },
                goto="research_team"
            )
        else:
            # No valid result, log and continue
            error_msg = f"数据分析节点未能获得有效结果: {current_step.title}"
            return Command(
                update={
                    "observations": state.get("observations", []) + [error_msg]
                },
                goto="research_team"
            )
            
    except Exception as e:
        # Handle errors gracefully
        error_msg = f"数据分析节点执行失败: {str(e)}"
        
        # Log error and continue workflow
        return Command(
            update={
                "observations": state.get("observations", []) + [error_msg],
                "errors": state.get("errors", []) + [f"data_analysis_node: {str(e)}"]
            },
            goto="research_team"  # Continue to research team as fallback
        )


async def lightweight_data_analysis_node(
    state: State, config: RunnableConfig  
) -> Command[Literal["research_team", "human_feedback", "report_writing"]]:
    """
    Lightweight Data Analysis Node for development and testing.
    
    Uses a simplified data supervisor for faster execution during development.
    
    Args:
        state: Current graph state
        config: Runnable configuration
        
    Returns:
        Command with updated state and next node destination
    """
    try:
        from src.agents.data_supervisor import create_lightweight_data_supervisor
        
        # Get current step and configuration
        current_step = get_current_step(state)
        deer_config = get_configuration(config)
        
        # Check if this is a data analysis step
        if current_step.step_type != "data_analysis":
            return Command(goto="research_team")
        
        # Create lightweight supervisor
        data_supervisor = create_lightweight_data_supervisor(deer_config)
        
        # Simplified analysis input
        analysis_input = {
            "messages": [{"role": "user", "content": current_step.description}]
        }
        
        # Execute analysis
        result = await data_supervisor.ainvoke(analysis_input, config)
        
        # Process result
        if result and "messages" in result:
            content = str(result["messages"][-1])
            return Command(
                update={
                    "observations": state.get("observations", []) + [
                        f"轻量数据分析 - {current_step.title}: {content}"
                    ]
                },
                goto="research_team"
            )
        else:
            return Command(goto="research_team")
            
    except Exception as e:
        return Command(
            update={
                "observations": state.get("observations", []) + [
                    f"轻量数据分析失败: {str(e)}"
                ]
            },
            goto="research_team"
        )