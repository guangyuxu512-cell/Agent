# app/图引擎/知识检索.py
# Step 5: RAGFlow 知识库检索
# 设计原则：有则增强，无则不影响

import logging
import httpx
from app.配置 import 环境变量
from app.常量 import RAGFLOW_TIMEOUT, RAGFLOW_DEFAULT_TOP_K

logger = logging.getLogger(__name__)


async def 检索知识库(问题: str, top_k: int = RAGFLOW_DEFAULT_TOP_K) -> str:
    """
    调用 RAGFlow 检索 API，返回格式化的检索结果文本。

    - 如果 RAGFlow 未配置（API Key 或 Dataset IDs 为空），返回空字符串
    - 如果检索失败（网络错误、API 错误），返回空字符串，不影响正常对话
    - 只有检索成功且有结果时，才返回格式化文本
    """
    # ===== 1. 检查配置 =====
    base_url = 环境变量.RAGFLOW_BASE_URL
    api_key = 环境变量.RAGFLOW_API_KEY
    dataset_ids = 环境变量.RAGFLOW_DATASET_IDS

    if not api_key or not dataset_ids:
        return ""

    # 解析 dataset_ids（逗号分隔）
    id_list = [did.strip() for did in dataset_ids.split(",") if did.strip()]
    if not id_list:
        return ""

    # ===== 2. 调用 RAGFlow 检索 API =====
    url = f"{base_url}/api/v1/retrieval"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "question": 问题,
        "dataset_ids": id_list,
        "top_k": top_k,
    }

    try:
        async with httpx.AsyncClient(timeout=RAGFLOW_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code != 200:
                logger.warning("[知识检索] RAGFlow API 返回 %d: %s", resp.status_code, resp.text[:200])
                return ""

            data = resp.json()

            # RAGFlow 响应格式：
            # { "code": 0, "data": { "chunks": [...], "doc_aggs": [...] } }
            if data.get("code") != 0:
                logger.warning("[知识检索] RAGFlow 错误: %s", data.get('message', '未知错误'))
                return ""

            chunks = data.get("data", {}).get("chunks", [])
            if not chunks:
                return ""

            # ===== 3. 格式化结果 =====
            结果片段 = []
            for i, chunk in enumerate(chunks, 1):
                内容 = chunk.get("content", "").strip()
                文档名 = chunk.get("document_name", "")
                相似度 = chunk.get("similarity", 0)

                if not 内容:
                    continue

                片段 = f"[片段{i}]"
                if 文档名:
                    片段 += f"（来源：{文档名}，相关度：{相似度:.2f}）"
                片段 += f"\n{内容}"
                结果片段.append(片段)

            if not 结果片段:
                return ""

            return "\n\n".join(结果片段)

    except httpx.TimeoutException:
        logger.warning("[知识检索] RAGFlow 请求超时（15秒）")
        return ""
    except Exception as e:
        logger.warning("[知识检索] RAGFlow 请求异常: %s", e)
        return ""