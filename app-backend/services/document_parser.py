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

    def _process_paragraph(self, p: str, page_num: int, chunk_size: int, chunks_data: List[Dict[str, Any]], headers: str = ""):
        p = p.strip()
        if not p:
            return
            
        prefix = headers + "\n" if headers else ""

        # 对短文本或代码块，直接将其子分块与父分块内容设为一致
        if len(p) <= chunk_size or p.startswith("```"):
            chunks_data.append({
                "child_content": prefix + p,
                "parent_content": prefix + p,
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
                        "child_content": prefix + child_text,
                        "parent_content": prefix + p,
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
                "child_content": prefix + child_text,
                "parent_content": prefix + p,
                "page_number": page_num
            })

    def chunk_document_parent_child(self, pages: List[Dict]) -> List[Dict[str, Any]]:
        """
        父子切片算法（支持跨页保持代码块与段落状态，并记录页码）：
        1. 遍历每一页，保持代码块的完整性作为 Parent Chunks。
        2. 若段落较短或属于代码块、标题行，则子分块与父分块内容相同。
        3. 若段落较长，则进行句子粒度分割为不超长的子分块。
        4. 优化：如果一个分块是标题行（# 开头或加粗/短行），将其作为层级标题上下文暂存，
           并自动在后续内容分块切片时，在 parent_content 和 child_content 的最前部拼接上层标题上下文。
        """
        reload_settings()
        chunk_size = settings.TEXTBOOK_CHUNK_SIZE

        chunks_data = []
        in_code_block = False
        current_block = []
        current_block_page = 1
        
        active_headers = [] # list of tuples: (level, text)

        def is_header(text: str) -> bool:
            text = text.strip()
            if not text:
                return False
            if text.startswith("#"):
                return True
            if text.startswith("```"):
                return False
            # 过滤列表项（如 * 列表，- 列表，1. 列表）
            if re.match(r'^(\*|-|\+|\d+\.)\s', text):
                return False
            if (text.startswith("**") and text.endswith("**")) or (text.startswith("***") and text.endswith("***")):
                if len(text) < 120 and not text.endswith((".", "。", "?", "？", "!", "！", ":", "：")):
                    return True
            if len(text) < 60 and not text.endswith((".", "。", "?", "？", "!", "！", ":", "：")):
                return True
            return False

        def get_header_level_and_text(text: str) -> tuple[int, str]:
            text = text.strip()
            # 检查 # 开头的 Markdown 标题
            m = re.match(r'^(#+)\s*(.*)$', text)
            if m:
                level = len(m.group(1))
                return level, text
            # 其它加粗或短标题默认归为 level 4 (叶子节点级别)
            return 4, text

        def process_and_reset_block():
            nonlocal current_block, active_headers
            if current_block:
                block_text = "\n".join(current_block).strip()
                if not block_text:
                    current_block = []
                    return

                if is_header(block_text):
                    new_level, header_text = get_header_level_and_text(block_text)
                    # 弹出所有同级及更深子层级的已有标题，保持最新的标题路径
                    active_headers = [h for h in active_headers if h[0] < new_level]
                    active_headers.append((new_level, header_text))
                else:
                    headers_prefix = "\n".join(h[1] for h in active_headers).strip()
                    self._process_paragraph(block_text, current_block_page, chunk_size, chunks_data, headers=headers_prefix)
                
                current_block = []

        for page_dict in pages:
            page_text = page_dict.get("text", "")
            # PyMuPDF 元数据中的 page_number 直接就是从 1 开始索引的
            page_num = page_dict.get("metadata", {}).get("page_number", 1)
            
            lines = page_text.splitlines()
            for line in lines:
                if line.strip().startswith("```"):
                    if in_code_block:
                        current_block.append(line)
                        process_and_reset_block()
                        in_code_block = False
                    else:
                        process_and_reset_block()
                        current_block.append(line)
                        in_code_block = True
                        current_block_page = page_num
                else:
                    if in_code_block:
                        current_block.append(line)
                    else:
                        if line.strip() == "":
                            process_and_reset_block()
                        else:
                            if not current_block:
                                current_block_page = page_num
                            current_block.append(line)
                            
        process_and_reset_block()
        
        # 兜底：如果整个文档无任何内容块但有标题，则输出标题本身以防为空
        if not chunks_data and active_headers:
            headers_text = "\n".join(h[1] for h in active_headers).strip()
            if headers_text:
                self._process_paragraph(headers_text, current_block_page, chunk_size, chunks_data)
            
        return chunks_data
