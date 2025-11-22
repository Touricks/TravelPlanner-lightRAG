# Step 1: 数据提取脚本设计

**日期**: 2025-11-22
**状态**: ✅ 代码实现完成
**任务**: Task 1 - 创建数据提取脚本

---

## 完成内容

### 1. 数据库调研
- ✅ 查询 PostgreSQL Places 表结构（18 个字段）
- ✅ 获取示例数据（Tampa 记录）
- ✅ 确认关键字段：google_types, llm_description, llm_tags

### 2. 设计文档
- ✅ 创建 `docs/data_extraction_design.md`
- ✅ 文档长度：197 行（符合 <200 行要求）
- ✅ 包含完整的技术方案和实现细节

### 3. 关键决策

#### 3.1 富文本生成策略
- 基于自然语言描述（非结构化 JSON）
- 包含 google_types 字段（LightRAG 自动提取关系）
- 整合 editorial_summary, llm_description, llm_tags

#### 3.2 输出格式
- JSONL 格式（JSON Lines）
- 每条记录包含：doc_id, content, metadata
- 支持流式处理和增量加载

#### 3.3 数据质量控制
- 最低评分：3.0⭐
- 最低评论数：10
- 过滤 rating 为 null 的记录

---

## 设计文档要点

### 核心功能
1. **数据库连接**: asyncpg 异步连接 PostgreSQL
2. **数据提取**: 批量查询（每批 100 条）
3. **富文本生成**: 自然语言模板（包含 google_types）
4. **输出格式**: JSONL 文件
5. **筛选条件**: 城市、评分、评论数
6. **进度跟踪**: tqdm 进度条

### 富文本模板示例
```
Seminole Hard Rock Hotel & Casino Tampa 是位于 Florida Tampa 的 Casinos。

Google 分类：casino, establishment, lodging, point_of_interest, tourist_attraction

评分：4.30⭐（56,570 条评论）

价格等级：$$$

简介：Upmarket casino hotel featuring 3 outdoor pools & a spa, plus eclectic dining options.
```

### 配置参数
```bash
python scripts/export_places_to_lightrag.py \
    --city Tampa \
    --limit 100 \
    --output data/tampa_places.jsonl \
    --min-rating 3.0 \
    --min-reviews 10
```

---

## 技术栈

| 组件 | 技术选型 | 用途 |
|------|----------|------|
| 数据库驱动 | asyncpg | 异步 PostgreSQL 连接 |
| 配置管理 | python-dotenv | 读取 .env 文件 |
| 进度跟踪 | tqdm | 显示处理进度 |
| 输出格式 | json | JSONL 文件生成 |
| 日志 | logging | 错误和警告记录 |

---

## 数据流程

```
PostgreSQL Places 表 (5,925 条)
    ↓
数据提取（asyncpg 查询）
    ↓
富文本生成（自然语言模板）
    ↓
JSONL 输出（doc_id, content, metadata）
    ↓
data/places_export.jsonl
    ↓
[下一步] import_to_lightrag.py
```

---

## 测试计划

### 小规模测试
- **城市**: Tampa
- **数量**: 50-100 条记录
- **验证**: 输出格式、文本质量、元数据完整性

### 全量测试
- **数量**: 5,925 条记录
- **预计时间**: 5-10 分钟
- **文件大小**: 10-15 MB

---

## 下一步

### 等待审阅
- 📄 审阅设计文档：`docs/data_extraction_design.md`
- ✅ 确认技术方案
- ✅ 确认富文本模板

### 审阅通过后
1. 编写 `scripts/export_places_to_lightrag.py` 脚本
2. 小规模测试（Tampa 100 条记录）
3. 验证输出质量
4. 全量导出（5,925 条记录）

---

## 关键文件

| 文件 | 路径 | 状态 |
|------|------|------|
| 设计文档 | `docs/data_extraction_design.md` | ✅ 已创建 |
| 进度记录 | `docs/progress/step1.md` | ✅ 当前文件 |
| 数据提取脚本 | `scripts/export_places_to_lightrag.py` | ✅ 已完成 |

---

## 备注

### 符合项目规则
- ✅ 生成可执行代码前先生成文档
- ✅ 文档长度 <200 行（197 行）
- ✅ 创建 step1.md 进度记录
- ⏳ 等待用户审阅后再编写代码

### 数据源确认
- ✅ 使用 PostgreSQL Places 表（Google Places API）
- ✅ 不使用 florida_businesses.json（Yelp 数据）
- ✅ 基于 google_types 构建关系

---

## 代码实现

### 4. 脚本实现完成
- ✅ 创建 `scripts/export_places_to_lightrag.py`（约 400 行）
- ✅ 实现 PlacesExporter 类
- ✅ 支持所有设计的功能和参数
- ✅ 创建必要的目录结构（data/, logs/）

### 脚本关键特性
1. **异步数据库访问**: 使用 asyncpg 高效提取数据
2. **富文本生成**: 完整实现设计的自然语言模板
3. **批量处理**: 使用游标流式读取，避免内存溢出
4. **进度跟踪**: tqdm 进度条实时显示
5. **日志记录**: 双输出（文件 + 控制台）
6. **灵活配置**: 支持 6 个命令行参数
7. **错误处理**: 完善的异常捕获和日志

### 使用示例
```bash
# 小规模测试（Tampa 100 条记录）
python scripts/export_places_to_lightrag.py \
    --city Tampa \
    --limit 100 \
    --output data/tampa_places_100.jsonl \
    --min-rating 3.0 \
    --min-reviews 10

# 全量导出
python scripts/export_places_to_lightrag.py \
    --output data/places_export.jsonl
```

---

## 下一步行动

### 立即测试
1. **安装依赖**: `pip install asyncpg python-dotenv tqdm`
2. **小规模测试**: Tampa 100 条记录
3. **验证输出**:
   - JSONL 格式正确性
   - 富文本内容质量
   - 元数据完整性
   - google_types 数组正确

### 测试通过后
4. **全量导出**: 5,925 条记录
5. **进入 Task 2**: 创建数据导入脚本（import_to_lightrag.py）

---

## 测试结果

### 5. 小规模测试完成
- ✅ 安装依赖：asyncpg, python-dotenv, tqdm
- ✅ 执行测试：Tampa 100 条记录
- ✅ 测试成功：0.0 秒完成

### Bug 修复
在测试过程中发现并修复了 2 个 bug：
1. **Count 查询错误**: count_query 使用 replace() 方法不正确，已重写为独立查询
2. **游标使用错误**: asyncpg 不支持 `async for cursor`，已改为使用 `fetch()` 方法

### 测试结果统计
```
总记录数: 100
输出文件: data/tampa_places_100.jsonl
文件大小: 60.8 KB
平均文本长度: 237 字符
处理时间: 0.0 秒（极快！）
```

### 输出质量验证
✅ **JSONL 格式**: 每行一个有效的 JSON 对象
✅ **doc_id 字段**: google_place_id 正确设置
✅ **content 字段**: 富文本描述包含所有关键信息
  - 地点名称和位置
  - Google 分类（google_types）
  - 评分和评论数
  - 简介（editorial_summary）
✅ **metadata 字段**: 完整的结构化元数据
  - city, state, latitude, longitude
  - rating, reviews_count, price_level
  - google_types 数组
  - primary_category

### 示例输出
```json
{
  "doc_id": "ChIJhRo4DU_GwogRUgjhMAj-pag",
  "content": "Busch Gardens Tampa Bay 是位于 Florida Tampa 的 Amusement Parks。\nGoogle 分类：amusement_park, establishment, point_of_interest, tourist_attraction\n评分：4.40⭐（95,181 条评论）\n\n简介：Venerable theme park with thrill rides, African animals, live entertainment & kiddie attractions.",
  "metadata": {
    "city": "Tampa",
    "rating": 4.4,
    "reviews_count": 95181,
    "google_types": ["amusement_park", "establishment", "point_of_interest", "tourist_attraction"],
    "primary_category": "Amusement Parks"
  }
}
```

---

## 总结

**Step 1 完成！✅**
- 设计文档完成
- 代码实现完成
- 测试成功通过
- 输出质量验证通过

**准备进入下一阶段！**
