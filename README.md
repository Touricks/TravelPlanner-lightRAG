# TravelPlanner-LightRAG

**基于 LightRAG 的旅游知识图谱和智能推荐系统**


## 项目简介

本项目使用 [LightRAG](https://github.com/HKUDS/LightRAG) 框架构建旅游知识图谱，基于 Google Places API 数据提供智能旅游推荐和问答服务。

**核心特性**:
- ✅ 自动构建旅游知识图谱（基于 google_types 关系）
- ✅ PostgreSQL + pgvector 统一存储后端
- ✅ 5,925+ 旅游地点数据（10+ 城市）

##  技术架构

```
PostgreSQL 15.2 + pgvector
├── KV Storage: 缓存、文档
├── Vector Storage: Embeddings（HNSW 索引）
├── Graph Storage: 实体和关系
└── Doc Status: 文档处理状态

LightRAG Framework
├── 自动分块 (Chunking)
├── 实体提取 (Entity Extraction)
├── 关系提取 (Relation Extraction)
└── 知识图谱构建 (Knowledge Graph)

LLM: Qwen Plus
Embedding: Qwen text-embedding-v4
```
## 🚀 快速开始

### 1️⃣ 克隆与环境配置

```bash
# Clone repository
git clone https://github.com/Touricks/TravelPlanner-lightRAG.git
cd TravelPlanner-lightRAG

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# LLM API (Qwen)
QWEN_API_KEY=your_api_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Database (auto-configured by docker-compose)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret
POSTGRES_DB=TravelPlanner
```

**Start PostgreSQL + pgvector with Docker:**
```bash
docker-compose up -d

# Verify database is ready
docker-compose ps
```

### 2️⃣ 加载数据到 LightRAG

```bash
# Import places data into LightRAG (builds knowledge graph)
python scripts/import_to_lightrag.py --input data/places_export.jsonl

# Optional: limit records for testing
python scripts/import_to_lightrag.py --input data/places_export.jsonl --limit 100
```

This will:
- Parse place documents from JSONL
- Extract entities (places, cities, categories)
- Build relationships (LOCATED_IN, IS_A, HAS_RATING)
- Store vectors in PostgreSQL + pgvector
- Save knowledge graph to `travel_rag/graph_chunk_entity_relation.graphml`

### 3️⃣ 查询 LightRAG

**Command Line:**
```bash
# Simple query (clean output)
python scripts/query.py -q "What attractions are in New York?"

# With detailed logs
python scripts/query.py -q "Tell me about Central Park" --verbose
```

**Example Output:**
```
Central Park is a major tourist attraction located in New York City.
It features various activities including walking trails, boat rentals,
and the Central Park Zoo. The park has a rating of 4.8 stars...
```

**Python API:**
```python
from config.lightrag_config import initialize_rag_async, QueryParam
import asyncio

async def main():
    rag = await initialize_rag_async()
    result = await rag.aquery(
        "What are some family-friendly attractions in Tampa?",
        param=QueryParam(mode="mix")
    )
    print(result)

asyncio.run(main())
```

**Query Modes** (use `scripts/query_lightrag.py --mode <mode>` for advanced options):

| Mode | Description | Use Case |
|------|-------------|----------|
| `mix` | All modes combined | **Default, best results** |
| `local` | Entity-focused | Specific place queries |
| `global` | Community-level | City overviews |
| `hybrid` | Vector + keyword | Balanced search |
| `naive` | Keyword only | Simple lookups |

## 🔑 环境变量

```env
# LLM
QWEN_API_KEY=your_qwen_api_key

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=travel_kg
```