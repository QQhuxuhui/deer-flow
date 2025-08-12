"""
Intelligent Router for DeerFlow - Intent Classification and Workflow Routing

Provides intelligent routing based on user intent analysis, directing tasks to
optimal workflows (data analysis, research, or hybrid) for enhanced efficiency.
"""

from enum import Enum
from typing import Literal, Optional, List
from dataclasses import dataclass
from langchain_core.runnables import RunnableConfig
from langchain_core.language_models import BaseChatModel
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.config.configuration import Configuration
from src.graph.types import State
from src.graph.utils import get_configuration
from src.llms.llm import get_llm_by_type


class WorkflowType(str, Enum):
    """Workflow routing types."""
    DATA_ANALYSIS = "data_analysis"      # Pure data analysis tasks
    TRADITIONAL_RESEARCH = "research"     # Traditional research tasks
    HYBRID = "hybrid"                    # Mixed data analysis + research


class TaskComplexity(str, Enum):
    """Task complexity levels."""
    SIMPLE = "simple"        # Single-step, straightforward tasks
    MODERATE = "moderate"    # Multi-step, moderate complexity
    COMPLEX = "complex"      # Multi-domain, high complexity


@dataclass
class IntentClassification:
    """Intent classification result."""
    workflow_type: WorkflowType
    complexity: TaskComplexity
    confidence: float
    reasoning: str
    data_indicators: List[str]      # Data-related keywords found
    research_indicators: List[str]  # Research-related keywords found
    domain_keywords: List[str]      # Domain-specific terms


class IntentAnalysisInput(BaseModel):
    """Input schema for intent analysis."""
    user_query: str = Field(description="User's original query")
    context: str = Field(description="Additional context if available", default="")


def create_intent_classifier_prompt() -> str:
    """Create system prompt for intent classification."""
    return """你是一个专业的智能任务路由分析师，负责分析用户查询并确定最佳的处理工作流。

**核心分析维度：**

1. **数据分析指标** (DATA_ANALYSIS) - 优先级最高:
   - 🎯 强烈信号：数据库查询、SQL操作、统计分析、预测建模、可视化图表
   - 📊 关键词：数据库、查询、统计、分析、预测、模型、流失、客户、可视化、图表、趋势、报表
   - 💡 场景：需要对现有数据进行分析、统计、预测或可视化的任务
   - ⚠️ 重要：只要涉及数据分析、统计、预测、建模，优先选择此类型

2. **传统研究指标** (TRADITIONAL_RESEARCH):
   - 🔍 强烈信号：网络搜索、资料收集、文献调研、市场调查
   - 📚 关键词：搜索、调研、收集、整理、创作、市场、技术、文档、研究
   - 💡 场景：需要从外部获取信息、调研资料的任务

3. **混合任务指标** (HYBRID):
   - 🔄 需要数据分析+外部研究结合
   - 🎯 关键词：综合分析、多维度、结合、整合、对比、全面
   - 💡 场景：既需要内部数据分析，又需要外部市场研究

**分类优先级规则：**
1. 如果查询包含"分析、统计、预测、模型、流失、数据"等词汇 → DATA_ANALYSIS
2. 如果明确要求"调研、搜索、收集资料" → TRADITIONAL_RESEARCH  
3. 如果同时需要数据分析和外部研究 → HYBRID

**复杂度评估：**
- SIMPLE: 单一明确任务，单个领域，< 10个字
- MODERATE: 多步骤任务，2-3个方面，10-20个字
- COMPLEX: 多领域综合，需要深度分析，> 20个字

**输出格式：**
严格按照以下JSON格式输出：
```json
{
    "workflow_type": "data_analysis|research|hybrid",
    "complexity": "simple|moderate|complex", 
    "confidence": 0.9,
    "reasoning": "具体的分析依据和逻辑",
    "data_indicators": ["数据相关关键词"],
    "research_indicators": ["研究相关关键词"],
    "domain_keywords": ["领域专业术语"]
}
```

**关键提醒：**
- 优先考虑DATA_ANALYSIS：任何涉及数据分析、统计、预测的任务都应该选择此类型
- 置信度计算：强信号0.9+，中等信号0.7-0.8，弱信号0.5-0.6
- reasoning字段必须说明选择理由

请分析用户查询并给出分类结果："""


async def classify_user_intent(
    user_query: str, 
    config: Configuration,
    context: str = ""
) -> IntentClassification:
    """
    Classify user intent using LLM analysis.
    
    Args:
        user_query: User's original query
        config: DeerFlow configuration
        context: Additional context information
        
    Returns:
        IntentClassification result
    """
    try:
        # Get LLM for intent classification
        llm = get_llm_by_type("coordinator")
        
        # Prepare analysis input
        analysis_prompt = create_intent_classifier_prompt()
        analysis_input = f"""
用户查询: {user_query}

上下文信息: {context}

请分析并分类这个查询。"""

        # Execute classification
        response = await llm.ainvoke([
            {"role": "system", "content": analysis_prompt},
            {"role": "user", "content": analysis_input}
        ])
        
        # Parse response (assuming structured output)
        import json
        result_text = response.content.strip()
        
        # Extract JSON from response
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}') + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_text = result_text[start_idx:end_idx]
            result_dict = json.loads(json_text)
            
            return IntentClassification(
                workflow_type=WorkflowType(result_dict["workflow_type"]),
                complexity=TaskComplexity(result_dict["complexity"]),
                confidence=result_dict["confidence"],
                reasoning=result_dict["reasoning"],
                data_indicators=result_dict.get("data_indicators", []),
                research_indicators=result_dict.get("research_indicators", []),
                domain_keywords=result_dict.get("domain_keywords", [])
            )
        else:
            # Fallback classification
            return _fallback_classification(user_query)
            
    except Exception as e:
        print(f"Intent classification error: {e}")
        return _fallback_classification(user_query)


def _fallback_classification(user_query: str) -> IntentClassification:
    """Enhanced fallback classification using weighted keyword matching."""
    query_lower = user_query.lower()
    
    # Enhanced data analysis keywords with weights
    data_keywords = {
        # High confidence indicators (weight 3)
        "数据库": 3, "sql": 3, "查询": 2, "统计": 3, "预测": 3, "模型": 2,
        "可视化": 3, "图表": 2, "报表": 2, "仪表板": 3, "dashboard": 3,
        # Medium confidence indicators (weight 2)  
        "分析": 2, "流失": 2, "客户": 1.5, "数据": 2, "趋势": 1.5,
        "挖掘": 2, "建模": 3, "算法": 2, "回归": 3, "分类": 2,
        # Domain specific (weight 2.5)
        "电信": 1.5, "金融": 1.5, "零售": 1.5, "用户行为": 2,
    }
    
    # Enhanced research keywords with weights  
    research_keywords = {
        # High confidence indicators (weight 3)
        "调研": 3, "搜索": 2, "收集": 2, "整理": 2, "研究": 2,
        "市场": 2, "技术": 1.5, "文档": 1.5, "资料": 2,
        # Medium confidence indicators (weight 2)
        "趋势": 1.5, "行业": 2, "竞品": 3, "分析": 1, "报告": 1.5,
        "综述": 2, "调查": 2, "访谈": 2, "问卷": 2,
    }
    
    # Calculate weighted scores
    data_score = sum(weight for keyword, weight in data_keywords.items() if keyword in query_lower)
    research_score = sum(weight for keyword, weight in research_keywords.items() if keyword in query_lower)
    
    # Enhanced decision logic with better thresholds
    if data_score >= 4 and data_score > research_score * 1.2:  # Strong data analysis signal
        workflow_type = WorkflowType.DATA_ANALYSIS
        confidence = min(0.9, 0.6 + (data_score - 4) * 0.05)
    elif research_score >= 4 and research_score > data_score * 1.2:  # Strong research signal
        workflow_type = WorkflowType.TRADITIONAL_RESEARCH
        confidence = min(0.9, 0.6 + (research_score - 4) * 0.05)
    elif data_score >= 2 and research_score >= 2:  # Both present - hybrid
        workflow_type = WorkflowType.HYBRID
        confidence = min(0.85, 0.7 + abs(data_score - research_score) * 0.02)
    elif data_score > research_score and data_score >= 1.5:
        workflow_type = WorkflowType.DATA_ANALYSIS
        confidence = min(0.8, 0.5 + data_score * 0.1)
    elif research_score > data_score and research_score >= 1.5:
        workflow_type = WorkflowType.TRADITIONAL_RESEARCH
        confidence = min(0.8, 0.5 + research_score * 0.1)
    else:
        # Default to research with low confidence
        workflow_type = WorkflowType.TRADITIONAL_RESEARCH
        confidence = 0.4
    
    # Enhanced complexity assessment
    complexity = TaskComplexity.SIMPLE
    complexity_indicators = ["综合", "多维", "复杂", "深度", "全面", "系统", "完整"]
    domain_count = len([k for k in ["电信", "金融", "零售", "医疗", "教育"] if k in query_lower])
    
    if len(query_lower.split()) > 15 or any(word in query_lower for word in complexity_indicators):
        complexity = TaskComplexity.COMPLEX
    elif len(query_lower.split()) > 8 or domain_count > 1:
        complexity = TaskComplexity.MODERATE
    
    # Extract found keywords for transparency
    found_data_keywords = [kw for kw in data_keywords.keys() if kw in query_lower]
    found_research_keywords = [kw for kw in research_keywords.keys() if kw in query_lower]
    
    reasoning = f"关键词分析: 数据({data_score}分) vs 研究({research_score}分)"
    
    return IntentClassification(
        workflow_type=workflow_type,
        complexity=complexity,
        confidence=confidence,
        reasoning=reasoning,
        data_indicators=found_data_keywords,
        research_indicators=found_research_keywords,
        domain_keywords=[k for k in ["电信", "金融", "零售", "医疗"] if k in query_lower]
    )