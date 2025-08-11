# DeerFlow Deployment and Configuration Guide

> **Operations Guide**: Comprehensive reference for deploying, configuring, and maintaining DeerFlow in production environments.

## Table of Contents

- [Configuration Management](#configuration-management)
- [Environment Setup](#environment-setup)
- [Deployment Strategies](#deployment-strategies)
- [Security Configuration](#security-configuration)
- [Monitoring and Observability](#monitoring-and-observability)
- [Scaling and Performance](#scaling-and-performance)
- [Maintenance and Updates](#maintenance-and-updates)
- [Troubleshooting](#troubleshooting)

## Configuration Management

### Configuration Architecture

DeerFlow uses a **multi-layered configuration system** that prioritizes environment-specific settings while maintaining secure defaults.

```
Priority Order (Highest to Lowest):
1. Environment Variables
2. Runtime Configuration (conf.yaml)
3. Request-Level Parameters
4. System Defaults
```

### Core Configuration Files

#### Main Configuration (`conf.yaml`)
```yaml
# LLM Configuration
BASIC_MODEL:
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"
  api_key: "${OPENAI_API_KEY}"
  timeout: 30
  verify_ssl: true

REASONING_MODEL:
  base_url: "https://api.openai.com/v1" 
  model: "o1-mini"
  api_key: "${OPENAI_API_KEY}"

# Search Engine Configuration
SEARCH_ENGINE:
  engine: tavily  # Options: tavily, duckduckgo, brave_search, arxiv
  api_key: "${TAVILY_API_KEY}"
  max_results: 5
  timeout: 15
  include_domains:
    - reliable-source.com
    - trusted-news.org
  exclude_domains:
    - unreliable-site.com

# RAG Configuration
RAG_PROVIDER: ragflow  # Options: ragflow, vikingdb
RAGFLOW_CONFIG:
  api_url: "${RAGFLOW_API_URL}"
  api_key: "${RAGFLOW_API_KEY}"
  retrieval_size: 10
  cross_languages: ["English", "Chinese", "Spanish"]

# Agent Configuration
AGENT_SETTINGS:
  max_recursion_limit: 25
  max_plan_iterations: 3
  max_step_num: 5
  enable_background_investigation: true
  report_style: academic  # Options: academic, popular_science, news, social_media

# MCP Server Configuration
MCP_SERVERS:
  github-trending:
    transport: stdio
    command: uvx
    args: ["mcp-github-trending"]
    enabled_tools: ["get_github_trending_repositories"]
    add_to_agents: ["researcher"]
    
  custom-tools:
    transport: stdio
    command: python
    args: ["-m", "custom_mcp_server"]
    enabled_tools: ["custom_analysis", "data_processor"]
    add_to_agents: ["coder", "researcher"]
```

#### Environment Configuration (`.env`)
```bash
# Core API Keys
OPENAI_API_KEY=sk-your-openai-key
TAVILY_API_KEY=tvly-your-tavily-key
BRAVE_SEARCH_API_KEY=your-brave-key

# RAG Configuration
RAGFLOW_API_URL=http://localhost:9388
RAGFLOW_API_KEY=ragflow-your-key
RAGFLOW_RETRIEVAL_SIZE=10

# TTS Configuration
VOLCENGINE_TTS_APPID=your-app-id
VOLCENGINE_TTS_ACCESS_TOKEN=your-access-token
VOLCENGINE_TTS_CLUSTER=volcano_tts
VOLCENGINE_TTS_VOICE_TYPE=BV700_V2_streaming

# Search Configuration
SEARCH_API=tavily
SELECTED_RAG_PROVIDER=ragflow

# Security Settings
ALLOWED_ORIGINS=http://localhost:3000,https://your-domain.com
ENABLE_MCP_SERVER_CONFIGURATION=false
CORS_ALLOW_CREDENTIALS=true

# Performance Settings
AGENT_RECURSION_LIMIT=25
MAX_CONCURRENT_REQUESTS=10

# Monitoring
LANGSMITH_TRACING=false
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=deer-flow-production

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=structured
```

### Configuration Validation

#### Configuration Schema
```python
from pydantic import BaseModel, validator, Field
from typing import Optional, List, Dict

class LLMConfig(BaseModel):
    """LLM provider configuration."""
    base_url: str = Field(..., description="API endpoint URL")
    model: str = Field(..., description="Model identifier")
    api_key: str = Field(..., description="Authentication key")
    timeout: int = Field(30, description="Request timeout in seconds")
    verify_ssl: bool = Field(True, description="SSL certificate verification")
    
    @validator('base_url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Base URL must be a valid HTTP/HTTPS URL')
        return v
    
    @validator('timeout')
    def validate_timeout(cls, v):
        if v < 1 or v > 300:
            raise ValueError('Timeout must be between 1 and 300 seconds')
        return v

class SearchEngineConfig(BaseModel):
    """Search engine configuration."""
    engine: str = Field(..., description="Search engine type")
    api_key: Optional[str] = Field(None, description="API key for search service")
    max_results: int = Field(5, description="Maximum search results")
    include_domains: List[str] = Field(default_factory=list)
    exclude_domains: List[str] = Field(default_factory=list)
    
    @validator('engine')
    def validate_engine(cls, v):
        valid_engines = ['tavily', 'duckduckgo', 'brave_search', 'arxiv']
        if v not in valid_engines:
            raise ValueError(f'Engine must be one of: {valid_engines}')
        return v

class ProductionConfig(BaseModel):
    """Complete production configuration."""
    basic_model: LLMConfig
    search_engine: SearchEngineConfig
    allowed_origins: List[str]
    max_concurrent_requests: int = Field(10, le=100)
    enable_monitoring: bool = Field(True)
    log_level: str = Field('INFO')
    
    @validator('allowed_origins')
    def validate_origins(cls, v):
        for origin in v:
            if not origin.startswith(('http://', 'https://')):
                raise ValueError(f'Invalid origin: {origin}')
        return v
```

#### Configuration Loading and Validation
```python
import os
import yaml
from pathlib import Path

def load_and_validate_config(config_path: str = "conf.yaml") -> ProductionConfig:
    """Load and validate configuration with environment variable substitution."""
    
    # Load YAML configuration
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    # Substitute environment variables
    config_data = substitute_env_vars(config_data)
    
    # Validate configuration
    try:
        config = ProductionConfig(**config_data)
        return config
    except ValueError as e:
        raise ConfigurationError(f"Invalid configuration: {e}")

def substitute_env_vars(config_dict: dict) -> dict:
    """Recursively substitute environment variables in configuration."""
    if isinstance(config_dict, dict):
        return {k: substitute_env_vars(v) for k, v in config_dict.items()}
    elif isinstance(config_dict, list):
        return [substitute_env_vars(item) for item in config_dict]
    elif isinstance(config_dict, str) and config_dict.startswith('${') and config_dict.endswith('}'):
        var_name = config_dict[2:-1]
        return os.getenv(var_name, config_dict)
    else:
        return config_dict
```

## Environment Setup

### Development Environment

#### Local Development Setup
```bash
# Prerequisites installation
curl -LsSf https://astral.sh/uv/install.sh | sh  # Install uv
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash  # Install nvm
curl -fsSL https://get.pnpm.io/install.sh | sh  # Install pnpm

# Project setup
git clone https://github.com/bytedance/deer-flow.git
cd deer-flow

# Python environment
uv sync --all-extras

# Web UI dependencies (optional)
cd web && pnpm install

# Configuration
cp .env.example .env
cp conf.yaml.example conf.yaml

# Edit configuration files with your API keys
```

#### Development Configuration
```yaml
# development.yaml
BASIC_MODEL:
  base_url: "http://localhost:8080/v1"  # Local model server
  model: "llama-3.1-8b"
  api_key: "not-needed"
  verify_ssl: false

SEARCH_ENGINE:
  engine: duckduckgo  # No API key required
  max_results: 3

RAG_PROVIDER: none  # Disable RAG for development

AGENT_SETTINGS:
  max_recursion_limit: 10  # Lower limits for faster testing
  max_plan_iterations: 1
  max_step_num: 2
  enable_background_investigation: false
```

### Staging Environment

#### Staging Configuration
```yaml
# staging.yaml
BASIC_MODEL:
  base_url: "https://staging-api.openai.com/v1"
  model: "gpt-4o-mini"
  api_key: "${OPENAI_STAGING_KEY}"

SEARCH_ENGINE:
  engine: tavily
  api_key: "${TAVILY_STAGING_KEY}"
  max_results: 3

MONITORING:
  enable_telemetry: true
  log_level: DEBUG
  export_metrics: true
```

#### Staging Deployment Script
```bash
#!/bin/bash
# deploy-staging.sh

set -e

echo "Deploying to staging environment..."

# Load staging environment variables
source .env.staging

# Validate configuration
uv run python -c "
from src.config.configuration import Configuration
config = Configuration.from_runnable_config()
print('Configuration validated successfully')
"

# Run database migrations (if applicable)
# uv run alembic upgrade head

# Deploy application
docker build -t deer-flow:staging .
docker tag deer-flow:staging registry.example.com/deer-flow:staging
docker push registry.example.com/deer-flow:staging

# Update staging deployment
kubectl apply -f k8s/staging/

echo "Staging deployment completed successfully"
```

### Production Environment

#### Production Configuration Template
```yaml
# production.yaml
BASIC_MODEL:
  base_url: "${PRODUCTION_LLM_ENDPOINT}"
  model: "${PRODUCTION_MODEL}"
  api_key: "${PRODUCTION_API_KEY}"
  timeout: 60
  verify_ssl: true

SEARCH_ENGINE:
  engine: tavily
  api_key: "${TAVILY_PRODUCTION_KEY}"
  max_results: 5
  timeout: 30
  include_domains:
    - reuters.com
    - bbc.com
    - nature.com
    - arxiv.org

SECURITY:
  allowed_origins:
    - "https://app.yourcompany.com"
    - "https://api.yourcompany.com"
  enable_auth: true
  cors_allow_credentials: true
  rate_limit: 1000  # requests per hour per IP

PERFORMANCE:
  max_concurrent_requests: 50
  request_timeout: 120
  worker_processes: 4
  thread_pool_size: 20

MONITORING:
  enable_telemetry: true
  metrics_endpoint: "/metrics"
  health_check_endpoint: "/health"
  log_level: INFO
  log_format: json
  
  # External monitoring services
  prometheus_enabled: true
  jaeger_endpoint: "${JAEGER_ENDPOINT}"
  sentry_dsn: "${SENTRY_DSN}"

CACHING:
  redis_url: "${REDIS_URL}"
  cache_ttl: 3600
  enable_distributed_cache: true
```

## Deployment Strategies

### Docker Deployment

#### Production Dockerfile Optimization
```dockerfile
# Multi-stage build for production
FROM ghcr.io/astral-sh/uv:python3.12-bookworm as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies in virtual environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Production stage
FROM python:3.12-slim-bookworm

# Create non-root user
RUN groupadd -r deerflow && useradd -r -g deerflow deerflow

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY --chown=deerflow:deerflow . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R deerflow:deerflow /app/logs /app/data

# Switch to non-root user
USER deerflow

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose for Production
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  deer-flow-api:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    env_file:
      - .env.production
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    depends_on:
      - redis
      - postgres
    networks:
      - deer-flow-network

  deer-flow-web:
    build:
      context: ./web
      dockerfile: Dockerfile
      target: production
    environment:
      - NODE_ENV=production
      - API_BASE_URL=http://deer-flow-api:8000
    ports:
      - "3000:3000"
    restart: unless-stopped
    depends_on:
      - deer-flow-api
    networks:
      - deer-flow-network

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis-data:/data
    restart: unless-stopped
    networks:
      - deer-flow-network

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=${DB_NAME}
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - deer-flow-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - deer-flow-web
      - deer-flow-api
    restart: unless-stopped
    networks:
      - deer-flow-network

volumes:
  redis-data:
  postgres-data:

networks:
  deer-flow-network:
    driver: bridge
```

### Kubernetes Deployment

#### Kubernetes Manifests

**Namespace and ConfigMap**
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: deer-flow
---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: deer-flow-config
  namespace: deer-flow
data:
  conf.yaml: |
    BASIC_MODEL:
      base_url: "https://api.openai.com/v1"
      model: "gpt-4o"
      timeout: 60
    SEARCH_ENGINE:
      engine: tavily
      max_results: 5
    AGENT_SETTINGS:
      max_recursion_limit: 25
      max_plan_iterations: 3
```

**Deployment**
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: deer-flow-api
  namespace: deer-flow
  labels:
    app: deer-flow-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: deer-flow-api
  template:
    metadata:
      labels:
        app: deer-flow-api
    spec:
      containers:
      - name: deer-flow-api
        image: deer-flow:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        envFrom:
        - secretRef:
            name: deer-flow-secrets
        volumeMounts:
        - name: config-volume
          mountPath: /app/conf.yaml
          subPath: conf.yaml
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
      volumes:
      - name: config-volume
        configMap:
          name: deer-flow-config
```

**Service and Ingress**
```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: deer-flow-api-service
  namespace: deer-flow
spec:
  selector:
    app: deer-flow-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: deer-flow-ingress
  namespace: deer-flow
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  tls:
  - hosts:
    - api.yourcompany.com
    secretName: deer-flow-tls
  rules:
  - host: api.yourcompany.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: deer-flow-api-service
            port:
              number: 80
```

#### Helm Chart Structure
```
helm/deer-flow/
├── Chart.yaml
├── values.yaml
├── values-production.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── hpa.yaml
│   └── servicemonitor.yaml
└── charts/
    ├── redis/
    └── postgresql/
```

**Helm Values for Production**
```yaml
# values-production.yaml
replicaCount: 3

image:
  repository: your-registry.com/deer-flow
  tag: "v1.0.0"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.yourcompany.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: deer-flow-tls
      hosts:
        - api.yourcompany.com

resources:
  limits:
    cpu: 1000m
    memory: 2Gi
  requests:
    cpu: 250m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
    interval: 30s

redis:
  enabled: true
  auth:
    enabled: true
  replica:
    replicaCount: 1

postgresql:
  enabled: true
  auth:
    database: deerflow
  primary:
    persistence:
      enabled: true
      size: 20Gi
```

### Cloud Platform Deployment

#### AWS ECS Deployment
```json
{
  "family": "deer-flow-task",
  "networkMode": "awsvpc",
  "requiresAttributes": [
    {
      "name": "com.amazonaws.ecs.capability.docker-remote-api.1.18"
    },
    {
      "name": "ecs.capability.task-iam-role"
    }
  ],
  "cpu": "1024",
  "memory": "2048",
  "taskRoleArn": "arn:aws:iam::account:role/DeerFlowTaskRole",
  "executionRoleArn": "arn:aws:iam::account:role/DeerFlowExecutionRole",
  "containerDefinitions": [
    {
      "name": "deer-flow-api",
      "image": "your-account.dkr.ecr.region.amazonaws.com/deer-flow:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:deer-flow/openai-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/deer-flow",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "curl -f http://localhost:8000/health || exit 1"
        ],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

#### Google Cloud Run Deployment
```yaml
# cloudrun.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: deer-flow-api
  namespace: default
  annotations:
    run.googleapis.com/ingress: all
    run.googleapis.com/execution-environment: gen2
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        autoscaling.knative.dev/minScale: "1"
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/memory: "2Gi"
        run.googleapis.com/cpu: "1000m"
    spec:
      containerConcurrency: 10
      containers:
      - image: gcr.io/your-project/deer-flow:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: production
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: deer-flow-secrets
              key: openai-api-key
        resources:
          limits:
            memory: 2Gi
            cpu: 1000m
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          timeoutSeconds: 5
          periodSeconds: 30
```

## Security Configuration

### Authentication and Authorization

#### JWT Authentication Implementation
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta

security = HTTPBearer()

class AuthManager:
    """JWT-based authentication manager."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_token(self, user_id: str, expires_in: int = 3600) -> str:
        """Create JWT token for user."""
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(seconds=expires_in),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

# Authentication dependency
auth_manager = AuthManager(os.getenv("JWT_SECRET_KEY"))

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user."""
    token = credentials.credentials
    payload = auth_manager.verify_token(token)
    return payload["user_id"]

# Protected endpoint example
@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: str = Depends(get_current_user)
):
    """Protected chat endpoint."""
    # Implementation with user context
    pass
```

#### API Key Authentication
```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key authentication."""
    valid_keys = set(os.getenv("VALID_API_KEYS", "").split(","))
    
    if not valid_keys or x_api_key not in valid_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return x_api_key

# Usage
@app.post("/api/protected-endpoint")
async def protected_endpoint(api_key: str = Depends(verify_api_key)):
    """API key protected endpoint."""
    pass
```

### HTTPS and SSL Configuration

#### Nginx SSL Configuration
```nginx
# nginx/ssl.conf
server {
    listen 80;
    server_name api.yourcompany.com;
    
    # Redirect all HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourcompany.com;
    
    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Proxy to backend
    location / {
        proxy_pass http://deer-flow-api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Request size limits
        client_max_body_size 10m;
    }
}
```

### Input Validation and Sanitization

#### Request Validation
```python
from pydantic import BaseModel, validator, Field
from typing import List, Optional
import re

class SecureChatRequest(BaseModel):
    """Security-enhanced chat request model."""
    
    messages: List[dict] = Field(..., max_items=100)
    thread_id: str = Field(..., min_length=1, max_length=50)
    max_plan_iterations: int = Field(1, ge=1, le=5)
    max_step_num: int = Field(3, ge=1, le=10)
    
    @validator('thread_id')
    def validate_thread_id(cls, v):
        """Validate thread ID format."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Thread ID contains invalid characters')
        return v
    
    @validator('messages')
    def validate_messages(cls, v):
        """Validate message content."""
        for msg in v:
            if 'content' in msg:
                content = msg['content']
                if len(content) > 10000:
                    raise ValueError('Message content too long')
                if contains_suspicious_content(content):
                    raise ValueError('Message contains prohibited content')
        return v

def contains_suspicious_content(content: str) -> bool:
    """Check for potentially malicious content."""
    suspicious_patterns = [
        r'<script.*?>.*?</script>',  # Script tags
        r'javascript:',              # JavaScript URLs
        r'data:.*base64',           # Data URLs with base64
        r'\$\(.*\)',                # jQuery selectors
        r'eval\s*\(',               # eval() calls
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
            return True
    
    return False
```

### Rate Limiting

#### Redis-based Rate Limiting
```python
import redis
import time
from functools import wraps

class RateLimiter:
    """Redis-based rate limiter."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """Check if request is within rate limit."""
        current = int(time.time())
        pipeline = self.redis.pipeline()
        
        # Remove expired entries
        pipeline.zremrangebyscore(key, 0, current - window)
        
        # Count current requests
        pipeline.zcard(key)
        
        # Add current request
        pipeline.zadd(key, {str(current): current})
        
        # Set expiry
        pipeline.expire(key, window)
        
        results = pipeline.execute()
        current_requests = results[1]
        
        return current_requests < limit

# Rate limiting decorator
def rate_limit(requests_per_minute: int = 60):
    """Rate limiting decorator."""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            client_ip = request.client.host
            key = f"rate_limit:{client_ip}"
            
            if not rate_limiter.is_allowed(key, requests_per_minute, 60):
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later."
                )
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

# Usage
@app.post("/api/chat/stream")
@rate_limit(requests_per_minute=30)
async def chat_stream(request: ChatRequest):
    """Rate-limited chat endpoint."""
    pass
```

## Monitoring and Observability

### Metrics Collection

#### Prometheus Metrics Integration
```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Define metrics
request_count = Counter(
    'deer_flow_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'deer_flow_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint']
)

active_workflows = Gauge(
    'deer_flow_active_workflows',
    'Number of active workflows'
)

agent_execution_duration = Histogram(
    'deer_flow_agent_execution_seconds',
    'Agent execution time',
    ['agent_type']
)

llm_api_calls = Counter(
    'deer_flow_llm_api_calls_total',
    'Total LLM API calls',
    ['model', 'status']
)

# Metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Collect request metrics."""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    # Record metrics
    request_count.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    request_duration.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

# Agent execution metrics
def track_agent_execution(agent_type: str):
    """Track agent execution metrics."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                agent_execution_duration.labels(
                    agent_type=agent_type
                ).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                agent_execution_duration.labels(
                    agent_type=f"{agent_type}_error"
                ).observe(duration)
                raise
        return wrapper
    return decorator

# Start Prometheus metrics server
start_http_server(9090)
```

#### Custom Metrics Dashboard
```python
class MetricsDashboard:
    """Custom metrics collection and dashboard."""
    
    def __init__(self):
        self.metrics = {
            'requests': {'total': 0, 'errors': 0},
            'agents': {'executions': 0, 'failures': 0},
            'performance': {'avg_response_time': 0.0}
        }
    
    def record_request(self, status_code: int, duration: float):
        """Record request metrics."""
        self.metrics['requests']['total'] += 1
        if status_code >= 400:
            self.metrics['requests']['errors'] += 1
        
        # Update average response time
        current_avg = self.metrics['performance']['avg_response_time']
        total_requests = self.metrics['requests']['total']
        self.metrics['performance']['avg_response_time'] = (
            (current_avg * (total_requests - 1) + duration) / total_requests
        )
    
    def get_health_status(self) -> dict:
        """Generate health status report."""
        error_rate = (
            self.metrics['requests']['errors'] / 
            max(self.metrics['requests']['total'], 1)
        )
        
        return {
            'status': 'healthy' if error_rate < 0.05 else 'degraded',
            'error_rate': error_rate,
            'total_requests': self.metrics['requests']['total'],
            'avg_response_time': self.metrics['performance']['avg_response_time']
        }

dashboard = MetricsDashboard()

@app.get("/metrics/dashboard")
async def get_metrics_dashboard():
    """Get custom metrics dashboard."""
    return dashboard.get_health_status()
```

### Logging Configuration

#### Structured Logging Setup
```python
import logging
import json
from datetime import datetime
from typing import Any, Dict

class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)

def setup_logging(log_level: str = "INFO", log_format: str = "structured"):
    """Configure application logging."""
    level = getattr(logging, log_level.upper())
    
    # Create formatters
    if log_format == "structured":
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for errors
    error_handler = logging.FileHandler('/app/logs/error.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

# Context-aware logger
class ContextualLogger:
    """Logger with request context."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Set logging context."""
        self.context.update(kwargs)
    
    def info(self, message: str, **extra):
        """Log info message with context."""
        extra.update(self.context)
        self.logger.info(message, extra={'extra_fields': extra})
    
    def error(self, message: str, **extra):
        """Log error message with context."""
        extra.update(self.context)
        self.logger.error(message, extra={'extra_fields': extra})

# Usage in request handling
async def handle_request(request: Request):
    """Handle request with contextual logging."""
    logger = ContextualLogger(__name__)
    logger.set_context(
        request_id=str(uuid4()),
        user_id=request.headers.get('user-id'),
        endpoint=request.url.path
    )
    
    logger.info("Processing request")
    
    try:
        # Process request
        result = await process_request(request)
        logger.info("Request completed successfully")
        return result
    except Exception as e:
        logger.error("Request failed", error=str(e))
        raise
```

### Health Checks and Monitoring

#### Comprehensive Health Check System
```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio

class HealthStatus(Enum):
    """Health check status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheck:
    """Individual health check result."""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    response_time: Optional[float] = None
    details: Optional[Dict] = None

class HealthCheckManager:
    """Comprehensive health check manager."""
    
    def __init__(self):
        self.checks = {}
    
    def register_check(self, name: str, check_func):
        """Register a health check."""
        self.checks[name] = check_func
    
    async def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks."""
        results = {}
        
        for name, check_func in self.checks.items():
            try:
                start_time = time.time()
                result = await check_func()
                response_time = time.time() - start_time
                
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    response_time=response_time
                )
            except Exception as e:
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e)
                )
        
        return results
    
    async def get_overall_status(self) -> HealthStatus:
        """Get overall system health status."""
        checks = await self.run_all_checks()
        
        if any(check.status == HealthStatus.UNHEALTHY for check in checks.values()):
            return HealthStatus.UNHEALTHY
        elif any(check.status == HealthStatus.DEGRADED for check in checks.values()):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

# Initialize health check manager
health_manager = HealthCheckManager()

# Register health checks
@health_manager.register_check("database")
async def check_database():
    """Check database connectivity."""
    # Implementation depends on database type
    return True

@health_manager.register_check("llm_service")
async def check_llm_service():
    """Check LLM service availability."""
    try:
        llm = get_llm_by_type("basic")
        response = await llm.ainvoke("test")
        return response is not None
    except Exception:
        return False

@health_manager.register_check("search_service")
async def check_search_service():
    """Check search service availability."""
    try:
        search_tool = get_web_search_tool(1)
        results = await search_tool.ainvoke("test query")
        return results is not None
    except Exception:
        return False

@app.get("/health")
async def health_endpoint():
    """Comprehensive health check endpoint."""
    checks = await health_manager.run_all_checks()
    overall_status = await health_manager.get_overall_status()
    
    return {
        "status": overall_status.value,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {name: {
            "status": check.status.value,
            "message": check.message,
            "response_time": check.response_time
        } for name, check in checks.items()}
    }
```

---

This deployment and configuration guide provides comprehensive coverage of production deployment patterns, security considerations, and monitoring strategies for DeerFlow. For additional deployment examples and infrastructure templates, refer to the project's `/deploy` directory and infrastructure-as-code examples.