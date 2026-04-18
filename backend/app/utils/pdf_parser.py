"""
PDF解析工具
只使用 pdfplumber（更稳定）
"""
import pdfplumber
from typing import List, Dict, Optional
from pathlib import Path
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()


class PDFParser:
    """PDF解析器"""

    def __init__(self, pdf_path: str):
        """
        初始化PDF解析器

        Args:
            pdf_path: PDF文件路径
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        logger.info(f"加载PDF: {self.pdf_path.name}")

    def parse(self, pages: Optional[str] = None) -> List[Dict]:
        """
        解析PDF，提取文本和表格

        Args:
            pages: 页码范围（如 "3-9" 或 "3,4,5"）

        Returns:
            [{"page": 1, "content": "..."}, ...]
        """
        chunks = []

        with pdfplumber.open(self.pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"PDF总页数: {total_pages}")

            # 确定要处理的页码
            page_indices = self._parse_page_range(pages, total_pages)
            logger.info(f"处理页码: {len(page_indices)} 页")

            for i in page_indices:
                page = pdf.pages[i]

                # 提取文本
                text = page.extract_text() or ""

                # 提取表格并合并到文本（使用pdfplumber的表格提取）
                try:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                if row:
                                    # 过滤None值
                                    row_text = "\t".join(
                                        [str(cell) if cell else "" for cell in row]
                                    )
                                    text += "\n" + row_text
                except Exception as e:
                    logger.warning(f"第{i + 1}页表格提取失败: {e}")

                # 过滤空页
                if len(text.strip()) < 50:
                    logger.debug(f"跳过空页: {i + 1}")
                    continue

                # 限制文本长度
                text_truncated = text[:settings.MAX_TEXT_LENGTH]

                chunks.append({
                    "page": i + 1,
                    "content": text_truncated
                })

                logger.debug(f"第{i + 1}页: {len(text_truncated)} 字符")

        logger.success(f"共解析 {len(chunks)} 个有效页面")
        return chunks

    def _parse_page_range(self, pages: Optional[str], total_pages: int) -> List[int]:
        """
        解析页码范围

        Examples:
            "3-9" → [2, 3, 4, 5, 6, 7, 8]  (0-indexed)
            "3,4,5" → [2, 3, 4]
            None → [0, 1, 2, ..., total_pages-1]
        """
        if not pages:
            return list(range(total_pages))

        try:
            if "-" in pages:
                # 范围格式：3-9
                start, end = map(int, pages.split("-"))
                return list(range(start - 1, min(end, total_pages)))
            else:
                # 逗号分隔：3,4,5
                page_list = [int(p.strip()) - 1 for p in pages.split(",")]
                return [p for p in page_list if 0 <= p < total_pages]
        except ValueError as e:
            logger.warning(f"页码格式错误: {pages}，处理所有页面")
            return list(range(total_pages))


# 测试代码
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python pdf_parser.py <PDF路径> [页码范围]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    pages = sys.argv[2] if len(sys.argv) > 2 else None

    parser = PDFParser(pdf_path)
    chunks = parser.parse(pages=pages)

    print(f"\n提取结果：")
    for chunk in chunks[:3]:  # 只显示前3页
        print(f"\n第{chunk['page']}页（前200字符）：")
        print(chunk['content'][:200])