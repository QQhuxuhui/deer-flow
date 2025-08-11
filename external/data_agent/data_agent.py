from __future__ import annotations

import os
import asyncio
from typing import Literal
from dotenv import load_dotenv 
load_dotenv(override=True)
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.tools.retriever import create_retriever_tool
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field
from dotenv import load_dotenv 
load_dotenv(override=True)
from langchain_deepseek import ChatDeepSeek
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langgraph_supervisor import create_supervisor
from pydantic import BaseModel, Field
import matplotlib
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import pymysql
from langchain_tavily import TavilySearch

# ---------------------------------------------------------------------------
# LLM & Embeddings
# ---------------------------------------------------------------------------
model = ChatDeepSeek(model="deepseek-chat")
grader_model = ChatDeepSeek(model="deepseek-chat")

embed = OpenAIEmbeddings(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ai.devtool.tech/proxy/v1",
    model="text-embedding-3-small",
)

# ---------------------------------------------------------------------------
# Vector store & Retriever tool
# ---------------------------------------------------------------------------
VS_PATH = "telco_customer_churn_analytics_handbook"

vector_store = FAISS.load_local(
    folder_path=VS_PATH,
    embeddings=embed,
    allow_dangerous_deserialization=True,
)
retriever_tool = create_retriever_tool(
    vector_store.as_retriever(search_kwargs={"k": 3}),
    name="retrieve_telco_handbook",
    description="Search and return relevant sections from the Telco Customer Churn Analytics Handbook.",
)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
SYSTEM_INSTRUCTION = (
    "You are a telecom data analysis assistant. You can answer ONLY questions related to the "
    "Telco Customer Churn Analytics Handbook, including topics such as customer churn prediction, "
    "data dictionary, modeling strategies, visualization analysis, business insights, and feature engineering. "
    "If the user's question is NOT related to this document, reply exactly: '我只能回答与电信客户流失分析手册相关的问题。' "
    "You may call the provided tool `retrieve_telco_handbook` when you need more context from the document."
)

GRADE_PROMPT = (
    "You are a grader assessing relevance of a retrieved document to a user question.\n"
    "Retrieved document:\n{context}\n\nUser question: {question}\n"
    "Return 'yes' if relevant, otherwise 'no'."
)

REWRITE_PROMPT = (
    "You are a telecom domain expert assistant.\n"
    "Given a user's question about the Telco Customer Churn Analytics Handbook, "
    "your task is to rewrite or expand it in a way that captures the underlying intent clearly, "
    "while improving its recall ability for document-based retrieval. Use formal and unambiguous wording.\n\n"
    "Original question:\n{question}\n\n"
    "Improved version:"
)


ANSWER_PROMPT = (
    "You are an expert assistant trained on the Telco Customer Churn Analytics Handbook.\n"
    "Please use the provided context to answer the question in a detailed, structured manner.\n"
    "Your answer should ideally include:\n"
    "- A concise summary of the relevant concept or finding\n"
    "- An explanation of its background or rationale\n"
    "- Practical implications or usage suggestions\n"
    "- Any supporting statistics or examples from the document\n\n"
    "If the context lacks relevant information, reply with: '很抱歉，我无法从手册中找到相关信息。'\n\n"
    "Question:\n{question}\n\n"
    "Context:\n{context}\n\n"
    "Answer:"
)

# ---------------------------------------------------------------------------
# LangGraph Nodes
# ---------------------------------------------------------------------------
async def generate_query_or_respond(state: MessagesState):
    """LLM decides to answer directly or call retriever tool."""
    response = await model.bind_tools([retriever_tool]).ainvoke(
        [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            *state["messages"],
        ]
    )
    return {"messages": [response]}


class GradeDoc(BaseModel):
    binary_score: str = Field(description="Relevance score 'yes' or 'no'.")


async def grade_documents(state: MessagesState) -> Literal["generate_answer", "rewrite_question"]:
    question = state["messages"][0].content  # original user question
    ctx = state["messages"][-1].content      # retriever output
    prompt = GRADE_PROMPT.format(question=question, context=ctx)
    result = await grader_model.with_structured_output(GradeDoc).ainvoke([
        {"role": "user", "content": prompt}
    ])
    return "generate_answer" if result.binary_score.lower().startswith("y") else "rewrite_question"


async def rewrite_question(state: MessagesState):
    question = state["messages"][0].content
    prompt = REWRITE_PROMPT.format(question=question)
    resp = await model.ainvoke([{"role": "user", "content": prompt}])
    return {"messages": [{"role": "user", "content": resp.content}]}


async def generate_answer(state: MessagesState):
    question = state["messages"][0].content
    ctx = state["messages"][-1].content
    prompt = ANSWER_PROMPT.format(question=question, context=ctx)
    resp = await model.ainvoke([{"role": "user", "content": prompt}])
    return {"messages": [resp]}

# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------
workflow = StateGraph(MessagesState)
workflow.add_node("generate_query_or_respond", generate_query_or_respond)
workflow.add_node("retrieve", ToolNode([retriever_tool]))
workflow.add_node("rewrite_question", rewrite_question)
workflow.add_node("generate_answer", generate_answer)

workflow.add_edge(START, "generate_query_or_respond")
workflow.add_conditional_edges(
    "generate_query_or_respond", tools_condition, {"tools": "retrieve", END: END}
)
workflow.add_conditional_edges("retrieve", grade_documents)
workflow.add_edge("generate_answer", END)
workflow.add_edge("rewrite_question", "generate_query_or_respond")

rag_agent = workflow.compile(name="rag_agent")

# ✅ 创建SQL查询工具
description = """
当用户需要进行数据库查询工作时，请调用该函数。
该函数用于在指定MySQL服务器上运行一段SQL代码，完成数据查询相关工作，
并且当前函数是使用pymsql连接MySQL数据库。
本函数只负责运行SQL代码并进行数据查询，若要进行数据提取，则使用另一个extract_data函数。
"""

# 定义结构化参数模型
class SQLQuerySchema(BaseModel):
    sql_query: str = Field(description=description)

# 封装为 LangGraph 工具
@tool(args_schema=SQLQuerySchema)
def sql_inter(sql_query: str) -> str:
    """
    当用户需要进行数据库查询工作时，请调用该函数。
    该函数用于在指定MySQL服务器上运行一段SQL代码，完成数据查询相关工作，
    并且当前函数是使用pymsql连接MySQL数据库。
    本函数只负责运行SQL代码并进行数据查询，若要进行数据提取，则使用另一个extract_data函数。
    :param sql_query: 字符串形式的SQL查询语句，用于执行对MySQL中telco_data数据库中各张表进行查询，并获得各表中的各类相关信息
    :return：sql_query在MySQL中的运行结果。   
    """
    # print("正在调用 sql_inter 工具运行 SQL 查询...")
    
    # 加载环境变量
    load_dotenv(override=True)
    host = os.getenv('HOST')
    user = os.getenv('USER')
    mysql_pw = os.getenv('MYSQL_PW')
    db = os.getenv('DB_NAME')
    port = os.getenv('PORT')
    
    # 创建连接
    connection = pymysql.connect(
        host=host,
        user=user,
        passwd=mysql_pw,
        db=db,
        port=int(port),
        charset='utf8'
    )
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql_query)
            results = cursor.fetchall()
            # print("SQL 查询已成功执行，正在整理结果...")
    finally:
        connection.close()

    # 将结果以 JSON 字符串形式返回
    return json.dumps(results, ensure_ascii=False)

# ✅ 创建数据提取工具
# 定义结构化参数
class ExtractQuerySchema(BaseModel):
    sql_query: str = Field(description="用于从 MySQL 提取数据的 SQL 查询语句。")
    df_name: str = Field(description="指定用于保存结果的 pandas 变量名称（字符串形式）。")

# 注册为 Agent 工具
@tool(args_schema=ExtractQuerySchema)
def extract_data(sql_query: str, df_name: str) -> str:
    """
    用于在MySQL数据库中提取一张表到当前Python环境中，注意，本函数只负责数据表的提取，
    并不负责数据查询，若需要在MySQL中进行数据查询，请使用sql_inter函数。
    同时需要注意，编写外部函数的参数消息时，必须是满足json格式的字符串，
    :param sql_query: 字符串形式的SQL查询语句，用于提取MySQL中的某张表。
    :param df_name: 将MySQL数据库中提取的表格进行本地保存时的变量名，以字符串形式表示。
    :return：表格读取和保存结果
    """
    print("正在调用 extract_data 工具运行 SQL 查询...")
    
    load_dotenv(override=True)
    host = os.getenv('HOST')
    user = os.getenv('USER')
    mysql_pw = os.getenv('MYSQL_PW')
    db = os.getenv('DB_NAME')
    port = os.getenv('PORT')

    # 创建数据库连接
    connection = pymysql.connect(
        host=host,
        user=user,
        passwd=mysql_pw,
        db=db,
        port=int(port),
        charset='utf8'
    )

    try:
        # 执行 SQL 并保存为全局变量
        df = pd.read_sql(sql_query, connection)
        globals()[df_name] = df
        # print("数据成功提取并保存为全局变量：", df_name)
        return f"✅ 成功创建 pandas 对象 `{df_name}`，包含从 MySQL 提取的数据。"
    except Exception as e:
        return f"❌ 执行失败：{e}"
    finally:
        connection.close()

SQL_Agent_prompt = """
你是一名经验丰富的智能数据分析助手，擅长帮助用户高效完成以下任务：

1. **数据库查询：**
   - 当用户需要获取数据库中某些数据或进行SQL查询时，请调用`sql_inter`工具，该工具已经内置了pymysql连接MySQL数据库的全部参数，包括数据库名称、用户名、密码、端口等，你只需要根据用户需求生成SQL语句即可。
   - 你需要准确根据用户请求生成SQL语句，例如 `SELECT * FROM 表名` 或包含条件的查询。

2. **数据表提取：**
   - 当用户希望将数据库中的表格导入Python环境进行后续分析时，请调用`extract_data`工具。
   - 你需要根据用户提供的表名或查询条件生成SQL查询语句，并将数据保存到指定的pandas变量中。
"""

sql_tool = [sql_inter, extract_data]
sql_agent = create_react_agent(model=model, tools=sql_tool, prompt=SQL_Agent_prompt, name="sql_agent")


# ✅创建Python代码执行工具
# Python代码执行工具结构化参数说明
class PythonCodeInput(BaseModel):
    py_code: str = Field(description="一段合法的 Python 代码字符串，例如 '2 + 2' 或 'x = 3\\ny = x * 2'")

@tool(args_schema=PythonCodeInput)
def python_inter(py_code):
    """
    当用户需要编写Python程序并执行时，请调用该函数。
    该函数可以执行一段Python代码并返回最终结果，需要注意，本函数只能执行非绘图类的代码，若是绘图相关代码，则需要调用fig_inter函数运行。
    """    
    g = globals()
    try:
        # 尝试如果是表达式，则返回表达式运行结果
        return str(eval(py_code, g))
    # 若报错，则先测试是否是对相同变量重复赋值
    except Exception as e:
        global_vars_before = set(g.keys())
        try:            
            exec(py_code, g)
        except Exception as e:
            return f"代码执行时报错{e}"
        global_vars_after = set(g.keys())
        new_vars = global_vars_after - global_vars_before
        # 若存在新变量
        if new_vars:
            result = {var: g[var] for var in new_vars}
            # print("代码已顺利执行，正在进行结果梳理...")
            return str(result)
        else:
            # print("代码已顺利执行，正在进行结果梳理...")
            return "已经顺利执行代码"

# ✅ 创建绘图工具
# 绘图工具结构化参数说明
class FigCodeInput(BaseModel):
    py_code: str = Field(description="要执行的 Python 绘图代码，必须使用 matplotlib/seaborn 创建图像并赋值给变量")
    fname: str = Field(description="图像对象的变量名，例如 'fig'，用于从代码中提取并保存为图片")

@tool(args_schema=FigCodeInput)
def fig_inter(py_code: str, fname: str) -> str:
    """
    当用户需要使用 Python 进行可视化绘图任务时，请调用该函数。

    注意：
    1. 所有绘图代码必须创建一个图像对象，并将其赋值为指定变量名（例如 `fig`）。
    2. 必须使用 `fig = plt.figure()` 或 `fig = plt.subplots()`。
    3. 不要使用 `plt.show()`。
    4. 请确保代码最后调用 `fig.tight_layout()`。
    5. 所有绘图代码中，坐标轴标签（xlabel、ylabel）、标题（title）、图例（legend）等文本内容，必须使用英文描述。

    示例代码：
    fig = plt.figure(figsize=(10,6))
    plt.plot([1,2,3], [4,5,6])
    fig.tight_layout()
    """
    # print("正在调用fig_inter工具运行Python代码...")

    current_backend = matplotlib.get_backend()
    matplotlib.use('Agg')

    local_vars = {"plt": plt, "pd": pd, "sns": sns}
    
    # ✅ 设置图像保存路径（你自己的绝对路径）
    base_dir = r"C:\Users\Administrator\Desktop\Data_Agent_Pro\agent-chat-ui\public"
    images_dir = os.path.join(base_dir, "images")
    os.makedirs(images_dir, exist_ok=True)  # ✅ 自动创建 images 文件夹（如不存在）
    try:
        g = globals()
        exec(py_code, g, local_vars)
        g.update(local_vars)

        fig = local_vars.get(fname, None)
        if fig:
            image_filename = f"{fname}.png"
            abs_path = os.path.join(images_dir, image_filename)  # ✅ 绝对路径
            rel_path = os.path.join("images", image_filename)    # ✅ 返回相对路径（给前端用）

            fig.savefig(abs_path, bbox_inches='tight')
            return f"✅ 图片已保存，路径为: {rel_path}"
        else:
            return "⚠️ 图像对象未找到，请确认变量名正确并为 matplotlib 图对象。"
    except Exception as e:
        return f"❌ 执行失败：{e}"
    finally:
        plt.close('all')
        matplotlib.use(current_backend)

Python_Agent_prompt = """
你是一名经验丰富的智能数据分析助手，擅长帮助用户高效完成以下任务：

1. **非绘图类任务的Python代码执行：**
   - 当用户需要执行Python脚本或进行数据处理、统计计算时，请调用`python_inter`工具。
   - 仅限执行非绘图类代码，例如变量定义、数据分析等。

2. **绘图类Python代码执行：**
   - 当用户需要进行可视化展示（如生成图表、绘制分布等）时，请调用`fig_inter`工具。
   - 你可以直接读取数据并进行绘图，不需要借助`python_inter`工具读取图片。
   - 你应根据用户需求编写绘图代码，并正确指定绘图对象变量名（如 `fig`）。
   - 当你生成Python绘图代码时必须指明图像的名称，如fig = plt.figure()或fig = plt.subplots()创建图像对象，并赋值为fig。
   - 不要调用plt.show()，否则图像将无法保存。

**回答要求：**
- 所有回答均使用**简体中文**，清晰、礼貌、简洁。
- 若需要用户提供更多信息，请主动提出明确的问题。
- 如果有生成的图片文件，不要仅输出图片路径文字，或者仅申明已经绘制完图像，请务必在回答中使用Markdown格式插入图片，如：![Categorical Features vs Churn](images/fig.png)
"""

python_tool = [python_inter, fig_inter]
python_agent = create_react_agent(model=model, tools=python_tool, prompt=Python_Agent_prompt, name="python_agent")

SUPERVISOR_PROMPT = """你是一个顶级的AI项目总监，负责管理一个由三位专家组成的AI数据分析团队。
你的唯一职责是：根据用户的原始任务和当前的进展，决定下一步应该将任务分配给哪一位专家。你本人不直接执行任务。

**你的团队成员档案如下:**

1.  **`rag_agent` (文档与知识库专家)**
    - **能力**: 能够访问并理解《电信客户流失分析手册》。
    - **调用时机**:
        - 当用户的请求中包含**模糊的业务术语**（例如“高价值客户”、“流失预警期”等）需要从手册中查找定义时。
        - 当需要了解**数据来源、字段含义、或业务背景**才能进行下一步的SQL或Python操作时。
        - 当用户明确要求**“根据手册/文档”**进行查询时。

2.  **`sql_agent` (数据库操作专家)**
    - **能力**: 能够直接连接数据库执行SQL操作。需要套注意的是，sql_agent已经保存了数据库相关信息，知道如何连接数据库并查找对应的数据集。
    - **调用时机**:
        - 当需要**直接查询数据**以回答问题时（例如“数据库里有多少用户？”）。
        - **关键**: 当后续的 `python_agent` 需要对数据进行分析或绘图时，你必须先调用 `sql_agent` 使用 `extract_data` 工具将数据**提取到一个 pandas DataFrame** 中。

3.  **`python_agent` (Python数据分析与可视化专家)**
    - **能力**: 能够执行Python代码进行复杂计算和数据可视化。**它不能直接访问数据库**。
    - **调用时机**:
        - 在 `sql_agent` 已经将数据提取到 DataFrame 之后，用它来进行**数据处理、计算或统计分析**。
        - 在数据准备好后，用它来**绘制图表**。       

**工作流程与规则**:
- **审视全局**: 查看用户的原始任务（Task）和最新的消息历史（Messages），理解当前所处的阶段。
- **循序渐进**: 每次只分配一个任务给一个专家。
- **逻辑依赖**: 严格遵守依赖关系。如果需要绘图，必须先用 `sql_agent` 提取数据，再用 `python_agent` 绘图。如果SQL查询需要领域知识，必须先用 `rag_agent` 获取知识。
- **任务完成**: 当你判断用户的原始任务已经完全被解决时，输出 `FINISH`。
- **做出决策**: 从 `['rag_agent', 'sql_agent', 'python_agent', 'FINISH']` 中选择一个作为下一步行动。
- **注意事项**: 如果用户提出需要进行可视化分析，需要对图像进行打印，而不仅仅输出绘图完成等字样。
"""

from langchain.chat_models import init_chat_model
supervisor = create_supervisor(
    model=init_chat_model(model="deepseek-chat", model_provider="deepseek", temperature=0),
    agents=[rag_agent, python_agent, sql_agent],
    prompt=SUPERVISOR_PROMPT,
    add_handoff_back_messages=True
).compile()