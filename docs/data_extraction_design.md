# 数据提取脚本设计文档

**脚本名称**: `export_places_to_lightrag.py`
**文档版本**: 1.0
**创建日期**: 2025-11-22
**状态**: 设计阶段

---

## 1. 概述

### 1.1 目标
从 PostgreSQL Places 表提取旅游地点数据，转换为富文本描述，输出为 JSON Lines 格式，供 LightRAG 框架处理。

### 1.2 核心功能
- 异步连接 PostgreSQL 数据库
- 批量提取 Places 表数据
- 生成自然语言富文本描述
- 输出 JSONL 格式文件
- 支持筛选和限制条件
- 进度跟踪和错误处理

---

## 2. 数据源分析

### 2.1 Places 表结构

| 字段名 | 数据类型 | 说明 | 用途 |
|--------|----------|------|------|
| google_place_id | VARCHAR(255) | Google 地点 ID | 文档唯一标识 |
| name | VARCHAR(500) | 地点名称 | 富文本主体 |
| city | VARCHAR(100) | 城市 | 地理关系 |
| state | VARCHAR(100) | 州 | 地理关系 |
| latitude | NUMERIC(10,7) | 纬度 | 元数据 |
| longitude | NUMERIC(10,7) | 经度 | 元数据 |
| rating | NUMERIC(3,2) | 评分 (0-5) | 评价信息 |
| reviews_count | INTEGER | 评论数 | 热度指标 |
| price_level | INTEGER | 价格等级 (0-4) | 消费信息 |
| google_types | TEXT[] | Google 分类数组 | **核心关系字段** |
| primary_category | VARCHAR(100) | 主分类 | 类别归属 |
| editorial_summary | TEXT | 编辑摘要 | 描述信息 |
| llm_description | TEXT | LLM 生成描述 | 补充描述 |
| llm_tags | TEXT[] | LLM 生成标签 | 场景标签 |

### 2.2 数据示例

```json
{
  "google_place_id": "ChIJ32l5iEzPwogR8KrRdgHfdwc",
  "name": "Seminole Hard Rock Hotel & Casino Tampa",
  "city": "Tampa",
  "state": "Florida",
  "rating": 4.30,
  "reviews_count": 56570,
  "google_types": ["casino", "establishment", "lodging", "point_of_interest", "tourist_attraction"],
  "primary_category": "Casinos",
  "editorial_summary": "Upmarket casino hotel featuring 3 outdoor pools & a spa, plus eclectic dining options."
}
```

### 2.3 数据质量
- 总记录数: 5,925
- 覆盖城市: 10+ (Tampa, Houston, Austin, Nashville 等)
- 平均评分: 4.4⭐
- 平均评论数: 56k+
- llm_description/llm_tags: 可能为 null（需处理）

---

## 3. 富文本生成策略

### 3.1 设计原则
根据 `docs/development_summary.md` 第 3.3 节，LightRAG 应自动提取实体和关系，因此需要生成包含丰富信息的自然语言描述。

### 3.2 文本模板

```python
def generate_place_description(place: dict) -> str:
    """
    生成地点的富文本描述

    包含：
    - 基本信息（名称、位置、分类）
    - Google 类型（关键关系来源）
    - 评价信息（评分、评论数）
    - 描述性文本（editorial_summary, llm_description）
    - 场景标签（llm_tags）
    """
    parts = []

    # 1. 基本信息
    location = f"{place['state']} {place['city']}" if place['state'] else place['city']
    parts.append(f"{place['name']} 是位于 {location} 的 {place['primary_category']}。")

    # 2. Google 分类（核心关系字段）
    if place['google_types']:
        types_str = ', '.join(place['google_types'])
        parts.append(f"\nGoogle 分类：{types_str}")

    # 3. 评价信息
    rating_text = f"评分：{place['rating']}⭐" if place['rating'] else "评分：暂无"
    reviews_text = f"（{place['reviews_count']:,} 条评论）" if place['reviews_count'] > 0 else ""
    parts.append(f"\n{rating_text}{reviews_text}")

    # 4. 价格等级
    if place['price_level'] is not None:
        price_symbols = '$' * (place['price_level'] + 1)
        parts.append(f"\n价格等级：{price_symbols}")

    # 5. 编辑摘要
    if place['editorial_summary']:
        parts.append(f"\n\n简介：{place['editorial_summary']}")

    # 6. LLM 描述
    if place['llm_description']:
        parts.append(f"\n\nLLM 描述：{place['llm_description']}")

    # 7. 场景标签
    if place['llm_tags']:
        tags_str = ', '.join(place['llm_tags'])
        parts.append(f"\n\n适合场景：{tags_str}")

    return ''.join(parts)
```

### 3.3 输出示例

```
Seminole Hard Rock Hotel & Casino Tampa 是位于 Florida Tampa 的 Casinos。

Google 分类：casino, establishment, lodging, point_of_interest, tourist_attraction

评分：4.30⭐（56,570 条评论）

价格等级：$$$

简介：Upmarket casino hotel featuring 3 outdoor pools & a spa, plus eclectic dining options.
```

---

## 4. 输出格式设计

### 4.1 JSONL 格式
使用 JSON Lines 格式（每行一个 JSON 对象），便于流式处理和增量加载。

### 4.2 文档结构

```json
{
  "doc_id": "ChIJ32l5iEzPwogR8KrRdgHfdwc",
  "content": "富文本描述（见上节）",
  "metadata": {
    "city": "Tampa",
    "state": "Florida",
    "latitude": 28.0394654,
    "longitude": -82.5126512,
    "rating": 4.30,
    "reviews_count": 56570,
    "price_level": 3,
    "google_types": ["casino", "lodging", "tourist_attraction", "point_of_interest", "establishment"],
    "primary_category": "Casinos"
  }
}
```

### 4.3 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| doc_id | string | google_place_id，LightRAG 文档唯一标识 |
| content | string | 富文本描述，LightRAG 处理的主要内容 |
| metadata | object | 结构化元数据，用于过滤和分析 |

---

## 5. 技术实现方案

### 5.1 技术栈
- **数据库驱动**: asyncpg（异步 PostgreSQL）
- **配置管理**: python-dotenv（读取 .env）
- **进度跟踪**: tqdm（进度条）
- **数据处理**: json（JSONL 输出）
- **日志**: logging（错误和警告）

### 5.2 核心流程

```
1. 加载配置（.env）
   ↓
2. 建立数据库连接池
   ↓
3. 构建查询（应用筛选条件）
   ↓
4. 批量提取数据（每批 100 条）
   ↓
5. 生成富文本描述
   ↓
6. 写入 JSONL 文件
   ↓
7. 关闭连接，输出统计
```

### 5.3 数据库查询

```sql
SELECT
    google_place_id,
    name,
    city,
    state,
    latitude,
    longitude,
    rating,
    reviews_count,
    price_level,
    google_types,
    primary_category,
    editorial_summary,
    llm_description,
    llm_tags
FROM places
WHERE
    rating IS NOT NULL
    AND rating >= $1  -- min_rating
    AND reviews_count >= $2  -- min_reviews
    AND ($3::text IS NULL OR city = $3)  -- city filter
ORDER BY reviews_count DESC
LIMIT $4;  -- limit
```

### 5.4 批量处理策略
- 使用游标（cursor）流式读取，避免一次加载全部数据
- 每批处理 100 条记录
- 每批写入一次文件，减少内存占用

---

## 6. 配置和参数

### 6.1 命令行参数

```bash
python scripts/export_places_to_lightrag.py \
    --city Tampa \
    --limit 100 \
    --output data/tampa_places.jsonl \
    --min-rating 3.0 \
    --min-reviews 10
```

### 6.2 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| --city | str | None | 筛选城市（如 Tampa） |
| --limit | int | None | 限制记录数（None = 全部） |
| --output | str | data/places_export.jsonl | 输出文件路径 |
| --min-rating | float | 3.0 | 最低评分过滤 |
| --min-reviews | int | 10 | 最低评论数过滤 |
| --batch-size | int | 100 | 批处理大小 |

### 6.3 环境变量（.env）

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=***
POSTGRES_DB=travel_kg
```

---

## 7. 错误处理

### 7.1 数据库异常
- 捕获连接失败，输出清晰错误信息
- 查询超时自动重试（最多 3 次）
- 记录失败的记录 ID

### 7.2 数据质量问题
- google_types 为空：记录警告，跳过该记录
- llm_description/llm_tags 为 null：正常处理，不包含在描述中
- rating/reviews_count 异常：应用默认值或跳过

### 7.3 日志记录

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/export_places.log'),
        logging.StreamHandler()
    ]
)
```

---

## 8. 测试计划

### 8.1 小规模测试
- 城市：Tampa
- 数量：50-100 条记录
- 验证：输出格式、文本质量、元数据完整性

### 8.2 验证点
- [ ] 数据库连接成功
- [ ] 查询返回预期记录数
- [ ] 富文本生成正确（包含所有关键字段）
- [ ] JSONL 格式有效（可被 json.loads 解析）
- [ ] metadata 字段完整
- [ ] google_types 数组正确
- [ ] 处理 null 值无异常

### 8.3 全量测试
- 数量：5,925 条记录
- 性能：预计 5-10 分钟
- 输出文件大小：约 10-15 MB

---

## 9. 输出文件管理

### 9.1 文件命名
```
data/places_export.jsonl           # 全量导出
data/tampa_places.jsonl            # 按城市导出
data/tampa_places_100.jsonl        # 带数量限制
```

### 9.2 文件统计
输出完成后显示：
```
导出完成！
- 总记录数: 100
- 输出文件: data/tampa_places.jsonl
- 文件大小: 250.5 KB
- 平均文本长度: 350 字符
- 处理时间: 12.3 秒
```

---

## 10. 后续步骤

### 10.1 下一步任务
1. **Step 1**: 编写 `export_places_to_lightrag.py` 脚本
2. **Step 2**: 小规模测试（Tampa 100 条记录）
3. **Step 3**: 验证输出质量
4. **Step 4**: 全量导出（5,925 条记录）

### 10.2 与 Task 2 的衔接
本脚本的输出（JSONL 文件）将作为 `import_to_lightrag.py` 的输入。

---

## 11. 附录

### 11.1 依赖安装

```bash
pip install asyncpg python-dotenv tqdm
```

### 11.2 目录结构

```
lightRAG-travelplanner/
├── scripts/
│   └── export_places_to_lightrag.py  # 本脚本
├── data/
│   ├── places_export.jsonl           # 输出文件
│   └── tampa_places.jsonl
├── logs/
│   └── export_places.log             # 日志文件
├── .env                              # 数据库配置
└── docs/
    └── data_extraction_design.md     # 本文档
```

---

**文档完成，等待审阅后开始编码实现。**
