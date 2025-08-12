"""
Intelligent Router Node for DeerFlow

Provides intelligent routing based on intent classification, directing tasks to
optimal workflows for enhanced efficiency and specialized processing.
"""

from typing import Literal
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.config.configuration import Configuration
from src.graph.types import State
from src.graph.utils import get_configuration
from src.graph.intent_classifier import (
    classify_user_intent, 
    WorkflowType, 
    TaskComplexity,
    IntentClassification
)


async def intelligent_router_node(
    state: State, config: RunnableConfig
) -> Command[Literal[
    "data_analysis_workflow", 
    "traditional_research_workflow", 
    "hybrid_workflow",
    "background_investigator"
]]:
    """
    Intelligent Router Node - Route tasks based on intent classification.
    
    Analyzes user intent and routes to the most appropriate workflow:
    - Data Analysis Workflow: Pure data analysis tasks
    - Traditional Research Workflow: Traditional DeerFlow research
    - Hybrid Workflow: Combined data analysis + research tasks
    
    Args:
        state: Current graph state
        config: Runnable configuration
        
    Returns:
        Command with routing decision and updated state
    """
    try:
        # Get user query from state
        messages = state.get("messages", [])
        if not messages:
            # No messages, use background investigator as fallback
            return Command(goto="background_investigator")
        
        # Extract user query (first human message)
        user_query = None
        for message in messages:
            if hasattr(message, 'type') and message.type == 'human':
                user_query = message.content
                break
            elif isinstance(message, dict) and message.get('role') == 'user':
                user_query = message.get('content', '')
                break
        
        if not user_query:
            user_query = str(messages[0]) if messages else ""
        
        # Get configuration
        deer_config = get_configuration(config)
        
        # Perform intent classification
        intent_result = await classify_user_intent(
            user_query=user_query,
            config=deer_config,
            context=str(state.get("context", ""))
        )
        
        # Store detailed classification result in state for frontend display
        alternative_routes = []
        if intent_result.workflow_type == WorkflowType.DATA_ANALYSIS:
            alternative_routes = ["traditional_research", "hybrid"]
        elif intent_result.workflow_type == WorkflowType.TRADITIONAL_RESEARCH:
            alternative_routes = ["data_analysis", "hybrid"]
        else:  # HYBRID
            alternative_routes = ["data_analysis", "traditional_research"]
            
        route_decision = {
            "workflow_type": intent_result.workflow_type.value,
            "complexity": intent_result.complexity.value,
            "confidence": intent_result.confidence,
            "reasoning": intent_result.reasoning,
            "data_indicators": intent_result.data_indicators,
            "research_indicators": intent_result.research_indicators,
            "domain_keywords": intent_result.domain_keywords,
            "query": user_query,
            "route_taken": intent_result.workflow_type.value,
            "alternative_routes": alternative_routes,
            "requires_confirmation": intent_result.confidence < 0.7
        }
        
        updated_state = {
            "intent_classification": route_decision,
            "route_decision_display": {
                "show_routing_info": True,
                "decision_data": route_decision
            }
        }
        
        # Check if we need user confirmation for routing decision
        if intent_result.confidence < 0.7:
            # Low confidence - ask user to confirm routing decision
            return Command(
                update=updated_state,
                goto="routing_confirmation"
            )
        
        # High confidence - proceed with routing
        # Route based on workflow type
        if intent_result.workflow_type == WorkflowType.DATA_ANALYSIS:
            # Route directly to data analysis workflow
            return Command(
                update=updated_state,
                goto="data_analysis_workflow"
            )
        
        elif intent_result.workflow_type == WorkflowType.HYBRID:
            # Route to hybrid workflow for complex tasks
            return Command(
                update=updated_state,
                goto="hybrid_workflow"
            )
        
        else:  # TRADITIONAL_RESEARCH
            # Route to traditional DeerFlow workflow
            return Command(
                update=updated_state,
                goto="traditional_research_workflow"
            )
            
    except Exception as e:
        # Error in routing, fallback to traditional workflow
        error_msg = f"智能路由分析失败: {str(e)}"
        
        return Command(
            update={
                "observations": state.get("observations", []) + [error_msg],
                "errors": state.get("errors", []) + [f"intelligent_router: {str(e)}"],
                "intent_classification": {
                    "workflow_type": "research",
                    "complexity": "moderate", 
                    "confidence": 0.5,
                    "reasoning": "路由器异常，使用默认研究工作流",
                    "data_indicators": [],
                    "research_indicators": [],
                    "domain_keywords": []
                }
            },
            goto="traditional_research_workflow"
        )


async def data_analysis_workflow_node(
    state: State, config: RunnableConfig
) -> Command[Literal["reporter"]]:
    """
    Pure Data Analysis Workflow - Direct to data analysis supervisor.
    
    For tasks identified as pure data analysis, bypass traditional planning
    and go directly to specialized data analysis processing.
    """
    try:
        from src.agents.data_supervisor import create_data_supervisor
        
        # Get configuration
        deer_config = get_configuration(config)
        
        # Extract user query
        messages = state.get("messages", [])
        user_query = ""
        for message in messages:
            if hasattr(message, 'type') and message.type == 'human':
                user_query = message.content
                break
            elif isinstance(message, dict) and message.get('role') == 'user':
                user_query = message.get('content', '')
                break
        
        # Create and execute data supervisor
        data_supervisor = create_data_supervisor(deer_config)
        
        # Execute data analysis
        analysis_input = {
            "messages": [
                {
                    "role": "user",
                    "content": f"数据分析任务: {user_query}\n\n"
                               f"请根据这个查询进行综合数据分析，包括数据查询、统计分析和可视化。"
                }
            ]
        }
        
        result = await data_supervisor.ainvoke(analysis_input, config)
        
        # Extract final result
        if result and "messages" in result:
            final_message = result["messages"][-1]
            analysis_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
            
            # Update state with comprehensive results
            return Command(
                update={
                    "observations": [f"数据分析完成: {analysis_content}"],
                    "data_analysis_results": {
                        "content": analysis_content,
                        "workflow": "pure_data_analysis",
                        "supervisor_result": result
                    },
                    "workflow_type": "data_analysis_only"
                },
                goto="reporter"
            )
        else:
            return Command(
                update={
                    "observations": ["数据分析工作流执行完成，但未获得有效结果"],
                    "workflow_type": "data_analysis_only"
                },
                goto="reporter"
            )
            
    except Exception as e:
        error_msg = f"数据分析工作流执行失败: {str(e)}"
        return Command(
            update={
                "observations": [error_msg],
                "errors": state.get("errors", []) + [f"data_analysis_workflow: {str(e)}"],
                "workflow_type": "data_analysis_only"
            },
            goto="reporter"
        )


async def traditional_research_workflow_node(
    state: State, config: RunnableConfig
) -> Command[Literal["background_investigator"]]:
    """
    Traditional Research Workflow - Use original DeerFlow pipeline.
    
    For tasks identified as traditional research, use the original
    DeerFlow workflow with background investigation and planning.
    """
    # Simply pass through to background investigator
    # This maintains the original DeerFlow workflow
    return Command(
        update={
            "workflow_type": "traditional_research"
        },
        goto="background_investigator"
    )


async def hybrid_workflow_node(
    state: State, config: RunnableConfig
) -> Command[Literal["hybrid_planner"]]:
    """
    Hybrid Workflow - Combine data analysis and research capabilities.
    
    For complex tasks requiring both data analysis and research,
    use an enhanced planner that can coordinate both workflows.
    """
    try:
        # Get intent classification from state
        intent_classification = state.get("intent_classification", {})
        
        # Prepare hybrid task analysis
        user_query = ""
        messages = state.get("messages", [])
        for message in messages:
            if hasattr(message, 'type') and message.type == 'human':
                user_query = message.content
                break
            elif isinstance(message, dict) and message.get('role') == 'user':
                user_query = message.get('content', '')
                break
        
        # Update state with hybrid workflow information
        return Command(
            update={
                "workflow_type": "hybrid",
                "hybrid_task_info": {
                    "user_query": user_query,
                    "data_indicators": intent_classification.get("data_indicators", []),
                    "research_indicators": intent_classification.get("research_indicators", []),
                    "complexity": intent_classification.get("complexity", "moderate")
                }
            },
            goto="hybrid_planner"
        )
        
    except Exception as e:
        error_msg = f"混合工作流初始化失败: {str(e)}"
        return Command(
            update={
                "observations": [error_msg],
                "errors": state.get("errors", []) + [f"hybrid_workflow: {str(e)}"],
                "workflow_type": "hybrid"
            },
            goto="hybrid_planner"
        )


async def routing_confirmation_node(
    state: State, config: RunnableConfig
) -> Command[Literal["data_analysis_workflow", "traditional_research_workflow", "hybrid_workflow", "background_investigator"]]:
    """
    Routing Confirmation Node - Let user confirm or change routing decision.
    
    When intent classification confidence is low, this node presents the routing
    decision to the user and allows them to confirm or select a different workflow.
    """
    try:
        route_decision = state.get("intent_classification", {})
        
        # Create confirmation message with routing details
        confirmation_message = f"""🤖 **智能路由分析结果**

📝 **您的问题**: {route_decision.get('query', '未知查询')}

🎯 **推荐工作流**: {get_workflow_display_name(route_decision.get('workflow_type', 'research'))}
📊 **置信度**: {route_decision.get('confidence', 0.5):.0%}
🧠 **分析依据**: {route_decision.get('reasoning', '未知原因')}

📋 **发现的关键词**:
- 数据指标: {', '.join(route_decision.get('data_indicators', []))}
- 研究指标: {', '.join(route_decision.get('research_indicators', []))}
- 领域词汇: {', '.join(route_decision.get('domain_keywords', []))}

🔀 **可选工作流**:
1. **数据分析** - 专业数据处理、统计分析、预测建模
2. **传统研究** - 网络搜索、资料收集、文档整理  
3. **混合模式** - 数据分析+外部研究的综合处理

请确认使用推荐的工作流，或回复以下选项之一：
- 回复 "1" 或 "数据分析" 选择数据分析工作流
- 回复 "2" 或 "传统研究" 选择传统研究工作流  
- 回复 "3" 或 "混合模式" 选择混合工作流
- 回复 "确认" 或 "继续" 使用推荐的工作流"""

        from langgraph.prebuilt import interrupt
        from langchain_core.messages import HumanMessage
        
        # Show routing decision and wait for user confirmation
        feedback = interrupt(confirmation_message)
        
        # Parse user feedback to determine final workflow
        if feedback:
            feedback_lower = str(feedback).lower().strip()
            
            # Parse user choice
            if any(word in feedback_lower for word in ["1", "数据分析", "data"]):
                chosen_workflow = "data_analysis"
            elif any(word in feedback_lower for word in ["2", "传统研究", "research", "调研"]):
                chosen_workflow = "research"
            elif any(word in feedback_lower for word in ["3", "混合", "hybrid", "结合"]):
                chosen_workflow = "hybrid"
            elif any(word in feedback_lower for word in ["确认", "继续", "ok", "yes"]):
                chosen_workflow = route_decision.get('workflow_type', 'research')
            else:
                # Default to original recommendation
                chosen_workflow = route_decision.get('workflow_type', 'research')
        else:
            chosen_workflow = route_decision.get('workflow_type', 'research')
        
        # Update state with final routing decision
        final_decision = route_decision.copy()
        final_decision['workflow_type'] = chosen_workflow
        final_decision['user_confirmed'] = True
        final_decision['confidence'] = 0.9  # User confirmed, high confidence
        
        # Route to chosen workflow
        if chosen_workflow == "data_analysis":
            return Command(
                update={
                    "intent_classification": final_decision,
                    "messages": [HumanMessage(content=f"已确认使用数据分析工作流处理您的问题。", name="router")]
                },
                goto="data_analysis_workflow"
            )
        elif chosen_workflow == "hybrid":
            return Command(
                update={
                    "intent_classification": final_decision,
                    "messages": [HumanMessage(content=f"已确认使用混合工作流处理您的问题。", name="router")]
                },
                goto="hybrid_workflow"
            )
        else:  # traditional research
            return Command(
                update={
                    "intent_classification": final_decision,
                    "messages": [HumanMessage(content=f"已确认使用传统研究工作流处理您的问题。", name="router")]
                },
                goto="traditional_research_workflow"
            )
            
    except Exception as e:
        error_msg = f"路由确认失败: {str(e)}"
        return Command(
            update={
                "observations": state.get("observations", []) + [error_msg],
                "errors": state.get("errors", []) + [f"routing_confirmation: {str(e)}"]
            },
            goto="traditional_research_workflow"  # Fallback
        )


def get_workflow_display_name(workflow_type: str) -> str:
    """Get user-friendly workflow display name."""
    workflow_names = {
        "data_analysis": "数据分析工作流",
        "research": "传统研究工作流", 
        "hybrid": "混合工作流"
    }
    return workflow_names.get(workflow_type, "传统研究工作流")