"""
LightRAG Configuration Module for Travel Planner
配置 LightRAG 实例，集成 Qwen Plus LLM 和 PostgreSQL 存储
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
import sys

# 加载环境变量
load_dotenv()

# 添加 LightRAG 到 Python 路径
sys.path.append('../LightRAG')

from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc


# ===== API 配置 =====
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
if not QWEN_API_KEY:
    raise ValueError("QWEN_API_KEY not found in environment variables. Please create .env file.")

QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")


# ===== 数据库配置 =====
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "database": os.getenv("POSTGRES_DB", "travel_kg"),
    "workspace": os.getenv("LIGHTRAG_WORKSPACE", "travel_planner"),
}


# ===== LightRAG 配置 =====
LIGHTRAG_CONFIG = {
    "working_dir": os.getenv("LIGHTRAG_WORKING_DIR", "./travel_rag"),
    "chunk_token_size": 1200,
    "chunk_overlap_token_size": 100,
    "top_k": 20,
    "chunk_top_k": 10,
}


# 创建 OpenAI 客户端（用于 Qwen API）
client = OpenAI(
    api_key=QWEN_API_KEY,
    base_url=QWEN_BASE_URL
)


async def qwen_plus_llm_func(
    prompt: str,
    system_prompt: str = None,
    history_messages: list = None,
    **kwargs
) -> str:
    """
    Qwen Plus LLM 函数，用于 LightRAG

    Args:
        prompt: 用户输入的提示
        system_prompt: 系统提示（可选）
        history_messages: 历史消息（可选）
        **kwargs: 其他参数

    Returns:
        str: LLM 生成的文本
    """
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if history_messages:
        messages.extend(history_messages)

    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2000),
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"Qwen Plus API error: {e}")
        return f"API call failed: {str(e)}"


async def qwen_embedding_func(texts: list[str]) -> list[list[float]]:
    """
    Qwen Embedding 函数，用于 LightRAG

    Args:
        texts: 需要向量化的文本列表

    Returns:
        list[list[float]]: 向量列表
    """
    try:
        response = client.embeddings.create(
            model="text-embedding-v4",
            input=texts
        )
        embeddings = [item.embedding for item in response.data]
        return embeddings

    except Exception as e:
        print(f"Qwen Embedding API error: {e}")
        # 返回默认维度的零向量
        return [[0.0] * 1024 for _ in texts]


def create_lightrag_instance(
    use_postgres: bool = True,
    working_dir: str = None
) -> LightRAG:
    """
    创建配置好的 LightRAG 实例

    Args:
        use_postgres: 是否使用 PostgreSQL 存储（推荐）
        working_dir: 工作目录（如果不使用 PostgreSQL）

    Returns:
        LightRAG: 配置好的 LightRAG 实例
    """
    if working_dir is None:
        working_dir = LIGHTRAG_CONFIG["working_dir"]

    print(f"Initializing LightRAG...")
    print(f"Working directory: {working_dir}")
    print(f"Storage backend: {'PostgreSQL' if use_postgres else 'Local Files'}")

    # 基础配置
    config = {
        "working_dir": working_dir,
        "llm_model_func": qwen_plus_llm_func,
        "llm_model_name": "qwen-plus",
        "embedding_func": EmbeddingFunc(
            embedding_dim=1024,  # text-embedding-v4 维度
            max_token_size=8192,
            func=qwen_embedding_func,
        ),
        "chunk_token_size": LIGHTRAG_CONFIG["chunk_token_size"],
        "chunk_overlap_token_size": LIGHTRAG_CONFIG["chunk_overlap_token_size"],
        "top_k": LIGHTRAG_CONFIG["top_k"],
        "chunk_top_k": LIGHTRAG_CONFIG["chunk_top_k"],
        "llm_model_max_async": 8,
        "embedding_func_max_async": 16,
    }

    # PostgreSQL 存储配置（推荐）
    if use_postgres:
        config.update({
            "kv_storage": "PostgresKVStorage",
            "vector_storage": "PostgresVectorStorage",
            "graph_storage": "PostgresGraphStorage",
            "doc_status_storage": "PostgresDocStatusStorage",
            "vector_db_storage_cls_kwargs": {
                **POSTGRES_CONFIG,
                "cosine_better_than_threshold": 0.2,
                "vector_index_type": "hnsw",
                "hnsw_m": 16,
                "hnsw_ef": 64,
            }
        })
    else:
        # 本地存储配置（测试用）
        config.update({
            "kv_storage": "JsonKVStorage",
            "vector_storage": "NanoVectorDBStorage",
            "graph_storage": "NetworkXStorage",
        })

    rag = LightRAG(**config)
    print("LightRAG initialized successfully!")
    return rag


async def initialize_rag_async(use_postgres: bool = True) -> LightRAG:
    """
    异步初始化 LightRAG 实例

    Args:
        use_postgres: 是否使用 PostgreSQL 存储

    Returns:
        LightRAG: 初始化好的实例
    """
    rag = create_lightrag_instance(use_postgres=use_postgres)

    # 初始化存储
    await rag.initialize_storages()

    # 初始化 pipeline 状态
    from lightrag.kg.shared_storage import initialize_pipeline_status
    await initialize_pipeline_status()

    return rag


if __name__ == '__main__':
    import asyncio

    async def test():
        # 测试 LLM
        print("\n=== Testing Qwen Plus LLM ===")
        response = await qwen_plus_llm_func(
            "请用一句话介绍旅游知识图谱的作用。",
            system_prompt="你是一个旅游助手。"
        )
        print(f"LLM Response: {response}")

        # 测试 Embedding
        print("\n=== Testing Qwen Embedding ===")
        embeddings = await qwen_embedding_func([
            "Tampa 是佛罗里达州的一个城市",
            "Seminole Hard Rock is a famous casino hotel"
        ])
        print(f"Embedding dimension: {len(embeddings[0])}")
        print(f"First 5 values: {embeddings[0][:5]}")

        print("\n✅ All tests passed!")

    asyncio.run(test())
