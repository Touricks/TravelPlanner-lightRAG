#!/usr/bin/env python3
"""
数据提取脚本：从 PostgreSQL Places 表导出数据为 LightRAG 可用的 JSONL 格式

功能：
- 异步连接 PostgreSQL 数据库
- 批量提取 Places 表数据
- 生成富文本描述
- 输出 JSONL 格式文件
- 支持筛选和限制条件

使用示例：
    python scripts/export_places_to_lightrag.py --city Tampa --limit 100
"""

import asyncio
import asyncpg
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
import argparse

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
load_dotenv(PROJECT_ROOT / '.env')

# 配置日志
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'export_places.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PlacesExporter:
    """Places 数据导出器"""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str
    ):
        """
        初始化导出器

        Args:
            host: PostgreSQL 主机
            port: PostgreSQL 端口
            database: 数据库名称
            user: 用户名
            password: 密码
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.conn = None

    async def connect(self):
        """建立数据库连接"""
        try:
            self.conn = await asyncpg.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info(f"成功连接到数据库: {self.database}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    async def close(self):
        """关闭数据库连接"""
        if self.conn:
            await self.conn.close()
            logger.info("数据库连接已关闭")

    def generate_place_description(self, place: Dict) -> str:
        """
        生成地点的富文本描述

        Args:
            place: 地点数据字典

        Returns:
            富文本描述字符串
        """
        parts = []

        # 1. 基本信息
        location = f"{place['state']} {place['city']}" if place['state'] else place['city']
        primary_cat = place['primary_category'] if place['primary_category'] else "旅游景点"
        parts.append(f"{place['name']} 是位于 {location} 的 {primary_cat}。")

        # 2. Google 分类（核心关系字段）
        if place['google_types']:
            types_str = ', '.join(place['google_types'])
            parts.append(f"\nGoogle 分类：{types_str}")

        # 3. 评价信息
        if place['rating'] is not None:
            rating_text = f"评分：{place['rating']}"
            reviews_text = f"（{place['reviews_count']:,} 条评论）" if place['reviews_count'] and place['reviews_count'] > 0 else ""
            parts.append(f"\n{rating_text}{reviews_text}")

        # 4. 价格等级（转换为美元金额范围）
        if place['price_level'] is not None:
            price_ranges = {
                0: "免费或非常便宜（$10以下）",
                1: "便宜（$10-25）",
                2: "中等价位（$25-50）",
                3: "较贵（$50-100）",
                4: "昂贵（$100以上）"
            }
            price_text = price_ranges.get(place['price_level'], "价格未知")
            parts.append(f"\n价格等级：{price_text}")

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

    async def export_places(
        self,
        output_path: Path,
        city: Optional[str] = None,
        limit: Optional[int] = None,
        min_rating: float = 3.0,
        min_reviews: int = 10,
        batch_size: int = 100
    ) -> Dict:
        """
        导出 Places 数据到 JSONL 文件

        Args:
            output_path: 输出文件路径
            city: 筛选城市（可选）
            limit: 限制记录数（可选）
            min_rating: 最低评分
            min_reviews: 最低评论数
            batch_size: 批处理大小

        Returns:
            统计信息字典
        """
        # 构建查询
        query = """
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
                AND rating >= $1
                AND reviews_count >= $2
        """
        params = [min_rating, min_reviews]

        # 添加城市筛选
        if city:
            query += " AND city = $3"
            params.append(city)
            order_param_idx = 4
        else:
            order_param_idx = 3

        # 构建 count 查询获取总数
        count_query = """
            SELECT COUNT(*)
            FROM places
            WHERE
                rating IS NOT NULL
                AND rating >= $1
                AND reviews_count >= $2
        """
        if city:
            count_query += " AND city = $3"

        # 执行 count 查询（注意：不包含 limit 参数）
        count_params = params[:order_param_idx - 1] if not limit else params[:order_param_idx - 1]
        total_count = await self.conn.fetchval(count_query, *count_params)

        # 如果设置了 limit，取较小值
        if limit and total_count > limit:
            total_count = limit

        # 添加排序和限制到主查询
        query += " ORDER BY reviews_count DESC"
        if limit:
            query += f" LIMIT ${order_param_idx}"
            params.append(limit)

        logger.info(f"开始导出，预计记录数: {total_count}")

        # 准备输出文件
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 统计信息
        stats = {
            'total_records': 0,
            'total_size': 0,
            'avg_content_length': 0,
            'start_time': datetime.now()
        }

        # 批量提取和写入
        with open(output_path, 'w', encoding='utf-8') as f:
            # 执行查询获取所有记录
            records = await self.conn.fetch(query, *params)

            # 进度条
            pbar = tqdm(total=len(records), desc="导出进度", unit="条")

            for record in records:
                # 转换为字典
                place = dict(record)

                # 生成富文本
                content = self.generate_place_description(place)

                # 构建文档
                doc = {
                    'doc_id': place['google_place_id'],
                    'content': content,
                    'metadata': {
                        'city': place['city'],
                        'state': place['state'],
                        'latitude': float(place['latitude']) if place['latitude'] else None,
                        'longitude': float(place['longitude']) if place['longitude'] else None,
                        'rating': float(place['rating']) if place['rating'] else None,
                        'reviews_count': place['reviews_count'],
                        'price_level': place['price_level'],
                        'google_types': place['google_types'],
                        'primary_category': place['primary_category']
                    }
                }

                # 写入文件
                f.write(json.dumps(doc, ensure_ascii=False) + '\n')

                # 更新统计
                stats['total_records'] += 1
                stats['total_size'] += len(content)

                # 更新进度条
                pbar.update(1)

            pbar.close()

        # 计算平均值
        if stats['total_records'] > 0:
            stats['avg_content_length'] = stats['total_size'] / stats['total_records']

        stats['end_time'] = datetime.now()
        stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()

        return stats


async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='从 PostgreSQL Places 表导出数据为 LightRAG JSONL 格式'
    )
    parser.add_argument(
        '--city',
        type=str,
        default=None,
        help='筛选城市（如 Tampa）'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='限制记录数（默认：全部）'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/places_export.jsonl',
        help='输出文件路径（默认：data/places_export.jsonl）'
    )
    parser.add_argument(
        '--min-rating',
        type=float,
        default=3.0,
        help='最低评分过滤（默认：3.0）'
    )
    parser.add_argument(
        '--min-reviews',
        type=int,
        default=10,
        help='最低评论数过滤（默认：10）'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='批处理大小（默认：100）'
    )

    args = parser.parse_args()

    # 从环境变量读取数据库配置
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'travel_kg'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    # 输出配置信息
    logger.info("=" * 60)
    logger.info("数据导出配置")
    logger.info("=" * 60)
    logger.info(f"数据库: {db_config['database']}")
    logger.info(f"城市筛选: {args.city or '全部'}")
    logger.info(f"记录限制: {args.limit or '无限制'}")
    logger.info(f"最低评分: {args.min_rating}")
    logger.info(f"最低评论数: {args.min_reviews}")
    logger.info(f"输出文件: {args.output}")
    logger.info("=" * 60)

    # 创建导出器
    exporter = PlacesExporter(**db_config)

    try:
        # 连接数据库
        await exporter.connect()

        # 导出数据
        output_path = PROJECT_ROOT / args.output
        stats = await exporter.export_places(
            output_path=output_path,
            city=args.city,
            limit=args.limit,
            min_rating=args.min_rating,
            min_reviews=args.min_reviews,
            batch_size=args.batch_size
        )

        # 输出统计信息
        logger.info("=" * 60)
        logger.info("导出完成！")
        logger.info("=" * 60)
        logger.info(f"总记录数: {stats['total_records']}")
        logger.info(f"输出文件: {output_path}")

        # 计算文件大小
        file_size = output_path.stat().st_size
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"

        logger.info(f"文件大小: {size_str}")
        logger.info(f"平均文本长度: {stats['avg_content_length']:.0f} 字符")
        logger.info(f"处理时间: {stats['duration']:.1f} 秒")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"导出失败: {e}", exc_info=True)
        return 1

    finally:
        # 关闭连接
        await exporter.close()

    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
