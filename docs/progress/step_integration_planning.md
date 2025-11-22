# Step: Places 数据接入 LightRAG 方案规划

**日期**: 2024-11-22
**任务**: 设计将 PostgreSQL Places 表数据接入 LightRAG 的方案

---

## 任务背景

**数据现状**:
- PostgreSQL Places 表已有 5925 个旅游地点数据
- 包含 google_types 字段（数组类型），提供多维度分类
- 需要将这些数据接入 LightRAG 构建旅游知识图谱

**目标**:
- 利用 google_types 构建实体间关系
- 实现智能旅游推荐和问答

---

## 核心发现

### google_types 是关系构建的理想基础

**关键特征**:
1. **多维度分类**: 每个地点平均有 3-5 个类型标签
2. **强共现模式**: `establishment` ↔ `point_of_interest` (5573 次)
3. **语义层次**: `restaurant` → `food` → `establishment`
4. **自然聚类**: 相同类型地点形成相似性群组

**数据统计**:
- Top 类型: establishment (5881), point_of_interest (5573), food (1925)
- 城市分布: Tampa (144), Houston (139), Austin (131)
- 平均评分: 4.4⭐

### 可构建的关系类型

1. **同类关系** (SIMILAR_TO): 相同 google_types 的地点
2. **层级关系** (IS_A): restaurant → food → establishment
3. **地理关系** (LOCATED_IN): 地点 → 城市
4. **组合关系** (OFFERS): lodging + casino → 多功能

---

## 设计方案

### 推荐方案：混合模式

**核心思路**: 结构化文本 + 自动关系提取 + google_types 增强

**方案优势**:
- ✅ 简单快速（文本生成）
- ✅ 关系明确（基于 google_types）
- ✅ 利用 LLM 发现隐含关系

### 数据转换流程

```
PostgreSQL Places
    ↓
生成结构化文本描述
    ↓
LightRAG.insert() 自动提取实体和关系
    ↓
基于 google_types 增强关系
    ↓
知识图谱完成
```

### 文本描述模板

```
{name} 是位于 {city} 的 {primary_category}。
评分: {rating}⭐ ({reviews_count} 条评论)
类型: {google_types[0]}, {google_types[1]}, ...
{llm_description}
```

**示例**:
```
Seminole Hard Rock Hotel & Casino Tampa 是位于 Tampa 的 Casinos。
评分: 4.3⭐ (56570 条评论)
类型: casino, lodging, establishment, tourist_attraction
这是一个集赌场、住宿和娱乐于一体的综合性场所...
```

---

## 实施步骤

### 阶段 1: 数据提取脚本

**文件**: `scripts/export_places_to_lightrag.py`

**功能**:
- 从 PostgreSQL 读取 Places 数据
- 生成 LightRAG 友好的文本描述
- 输出 JSON 格式

### 阶段 2: 小规模测试

**范围**: Tampa 的 50-100 个地点

**验证内容**:
- 实体提取准确性
- 关系类型和数量
- 查询响应质量

### 阶段 3: 全量导入和优化

**任务**:
- 导入全部 5925 个地点
- 基于 google_types 构建额外关系
- 性能测试和调优

---

## 关键配置

### LightRAG 配置

```python
LightRAG(
    working_dir="./travel_rag",
    kv_storage="PostgresKVStorage",
    graph_storage="NetworkXStorage",  # 测试用
    chunk_token_size=800,
    max_async=8,
    top_k=20
)
```

### 生产环境建议

- **图存储**: Neo4j (支持复杂图查询)
- **向量存储**: Milvus (高性能检索)
- **KV 存储**: PostgreSQL (复用现有)

---

## 预期效果

### 实体类型
- Place (地点): 5925 个
- City (城市): 10+ 个
- Type (类型标签): ~50 个

### 关系类型
- LOCATED_IN: 地点 → 城市
- IS_A: 地点 → 类型
- SIMILAR_TO: 地点 ↔ 地点
- OFFERS: 地点 → 功能

### 查询能力
- "Tampa 有哪些高评分娱乐场所？"
- "推荐类似 Hard Rock 的地点"
- "适合家庭的旅游景点"

---

## 成功标准

- ✅ 实体提取准确率 > 90%
- ✅ 关系覆盖度 > 80%
- ✅ 查询响应时间 < 3 秒
- ✅ 推荐结果相关性 > 85%

---

## 输出文档

1. **集成方案 (简化版)**: `lightRAG/docs/integration_plan.md` (197 行)
2. **集成方案 (详细版)**: `lightRAG/docs/postgres_to_lightrag_integration_plan.md` (430 行)
3. **步骤记录**: 本文档

---

## 下一步

等待用户审阅方案文档后，开始编写数据提取脚本。

**状态**: ✅ 方案设计完成，待审阅
