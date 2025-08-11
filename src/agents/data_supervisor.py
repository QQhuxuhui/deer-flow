"""
Data Analysis Supervisor for DeerFlow

Intelligent supervisor that coordinates RAG, SQL, and Python agents for comprehensive data analysis.
Adapted from external data analysis module with DeerFlow integration.
"""

from typing import Literal, Optional
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph
from langgraph_supervisor import create_supervisor

from src.config.configuration import Configuration
from src.agents.data_agents import create_data_analysis_agents
from src.llms.llm import get_llm_by_type


def create_data_supervisor_prompt() -> str:
    """Create system prompt for data analysis supervisor."""
    return """你是一个顶级的AI数据分析项目总监，负责管理一个由三位专家组成的数据分析团队。
你的职责是根据用户的数据分析任务，智能调度合适的专家来完成工作。

**你的团队成员：**

1. **`rag_agent` (领域知识专家)**
   - **能力**: 访问《电信客户流失分析手册》，提供专业领域知识
   - **调用时机**:
     - 需要了解业务术语定义（如"高价值客户"、"流失预警期"）
     - 需要获取数据字典、字段含义、业务背景
     - 需要建模策略、特征工程等专业指导
     - 用户明确要求"根据手册"或"参考文档"

2. **`sql_agent` (数据库专家)**  
   - **能力**: 连接MySQL数据库，执行SQL查询和数据提取
   - **调用时机**:
     - 需要查询数据库获取具体数据
     - 需要了解数据库结构和表信息
     - **关键**: 当后续需要Python分析时，必须先用sql_agent提取数据到DataFrame

3. **`python_agent` (分析与可视化专家)**
   - **能力**: 执行Python代码进行数据分析、统计计算、可视化
   - **限制**: 不能直接访问数据库
   - **调用时机**:
     - 在sql_agent提取数据后，进行数据处理和分析
     - 需要统计计算、机器学习分析
     - 需要创建图表和可视化

**工作流程和规则：**

1. **分析任务需求**: 理解用户的完整需求，识别需要哪些专家参与
2. **遵循依赖关系**: 严格按照逻辑顺序分配任务
   - 需要领域知识 → 先调用 rag_agent
   - 需要数据分析 → 先用 sql_agent 提取数据，再用 python_agent 分析
   - 需要可视化 → 确保数据已提取，再用 python_agent 绘图
3. **循序渐进**: 每次只分配给一个专家，等待完成后再进行下一步
4. **任务完成判断**: 当用户的原始需求完全得到解决时，输出 `FINISH`

**决策选项**: 从 ['rag_agent', 'sql_agent', 'python_agent', 'FINISH'] 中选择下一步行动。

请根据用户需求，智能选择合适的专家来逐步完成数据分析任务。"""


def create_data_supervisor(config: Configuration, model: Optional[BaseChatModel] = None) -> StateGraph:
    """
    Create data analysis supervisor that coordinates RAG, SQL, and Python agents.
    
    Args:
        config: DeerFlow configuration object
        model: Optional language model (uses coordinator model if not provided)
        
    Returns:
        Compiled supervisor StateGraph
    """
    if model is None:
        model = get_llm_by_type("coordinator")
    
    # Create specialized agents
    try:
        rag_agent, sql_agent, python_agent = create_data_analysis_agents(config)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize data analysis agents: {str(e)}")
    
    # Create supervisor using langgraph_supervisor
    supervisor = create_supervisor(
        model=model,
        agents=[rag_agent, sql_agent, python_agent],
        prompt=create_data_supervisor_prompt(),
        add_handoff_back_messages=True
    )
    
    return supervisor.compile()


def create_lightweight_data_supervisor(config: Configuration) -> StateGraph:
    """
    Create a lightweight version of data supervisor for testing and development.
    
    Args:
        config: DeerFlow configuration object
        
    Returns:
        Compiled lightweight supervisor StateGraph
    """
    # Use faster model for development
    model = get_llm_by_type("researcher")  # Typically faster than coordinator
    
    return create_data_supervisor(config, model)