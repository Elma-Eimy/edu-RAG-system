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

    async def get_embedding(self, text: str) -> List[float]:
        """为给定的文本段落生成对应的向量特征值 (Embedding)。"""
        response = await self.embedding_client.embeddings.create(
            input=text,
            model=settings.EMBEDDING_MODEL_NAME
        )
        return response.data[0].embedding

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """单次批量为多个文本段落生成对应的向量值。"""
        response = await self.embedding_client.embeddings.create(
            input=texts,
            model=settings.EMBEDDING_MODEL_NAME
        )
        return [data.embedding for data in response.data]

    async def chat_completion(self, messages: List[Dict[str, str]], stream: bool = False) -> Any:
        """
        标准聊天问答接口。
        若指定 stream=True，则返回一个用于 SSE 的流式传输响应对象。
        """
        response = await self.llm_client.chat.completions.create(
            model=settings.LLM_MODEL_NAME,
            messages=messages,
            stream=stream
        )
        return response

