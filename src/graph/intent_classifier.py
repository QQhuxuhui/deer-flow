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
    return """你是一个智能任务路由分析师，负责分析用户查询并确定最佳的处理工作流。

**分析维度：**

1. **数据分析指标** (DATA_ANALYSIS):
   - 数据库查询、SQL操作
   - 统计分析、数据挖掘
   - 可视化图表、报表生成
   - 客户分析、流失预测
   - 关键词：数据库、查询、统计、图表、分析、预测、客户、流失、可视化、报告

2. **传统研究指标** (TRADITIONAL_RESEARCH):
   - 网络搜索、资料收集
   - 技术调研、市场分析
   - 文档整理、内容创作
   - 关键词：搜索、调研、收集、整理、创作、市场、技术、文档

3. **混合任务指标** (HYBRID):
   - 需要数据分析+研究结合
   - 多领域综合分析
   - 复杂业务问题解决
   - 关键词：综合分析、多维度、结合、整合

**复杂度评估：**
- SIMPLE: 单一明确任务，单个领域
- MODERATE: 多步骤任务，涉及2-3个方面
- COMPLEX: 多领域综合，需要深度分析

**输出格式：**
严格按照以下JSON格式输出：
```json
{
    "workflow_type": "data_analysis|research|hybrid",
    "complexity": "simple|moderate|complex", 
    "confidence": 0.8,
    "reasoning": "分析依据和逻辑",
    "data_indicators": ["数据相关关键词"],
    "research_indicators": ["研究相关关键词"],
    "domain_keywords": ["领域专业术语"]
}
```

**示例分析：**

用户查询："分析电信客户流失情况，包括流失率统计和预测模型"
输出：
```json
{
    "workflow_type": "data_analysis",
    "complexity": "moderate",
    "confidence": 0.95,
    "reasoning": "明确的数据分析任务，涉及数据库查询、统计分析和预测模型建立",
    "data_indicators": ["分析", "流失", "统计", "预测模型"],
    "research_indicators": [],
    "domain_keywords": ["电信", "客户流失", "流失率"]
}
```

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
    """Fallback classification using keyword matching."""
    query_lower = user_query.lower()
    
    # Data analysis keywords
    data_keywords = [
        "数据库", "查询", "sql", "统计", "分析", "图表", "可视化", 
        "流失", "预测", "客户", "报告", "数据"
    ]
    
    # Research keywords  
    research_keywords = [
        "搜索", "调研", "收集", "整理", "市场", "技术", "文档", 
        "报告", "研究", "分析"
    ]
    
    data_score = sum(1 for kw in data_keywords if kw in query_lower)
    research_score = sum(1 for kw in research_keywords if kw in query_lower)
    
    if data_score > research_score and data_score >= 2:
        workflow_type = WorkflowType.DATA_ANALYSIS
    elif research_score > data_score and research_score >= 2:
        workflow_type = WorkflowType.TRADITIONAL_RESEARCH
    elif data_score > 0 and research_score > 0:
        workflow_type = WorkflowType.HYBRID
    else:
        workflow_type = WorkflowType.TRADITIONAL_RESEARCH  # Default
    
    # Simple complexity assessment
    complexity = TaskComplexity.SIMPLE
    if len(query_lower.split()) > 10:
        complexity = TaskComplexity.MODERATE
    if any(word in query_lower for word in ["综合", "多维", "复杂", "深度"]):
        complexity = TaskComplexity.COMPLEX
    
    return IntentClassification(
        workflow_type=workflow_type,
        complexity=complexity,
        confidence=0.7,
        reasoning="基于关键词匹配的后备分类",
        data_indicators=[kw for kw in data_keywords if kw in query_lower],
        research_indicators=[kw for kw in research_keywords if kw in query_lower],
        domain_keywords=[]
    )