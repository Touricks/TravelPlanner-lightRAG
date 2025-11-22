# LightRAG 执行模式分析文档

## 1. 概述

LightRAG 是一个轻量级的检索增强生成（RAG）框架，通过知识图谱和向量检索的双层结构，实现高效的文档索引和智能问答。

**核心特点**：
- 基于知识图谱的结构化信息存储
- 向量检索与图检索的混合模式
- 异步并发处理提升性能
- 灵活的存储后端支持
- 完整的文档处理生命周期管理

---

## 2. 系统架构

### 2.1 核心组件层次

```
LightRAG
├── 初始化层 (Initialization Layer)
│   ├── 配置管理 (Configuration)
│   ├── 存储初始化 (Storage Setup)
│   └── 模型初始化 (Model Setup)
│
├── 数据处理层 (Data Processing Layer)
│   ├── 文档分块 (Chunking)
│   ├── 实体提取 (Entity Extraction)
│   ├── 关系提取 (Relation Extraction)
│   └── 向量化 (Vectorization)
│
├── 存储层 (Storage Layer)
│   ├── KV Storage (键值存储)
│   ├── Vector Storage (向量存储)
│   ├── Graph Storage (图存储)
│   └── DocStatus Storage (文档状态存储)
│
└── 查询层 (Query Layer)
    ├── 检索引擎 (Retrieval Engine)
    ├── 重排序 (Re-ranking)
    └── LLM 生成 (Generation)
```

### 2.2 存储后端支持

LightRAG 支持多种存储后端，可根据需求选择：

**KV Storage**:
- JsonKVStorage (默认)
- MongoDB
- Redis
- PostgreSQL

**Vector Storage**:
- NanoVectorDBStorage (默认)
- Milvus
- Qdrant
- FAISS

**Graph Storage**:
- NetworkXStorage (默认)
- Neo4j
- MemGraph
- PostgreSQL (with pgvector)

**DocStatus Storage**:
- JsonDocStatusStorage (默认)
- MongoDB
- PostgreSQL

---

## 3. 执行模式详解

### 3.1 初始化模式 (Initialization Mode)

**文件**: `lightrag/lightrag.py`

#### 3.1.1 配置加载
```python
@dataclass
class LightRAG:
    # 核心配置项
    working_dir: str = "./rag_storage"
    kv_storage: str = "JsonKVStorage"
    vector_storage: str = "NanoVectorDBStorage"
    graph_storage: str = "NetworkXStorage"
    doc_status_storage: str = "JsonDocStatusStorage"
```

#### 3.1.2 初始化流程
1. **加载环境变量** (.env 文件)
2. **验证存储实现兼容性** (verify_storage_implementation)
3. **检查环境变量配置** (check_storage_env_vars)
4. **初始化 Tokenizer** (默认使用 TiktokenTokenizer)
5. **初始化 Embedding 函数** (priority_limit_async_func_call 包装)
6. **创建存储类实例** (partial 函数预配置)
7. **初始化共享数据** (initialize_share_data)

#### 3.1.3 关键代码位置
- 初始化入口: `lightrag.py:432` (__post_init__)
- 存储初始化: `lightrag.py:522-549`
- 异步初始化: 需调用 `initialize_storages()` 方法

**使用示例**:
```python
# 来源: reproduce/Step_1.py:35-41
async def initialize_rag():
    rag = LightRAG(working_dir=WORKING_DIR)
    await rag.initialize_storages()
    await initialize_pipeline_status()
    return rag
```

---

### 3.2 数据插入模式 (Insert/Index Pipeline)

**核心文件**: `lightrag/operate.py`

#### 3.2.1 插入流程概览

```
输入文档
    ↓
[1] 文档入队 (apipeline_enqueue_documents)
    ↓
[2] 文档分块 (chunking_by_token_size)
    ↓
[3] 实体和关系提取 (extract_entities)
    ↓
[4] 向量化 (embedding_func)
    ↓
[5] 知识图谱构建 (merge_nodes_and_edges)
    ↓
[6] 存储到后端
    ↓
完成
```

#### 3.2.2 文档分块 (Chunking)

**函数**: `chunking_by_token_size` (`operate.py:96-148`)

**关键参数**:
- `max_token_size`: 最大 token 数 (默认 1200)
- `overlap_token_size`: 重叠 token 数 (默认 100)
- `split_by_character`: 按字符分割标记 (可选)
- `split_by_character_only`: 仅按字符分割 (可选)

**分块策略**:
1. **字符分割优先**: 如果指定 `split_by_character`，先按字符分割
2. **Token 限制**: 超过 `max_token_size` 的块会进一步分割
3. **重叠窗口**: 使用 `overlap_token_size` 保证上下文连续性
4. **索引编号**: 每个 chunk 带有 `chunk_order_index`

**输出格式**:
```python
{
    "tokens": int,           # chunk 的 token 数
    "content": str,          # chunk 的文本内容
    "chunk_order_index": int # chunk 在文档中的序号
}
```

#### 3.2.3 实体和关系提取 (Entity & Relation Extraction)

**函数**: `extract_entities` (`operate.py`)

**提取流程**:
1. **LLM 调用**: 使用 Prompt 模板请求 LLM 提取实体和关系
2. **结果解析**: 解析 LLM 返回的 JSON 格式
3. **数据清洗**:
   - 去除重复实体
   - 标准化实体名称
   - 截断过长的标识符 (`_truncate_entity_identifier`)
4. **元数据附加**: 添加 source_id, chunk_key 等元信息

**Prompt 模板**: `lightrag/prompt.py` → `PROMPTS["entity_extraction"]`

**提取的信息**:
- **实体 (Entities)**: name, type, description, source_id
- **关系 (Relations)**: src_id, tgt_id, description, keywords, weight, source_id

#### 3.2.4 知识图谱合并 (Graph Merge)

**函数**: `merge_nodes_and_edges` (`operate.py`)

**合并策略**:
1. **实体合并**:
   - 相同名称的实体合并为一个节点
   - description 列表聚合
   - source_ids 合并（支持 FIFO/KEEP 策略）
   - 可选 LLM 摘要（`_handle_entity_relation_summary`）

2. **关系合并**:
   - 相同 (src, tgt) 的关系合并
   - keywords 列表聚合
   - 权重累加或重新计算

3. **摘要生成**:
   - Map-Reduce 策略处理长描述列表
   - 分块摘要后递归合并
   - Token 限制: `summary_max_tokens`, `summary_context_size`

#### 3.2.5 并发控制

**关键机制**:
- **异步批量处理**: `asyncio.gather` 并发执行
- **限流控制**: `priority_limit_async_func_call` 限制并发数
- **锁机制**: `get_storage_keyed_lock` 避免竞态条件

**配置参数**:
- `max_async`: LLM 最大并发数 (默认 4)
- `max_parallel_insert`: 插入最大并发数 (默认 1)
- `embedding_func_max_async`: Embedding 最大并发数 (默认 16)

#### 3.2.6 Checkpoint 和容错

**文档状态跟踪**:
- 每个文档有状态: `NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `FAILED`
- 支持断点续传（通过 `track_id` 追踪）
- 失败重试机制（示例见 `reproduce/Step_1.py:14-25`）

**代码示例**:
```python
# 来源: reproduce/Step_1.py:10-26
def insert_text(rag, file_path):
    with open(file_path, mode="r") as f:
        unique_contexts = json.load(f)

    retries = 0
    max_retries = 3
    while retries < max_retries:
        try:
            rag.insert(unique_contexts)
            break
        except Exception as e:
            retries += 1
            print(f"Insertion failed, retrying ({retries}/{max_retries})")
            time.sleep(10)
```

---

### 3.3 查询模式 (Query/Retrieval Mode)

**核心文件**: `lightrag/lightrag.py`, `lightrag/operate.py`

#### 3.3.1 查询流程概览

```
用户查询
    ↓
[1] 查询预处理
    ↓
[2] 根据模式选择检索策略
    ├── local: 局部上下文检索
    ├── global: 全局知识检索
    ├── hybrid: 混合检索
    ├── naive: 简单向量检索
    ├── mix: 知识图谱 + 向量检索
    └── bypass: 直接 LLM 调用
    ↓
[3] 检索相关内容
    ├── 向量相似度检索
    └── 知识图谱查询
    ↓
[4] 重排序 (可选)
    ↓
[5] 构建 Prompt
    ↓
[6] LLM 生成响应
    ↓
返回结果
```

#### 3.3.2 查询模式详解

**1. Local 模式**
- **适用场景**: 问题依赖特定上下文
- **检索策略**: 提取查询关键实体 → 查找相关子图 → 检索关联 chunks
- **优点**: 精确匹配局部信息

**2. Global 模式**
- **适用场景**: 需要全局概览或汇总信息
- **检索策略**: 高层次实体 → 全局社区摘要 → 宏观信息聚合
- **优点**: 提供整体视角

**3. Hybrid 模式**
- **检索策略**: 结合 Local 和 Global 的结果
- **优点**: 平衡局部细节和全局概览

**4. Naive 模式**
- **检索策略**: 纯向量相似度检索
- **优点**: 简单快速，适合无结构化需求

**5. Mix 模式** (推荐)
- **检索策略**: 知识图谱实体检索 + 向量相似度检索
- **优点**: 结合结构化和非结构化信息优势

**6. Bypass 模式**
- **检索策略**: 跳过检索，直接调用 LLM
- **适用场景**: 通用问题或不依赖知识库

#### 3.3.3 知识图谱查询

**函数**: `kg_query` (`operate.py`)

**查询步骤**:
1. **实体识别**: 从查询中提取关键实体
2. **子图检索**: 根据实体查找相关的节点和边
3. **路径扩展**: 扩展关联实体（可配置跳数）
4. **结果聚合**: 收集实体描述、关系信息
5. **Chunk 关联**: 根据 source_id 检索原始文本块

**配置参数**:
- `top_k`: 返回实体数量 (默认 60)
- `max_entity_tokens`: 单个实体最大 token 数 (默认 1000)
- `max_relation_tokens`: 单个关系最大 token 数 (默认 800)
- `max_total_tokens`: 总 token 数限制 (默认 8000)

#### 3.3.4 向量检索

**向量相似度计算**:
- 使用 cosine similarity
- 阈值过滤: `cosine_better_than_threshold` (默认 0.2)
- Top-K 检索: `chunk_top_k` (默认 5)

**检索方法**:
```python
# 方式 1: 加权轮询 (weighted polling)
pick_by_weighted_polling(chunks, weights, top_k)

# 方式 2: 向量相似度 (vector similarity)
pick_by_vector_similarity(chunks, query_embedding, top_k)
```

**配置**: `kg_chunk_pick_method` (默认 "weighted")

#### 3.3.5 重排序 (Re-ranking)

**文件**: `lightrag/rerank.py`

**重排序策略**:
- 使用专门的重排序模型（如 Cross-Encoder）
- 根据查询和文档的相关性重新打分
- 过滤低分结果: `min_rerank_score` (默认 0.0)

**代码位置**: `rerank.py` 提供可选的重排序接口

#### 3.3.6 LLM 生成

**函数**: `aquery_llm` (`lightrag.py:2757`)

**生成流程**:
1. **上下文构建**: 检索结果 + 系统提示词 + 用户查询
2. **Prompt 模板**: `PROMPTS["rag_response"]`
3. **LLM 调用**:
   - 支持流式输出 (`stream=True`)
   - 支持非流式输出 (`stream=False`)
4. **结果返回**:
   - 流式: AsyncIterator[str]
   - 非流式: str

**缓存机制**:
- LLM 响应缓存到 `llm_response_cache` (KV Storage)
- 相同查询直接返回缓存结果

**代码示例**:
```python
# 来源: lightrag.py:2336-2355
def query(
    self,
    query: str,
    param: QueryParam = QueryParam(),
    system_prompt: str | None = None,
) -> str:
    loop = always_get_an_event_loop()
    return loop.run_until_complete(
        self.aquery(query, param, system_prompt)
    )
```

---

## 4. 数据流转详解

### 4.1 Insert 数据流

```
[外部输入]
    │
    ├─→ 文档字符串 / 文档列表
    │   (input: str | list[str])
    ↓
[分块处理]
    │
    ├─→ tokenizer.encode(content)
    ├─→ 按 max_token_size 分割
    ├─→ overlap_token_size 重叠
    │
    ↓
[Chunk 对象]
    │
    ├─→ {tokens, content, chunk_order_index, full_doc_id}
    │
    ↓
[实体提取]
    │
    ├─→ LLM 提取 (extract_entities)
    ├─→ 返回 {entities: [...], relationships: [...]}
    │
    ↓
[向量化]
    │
    ├─→ embedding_func(chunk.content)
    ├─→ 存储到 VectorDB
    │
    ↓
[图谱构建]
    │
    ├─→ merge_nodes_and_edges
    ├─→ 实体去重合并
    ├─→ 关系去重合并
    ├─→ 生成摘要 (可选)
    │
    ↓
[持久化存储]
    │
    ├─→ KV Storage: chunks, llm_cache
    ├─→ Vector Storage: embeddings
    ├─→ Graph Storage: entities, relations
    └─→ DocStatus Storage: document status
```

### 4.2 Query 数据流

```
[用户查询]
    │
    ├─→ query: str
    ├─→ param: QueryParam (mode, top_k, ...)
    │
    ↓
[查询向量化]
    │
    ├─→ embedding_func(query)
    │
    ↓
[检索策略选择]
    │
    ├─→ mode = "local"  → kg_query (局部)
    ├─→ mode = "global" → kg_query (全局)
    ├─→ mode = "hybrid" → kg_query (混合)
    ├─→ mode = "naive"  → vector_search
    ├─→ mode = "mix"    → kg_query + vector_search
    └─→ mode = "bypass" → 跳过检索
    │
    ↓
[知识图谱检索]
    │
    ├─→ 提取查询实体
    ├─→ 查找相关实体和关系
    ├─→ 根据 source_id 检索 chunks
    │
    ↓
[向量检索]
    │
    ├─→ cosine_similarity(query_emb, chunk_embs)
    ├─→ Top-K 过滤
    │
    ↓
[结果合并]
    │
    ├─→ 合并 KG 结果和向量结果
    ├─→ 去重
    │
    ↓
[重排序] (可选)
    │
    ├─→ rerank_model(query, chunks)
    ├─→ 过滤低分
    │
    ↓
[上下文构建]
    │
    ├─→ 系统提示词
    ├─→ 检索到的 chunks
    ├─→ 用户查询
    │
    ↓
[LLM 生成]
    │
    ├─→ llm_model_func(prompt)
    ├─→ 缓存响应
    │
    ↓
[返回结果]
    │
    ├─→ 流式: AsyncIterator[str]
    └─→ 非流式: str
```

---

## 5. 关键技术机制

### 5.1 异步并发控制

**核心工具**: `priority_limit_async_func_call` (`utils.py`)

**功能**:
- 限制并发任务数量
- 任务优先级队列
- 超时控制
- 异常处理和重试

**应用场景**:
- LLM 调用限流 (max_async)
- Embedding 批量计算 (embedding_func_max_async)
- 图谱插入并发控制 (max_parallel_insert)

### 5.2 缓存机制

**多层缓存**:
1. **LLM 响应缓存**: `llm_response_cache` (KV Storage)
   - Key: compute_args_hash(prompt, model, params)
   - Value: LLM 响应内容

2. **Chunk 缓存**: `CacheData` 结构
   - 缓存提取的实体和关系
   - 避免重复 LLM 调用

**缓存函数**:
- `use_llm_func_with_cache`: 带缓存的 LLM 调用
- `handle_cache`: 缓存读取
- `save_to_cache`: 缓存写入

### 5.3 锁机制 (Locking)

**文件**: `lightrag/kg/shared_storage.py`

**锁类型**:
- `get_storage_keyed_lock`: 存储操作锁
- `get_pipeline_status_lock`: 流水线状态锁
- `get_graph_db_lock`: 图数据库操作锁
- `get_data_init_lock`: 数据初始化锁

**用途**:
- 防止并发写入冲突
- 保证实体合并的原子性
- 协调多进程/多线程访问

### 5.4 命名空间 (Namespace)

**文件**: `lightrag/namespace.py`

**作用**:
- 隔离不同类型的数据存储
- 支持多租户（workspace）

**命名空间类型**:
```python
class NameSpace:
    KV_STORE_CHUNKS = "chunks"
    KV_STORE_ENTITIES = "entities"
    KV_STORE_RELATIONS = "relations"
    KV_STORE_LLM_RESPONSE_CACHE = "llm_response_cache"
    VECTOR_STORE_CHUNKS = "chunks_vector"
    GRAPH_STORE = "graph"
    DOC_STATUS = "doc_status"
```

### 5.5 错误处理

**异常类型**: `lightrag/exceptions.py`
- `PipelineCancelledException`: 流水线取消异常

**容错策略**:
- LLM 调用失败重试
- 向量存储操作异常处理 (`safe_vdb_operation_with_exception`)
- 前缀异常封装 (`create_prefixed_exception`)

---

## 6. 配置参数参考

### 6.1 核心参数

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `working_dir` | "./rag_storage" | 工作目录 |
| `chunk_token_size` | 1200 | 分块大小 (tokens) |
| `chunk_overlap_token_size` | 100 | 分块重叠大小 |
| `max_async` | 4 | LLM 最大并发数 |
| `embedding_func_max_async` | 16 | Embedding 最大并发 |
| `max_parallel_insert` | 1 | 插入最大并发数 |

### 6.2 检索参数

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `top_k` | 60 | 返回实体数量 |
| `chunk_top_k` | 5 | 返回 chunk 数量 |
| `max_entity_tokens` | 1000 | 单个实体最大 tokens |
| `max_relation_tokens` | 800 | 单个关系最大 tokens |
| `max_total_tokens` | 8000 | 总 tokens 限制 |
| `cosine_better_than_threshold` | 0.2 | 相似度阈值 |

### 6.3 摘要参数

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `summary_max_tokens` | 500 | 摘要最大 tokens |
| `summary_context_size` | 4096 | 摘要上下文大小 |
| `summary_length_recommended` | 200 | 推荐摘要长度 |
| `force_llm_summary_on_merge` | 3 | 强制 LLM 摘要阈值 |

---

## 7. 使用模式和最佳实践

### 7.1 基础使用流程

```python
import asyncio
from lightrag import LightRAG, QueryParam

# 1. 初始化
async def main():
    rag = LightRAG(
        working_dir="./my_rag",
        kv_storage="JsonKVStorage",
        vector_storage="NanoVectorDBStorage",
        graph_storage="NetworkXStorage"
    )
    await rag.initialize_storages()

    # 2. 插入文档
    documents = ["文档1内容", "文档2内容", ...]
    track_id = rag.insert(documents)

    # 3. 查询
    result = rag.query(
        "你的问题",
        param=QueryParam(mode="mix", top_k=10)
    )
    print(result)

asyncio.run(main())
```

### 7.2 生产环境配置建议

**1. 存储选择**:
- 小规模 (< 10万文档): 默认存储（JSON + NanoVectorDB + NetworkX）
- 中规模 (10万-100万): Milvus + Neo4j + MongoDB
- 大规模 (> 100万): PostgreSQL (全功能) 或 Redis + FAISS + Neo4j

**2. 并发调优**:
```python
LightRAG(
    max_async=8,                    # 根据 LLM API 限制调整
    embedding_func_max_async=32,    # Embedding 通常更快
    max_parallel_insert=4           # 根据存储性能调整
)
```

**3. Token 预算**:
```python
LightRAG(
    chunk_token_size=800,           # 减少以降低成本
    max_total_tokens=6000,          # 控制单次查询成本
    summary_max_tokens=300          # 控制摘要长度
)
```

**4. 缓存策略**:
- 启用 LLM 响应缓存（默认启用）
- 相同查询直接返回缓存
- 定期清理过期缓存

### 7.3 常见问题排查

**问题 1: 插入速度慢**
- 检查 `max_async` 和 `embedding_func_max_async`
- 确认 LLM API 响应时间
- 考虑批量插入

**问题 2: 查询质量不佳**
- 调整查询模式 (mode)
- 增加 `top_k` 和 `chunk_top_k`
- 检查实体提取 Prompt

**问题 3: 内存占用高**
- 减少 `max_total_tokens`
- 使用更高效的存储后端
- 限制并发数

---

## 8. 扩展和定制

### 8.1 自定义 Prompt

修改 `lightrag/prompt.py` 中的 `PROMPTS` 字典:

```python
PROMPTS["entity_extraction"] = """
你的自定义实体提取 Prompt
"""

PROMPTS["rag_response"] = """
你的自定义响应生成 Prompt
"""
```

### 8.2 自定义存储后端

实现 `BaseKVStorage`, `BaseVectorStorage`, `BaseGraphStorage` 接口:

```python
from lightrag.base import BaseVectorStorage

class MyCustomVectorDB(BaseVectorStorage):
    async def upsert(self, data: dict):
        # 实现向量插入逻辑
        pass

    async def query(self, query: str, top_k: int):
        # 实现向量查询逻辑
        pass
```

注册到 `STORAGES`:
```python
from lightrag.kg import STORAGES
STORAGES["MyCustomVectorDB"] = MyCustomVectorDB
```

### 8.3 自定义 Embedding 函数

```python
async def my_embedding_func(texts: list[str]) -> np.ndarray:
    # 调用自定义 Embedding API
    embeddings = await call_my_api(texts)
    return np.array(embeddings)

rag = LightRAG(
    embedding_func=my_embedding_func
)
```

---

## 9. 性能优化建议

### 9.1 索引阶段优化

1. **批量处理**: 一次插入多个文档而非逐个插入
2. **并发调优**: 根据硬件和 API 限制调整 `max_async`
3. **分块策略**: 根据文档特点调整 `chunk_token_size` 和 `overlap`
4. **缓存复用**: 相同文档不要重复插入

### 9.2 查询阶段优化

1. **模式选择**: 根据问题类型选择合适的查询模式
2. **Top-K 控制**: 不要设置过大的 `top_k` 值
3. **重排序**: 对于高精度需求，启用重排序
4. **流式输出**: 长回答使用流式输出提升用户体验

### 9.3 存储优化

1. **索引优化**: 为常查询字段建立索引
2. **定期清理**: 删除不再需要的文档和缓存
3. **分片策略**: 大规模数据使用分片存储
4. **备份恢复**: 定期备份关键数据

---

## 10. 总结

### 10.1 LightRAG 核心优势

1. **双层检索架构**: 知识图谱 + 向量检索，结合结构化和语义检索优势
2. **灵活存储**: 支持多种存储后端，适应不同规模需求
3. **异步高效**: 全异步设计，支持高并发处理
4. **完整生命周期**: 从文档索引到查询生成的完整流程
5. **易于扩展**: 清晰的接口设计，方便定制和扩展

### 10.2 适用场景

- **企业知识库**: 公司文档、技术手册检索
- **学术研究**: 论文、书籍的智能问答
- **客服系统**: 基于知识库的自动客服
- **内容推荐**: 基于语义理解的内容推荐

### 10.3 技术栈总结

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.8+ |
| 异步框架 | asyncio |
| LLM 接口 | OpenAI API (可扩展) |
| Tokenizer | tiktoken (GPT) |
| 图处理 | NetworkX / Neo4j |
| 向量检索 | NanoVectorDB / Milvus / FAISS |
| 数据存储 | JSON / MongoDB / PostgreSQL / Redis |

---

## 附录

### A. 核心文件索引

| 文件路径 | 核心功能 |
|----------|----------|
| `lightrag/lightrag.py` | LightRAG 主类，初始化和 API 入口 |
| `lightrag/base.py` | 存储接口定义 (BaseKVStorage, BaseVectorStorage, BaseGraphStorage) |
| `lightrag/operate.py` | 数据处理核心逻辑 (分块、提取、查询) |
| `lightrag/utils.py` | 工具函数 (异步控制、缓存、编码) |
| `lightrag/utils_graph.py` | 图处理工具函数 |
| `lightrag/prompt.py` | Prompt 模板定义 |
| `lightrag/kg/*.py` | 各种存储后端实现 |
| `lightrag/namespace.py` | 命名空间定义 |
| `lightrag/constants.py` | 常量和默认值定义 |
| `lightrag/exceptions.py` | 异常类定义 |

### B. 参考资源

- **官方仓库**: https://github.com/HKUDS/LightRAG
- **算法流程图**: `lightrag/docs/Algorithm.md`
- **示例代码**: `lightrag/reproduce/` 目录
- **API 文档**: `lightrag/lightrag/api/` 目录

---

**文档版本**: 1.0
**最后更新**: 2024-11-22
**适用 LightRAG 版本**: 1.4.9.8
