# DeerFlow Architecture Guide

> **For Developers**: Deep dive into DeerFlow's multi-agent system architecture, design patterns, and extensibility mechanisms.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Core Components](#core-components)
- [State Management](#state-management)
- [Agent Orchestration](#agent-orchestration)
- [Tool Integration](#tool-integration)
- [MCP Integration](#mcp-integration)
- [RAG System](#rag-system)
- [Data Analysis Module](#data-analysis-module)
- [Extension Points](#extension-points)
- [Performance Considerations](#performance-considerations)
- [Deployment Architecture](#deployment-architecture)

## Architecture Overview

DeerFlow implements a **state-driven multi-agent architecture** built on LangGraph, designed for scalable research automation and content generation. The system follows a **modular monolith pattern** with clear domain boundaries and plugin-based extensibility.

### Core Design Principles

1. **Declarative Workflows**: State transitions defined through LangGraph's StateGraph
2. **Agent Specialization**: Dedicated agents for specific domains (research, coding, planning)
3. **Pluggable Components**: Tool and LLM provider integration through standardized interfaces
4. **Human-in-Loop**: Interactive feedback mechanisms for plan refinement
5. **Fault Tolerance**: Graceful degradation and error recovery patterns

### High-Level Architecture

```mermaid
graph TD
    A[User Input] --> B[Coordinator Node]
    B --> C[Background Investigator]
    C --> D[Planner Node]
    D --> E[Human Feedback Node]
    E --> F[Research Team]
    F --> G[Reporter Node]
    G --> H[Final Output]
    
    F --> I[Researcher Node]
    F --> J[Coder Node]
    
    I --> K[Search Tools]
    I --> L[Crawling Tools]
    I --> M[RAG Tools]
    
    J --> N[Python REPL]
    J --> O[MCP Tools]
```

## Core Components

### 1. Graph Builder (`src/graph/builder.py`)

**Purpose**: Constructs the LangGraph state machine with proper node connections and flow control.

**Key Features**:
- **Node Registration**: Centralizes agent node definitions
- **Edge Management**: Defines state transition rules
- **Memory Integration**: Optional conversation persistence via MemorySaver
- **Conditional Routing**: Dynamic workflow paths based on state

```python
def build_graph():
    """Build and return the agent workflow graph without memory."""
    builder = StateGraph(State)
    builder.add_edge(START, "coordinator")
    builder.add_node("coordinator", coordinator_node)
    # ... additional nodes
    return builder.compile()
```

**Extension Points**:
- Add custom nodes via `builder.add_node()`
- Define routing logic in conditional edge functions
- Integrate custom checkpointing strategies

### 2. State Management (`src/graph/types.py`)

**Purpose**: Defines the shared state structure that flows through the agent workflow.

**State Schema**:
```python
class State(MessagesState):
    locale: str = "en-US"
    research_topic: str = ""
    observations: list[str] = []
    resources: list[Resource] = []
    plan_iterations: int = 0
    current_plan: Plan | str = None
    final_report: str = ""
    auto_accepted_plan: bool = False
    enable_background_investigation: bool = True
    background_investigation_results: str = None
```

**Design Benefits**:
- **Type Safety**: Pydantic-based validation
- **Extensibility**: Easy to add new state fields
- **Thread Safety**: Immutable state updates via Commands

### 3. Agent Nodes (`src/graph/nodes.py`)

**Purpose**: Implements the core business logic for each agent in the multi-agent system.

#### Coordinator Node
- **Role**: Entry point and workflow orchestration
- **Responsibilities**: User input parsing, locale detection, workflow routing
- **Tools**: `handoff_to_planner` for delegation

#### Planner Node
- **Role**: Strategic planning and task decomposition
- **Responsibilities**: Research plan generation, iteration management
- **LLM Integration**: Supports structured output and reasoning models

#### Research Team Nodes
- **Researcher Node**: Web search, content crawling, RAG integration
- **Coder Node**: Python execution, data analysis, technical tasks

#### Reporter Node
- **Role**: Final output generation and formatting
- **Responsibilities**: Aggregates findings, applies report styles, citation management

**Extension Pattern**:
```python
async def custom_node(state: State, config: RunnableConfig) -> Command:
    """Custom agent node implementation."""
    # 1. Extract state information
    # 2. Execute agent-specific logic
    # 3. Update state via Command
    # 4. Route to next node
    return Command(update={...}, goto="next_node")
```

## State Management

### State Flow Architecture

DeerFlow uses **immutable state updates** through LangGraph's Command system, ensuring thread safety and enabling distributed execution.

#### State Update Pattern
```python
return Command(
    update={
        "messages": [AIMessage(content=response)],
        "current_plan": validated_plan,
        "observations": observations + [new_observation]
    },
    goto="next_node"
)
```

#### State Persistence
- **Memory Mode**: `build_graph_with_memory()` for conversation persistence
- **Stateless Mode**: `build_graph()` for single-request execution
- **Custom Checkpointing**: Pluggable storage backends (SQLite, PostgreSQL planned)

### Configuration Management

#### Multi-Layer Configuration System
```
Environment Variables → conf.yaml → Runtime Config → Agent Settings
```

**Configuration Class** (`src/config/configuration.py`):
```python
@dataclass(kw_only=True)
class Configuration:
    resources: list[Resource] = field(default_factory=list)
    max_plan_iterations: int = 1
    max_step_num: int = 3
    max_search_results: int = 3
    mcp_settings: dict = None
    report_style: str = ReportStyle.ACADEMIC.value
    enable_deep_thinking: bool = False
```

## Agent Orchestration

### Workflow Execution Model

DeerFlow implements **event-driven agent coordination** where each node operates independently and communicates through shared state.

#### Execution Flow
1. **Coordinator**: Parses input, detects locale, routes to planner
2. **Background Investigator**: Performs initial research if enabled
3. **Planner**: Creates structured research plan
4. **Human Feedback**: Interactive plan review and refinement
5. **Research Team**: Executes plan steps via specialized agents
6. **Reporter**: Aggregates findings into final report

#### Agent Routing Logic
```python
def continue_to_running_research_team(state: State):
    """Dynamic routing based on current plan state."""
    current_plan = state.get("current_plan")
    if not current_plan or not current_plan.steps:
        return "planner"
    
    # Find first incomplete step
    incomplete_step = next(
        (step for step in current_plan.steps if not step.execution_res),
        None
    )
    
    if incomplete_step.step_type == StepType.RESEARCH:
        return "researcher"
    elif incomplete_step.step_type == StepType.PROCESSING:
        return "coder"
    return "planner"
```

### Agent Specialization

#### Tool Assignment Strategy
- **Researcher**: Search engines, crawlers, RAG systems
- **Coder**: Python REPL, data analysis libraries
- **Planner**: Structured output models, reasoning capabilities
- **Reporter**: Content generation models, formatting tools

#### MCP Integration Pattern
```python
async def _setup_and_execute_agent_step(
    state: State,
    config: RunnableConfig,
    agent_type: str,
    default_tools: list,
):
    """Dynamic tool loading based on MCP configuration."""
    if mcp_servers:
        client = MultiServerMCPClient(mcp_servers)
        loaded_tools = default_tools[:]
        all_tools = await client.get_tools()
        for tool in all_tools:
            if tool.name in enabled_tools:
                loaded_tools.append(tool)
        agent = create_agent(agent_type, loaded_tools)
    else:
        agent = create_agent(agent_type, default_tools)
    
    return await _execute_agent_step(state, agent, agent_type)
```

## Tool Integration

### Tool Architecture

DeerFlow implements a **plugin-based tool system** with standardized interfaces for easy extension.

#### Tool Categories

**Search Tools** (`src/tools/search.py`):
- Tavily (AI-optimized search)
- DuckDuckGo (privacy-focused)
- Brave Search (advanced features)
- ArXiv (scientific papers)

**Content Tools**:
- **Crawling** (`src/tools/crawl.py`): Jina AI reader integration
- **TTS** (`src/tools/tts.py`): Volcengine text-to-speech
- **Python REPL** (`src/tools/python_repl.py`): Code execution sandbox

**RAG Integration** (`src/rag/`):
- RAGFlow integration for private knowledge bases
- VikingDB vector storage
- Resource-based retrieval system

#### Tool Registration Pattern
```python
@tool
def custom_search_tool(
    query: Annotated[str, "Search query"],
    max_results: Annotated[int, "Maximum results"] = 3
) -> str:
    """Custom search tool implementation."""
    # Tool implementation
    return search_results
```

### MCP (Model Context Protocol) Integration

#### Dynamic Tool Loading
```python
# MCP server configuration
mcp_settings = {
    "servers": {
        "github-trending": {
            "transport": "stdio",
            "command": "uvx",
            "args": ["mcp-github-trending"],
            "enabled_tools": ["get_github_trending_repositories"],
            "add_to_agents": ["researcher"]
        }
    }
}
```

#### Tool Routing Strategy
- **Agent-Specific**: Tools assigned to specific agent types
- **Dynamic Loading**: Runtime tool discovery and registration
- **Fallback Handling**: Graceful degradation when tools unavailable

## MCP Integration

### MCP Architecture Overview

The Model Context Protocol (MCP) integration enables DeerFlow to dynamically discover and integrate external tools and services. This provides extensibility without requiring core system modifications.

```mermaid
graph TB
    A[DeerFlow Core] --> B[MCP Client Manager]
    B --> C[MCP Server 1<br/>Filesystem]
    B --> D[MCP Server 2<br/>Git Operations]  
    B --> E[MCP Server 3<br/>Database Access]
    B --> F[MCP Server N<br/>Custom Tools]
    
    C --> G[File Operations<br/>read, write, list]
    D --> H[Git Commands<br/>commit, push, diff]
    E --> I[DB Queries<br/>select, insert, update] 
    F --> J[Domain Tools<br/>custom logic]
```

### MCP Integration Points

#### 1. Configuration Layer (`src/config/configuration.py`)
```python
@dataclass(kw_only=True)
class Configuration:
    mcp_settings: dict = None  # MCP server configurations
    
# Example MCP configuration
mcp_settings = {
    "servers": {
        "filesystem": {
            "command": "uv",
            "args": ["tool", "run", "mcp-server-filesystem", "/workspace"]
        },
        "git": {
            "command": "uvx", 
            "args": ["mcp-server-git", "--repository", "/project"]
        }
    }
}
```

#### 2. Dynamic Tool Loading (`src/config/tools.py`)
```python
def load_mcp_tools(mcp_settings: dict) -> List[Tool]:
    """Dynamically load tools from MCP servers."""
    tools = []
    for server_name, config in mcp_settings.get("servers", {}).items():
        try:
            # Connect to MCP server
            client = MCPClient(config)
            
            # Discover available tools
            available_tools = client.list_tools()
            
            # Convert MCP tools to LangChain tools
            for mcp_tool in available_tools:
                langchain_tool = adapt_mcp_tool(mcp_tool)
                tools.append(langchain_tool)
                
        except Exception as e:
            logger.warning(f"Failed to load MCP server {server_name}: {e}")
    
    return tools
```

#### 3. Runtime Integration (`src/graph/nodes.py`)
```python
async def researcher_node(state: State, config: RunnableConfig):
    """Research node with MCP tool integration."""
    
    # Load base tools
    base_tools = [search_tool, crawl_tool]
    
    # Add MCP tools dynamically
    deer_config = get_configuration(config)
    if deer_config.mcp_settings:
        mcp_tools = load_mcp_tools(deer_config.mcp_settings)
        base_tools.extend(mcp_tools)
    
    return await _setup_and_execute_agent_step(
        state, config, "researcher", base_tools
    )
```

### MCP Use Cases

#### A. Development Workflow Integration
- **Git Operations**: Commit, push, branch management
- **File Management**: Read, write, directory operations
- **Code Analysis**: Static analysis, linting, formatting

#### B. Data Access and Integration
- **Database Connectivity**: SQL queries, data extraction
- **API Integration**: REST/GraphQL API calls
- **Cloud Services**: AWS, Azure, GCP service integration

#### C. Custom Business Logic
- **Domain-Specific Tools**: Industry-specific calculations
- **Internal System Integration**: ERP, CRM system connectivity
- **Workflow Automation**: Custom process automation

## RAG System

### RAG Architecture Overview

The Retrieval-Augmented Generation system enhances DeerFlow's knowledge capabilities by integrating external knowledge sources through vector similarity search.

```mermaid
graph TB
    A[User Query] --> B[RAG System]
    B --> C[Vector Store<br/>FAISS/Chroma]
    B --> D[Document Sources]
    
    D --> E[Web Crawling<br/>http://urls]
    D --> F[File System<br/>file://paths] 
    D --> G[RAG Protocol<br/>rag://resources]
    D --> H[API Sources<br/>api://endpoints]
    
    C --> I[Similarity Search]
    I --> J[Retrieved Context]
    J --> K[Enhanced LLM Input]
    K --> L[Knowledge-Augmented Response]
```

### RAG Integration Points

#### 1. Resource Configuration (`src/rag/retriever.py`)
```python
@dataclass
class Resource:
    """RAG resource configuration."""
    url: str           # Resource URL (rag://, http://, file://)
    description: str   # Human-readable description
    metadata: dict = field(default_factory=dict)  # Additional metadata

# Example resource configuration
resources = [
    Resource(
        url="rag://company-docs", 
        description="Internal company documentation"
    ),
    Resource(
        url="http://docs.example.com/api", 
        description="API documentation"
    ),
    Resource(
        url="file:///workspace/manuals/", 
        description="Product manuals"
    )
]
```

#### 2. Knowledge Base Construction (`src/rag/builder.py`)
```python
async def build_knowledge_base(resources: List[Resource]) -> VectorStore:
    """Build vector store from configured resources."""
    all_documents = []
    
    for resource in resources:
        documents = await process_resource(resource)
        all_documents.extend(documents)
    
    # Create embeddings and vector store
    embeddings = OpenAIEmbeddings()
    vector_store = FAISS.from_documents(all_documents, embeddings)
    
    return vector_store

async def process_resource(resource: Resource) -> List[Document]:
    """Process different resource types."""
    if resource.url.startswith("rag://"):
        return await load_rag_resource(resource)
    elif resource.url.startswith("http"):
        return await crawl_web_resource(resource)
    elif resource.url.startswith("file://"):
        return await load_file_resource(resource)
    else:
        raise ValueError(f"Unsupported resource type: {resource.url}")
```

#### 3. Retrieval Tool Integration (`src/tools/retriever.py`)
```python
@tool
def rag_retrieval_tool(
    query: str, 
    k: int = 5,
    similarity_threshold: float = 0.7
) -> str:
    """Retrieve relevant documents from RAG knowledge base."""
    
    # Get configured vector store
    vector_store = get_current_vector_store()
    
    if not vector_store:
        return "No knowledge base available for retrieval."
    
    # Perform similarity search
    relevant_docs = vector_store.similarity_search_with_score(
        query, k=k
    )
    
    # Filter by similarity threshold
    filtered_docs = [
        (doc, score) for doc, score in relevant_docs 
        if score >= similarity_threshold
    ]
    
    if not filtered_docs:
        return f"No relevant documents found for: {query}"
    
    # Format retrieved content
    formatted_content = []
    for i, (doc, score) in enumerate(filtered_docs, 1):
        formatted_content.append(
            f"**Source {i}** (relevance: {score:.3f}):\n"
            f"{doc.page_content}\n"
            f"*Metadata: {doc.metadata}*\n"
        )
    
    return "\n\n".join(formatted_content)
```

### RAG Use Cases

#### A. Domain-Specific Knowledge Enhancement
- **Technical Documentation**: API references, user manuals
- **Business Knowledge**: Company policies, procedures
- **Academic Research**: Scientific papers, research databases

#### B. Dynamic Context Enrichment  
- **Real-time Updates**: Latest news, market data
- **Personalized Context**: User-specific documents, preferences
- **Multi-lingual Support**: Documents in multiple languages

#### C. Specialized Knowledge Domains
- **Legal Documents**: Contracts, regulations, case law
- **Medical Literature**: Research papers, clinical guidelines
- **Financial Data**: Reports, analysis, market trends

## Data Analysis Module

### Data Analysis Architecture

The integrated data analysis module extends DeerFlow with specialized capabilities for structured data processing, statistical analysis, and visualization.

```mermaid
graph TB
    A[Data Analysis Request] --> B[Data Analysis Node]
    B --> C[Data Supervisor]
    C --> D[RAG Agent<br/>Domain Knowledge]
    C --> E[SQL Agent<br/>Database Operations] 
    C --> F[Python Agent<br/>Analysis & Viz]
    
    D --> G[FAISS Vector Store<br/>Business Knowledge]
    E --> H[MySQL Database<br/>Structured Data]
    F --> I[Analysis Results<br/>Charts & Reports]
    
    G --> J[Business Context]
    H --> K[Raw Data]
    I --> L[Visualizations]
    
    J --> M[Enhanced Analysis]
    K --> M
    L --> M
```

### Data Analysis Integration Points

#### 1. Step Type Extension (`src/prompts/planner_model.py`)
```python
class StepType(str, Enum):
    RESEARCH = "research"
    PROCESSING = "processing"
    DATA_ANALYSIS = "data_analysis"  # New step type

# Planner can now identify data analysis tasks
{
    "step_type": "data_analysis",
    "title": "Customer Churn Analysis", 
    "description": "Query customer database, perform churn analysis, generate visualizations"
}
```

#### 2. Specialized Agent Factory (`src/agents/data_agents.py`)
```python
def create_data_analysis_agents(config: Configuration):
    """Create specialized data analysis agents."""
    
    # RAG Agent - Domain knowledge expert
    rag_agent = create_react_agent(
        model=get_llm_by_type("coordinator"),
        tools=[domain_knowledge_tool],
        prompt=RAG_AGENT_PROMPT
    )
    
    # SQL Agent - Database operations expert  
    sql_agent = create_react_agent(
        model=get_llm_by_type("coder"),
        tools=[sql_query_tool, extract_data_tool],
        prompt=SQL_AGENT_PROMPT
    )
    
    # Python Agent - Analysis and visualization expert
    python_agent = create_react_agent(
        model=get_llm_by_type("coder"), 
        tools=[python_execution_tool, visualization_tool],
        prompt=PYTHON_AGENT_PROMPT
    )
    
    return rag_agent, sql_agent, python_agent
```

#### 3. Multi-Agent Orchestration (`src/agents/data_supervisor.py`)
```python
def create_data_supervisor(config: Configuration) -> StateGraph:
    """Create intelligent data analysis supervisor."""
    
    # Create specialized agents
    rag_agent, sql_agent, python_agent = create_data_analysis_agents(config)
    
    # Create supervisor with intelligent routing
    supervisor = create_supervisor(
        model=get_llm_by_type("coordinator"),
        agents=[rag_agent, sql_agent, python_agent],
        prompt=DATA_SUPERVISOR_PROMPT,
        add_handoff_back_messages=True
    )
    
    return supervisor.compile()
```

### Data Analysis Workflow

#### 1. Automatic Task Routing
```python
def continue_to_running_research_team(state: State):
    """Enhanced routing with data analysis support."""
    incomplete_step = get_incomplete_step(state)
    
    if incomplete_step.step_type == StepType.RESEARCH:
        return "researcher"
    elif incomplete_step.step_type == StepType.PROCESSING:
        return "coder"  
    elif incomplete_step.step_type == StepType.DATA_ANALYSIS:
        return "data_analyst"  # Route to specialized data analysis node
    return "planner"
```

#### 2. Multi-Modal Output Generation
```python
async def data_analysis_node(state: State, config: RunnableConfig):
    """Execute comprehensive data analysis."""
    
    # Create data supervisor
    supervisor = create_data_supervisor(config)
    
    # Execute analysis workflow
    result = await supervisor.ainvoke({
        "messages": [{"role": "user", "content": current_step.description}]
    })
    
    # Extract results including charts and insights
    analysis_content = result["messages"][-1].content
    
    # Update state with comprehensive results
    return Command(
        update={
            "observations": state.get("observations", []) + [analysis_content],
            "data_analysis_results": {
                "content": analysis_content,
                "charts": extract_chart_paths(analysis_content),
                "insights": extract_insights(analysis_content)
            }
        },
        goto="research_team"
    )
```

### Data Analysis Use Cases

#### A. Business Intelligence
- **Customer Segmentation**: RFM analysis, behavioral clustering
- **Sales Analytics**: Trend analysis, forecasting
- **Performance Metrics**: KPI tracking, dashboard generation

#### B. Scientific Research
- **Statistical Analysis**: Hypothesis testing, correlation analysis
- **Data Visualization**: Publication-ready charts and graphs
- **Experimental Design**: A/B testing, statistical power analysis

#### C. Financial Analysis
- **Risk Assessment**: Portfolio analysis, VaR calculations
- **Market Research**: Price trend analysis, volatility modeling
- **Compliance Reporting**: Regulatory reporting, audit trails

## Extension Points

### Adding Custom Agents

#### 1. Define Agent Node Function
```python
async def custom_agent_node(
    state: State, 
    config: RunnableConfig
) -> Command[Literal["next_node"]]:
    """Custom agent implementation."""
    # Extract state information
    current_task = state.get("current_task")
    
    # Execute agent logic
    result = await execute_custom_logic(current_task)
    
    # Update state and route
    return Command(
        update={"custom_result": result},
        goto="next_node"
    )
```

#### 2. Register in Graph Builder
```python
def build_custom_graph():
    builder = StateGraph(State)
    # ... existing nodes
    builder.add_node("custom_agent", custom_agent_node)
    builder.add_edge("planner", "custom_agent")
    builder.add_edge("custom_agent", "reporter")
    return builder.compile()
```

### Custom Tool Development

#### Tool Interface Implementation
```python
from langchain_core.tools import tool
from typing import Annotated

@tool
def custom_analysis_tool(
    data: Annotated[str, "Input data for analysis"],
    method: Annotated[str, "Analysis method"] = "standard"
) -> str:
    """Perform custom data analysis."""
    # Implementation
    return analysis_results
```

#### Tool Registration
```python
# Add to agent tools list
custom_tools = [custom_analysis_tool, existing_tool1, existing_tool2]
agent = create_agent("custom_agent", custom_tools)
```

### LLM Provider Integration

#### Custom Provider Configuration
```yaml
# conf.yaml
CUSTOM_MODEL:
  base_url: "https://your-api-endpoint.com/v1"
  model: "custom-model-name"
  api_key: "${CUSTOM_API_KEY}"
  verify_ssl: true
  timeout: 30
```

#### Provider Registration
```python
# In src/llms/llm.py
def get_custom_llm():
    """Initialize custom LLM provider."""
    config = load_model_config("CUSTOM_MODEL")
    return CustomChatModel(
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key
    )
```

## Performance Considerations

### Scalability Patterns

#### Asynchronous Execution
- **Agent Nodes**: Full async/await support
- **Tool Calls**: Concurrent tool execution where possible
- **Streaming**: Real-time response generation via SSE

#### Resource Management
```python
# Configurable limits
AGENT_RECURSION_LIMIT = 25  # Max tool call depth
max_plan_iterations = 3     # Plan refinement cycles
max_search_results = 5      # Search result limits
```

#### Caching Strategies
- **Tool Results**: Cache search and crawl results
- **LLM Responses**: Cache for repeated queries
- **State Snapshots**: Checkpoint intermediate results

### Performance Optimization

#### Memory Usage
- **State Immutability**: Prevents memory leaks
- **Tool Cleanup**: Proper resource disposal
- **Streaming Responses**: Reduces memory footprint

#### Network Optimization
- **Connection Pooling**: Reuse HTTP connections
- **Request Batching**: Group API calls where possible
- **Timeout Configuration**: Prevent hanging requests

## Deployment Architecture

### Container Strategy

#### Multi-Stage Docker Build
```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm

# Pre-cache dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-install-project

# Application layer
COPY . /app
RUN uv sync --locked

EXPOSE 8000
CMD ["uv", "run", "python", "server.py"]
```

#### Docker Compose Configuration
```yaml
services:
  deer-flow-api:
    build: .
    environment:
      - SEARCH_API=tavily
      - TAVILY_API_KEY=${TAVILY_API_KEY}
    ports:
      - "8000:8000"
    
  deer-flow-web:
    build: ./web
    ports:
      - "3000:3000"
    depends_on:
      - deer-flow-api
```

### Production Considerations

#### Security
- **Environment Variables**: Secure secret management
- **CORS Configuration**: Restricted origins in production
- **Input Validation**: Pydantic model validation
- **MCP Sandboxing**: Isolated tool execution

#### Monitoring
- **Structured Logging**: Agent-specific log namespaces
- **Performance Metrics**: Request duration, token usage
- **Error Tracking**: Exception capture and reporting
- **Health Checks**: Endpoint availability monitoring

#### High Availability
- **Stateless Design**: Horizontal scaling capability
- **Load Balancing**: Multiple instance deployment
- **Circuit Breakers**: Fail-fast for degraded services
- **Graceful Shutdown**: Proper resource cleanup

## Best Practices

### Development Guidelines

1. **State Updates**: Always use Command pattern for state modifications
2. **Error Handling**: Implement graceful degradation for all external calls
3. **Tool Development**: Follow standardized tool interface patterns
4. **Testing**: Write unit tests for agent nodes and integration tests for workflows
5. **Documentation**: Maintain inline documentation for complex logic

### Operational Guidelines

1. **Configuration**: Use environment-specific configuration files
2. **Monitoring**: Implement comprehensive logging and metrics
3. **Scaling**: Design for horizontal scalability from the start
4. **Security**: Apply defense-in-depth principles
5. **Maintenance**: Regular updates for dependencies and security patches

---

For more detailed implementation examples, see the `/examples` directory in the repository.