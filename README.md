# TravelPlanner-LightRAG

**基于 LightRAG 的旅游知识图谱和智能推荐系统**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## 📖 项目简介

本项目使用 [LightRAG](https://github.com/HKUDS/LightRAG) 框架构建旅游知识图谱，基于 Google Places API 数据提供智能旅游推荐和问答服务。

**核心特性**:
- ✅ 自动构建旅游知识图谱（基于 google_types 关系）
- ✅ PostgreSQL + pgvector 统一存储后端
- ✅ 5,925+ 旅游地点数据（10+ 城市）
- ✅ 智能推荐和语义搜索
- ✅ 自然语言问答

## 🏗️ 技术架构

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

## 📚 文档

详细文档位于 `docs/` 目录：

- [数据接入方案](docs/integration_plan.md) - 如何将 Places 数据接入 LightRAG
- [数据源分析](docs/data_source_and_storage_analysis.md) - PostgreSQL vs Florida 数据对比
- [LightRAG 工作流程](docs/lightrag_workflow_clarification.md) - 自动提取 vs 手动结构化
- [执行模式分析](docs/lightrag_workflow_clarification.md) - LightRAG 核心机制

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/Touricks/TravelPlanner-lightRAG.git
cd TravelPlanner-lightRAG

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 API key 和数据库配置
nano .env
```

### 3. 数据库配置

```sql
-- 在 PostgreSQL 中安装 pgvector 扩展
CREATE EXTENSION vector;

-- 验证安装
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

### 4. 导入数据

```bash
# 从 PostgreSQL Places 表提取数据
python scripts/export_places_to_lightrag.py

# 导入到 LightRAG
python scripts/import_to_lightrag.py
```

### 5. 查询示例

```python
from config.lightrag_config import initialize_rag_async
from lightrag import QueryParam
import asyncio

async def main():
    # 初始化 RAG
    rag = await initialize_rag_async(use_postgres=True)

    # 查询
    result = rag.query(
        "Tampa 有哪些适合家庭的高评分旅游景点？",
        param=QueryParam(mode="mix", top_k=10)
    )

    print(result)

asyncio.run(main())
```

## 📊 数据规模

| 指标 | 数值 |
|------|------|
| 总地点数 | 5,925 |
| 城市数 | 10+ |
| 平均评分 | 4.4⭐ |
| 平均评论数 | 56k+ |
| 数据源 | Google Places API |

## 🛠️ 项目结构

```
TravelPlanner-lightRAG/
├── LightRAG/              # LightRAG 框架代码（子模块）
├── config/                # 配置文件
│   └── lightrag_config.py # LightRAG 配置（读取 .env）
├── scripts/               # 数据处理脚本
│   ├── export_places_to_lightrag.py
│   └── import_to_lightrag.py
├── docs/                  # 项目文档
│   ├── integration_plan.md
│   ├── data_source_and_storage_analysis.md
│   └── lightrag_workflow_clarification.md
├── data/                  # 数据目录（不提交大文件）
├── .env.example           # 环境变量模板
├── .gitignore             # Git 忽略文件
├── requirements.txt       # Python 依赖
└── README.md              # 本文件
```

## 🔑 环境变量

需要在 `.env` 文件中配置：

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

## 📖 使用示例

### 示例 1: 推荐类似景点

```python
query = "Tampa 有哪些像 Seminole Hard Rock 一样的高评分娱乐场所？"
result = rag.query(query, param=QueryParam(mode="mix", top_k=10))
```

### 示例 2: 城市美食推荐

```python
query = "Tampa 有哪些评分高的餐厅和咖啡馆？"
result = rag.query(query, param=QueryParam(mode="local", top_k=15))
```

### 示例 3: 适合家庭的景点

```python
query = "推荐一些适合家庭的旅游景点"
result = rag.query(query, param=QueryParam(mode="hybrid", top_k=20))
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT License

## 🙏 致谢

- [LightRAG](https://github.com/HKUDS/LightRAG) - 知识图谱框架
- Google Places API - 数据源
- PostgreSQL & pgvector - 存储后端
- Qwen - LLM 和 Embedding 服务

## 📮 联系方式

如有问题，请提交 [Issue](https://github.com/Touricks/TravelPlanner-lightRAG/issues)。
