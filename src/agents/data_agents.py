"""
Data Analysis Agent Factory for DeerFlow

Creates specialized data analysis agents including RAG, SQL, and Python agents.
Integrates existing data analysis capabilities into DeerFlow's multi-agent system.
"""

import os
from typing import Optional, List
from langchain_core.language_models import BaseChatModel
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.tools.retriever import create_retriever_tool
from langgraph.prebuilt import create_react_agent
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field

from src.config.configuration import Configuration
from src.tools.data_analysis.sql_tools import sql_tools
from src.tools.data_analysis.python_tools import python_tools  
from src.tools.data_analysis.rag_tools import rag_tools, create_domain_retriever_tool
from src.llms.llm import get_llm_by_type


def create_rag_agent(config: Configuration, model: Optional[BaseChatModel] = None) -> StateGraph:
    """
    Create RAG agent for domain knowledge retrieval.
    
    Args:
        config: DeerFlow configuration object
        model: Optional language model (uses default if not provided)
        
    Returns:
        Compiled RAG agent StateGraph
    """
    if model is None:
        model = get_llm_by_type("coordinator")
    
    # Create retriever tool
    retriever_tool = create_domain_retriever_tool(config)
    if not retriever_tool:
        raise ValueError("Failed to initialize vector store for RAG agent")
    
    # RAG agent system prompt
    rag_system_prompt = """你是电信客户流失分析领域的专家助手。你可以回答与电信客户流失分析手册相关的问题，包括：

    - 客户流失预测策略和方法
    - 数据字典和特征定义
    - 建模方法和最佳实践  
    - 业务洞察和解释
    - 特征工程技巧

    如果用户的问题与此文档无关，请回复："我只能回答与电信客户流失分析手册相关的问题。"
    当你需要更多上下文时，请使用提供的工具 `retrieve_telco_handbook` 来搜索文档。

    请用简体中文回答，提供详细、结构化的答案。"""
    
    # Create RAG agent using create_react_agent
    return create_react_agent(
        model=model,
        tools=[retriever_tool],
        prompt=rag_system_prompt
    )


def create_sql_agent(config: Configuration, model: Optional[BaseChatModel] = None) -> StateGraph:
    """
    Create SQL agent for database operations.
    
    Args:
        config: DeerFlow configuration object
        model: Optional language model (uses default if not provided)
        
    Returns:
        Compiled SQL agent StateGraph
    """
    if model is None:
        model = get_llm_by_type("coder")
    
    # SQL agent system prompt
    sql_system_prompt = """你是一名经验丰富的数据库专家，擅长MySQL数据库操作和数据提取：

    **主要能力：**
    1. **数据库查询** - 使用 `sql_query_tool` 执行SQL查询获取数据库信息
    2. **数据提取** - 使用 `extract_data_tool` 将数据库表提取到pandas DataFrame中

    **工作原则：**
    - 根据用户需求生成准确的SQL语句
    - 为后续分析准备好数据，将数据提取到DataFrame中
    - 提供清晰的数据查询结果和状态反馈
    - 注意数据库连接配置已内置，你只需专注SQL逻辑

    **注意事项：**
    - 数据库名为 telco_data，包含电信客户相关数据表
    - 使用 sql_query_tool 进行数据探索和查询
    - 使用 extract_data_tool 将查询结果提取为DataFrame供Python分析

    请用简体中文回答，提供专业的数据库操作服务。"""
    
    return create_react_agent(
        model=model,
        tools=sql_tools,
        prompt=sql_system_prompt
    )


def create_python_agent(config: Configuration, model: Optional[BaseChatModel] = None) -> StateGraph:
    """
    Create Python agent for data analysis and visualization.
    
    Args:
        config: DeerFlow configuration object  
        model: Optional language model (uses default if not provided)
        
    Returns:
        Compiled Python agent StateGraph
    """
    if model is None:
        model = get_llm_by_type("coder")
    
    # Python agent system prompt
    python_system_prompt = """你是一名经验丰富的Python数据分析和可视化专家：

    **主要能力：**
    1. **数据分析** - 使用 `python_execution_tool` 执行数据处理、统计计算、机器学习等任务
    2. **数据可视化** - 使用 `visualization_tool` 创建图表、绘制分布、生成报表图像

    **工作原则：**
    - 使用pandas进行数据处理和分析
    - 使用matplotlib/seaborn创建专业的可视化图表
    - 提供详细的分析结果和数据洞察
    - 确保代码的健壮性和可读性

    **可视化要求：**
    - 创建图表时必须使用 `fig = plt.figure()` 或 `fig, ax = plt.subplots()` 
    - 图表标签、标题、图例使用英文描述
    - 不要使用 `plt.show()`，图像会自动保存
    - 确保调用 `fig.tight_layout()` 优化布局

    **回答要求：**
    - 如果生成了图表，请在回答中使用Markdown格式插入图片：`![描述](images/fig.png)`
    - 用简体中文提供分析解释和业务洞察
    - 提供清晰的数据统计结果和可视化描述

    请提供专业的Python数据分析服务。"""
    
    return create_react_agent(
        model=model,
        tools=python_tools,
        prompt=python_system_prompt
    )


def create_data_analysis_agents(config: Configuration) -> tuple[StateGraph, StateGraph, StateGraph]:
    """
    Create all data analysis agents (RAG, SQL, Python).
    
    Args:
        config: DeerFlow configuration object
        
    Returns:
        Tuple of (rag_agent, sql_agent, python_agent)
    """
    try:
        rag_agent = create_rag_agent(config)
        sql_agent = create_sql_agent(config)  
        python_agent = create_python_agent(config)
        
        return rag_agent, sql_agent, python_agent
        
    except Exception as e:
        raise RuntimeError(f"Failed to create data analysis agents: {str(e)}")