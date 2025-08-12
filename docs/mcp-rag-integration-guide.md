# DeerFlow MCP & RAG 集成使用指南

## 概述

本文档详细描述DeerFlow中MCP (Model Context Protocol)和RAG (Retrieval-Augmented Generation)的集成位置、调用方式和具体用途。

## 🔧 MCP (Model Context Protocol) 集成

### MCP调用位置

#### 1. 配置层面 (`src/config/configuration.py`)
```python
@dataclass(kw_only=True)
class Configuration:
    mcp_settings: dict = None  # MCP设置，包括动态加载的工具
```

#### 2. 服务器层面 (`src/server/mcp_utils.py`, `src/server/mcp_request.py`)
- **MCP服务器发现和连接**
- **动态工具加载和管理**
- **MCP协议通信处理**

#### 3. 工具集成 (`src/config/tools.py`)
- **动态工具注册机制**
- **MCP工具与LangChain工具的适配**

### MCP具体用途

#### A. 动态工具扩展
```python
# 在运行时动态添加新工具
mcp_settings = {
    "servers": {
        "filesystem": {
            "command": "uv",
            "args": ["tool", "run", "mcp-server-filesystem", "/path/to/allowed/files"]
        },
        "git": {
            "command": "uvx", 
            "args": ["mcp-server-git", "--repository", "/path/to/repo"]
        }
    }
}
```

#### B. 外部系统集成
- **文件系统操作** - 通过filesystem MCP服务器
- **Git版本控制** - 通过git MCP服务器  
- **数据库连接** - 通过自定义数据库MCP服务器
- **API集成** - 通过各种API MCP服务器

#### C. 工具链扩展
```python
# src/config/tools.py 中的动态工具加载
def load_mcp_tools(mcp_settings: dict) -> List[Tool]:
    """从MCP设置中动态加载工具"""
    tools = []
    for server_name, server_config in mcp_settings.get("servers", {}).items():
        # 连接MCP服务器并获取可用工具
        mcp_client = MCPClient(server_config)
        server_tools = mcp_client.get_available_tools()
        tools.extend(server_tools)
    return tools
```

### MCP在节点中的使用

#### 1. Research Node (`src/graph/nodes.py`)
```python
async def researcher_node(state: State, config: RunnableConfig):
    # 获取MCP工具
    mcp_tools = get_mcp_tools(config)
    
    # 将MCP工具添加到研究工具中
    research_tools = [search_tool, crawl_tool] + mcp_tools
    
    # 使用增强的工具集进行研究
    return await _setup_and_execute_agent_step(
        state, config, "researcher", research_tools
    )
```

#### 2. Coder Node (`src/graph/nodes.py`)
```python
async def coder_node(state: State, config: RunnableConfig):
    # 获取代码相关的MCP工具（如git, filesystem）
    code_tools = [python_repl_tool] + get_mcp_tools_by_category(config, "development")
    
    return await _setup_and_execute_agent_step(
        state, config, "coder", code_tools
    )
```

---

## 📚 RAG (Retrieval-Augmented Generation) 集成

### RAG调用位置

#### 1. 核心RAG模块 (`src/rag/`)

##### A. 检索器 (`src/rag/retriever.py`)
```python
class Resource:
    """RAG资源配置"""
    url: str           # 资源URL (支持 rag://, http://, file://)
    description: str   # 资源描述
    
def create_retriever(resources: List[Resource]) -> VectorStoreRetriever:
    """创建向量存储检索器"""
    # 处理不同类型的资源
    # 构建FAISS向量数据库
    # 返回配置好的检索器
```

##### B. 知识库构建 (`src/rag/builder.py`)
```python
async def build_knowledge_base(resources: List[Resource]) -> VectorStore:
    """构建知识库"""
    documents = []
    for resource in resources:
        if resource.url.startswith("rag://"):
            # 处理RAG协议资源
            docs = await load_rag_resource(resource.url)
        elif resource.url.startswith("http"):
            # 处理Web资源
            docs = await crawl_and_extract(resource.url)
        documents.extend(docs)
    
    # 构建向量数据库
    return create_vector_store(documents)
```

#### 2. 配置集成 (`src/config/configuration.py`)
```python
@dataclass(kw_only=True)
class Configuration:
    resources: list[Resource] = field(default_factory=list)  # RAG资源配置
```

#### 3. 工具集成 (`src/tools/retriever.py`)
```python
@tool
def rag_retrieval_tool(query: str, resources: List[Resource]) -> str:
    """RAG检索工具"""
    retriever = create_retriever(resources)
    relevant_docs = retriever.get_relevant_documents(query)
    return format_retrieved_documents(relevant_docs)
```

### RAG具体用途

#### A. 知识增强研究 (`src/graph/nodes.py`)
```python
async def researcher_node(state: State, config: RunnableConfig):
    """研究节点中的RAG使用"""
    
    # 获取配置的RAG资源
    deer_config = get_configuration(config)
    rag_resources = deer_config.resources
    
    if rag_resources:
        # 创建RAG检索工具
        rag_tool = create_rag_retrieval_tool(rag_resources)
        research_tools = [search_tool, crawl_tool, rag_tool]
    else:
        research_tools = [search_tool, crawl_tool]
    
    # 执行增强的研究任务
    return await _setup_and_execute_agent_step(
        state, config, "researcher", research_tools
    )
```

#### B. 上下文感知处理
```python
# 在planner.md提示词中使用RAG
"""
1. **Research Steps** (`need_search: true`):
   - Retrieve information from the file with the URL with `rag://` prefix
   - 从用户指定的rag://资源中检索信息
   - 结合向量相似性搜索获得最相关的内容
"""
```

#### C. 多源知识整合
```python
# 用户可以配置多种RAG资源
resources = [
    Resource(url="rag://company-docs", description="公司内部文档"),
    Resource(url="rag://product-manual", description="产品使用手册"),
    Resource(url="http://example.com/article", description="外部参考资料")
]
```

### RAG在数据分析中的使用

#### 专业领域RAG (`src/tools/data_analysis/rag_tools.py`)
```python
@tool
def domain_knowledge_tool(query: str, k: int = 3) -> str:
    """领域专业知识检索"""
    # 使用FAISS向量存储进行语义搜索
    vector_store = get_vector_store()  # 电信客户流失分析手册
    docs = vector_store.similarity_search(query, k=k)
    
    # 格式化返回专业知识
    return format_domain_knowledge(docs)
```

---

## 🔄 MCP与RAG协同工作流程

### 1. 资源发现阶段
```
用户请求 → MCP服务器发现可用资源 → RAG资源配置 → 知识库构建
```

### 2. 查询执行阶段
```
查询分析 → RAG检索相关知识 → MCP工具增强处理 → 综合结果生成
```

### 3. 具体示例

#### 场景：技术文档分析
```python
# 1. 用户配置
resources = [
    Resource(url="rag://tech-docs", description="技术文档库"),
    Resource(url="rag://api-specs", description="API规范文档")
]

mcp_settings = {
    "servers": {
        "filesystem": {"command": "mcp-server-filesystem", "args": ["/docs"]},
        "git": {"command": "mcp-server-git", "args": ["--repo", "/project"]}
    }
}

# 2. 执行流程
query = "如何实现用户认证功能？"

# RAG检索相关文档
rag_results = rag_retrieval_tool(query, resources)

# MCP工具获取代码示例
code_examples = filesystem_tool.read_files("/auth/examples/")

# 综合生成回答
final_answer = combine_rag_and_mcp_results(rag_results, code_examples)
```

---

## 📋 配置示例

### 完整配置示例 (`conf.yaml`)
```yaml
# RAG配置
resources:
  - url: "rag://internal-docs"
    description: "内部技术文档"
  - url: "rag://customer-data" 
    description: "客户数据分析手册"
  - url: "http://company-wiki.com/api-docs"
    description: "API文档"

# MCP配置
mcp_settings:
  servers:
    filesystem:
      command: "uv"
      args: ["tool", "run", "mcp-server-filesystem", "/workspace"]
    git:
      command: "uvx"
      args: ["mcp-server-git", "--repository", "/project"]
    database:
      command: "python"
      args: ["-m", "mcp_server_database", "--connection", "mysql://..."]

# 数据分析配置
database_config:
  host: "localhost"
  user: "analyst"
  password: "${DB_PASSWORD}"
  database: "analytics"
  
vector_store_path: "knowledge_base/domain_knowledge"
chart_output_path: "static/images"
```

### 程序化配置示例
```python
from src.config.configuration import Configuration
from src.rag.retriever import Resource

# 创建配置
config = Configuration(
    resources=[
        Resource(url="rag://domain-knowledge", description="专业领域知识"),
        Resource(url="file:///docs/manual.pdf", description="用户手册")
    ],
    mcp_settings={
        "servers": {
            "data": {
                "command": "python",
                "args": ["-m", "data_mcp_server"]
            }
        }
    },
    database_config={
        "host": "localhost",
        "database": "analytics"
    }
)
```

---

## 🎯 使用场景总结

| 场景 | MCP用途 | RAG用途 | 协同效果 |
|------|---------|---------|----------|
| **代码分析** | Git操作、文件读取 | 技术文档检索 | 代码+文档综合分析 |
| **数据分析** | 数据库连接、API调用 | 业务知识检索 | 数据+领域知识结合 |
| **研究报告** | 外部工具集成 | 学术资料检索 | 工具增强+知识支撑 |
| **产品开发** | 开发工具链 | 需求文档检索 | 开发+需求对齐 |

这个集成架构使DeerFlow具备了强大的扩展性和知识增强能力，通过MCP实现工具生态扩展，通过RAG实现知识库增强，两者结合形成了完整的AI研究助手系统。