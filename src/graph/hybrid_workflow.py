"""
Hybrid Workflow Components for DeerFlow

Provides enhanced planning and execution for tasks requiring both 
data analysis and traditional research capabilities.
"""

from typing import Literal, List, Dict, Any
from langchain_core.runnables import RunnableConfig  
from langgraph.types import Command

from src.config.configuration import Configuration
from src.graph.types import State
from src.graph.utils import get_configuration, get_current_step
from src.llms.llm import get_llm_by_type
from src.prompts.planner_model import Plan, Step, StepType


def create_hybrid_planner_prompt() -> str:
    """Create system prompt for hybrid workflow planning."""
    return """你是一个高级任务规划师，专门处理需要数据分析和研究结合的复杂任务。

**核心能力：**
- 数据分析规划：数据库查询、统计分析、可视化
- 研究规划：网络搜索、资料收集、内容分析
- 智能融合：数据洞察与研究发现的综合整合

**规划原则：**
1. **任务分解**：将复杂任务拆分为数据分析步骤和研究步骤
2. **依赖管理**：确保步骤间的逻辑依赖关系正确
3. **结果融合**：设计数据和研究结果的整合策略

**步骤类型说明：**
- `research`: 网络搜索、资料收集、市场调研
- `processing`: 数据处理、计算分析、结果整理
- `data_analysis`: 数据库查询、统计分析、可视化

**示例规划：**
```json
{
    "locale": "zh-CN",
    "has_enough_context": false,
    "thought": "这是一个需要结合客户数据分析和市场研究的复杂任务",
    "title": "客户流失综合分析计划",
    "steps": [
        {
            "need_search": false,
            "title": "客户流失数据分析",
            "description": "查询客户数据库，分析流失率趋势，生成流失客户画像",
            "step_type": "data_analysis"
        },
        {
            "need_search": true, 
            "title": "行业流失率基准研究",
            "description": "搜索行业流失率基准数据，了解市场平均水平",
            "step_type": "research"
        },
        {
            "need_search": false,
            "title": "综合分析报告",
            "description": "整合数据分析结果和行业研究，生成综合洞察报告",
            "step_type": "processing"
        }
    ]
}
```

请根据用户的混合任务需求，生成智能的执行计划。"""


async def hybrid_planner_node(
    state: State, config: RunnableConfig
) -> Command[Literal["hybrid_executor", "human_feedback"]]:
    """
    Hybrid Planner Node - Plan tasks requiring both data analysis and research.
    
    Creates intelligent plans that combine data analysis and research steps
    with proper dependency management and result integration.
    """
    try:
        # Get configuration and task info
        deer_config = get_configuration(config)
        hybrid_task_info = state.get("hybrid_task_info", {})
        user_query = hybrid_task_info.get("user_query", "")
        
        # Get planner LLM
        planner_llm = get_llm_by_type("planner")
        
        # Create hybrid planning prompt
        hybrid_prompt = create_hybrid_planner_prompt()
        
        # Prepare planning input with hybrid context
        planning_input = f"""
用户查询: {user_query}

任务复杂度: {hybrid_task_info.get('complexity', 'moderate')}
数据分析指标: {', '.join(hybrid_task_info.get('data_indicators', []))}
研究指标: {', '.join(hybrid_task_info.get('research_indicators', []))}

请生成一个综合执行计划，智能结合数据分析和研究步骤。"""

        # Execute planning
        response = await planner_llm.ainvoke([
            {"role": "system", "content": hybrid_prompt},
            {"role": "user", "content": planning_input}
        ])
        
        # Parse planning result
        import json
        from json_repair import repair_json
        
        try:
            # Try to parse the response as JSON
            plan_text = response.content.strip()
            
            # Remove markdown code blocks if present
            if plan_text.startswith("```"):
                start_idx = plan_text.find('{')
                end_idx = plan_text.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    plan_text = plan_text[start_idx:end_idx]
            
            # Repair and parse JSON
            repaired_json = repair_json(plan_text)
            plan_dict = json.loads(repaired_json)
            
            # Validate and create Plan object
            plan = Plan(**plan_dict)
            
        except Exception as parse_error:
            # Fallback: create default hybrid plan
            plan = create_default_hybrid_plan(user_query, hybrid_task_info)
        
        # Update state with hybrid plan
        return Command(
            update={
                "current_plan": plan,
                "hybrid_plan_created": True,
                "observations": state.get("observations", []) + [
                    f"混合工作流计划已创建: {plan.title} (包含{len(plan.steps)}个步骤)"
                ]
            },
            goto="hybrid_executor"
        )
        
    except Exception as e:
        error_msg = f"混合规划失败: {str(e)}"
        
        # Create fallback plan
        fallback_plan = create_default_hybrid_plan(
            hybrid_task_info.get("user_query", ""), 
            hybrid_task_info
        )
        
        return Command(
            update={
                "current_plan": fallback_plan,
                "observations": state.get("observations", []) + [error_msg],
                "errors": state.get("errors", []) + [f"hybrid_planner: {str(e)}"]
            },
            goto="hybrid_executor"
        )


def create_default_hybrid_plan(user_query: str, task_info: Dict[str, Any]) -> Plan:
    """Create a default hybrid plan as fallback."""
    
    # Extract indicators
    data_indicators = task_info.get("data_indicators", [])
    research_indicators = task_info.get("research_indicators", [])
    
    steps = []
    
    # Add data analysis step if data indicators present
    if data_indicators:
        steps.append(Step(
            need_search=False,
            title="数据分析处理",
            description=f"根据查询进行数据分析: {user_query}",
            step_type=StepType.DATA_ANALYSIS
        ))
    
    # Add research step if research indicators present  
    if research_indicators:
        steps.append(Step(
            need_search=True,
            title="相关资料研究",
            description=f"搜索和研究相关资料: {user_query}",
            step_type=StepType.RESEARCH
        ))
    
    # Add synthesis step
    steps.append(Step(
        need_search=False,
        title="综合分析整合",
        description="整合数据分析结果和研究发现，生成综合报告",
        step_type=StepType.PROCESSING
    ))
    
    return Plan(
        locale="zh-CN",
        has_enough_context=False,
        thought=f"为混合任务创建默认执行计划: {user_query}",
        title="混合工作流执行计划",
        steps=steps
    )


async def hybrid_executor_node(
    state: State, config: RunnableConfig
) -> Command[Literal["researcher", "coder", "data_analyst", "hybrid_coordinator", "reporter"]]:
    """
    Hybrid Executor Node - Execute hybrid workflow steps intelligently.
    
    Routes individual steps to appropriate processors while maintaining
    overall workflow coordination and result integration.
    """
    try:
        current_plan = state.get("current_plan")
        if not current_plan or not current_plan.steps:
            return Command(goto="reporter")

        # Find first incomplete step
        incomplete_step = None
        for step in current_plan.steps:
            if not step.execution_res:
                incomplete_step = step
                break

        if not incomplete_step:
            # All steps completed, move to reporting
            return Command(goto="reporter")

        # Route based on step type with hybrid awareness
        if incomplete_step.step_type == StepType.RESEARCH:
            return Command(goto="researcher")
        elif incomplete_step.step_type == StepType.PROCESSING:
            # Check if this is a synthesis step requiring hybrid coordination
            if "整合" in incomplete_step.description or "综合" in incomplete_step.description:
                return Command(goto="hybrid_coordinator")
            else:
                return Command(goto="coder")
        elif incomplete_step.step_type == StepType.DATA_ANALYSIS:
            return Command(goto="data_analyst")
        else:
            # Default fallback
            return Command(goto="coder")
            
    except Exception as e:
        error_msg = f"混合执行器路由失败: {str(e)}"
        return Command(
            update={
                "observations": state.get("observations", []) + [error_msg],
                "errors": state.get("errors", []) + [f"hybrid_executor: {str(e)}"]
            },
            goto="reporter"
        )


async def hybrid_coordinator_node(
    state: State, config: RunnableConfig
) -> Command[Literal["hybrid_executor", "reporter"]]:
    """
    Hybrid Coordinator Node - Integrate results from data analysis and research.
    
    Synthesizes findings from both data analysis and research steps to create
    comprehensive insights and recommendations.
    """
    try:
        # Get current step
        current_step = get_current_step(state)
        if not current_step:
            return Command(goto="reporter")
        
        # Collect previous results
        observations = state.get("observations", [])
        data_analysis_results = state.get("data_analysis_results", {})
        
        # Get coordinator LLM
        coordinator_llm = get_llm_by_type("coordinator")
        
        # Create synthesis prompt
        synthesis_prompt = f"""你是一个高级分析协调员，负责整合数据分析结果和研究发现。

**当前任务**: {current_step.description}

**已完成的工作**:
{chr(10).join(f"- {obs}" for obs in observations)}

**数据分析结果**:
{data_analysis_results.get('content', '暂无数据分析结果')}

请整合以上信息，生成综合洞察和建议。重点关注：
1. 数据驱动的发现与研究结论的关联性
2. 数据趋势与外部环境的对应关系
3. 基于综合分析的actionable建议
4. 潜在的风险和机会识别

输出格式要求：
- 结构化分析结果
- 关键发现总结
- 数据支撑的结论
- 具体的行动建议"""

        # Execute synthesis
        response = await coordinator_llm.ainvoke([
            {"role": "system", "content": "你是一个专业的数据和研究整合分析师。"},
            {"role": "user", "content": synthesis_prompt}
        ])
        
        # Update step execution result
        current_step.execution_res = response.content
        
        # Update state with synthesis results
        return Command(
            update={
                "observations": observations + [
                    f"混合协调完成 - {current_step.title}: {response.content}"
                ],
                "hybrid_synthesis_result": {
                    "content": response.content,
                    "step_title": current_step.title,
                    "integration_type": "data_research_synthesis"
                }
            },
            goto="hybrid_executor"
        )
        
    except Exception as e:
        error_msg = f"混合协调失败: {str(e)}"
        
        # Mark step as completed with error
        current_step = get_current_step(state)
        if current_step:
            current_step.execution_res = f"协调失败: {str(e)}"
        
        return Command(
            update={
                "observations": state.get("observations", []) + [error_msg],
                "errors": state.get("errors", []) + [f"hybrid_coordinator: {str(e)}"]
            },
            goto="hybrid_executor"
        )