# Step: 数据源与存储方案分析

**日期**: 2024-11-22
**问题**: florida_businesses.json vs Places 表 + PostgreSQL 统一存储可行性

---

## 执行任务

分析两个关键问题：
1. 使用 florida_businesses.json 作为数据源有什么问题？
2. PostgreSQL + pgvector 作为统一存储后端是否可行？

---

## 核心发现

### 1. florida_businesses.json 数据源问题

**关键发现**: ❌ **数据源完全不匹配**

- `florida_businesses.json`: **Yelp 数据**（20,354 条记录）
- PostgreSQL `Places` 表: **Google Places API 数据**（5,925 条记录）

**对比结果**:

| 维度 | Yelp (JSON) | Google (PostgreSQL) |
|------|-------------|---------------------|
| 数据源 | Yelp Dataset | Google Places API |
| 记录数 | 20,354 | 5,925 |
| 格式 | JSONL | PostgreSQL 表 |
| 类型字段 | categories (字符串) | google_types (数组) ✅ |
| 数据质量 | 较旧，用户生成 | 实时，API 质量高 ✅ |
| 结构化 | 中等 | 高（llm_description, llm_tags）✅ |

**结论**: **完全放弃 florida_businesses.json，使用 PostgreSQL Places 表**

---

### 2. PostgreSQL + pgvector 统一存储可行性

**关键发现**: ✅ **完全可行且强烈推荐！**

**LightRAG 已原生支持 PostgreSQL**:

| 存储类型 | 实现类 | 代码位置 |
|---------|--------|----------|
| KV Storage | `PGKVStorage` | postgres_impl.py:1683 |
| Vector Storage | `PGVectorStorage` | postgres_impl.py:2171 |
| Graph Storage | `PGGraphStorage` | postgres_impl.py:3206 |
| Doc Status | `PGDocStatusStorage` | postgres_impl.py:2560 |

**PostgreSQL 存储架构**:
```
PostgreSQL 15.2
├── KV Storage: LIGHTRAG_LLM_CACHE, LIGHTRAG_FULL_DOCS
├── Vector Storage: LIGHTRAG_DOC_CHUNKS, LIGHTRAG_VDB_ENTITY
├── Graph Storage: LIGHTRAG_GRAPH_NODES, LIGHTRAG_GRAPH_EDGES
└── Doc Status: LIGHTRAG_DOC_STATUS
```

**当前状态**: 数据库未安装 pgvector 扩展（但可以正常工作，向量存为 JSON）

---

## 方案推荐

### ✅ 推荐方案：PostgreSQL + pgvector 统一存储

**优势**:
1. **数据集中**: Places 表已在 PostgreSQL，避免数据分散
2. **性能优化**: pgvector 提供高效向量检索（HNSW 索引）
3. **成本节约**: 无需额外的向量数据库（Milvus）
4. **简化部署**: 单一数据库，降低运维复杂度
5. **原生支持**: LightRAG 已有完整实现

**性能估算**（5,925 个地点）:
- 向量检索延迟: ~10-50ms（with pgvector）
- 插入吞吐: ~100 docs/s
- 存储开销: ~600MB

---

## 实施路径

### 阶段 1: 快速启动（无 pgvector）

使用 LightRAG 现有 PostgreSQL 实现：
```python
rag = LightRAG(
    kv_storage="PostgresKVStorage",
    vector_storage="PostgresVectorStorage",
    graph_storage="PostgresGraphStorage",
    vector_db_storage_cls_kwargs={
        "host": "localhost",
        "port": 5432,
        "database": "your_db",
        "workspace": "travel_rag"
    }
)
```

### 阶段 2: 启用 pgvector（性能优化）

1. **安装扩展**:
   ```sql
   CREATE EXTENSION vector;
   ```

2. **创建向量列和索引**:
   ```sql
   ALTER TABLE LIGHTRAG_DOC_CHUNKS
   ADD COLUMN content_vector_pg vector(1536);

   CREATE INDEX ON LIGHTRAG_DOC_CHUNKS
   USING hnsw (content_vector_pg vector_cosine_ops);
   ```

3. **配置 LightRAG**:
   ```python
   vector_db_storage_cls_kwargs={
       "vector_index_type": "hnsw",
       "hnsw_m": 16,
       "hnsw_ef": 64
   }
   ```

---

## 输出文档

- **分析报告**: `lightRAG/docs/data_source_and_storage_analysis.md`
- **步骤记录**: 本文档

---

## 核心建议

### 数据源

❌ **不要使用 florida_businesses.json**
- 数据源不匹配（Yelp vs Google）
- 缺少关键字段（google_types, llm_description）

✅ **使用 PostgreSQL Places 表**
- 数据质量高，结构完善
- 天然支持 google_types 关系构建

### 存储后端

✅ **PostgreSQL + pgvector 统一存储**
- 数据集中在一个数据库
- 高效向量检索（pgvector HNSW 索引）
- LightRAG 原生支持，开箱即用

---

**状态**: ✅ 分析完成
**下一步**: 安装 pgvector 并开始数据导入
