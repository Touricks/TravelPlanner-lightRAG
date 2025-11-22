# Places 数据接入 LightRAG 方案

**日期**: 2024-11-22 | **数据规模**: 5925 个地点 | **核心**: 基于 google_types 构建关系

---

## 1. 核心观点

### ✅ google_types 是关系构建的关键

**数据特征**:
- 每个地点有 3-5 个 google_types 标签（数组类型）
- 最强共现: `establishment` ↔ `point_of_interest` (5573 次)
- 形成天然的**多维度分类体系**和**层级关系**

**关系类型**:
```
1. 同类关系: Tampa Theatre (movie_theater) --[SIMILAR_TO]--> 其他影院
2. 层级关系: Hard Rock (casino) --[IS_A]--> tourist_attraction
3. 地理关系: Tampa Theatre --[LOCATED_IN]--> Tampa
4. 组合关系: Hard Rock (lodging + casino) --[OFFERS]--> 多功能
```

---

## 2. 数据现状

### Places 表关键字段

| 字段 | 类型 | 用途 |
|------|------|------|
| `google_place_id` | varchar(255) | 实体唯一标识 |
| `name` | varchar(500) | 实体名称 |
| `city` | varchar(100) | 地理关系 |
| **`google_types`** | **text[]** | **关系构建核心** |
| `primary_category` | varchar(100) | 主分类 |
| `llm_description` | text | 文本内容源 |
| `rating` | numeric(3,2) | 质量指标 |
| `reviews_count` | integer | 热度指标 |

### Top 10 google_types

1. `establishment` (5881)
2. `point_of_interest` (5573)
3. `food` (1925)
4. `tourist_attraction` (1685)
5. `restaurant` (1682)
6. `store` (886)
7. `park` (845)
8. `bar` (734)
9. `museum` (667)
10. `cafe` (554)

---

## 3. 推荐方案：混合模式

### 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **A: 纯文本生成** | 简单快速，利用 LLM 自动提取 | 关系质量依赖 LLM | MVP 测试 |
| **B: 结构化图谱** | 关系明确可控，查询高效 | 需要预处理逻辑 | 生产环境 |
| **C: 混合模式** ✅ | 兼具两者优点 | 实现稍复杂 | **推荐** |

### 混合模式实施

**步骤 1: 生成结构化文本**
```python
def generate_place_description(place):
    return f"""
{place.name} 是位于 {place.city} 的 {place.primary_category}。
评分: {place.rating}⭐ ({place.reviews_count} 条评论)
类型: {', '.join(place.google_types)}
{place.llm_description}
"""
```

**步骤 2: 批量导入 LightRAG**
```python
rag = LightRAG(
    working_dir="./travel_rag",
    kv_storage="PostgresKVStorage",
    graph_storage="NetworkXStorage",
    chunk_token_size=800,
    max_async=8
)

descriptions = [generate_place_description(p) for p in places]
rag.insert(descriptions, ids=[p.google_place_id for p in places])
```

**步骤 3: 基于 google_types 增强关系**
```python
# 同类关系
for type_tag in unique_types:
    places_of_type = get_places_by_type(type_tag)
    add_similarity_relationships(places_of_type)

# 类型层级
type_hierarchy = {
    'restaurant': ['food', 'establishment'],
    'museum': ['tourist_attraction', 'point_of_interest']
}
add_hierarchical_relationships(type_hierarchy)
```

---

## 4. 关键配置

### LightRAG 配置

```python
LightRAG(
    # 存储
    kv_storage="PostgresKVStorage",      # 复用现有数据库
    vector_storage="NanoVectorDBStorage", # 本地测试
    graph_storage="NetworkXStorage",      # 本地测试

    # 分块
    chunk_token_size=800,        # 每个地点 ~200-300 tokens
    chunk_overlap_token_size=50,

    # 性能
    max_async=8,
    embedding_func_max_async=32,
    max_parallel_insert=4,

    # 检索
    top_k=20,
    chunk_top_k=10
)
```

### 生产环境建议

- `graph_storage`: **Neo4j** (复杂图查询)
- `vector_storage`: **Milvus** (高性能向量检索)
- `kv_storage`: **PostgreSQL** (复用现有)

---

## 5. 查询示例

```python
# 示例 1: 推荐类似景点
query = "Tampa 有哪些像 Seminole Hard Rock 一样的高评分娱乐场所？"
result = rag.query(query, param=QueryParam(mode="mix", top_k=10))

# 示例 2: 城市美食推荐
query = "Tampa 有哪些评分高的餐厅和咖啡馆？"
result = rag.query(query, param=QueryParam(mode="local", top_k=15))
```

---

## 6. 实施路线图

### 阶段 1: MVP (1-2 天)

- [ ] 编写数据提取脚本 `scripts/export_places_to_lightrag.py`
- [ ] 小规模测试 (Tampa 的 50-100 个地点)
- [ ] 验证实体和关系提取质量

### 阶段 2: 优化 (2-3 天)

- [ ] 全量导入 5925 个地点
- [ ] 基于 google_types 构建额外关系
- [ ] 调整 Prompt 和配置参数

### 阶段 3: 生产 (3-5 天)

- [ ] 切换到生产级存储 (Neo4j + Milvus)
- [ ] 性能测试和优化
- [ ] 查询接口封装

---

## 7. 优势与风险

### 优势

1. ✅ **结构化标签**: google_types 提供明确分类
2. ✅ **多维关系**: 一个地点属于多个类型，关系网丰富
3. ✅ **语义层次**: restaurant → food → establishment
4. ✅ **双层检索**: LightRAG 的图谱 + 向量检索

### 风险及缓解

| 风险 | 缓解策略 |
|------|----------|
| LLM 成本 | 复用 llm_description，批量处理 |
| 关系冗余 | 设置相似度阈值过滤 |
| 查询性能 | 使用 Neo4j 专业图数据库 |

---

## 8. 下一步

### 立即行动

1. **编写脚本**: `export_places_to_lightrag.py`
   - 从 PostgreSQL 提取数据
   - 生成文本描述
   - 输出 JSON 格式

2. **小规模测试**:
   ```bash
   python scripts/export_places_to_lightrag.py --city Tampa --limit 50
   python scripts/import_to_lightrag.py --input tampa_50.json
   ```

3. **验证效果**:
   - 检查提取的实体名称
   - 验证关系类型和准确性
   - 测试查询响应质量

### 成功标准

- ✅ 实体提取准确率 > 90%
- ✅ 关系覆盖度 > 80% (基于 google_types)
- ✅ 查询响应时间 < 3 秒
- ✅ 推荐结果相关性 > 85%

---

## 附录

### A. 数据统计

- **总地点数**: 5925
- **城市数**: 10+ (Tampa, Houston, Austin 等)
- **平均评分**: 4.4
- **平均 google_types 数**: 3.2

### B. 参考文档

- LightRAG 执行模式: `lightRAG/lightrag/memory/execution_mode_analysis.md`
- Google Types 参考: `DataPreprocessing/docs/1103/google_places_types_reference.md`
- 项目架构: `DataPreprocessing/docs/1103/midpoint.pdf`

---

**版本**: 1.0 | **作者**: Claude | **审阅状态**: 待审阅
