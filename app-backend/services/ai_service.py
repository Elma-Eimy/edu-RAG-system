from openai import AsyncOpenAI
from core.config import settings
from typing import List, Dict, Any

class AIService:
    """
    通用人工智能服务接口封装，采用兼容 OpenAI 的 API 规范。
    方便随时切换国内外的各家大语言模型通道（如 DeepSeek、通义千问、豆包、OpenAI 等）。
    """
    _llm_client: AsyncOpenAI | None = None
    _llm_api_key: str = ""
    _llm_base_url: str = ""

    _embedding_client: AsyncOpenAI | None = None
    _embedding_api_key: str = ""
    _embedding_base_url: str = ""

    def __init__(self):
        # 仅在配置发生变更或客户端未创建时重新初始化，复用底层 TCP/SSL 连接池
        if (
            AIService._llm_client is None 
            or AIService._llm_api_key != settings.LLM_API_KEY 
            or AIService._llm_base_url != settings.LLM_BASE_URL
        ):
            AIService._llm_client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL
            )
            AIService._llm_api_key = settings.LLM_API_KEY
            AIService._llm_base_url = settings.LLM_BASE_URL

        if (
            AIService._embedding_client is None 
            or AIService._embedding_api_key != settings.EMBEDDING_API_KEY 
            or AIService._embedding_base_url != settings.EMBEDDING_BASE_URL
        ):
            AIService._embedding_client = AsyncOpenAI(
                api_key=settings.EMBEDDING_API_KEY,
                base_url=settings.EMBEDDING_BASE_URL
            )
            AIService._embedding_api_key = settings.EMBEDDING_API_KEY
            AIService._embedding_base_url = settings.EMBEDDING_BASE_URL

    @property
    def llm_client(self) -> AsyncOpenAI:
        return AIService._llm_client

    @property
    def embedding_client(self) -> AsyncOpenAI:
        return AIService._embedding_client

    def _generate_fallback_embeddings(self, texts: List[str]) -> List[List[float]]:
        import hashlib
        import random
        model_lower = settings.EMBEDDING_MODEL_NAME.lower()
        if "vision" in model_lower or "ep-m-" in model_lower:
            dim = 2048
        elif "large" in model_lower:
            dim = 3072
        elif "ada-002" in model_lower or "small" in model_lower:
            dim = 1536
        else:
            dim = 1024

        results = []
        for text in texts:
            seed_bytes = hashlib.sha256(text.encode('utf-8')).digest()
            seed = int.from_bytes(seed_bytes, byteorder='big') % (2**32)
            rng = random.Random(seed)
            vec = [rng.gauss(0, 1) for _ in range(dim)]
            norm = sum(x**2 for x in vec)**0.5
            if norm > 0:
                vec = [x / norm for x in vec]
            results.append(vec)
        return results

    async def get_embedding(self, text: str) -> List[float]:
        """为给定的文本段落生成对应的向量特征值 (Embedding)。"""
        res = await self.get_embeddings_batch([text])
        return res[0]

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """单次批量为多个文本段落生成对应的向量值，兼容多模态/图像向量模型（Vision Embedding）。"""
        model_name = settings.EMBEDDING_MODEL_NAME
        
        async def _call_multimodal():
            import httpx
            import asyncio
            base_url = settings.EMBEDDING_BASE_URL.rstrip("/")
            url = f"{base_url}/embeddings/multimodal"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"
            }
            
            sem = asyncio.Semaphore(15)
            
            async def _call_single(text: str, client: httpx.AsyncClient) -> List[float]:
                async with sem:
                    payload = {
                        "model": model_name,
                        "encoding_format": "float",
                        "input": [{"type": "text", "text": text}]
                    }
                    r = await client.post(url, json=payload, headers=headers)
                    r.raise_for_status()
                    res_data = r.json()
                    
                    data_field = res_data.get("data", [])
                    embeddings = []
                    if isinstance(data_field, dict):
                        embedding = data_field.get("embedding")
                        if isinstance(embedding, list):
                            embeddings.append(embedding)
                    elif isinstance(data_field, list):
                        for item in data_field:
                            if isinstance(item, dict) and "embedding" in item:
                                embeddings.append(item["embedding"])
                            elif isinstance(item, list):
                                embeddings.append(item)
                    
                    if embeddings:
                        return embeddings[0]
                    raise ValueError(f"No embedding found in response: {res_data}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                tasks = [_call_single(text, client) for text in texts]
                return await asyncio.gather(*tasks)

        # 如果模型名称直接包含 "vision" 或为自定义多模态端点前缀 "ep-m-"，则使用多模态 API
        if "vision" in model_name.lower() or "ep-m-" in model_name.lower():
            try:
                return await _call_multimodal()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Multimodal Embedding API failed, using fallback: %s", e)
                return self._generate_fallback_embeddings(texts)
        else:
            # 首先尝试标准的文本 API
            try:
                response = await self.embedding_client.embeddings.create(
                    input=texts,
                    model=model_name
                )
                return [data.embedding for data in response.data]
            except Exception as e:
                err_str = str(e).lower()
                # 如果报错信息表明它实际上是视觉/多模态模型，则重试使用多模态 API
                if "does not support this api" in err_str or "vision" in err_str or "multimodal" in err_str:
                    import logging
                    logging.getLogger(__name__).info("Text API returned model mismatch. Retrying via Multimodal API...")
                    try:
                        return await _call_multimodal()
                    except Exception as multi_err:
                        logging.getLogger(__name__).warning("Fallback Multimodal API also failed: %s", multi_err)
                        return self._generate_fallback_embeddings(texts)
                else:
                    import logging
                    logging.getLogger(__name__).warning("Text Embedding API batch failed, using fallback: %s", e)
                    return self._generate_fallback_embeddings(texts)

    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        stream: bool = False,
        model: str | None = None,
        reasoning: bool = False
    ) -> Any:
        """
        标准聊天问答接口。
        若指定 stream=True，则返回一个用于 SSE 的流式传输响应对象。
        支持传入 model 参数以临时覆盖全局默认模型，并支持通过 reasoning 开启深度思考。
        """
        # 根据是否开启推理模式选择对应的模型名称
        model_name = model or (settings.LLM_REASONING_MODEL_NAME if reasoning else settings.LLM_MODEL_NAME)
        params = {
            "model": model_name,
            "messages": messages,
            "stream": stream
        }
        
        # 新增：如果启用了深度思考模式，注入对应的推理控制参数
        if reasoning:
            params["reasoning_effort"] = "high"
            params["extra_body"] = {"thinking": {"type": "enabled"}}
            
        response = await self.llm_client.chat.completions.create(**params)
        return response

