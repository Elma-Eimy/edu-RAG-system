import os
import re
from typing import List, Dict, Any
import pymupdf4llm
from core.config import settings, reload_settings

class DocumentParser:
    """
    基于 PyMuPDF / pymupdf4llm 的轻量级、CPU 友好的 PDF 教材解析与父子分块切片器。
    """
    def __init__(self):
        pass

    def parse_pdf(self, file_path: str) -> List[Dict]:
        """
        利用 pymupdf4llm 解析 PDF 文件并返回分页的 Markdown 字典列表。
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"未找到指定的 PDF 文件: {file_path}")
        
        # 转换为分页 Markdown 字典列表 (text, metadata)
        page_chunks = pymupdf4llm.to_markdown(file_path, page_chunks=True)
        return page_chunks

    def _process_paragraph(self, p: str, page_num: int, chunk_size: int, chunks_data: List[Dict[str, Any]]):
        p = p.strip()
        if not p:
            return
            
        # 对短文本、代码块或标题行，直接将其子分块与父分块内容设为一致
        if len(p) <= chunk_size or p.startswith("```") or p.startswith("#"):
            chunks_data.append({
                "child_content": p,
                "parent_content": p,
                "page_number": page_num
            })
            return
            
        # 长段落按照中英文常用标点符号进行句子粒度的切分
        sentences = re.split(r'(?<=[。！？\n])|(?<=[.!?])\s+', p)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        current_child = []
        current_len = 0
        
        for s in sentences:
            if current_len + len(s) > chunk_size:
                if current_child:
                    child_text = " ".join(current_child)
                    chunks_data.append({
                        "child_content": child_text,
                        "parent_content": p,
                        "page_number": page_num
                    })
                current_child = [s]
                current_len = len(s)
            else:
                current_child.append(s)
                current_len += len(s)
                
        if current_child:
            child_text = " ".join(current_child)
            chunks_data.append({
                "child_content": child_text,
                "parent_content": p,
                "page_number": page_num
            })

    def chunk_document_parent_child(self, pages: List[Dict]) -> List[Dict[str, Any]]:
        """
        父子切片算法（支持跨页保持代码块与段落状态，并记录页码）：
        1. 遍历每一页，保持代码块的完整性作为 Parent Chunks。
        2. 若段落较短或属于代码块、标题行，则子分块与父分块内容相同。
        3. 若段落较长，则进行句子粒度分割为不超长的子分块。
        """
        reload_settings()
        chunk_size = settings.TEXTBOOK_CHUNK_SIZE

        chunks_data = []
        in_code_block = False
        current_block = []
        current_block_page = 1
        
        for page_dict in pages:
            page_text = page_dict.get("text", "")
            # PyMuPDF metadata page is 0-indexed, we want 1-indexed human readable
            page_num = page_dict.get("metadata", {}).get("page", 0) + 1
            
            lines = page_text.splitlines()
            for line in lines:
                if line.strip().startswith("```"):
                    if in_code_block:
                        current_block.append(line)
                        self._process_paragraph("\n".join(current_block), current_block_page, chunk_size, chunks_data)
                        current_block = []
                        in_code_block = False
                    else:
                        if current_block:
                            self._process_paragraph("\n".join(current_block), current_block_page, chunk_size, chunks_data)
                            current_block = []
                        current_block.append(line)
                        in_code_block = True
                        current_block_page = page_num
                else:
                    if in_code_block:
                        current_block.append(line)
                    else:
                        if line.strip() == "":
                            if current_block:
                                self._process_paragraph("\n".join(current_block), current_block_page, chunk_size, chunks_data)
                                current_block = []
                        else:
                            if not current_block:
                                current_block_page = page_num
                            current_block.append(line)
                            
        if current_block:
            self._process_paragraph("\n".join(current_block), current_block_page, chunk_size, chunks_data)
            
        return chunks_data
