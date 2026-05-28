"""
本地磁盘文件存储服务

职责：
  - 接收 FastAPI UploadFile，写入本地磁盘
  - 按 YYYY/MM/{uuid}.pdf 组织子目录，避免单目录文件过多
  - 提供相对路径 ↔ 绝对路径互转（供 Celery Task 使用绝对路径）
"""

import os
import uuid
from datetime import datetime, timezone

import aiofiles
from fastapi import UploadFile

from core.config import settings


class FileStorageService:
    """本地磁盘文件存储服务实现类（生产环境可无缝替换为阿里 OSS、腾讯 COS 等对象存储服务）。"""

    def _build_relative_path(self, original_filename: str) -> str:
        """
        按年/月分门别类生成文件的相对路径。
        示例：2026/05/3f8a1c2d-....pdf
        """
        now = datetime.now(timezone.utc)
        year_month = now.strftime("%Y/%m")
        ext = os.path.splitext(original_filename)[-1].lower() or ".pdf"
        filename = f"{uuid.uuid4().hex}{ext}"
        return os.path.join(year_month, filename)

    def get_absolute_path(self, relative_path: str) -> str:
        """将存放在数据库中的相对路径映射为磁盘中的绝对路径（供给 Celery 后台工作进程直接定位物理文件）。"""
        return os.path.abspath(os.path.join(settings.UPLOAD_DIR, relative_path))

    async def save(self, file: UploadFile) -> str:
        """
        以异步非阻塞方式将上传的文件块写入本地磁盘。

        返回:
            relative_path (str): 最终持久化至数据库 textbooks.file_path 字段的相对路径值。

        抛出:
            IOError: 写入过程中发生 I/O 错误时抛出。
        """
        relative_path = self._build_relative_path(file.filename or "upload.pdf")
        absolute_path = self.get_absolute_path(relative_path)

        # 确保父级年月子目录已经存在，不存在则递归创建
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

        # 流式批量分块写入，防止超大文件全量载入内存导致 OOM
        async with aiofiles.open(absolute_path, "wb") as out_file:
            while chunk := await file.read(settings.FILE_BUFFER_CHUNK_BYTES):  # 每次读取配置的数据块大小
                await out_file.write(chunk)

        return relative_path

    async def save_with_size_check(self, file: UploadFile, max_bytes: int) -> tuple[str, int]:
        """
        以异步非阻塞方式流式写入文件，同时在写入过程中累计大小。
        若实际写入字节超出 max_bytes，立即删除已写入内容并抛出 ValueError。

        返回:
            (relative_path, actual_size): 相对路径与实际字节数。

        抛出:
            ValueError: 文件实际大小超出 max_bytes 时抛出。
            IOError: 写入过程中发生 I/O 错误时抛出。
        """
        relative_path = self._build_relative_path(file.filename or "upload.pdf")
        absolute_path = self.get_absolute_path(relative_path)
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

        total_written = 0
        try:
            async with aiofiles.open(absolute_path, "wb") as out_file:
                while chunk := await file.read(settings.FILE_BUFFER_CHUNK_BYTES):
                    total_written += len(chunk)
                    if total_written > max_bytes:
                        # 超限：删除已写入的临时文件后抛出错误
                        raise ValueError(
                            f"文件大小超出限制，最大允许 {max_bytes // (1024 * 1024)} MB"
                        )
                    await out_file.write(chunk)
        except ValueError:
            # 清理残留文件
            if os.path.exists(absolute_path):
                os.remove(absolute_path)
            raise

        return relative_path, total_written

    async def delete(self, relative_path: str) -> bool:
        """
        删除本地磁盘物理文件。

        返回:
            返回 True 表示成功物理删除该文件，返回 False 表示原文件本就不存在。
        """
        absolute_path = self.get_absolute_path(relative_path)
        if os.path.exists(absolute_path):
            os.remove(absolute_path)
            return True
        return False

