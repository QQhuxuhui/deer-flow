# DeerFlow 文档索引

## 📚 快速导航

### 核心架构文档
- **[Architecture Guide](architecture-guide.md)** - 完整的系统架构说明
- **[Developer Guide](developer-guide.md)** - 开发指南和最佳实践  
- **[Deployment Guide](deployment-guide.md)** - 部署和配置指南

### MCP & RAG 集成
- **[MCP & RAG Integration Guide](mcp-rag-integration-guide.md)** - MCP和RAG的详细使用指南
- **[Architecture Guide - MCP Integration](architecture-guide.md#mcp-integration)** - MCP架构集成说明
- **[Architecture Guide - RAG System](architecture-guide.md#rag-system)** - RAG系统架构说明

### 数据分析模块
- **[Data Analysis Integration](data-analysis-integration.md)** - 完整的数据分析模块集成方案
- **[Data Analysis Integration Summary](data-analysis-integration-summary.md)** - 集成完成总结
- **[Architecture Guide - Data Analysis Module](architecture-guide.md#data-analysis-module)** - 数据分析架构说明

### MCP具体使用位置

#### 1. 配置层面
- **文件位置**: `src/config/configuration.py`
- **用途**: MCP服务器配置和设置
- **文档**: [MCP Integration Guide - Configuration](mcp-rag-integration-guide.md#mcp调用位置)

#### 2. 动态工具加载  
- **文件位置**: `src/config/tools.py`
- **用途**: 运行时动态加载MCP工具
- **文档**: [Architecture Guide - Dynamic Tool Loading](architecture-guide.md#2-dynamic-tool-loading-srcconfigtoolspy)

#### 3. 节点集成
- **文件位置**: `src/graph/nodes.py` 
- **用途**: 在研究和编码节点中集成MCP工具
- **具体节点**: 
  - `researcher_node` - 集成搜索和文件操作MCP工具
  - `coder_node` - 集成Git和开发相关MCP工具

### RAG具体使用位置

#### 1. 核心RAG模块
- **文件位置**: `src/rag/retriever.py`, `src/rag/builder.py`
- **用途**: 向量存储构建和知识检索
- **文档**: [RAG System - Integration Points](architecture-guide.md#rag-integration-points)

#### 2. 资源配置
- **文件位置**: `src/config/configuration.py`
- **用途**: 配置RAG资源 (rag://, http://, file://)
- **支持格式**: 
  - `rag://` - RAG协议资源
  - `http://` - Web资源爬取
  - `file://` - 本地文件系统

#### 3. 检索工具集成
- **文件位置**: `src/tools/retriever.py`
- **用途**: 向量相似性搜索工具
- **在节点中使用**: `researcher_node` 自动使用RAG工具增强研究能力

#### 4. 数据分析中的RAG
- **文件位置**: `src/tools/data_analysis/rag_tools.py`
- **用途**: 领域专业知识检索 (电信客户流失分析手册)
- **集成方式**: 通过数据分析supervisor协调使用

### 实际调用示例

#### MCP使用示例
```python
# 1. 配置MCP服务器
mcp_settings = {
    "servers": {
        "filesystem": {
            "command": "uv",
            "args": ["tool", "run", "mcp-server-filesystem", "/workspace"]
        }
    }
}

# 2. 在节点中自动加载
async def researcher_node(state, config):
    base_tools = [search_tool, crawl_tool]
    if config.mcp_settings:
        mcp_tools = load_mcp_tools(config.mcp_settings)  
        base_tools.extend(mcp_tools)
    # 工具自动可用于LLM使用
```

#### RAG使用示例  
```python
# 1. 配置RAG资源
resources = [
    Resource(url="rag://company-docs", description="公司文档"),
    Resource(url="http://wiki.company.com", description="公司Wiki")
]

# 2. 在查询中自动使用
query = "公司的项目管理流程是什么？"
# Planner识别需要rag://资源 → researcher_node自动使用RAG检索
```

### 配置文件示例

#### 完整配置 (`conf.yaml`)
```yaml
# RAG资源配置
resources:
  - url: "rag://internal-docs"
    description: "内部技术文档"
  - url: "file:///workspace/manuals/"
    description: "产品手册"

# MCP服务器配置  
mcp_settings:
  servers:
    filesystem:
      command: "uv"
      args: ["tool", "run", "mcp-server-filesystem", "/workspace"]
    git:
      command: "uvx" 
      args: ["mcp-server-git", "--repository", "/project"]

# 数据分析配置
database_config:
  host: "localhost"
  user: "analyst"
  database: "analytics"

vector_store_path: "knowledge_base"
chart_output_path: "static/images"
```

## 🔍 快速查找

### 想了解MCP？
- [MCP Integration Guide](mcp-rag-integration-guide.md#mcp-model-context-protocol-集成) - 完整MCP使用指南
- [Architecture Guide - MCP](architecture-guide.md#mcp-integration) - MCP架构说明

### 想了解RAG？ 
- [RAG Integration Guide](mcp-rag-integration-guide.md#rag-retrieval-augmented-generation-集成) - 完整RAG使用指南
- [Architecture Guide - RAG](architecture-guide.md#rag-system) - RAG系统架构

### 想了解数据分析？
- [Data Analysis Integration](data-analysis-integration.md) - 数据分析模块详细方案
- [Integration Summary](data-analysis-integration-summary.md) - 集成完成总结

### 想了解具体调用位置？
- [MCP & RAG Integration Guide](mcp-rag-integration-guide.md) - 详细的调用位置和使用场景

## 📋 问题排查

### MCP相关问题
1. **MCP工具不可用** → 检查 `mcp_settings` 配置
2. **MCP服务器连接失败** → 检查命令和参数设置
3. **工具动态加载失败** → 查看 `src/config/tools.py` 日志

### RAG相关问题
1. **RAG检索无结果** → 检查 `resources` 配置和向量存储
2. **rag://协议不支持** → 确保资源URL格式正确
3. **向量存储构建失败** → 检查文档格式和embeddings配置

### 数据分析问题
1. **数据分析步骤不触发** → 检查planner是否识别为 `data_analysis` 类型
2. **数据库连接失败** → 检查 `database_config` 和环境变量
3. **图表生成失败** → 检查 `chart_output_path` 权限和matplotlib配置