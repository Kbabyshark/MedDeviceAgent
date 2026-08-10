"""
文档解析器 — 支持 PDF / Word / Markdown / 纯文本。

PDF 解析: MinerU CLI (pipeline 后端，CLI 自管临时 API 生命周期)
"""

from __future__ import annotations

import re
import tempfile
from collections import Counter
from pathlib import Path

from app.core.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_MIME_TYPES = {
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
}


class ParseResult:
    """文档解析结果。"""

    def __init__(
        self,
        text: str,
        page_count: int = 0,
        metadata: dict | None = None,
    ) -> None:
        self.text = text
        self.page_count = page_count
        self.metadata = metadata or {}


class DocumentParser:
    """文档解析器。"""

    async def parse(
        self,
        content: bytes,
        filename: str = "",
        mime_type: str = "",
    ) -> ParseResult:
        suffix = Path(filename).suffix.lower() if filename else ""
        mime = mime_type or self._guess_mime(filename)

        if suffix == ".pdf" or "pdf" in mime:
            return await self._parse_pdf(content, filename)
        if suffix == ".docx" or "docx" in mime:
            return await self._parse_docx(content, filename)
        if suffix in (".md", ".txt", ".csv", ".yaml", ".yml"):
            return self._parse_text(content, filename)
        try:
            return self._parse_text(content, filename)
        except UnicodeDecodeError:
            logger.warning("parser_unsupported_format", filename=filename)
            return ParseResult(text="", metadata={"error": "不支持的文件格式"})

    def _guess_mime(self, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        return {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".csv": "text/csv",
        }.get(suffix, "application/octet-stream")

    # ================================================================
    # PDF — MinerU CLI (pipeline 后端)
    # ================================================================

    async def _parse_pdf(self, content: bytes, filename: str) -> ParseResult:
        pdf_path = None
        _tmp_dir = Path(__file__).resolve().parent.parent.parent / "temp"
        _tmp_dir.mkdir(exist_ok=True)
        try:
            import time as _time
            stem = re.sub(r'[\\/:*?"<>|]', '_', Path(filename).stem)[:80]
            pdf_path = str(_tmp_dir / f"{stem}_{int(_time.time() * 1000)}.pdf")
            with open(pdf_path, "wb") as f:
                f.write(content)

            text = await self._run_mineru_api(pdf_path, filename)
            page_count = text.count("[Page ") or 1
            return ParseResult(text=text, page_count=page_count,
                               metadata={"format": "pdf", "filename": filename, "parser": "mineru-pipeline"})
        finally:
            pass  # PDF 和 debug md 保留在项目 temp 目录

    async def _run_mineru_api(self, pdf_path: str, filename: str) -> str:
        """调用常驻 MinerU API (端口 5566) pipeline 后端解析 PDF。"""
        import aiohttp
        pdf_name = Path(pdf_path).name
        api_base = "http://127.0.0.1:5566"
        logger.info("mineru_api_parse", pdf=pdf_name)

        async with aiohttp.ClientSession() as session:
            with open(pdf_path, "rb") as fh:
                form = aiohttp.FormData()
                form.add_field("files", fh, filename=pdf_name, content_type="application/pdf")
                form.add_field("backend", "pipeline")
                form.add_field("return_format", "md")
                async with session.post(f"{api_base}/file_parse", data=form,
                                        timeout=aiohttp.ClientTimeout(total=600)) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"MinerU API HTTP {resp.status}: {text[:300]}")
                    data = await resp.json()

            # 提取 markdown
            md_text = ""
            results = data.get("results", {})
            for val in results.values():
                if isinstance(val, dict):
                    md_text = val.get("md_content", "")
                    if md_text:
                        break
            if not md_text:
                result_url = data.get("result_url", "")
                if result_url:
                    url = result_url if result_url.startswith("http") else f"{api_base}{result_url}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r2:
                        if r2.status == 200:
                            rj = await r2.json()
                            md_text = rj.get("md_content", "") or rj.get("content", "")
            if not md_text:
                raise RuntimeError("MinerU API 返回空结果")

            text = _clean_mineru_output(md_text)
            # 保存原始和清洗后的 md 到本地调试用
            _raw_path = Path(pdf_path).with_suffix(".mineru_raw.md")
            _clean_path = Path(pdf_path).with_suffix(".mineru_clean.md")
            _raw_path.write_text(md_text, encoding="utf-8")
            _clean_path.write_text(text, encoding="utf-8")
            logger.info("mineru_debug_saved", raw=str(_raw_path), clean=str(_clean_path))
            text = _inject_page_markers(pdf_path, text)
            logger.info("mineru_api_done", filename=filename, chars=len(text))
            return text

    # ================================================================
    # Word
    # ================================================================

    async def _parse_docx(self, content: bytes, filename: str) -> ParseResult:
        try:
            import io, docx
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs)
            return ParseResult(text=text, metadata={"format": "docx", "filename": filename})
        except ImportError:
            return ParseResult(text="[Word 解析待安装 python-docx]",
                               metadata={"format": "docx", "filename": filename})
        except Exception as e:
            logger.error("parser_docx_error", filename=filename, error=str(e))
            raise

    # ================================================================
    # 纯文本
    # ================================================================

    def _parse_text(self, content: bytes, filename: str) -> ParseResult:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("gbk", errors="ignore")
        return ParseResult(text=text, page_count=1,
                           metadata={"format": "text", "filename": filename})


# ================================================================
# 工具函数
# ================================================================

def _clean_mineru_output(text: str) -> str:
    """清洗 MinerU 输出：去除页眉页脚、目录行、高频重复行。"""
    lines = text.split("\n")

    # 1. 目录块检测与删除：
    #    找到"目录"标题 → 进入目录模式 → 连续匹配目录行 → 直到正文出现 → 整块删除
    _toc_heading = re.compile(r"(目录|目次|Contents|Table of Contents|CONTENT)")
    _toc_patterns = [
        re.compile(r) for r in [
            # 点线+可选页码
            r"\.{2,}\s*\d*\s*$",                                       # "..........17"
            r"\.{3,}|…{2,}",                                          # "..." 或 "……"
            # 编号 + 标题 + 点线 + 可选页码
            r"^\s*\d+(\.\d+)*\s+.*?((\.{1,}\s*\d*)|(\s+\d+))?\s*$",  # "1 试验.." / "2.1 描述. 4"
            r"^\d+(\s*\.\s*\d+)*\s+.{2,30}\.{2,}\s*\d*\s*$",          # "4. 1 光学..17"
            r"^\d+(\s*\.\s*\d+)*\s+.{2,30}\.{1,2}\s*\d{0,2}\s*$",     # "4.1.1 试验.17"
            r"^\d+\s+.{2,30}\.{2,}\s*\d*\s*$",                        # "1 试验结果.."
            r"^\d+(\.\d+)*\s+.+\s+\d+\s*$",                            # "1 产品介绍 5"
            r"^.*\.{2,}\s*\d+\s*$",                                    # "产品介绍........1"
            # 中文章节
            r"^第[一二三四五六七八九十百千\d]+章.*\d*\s*$",     

                                # "第一章 概述 1"
            r"^\s*(第\s*[一二三四五六七八九十\d]+\s*[章节篇])\s*$",       # "第一章"
            # 英文/罗马目录
            r"^[IVX]+[\.\s].*\d+\s*$",                                 # "I. Intro 1"
            r"^[A-Z][a-z]*\s+\d+\s*$",      




                                                               # "Chapter 1"
        ]
    ]

    def _is_toc_line(s: str) -> bool:
        return any(p.search(s) for p in _toc_patterns)

    cleaned = []
    in_toc = False
    toc_buf = []

    for line in lines:
        s = line.strip()

        # 检测目录标题 → 进入目录模式
        if not in_toc and _toc_heading.search(s):
            in_toc = True
            toc_buf = [line]
            continue

        if in_toc:
            # 空行或 markdown 标题 → 可能还在目录区域
            if not s or s.startswith("#"):
                toc_buf.append(line)
                continue
            # 匹配目录行 → 继续收集
            if _is_toc_line(s):
                toc_buf.append(line)
                continue
            # 不匹配目录格式 → 正文开始，目录块结束
            # 目录块至少要有 3 行目录格式才判定有效
            toc_format_lines = sum(1 for l in toc_buf if _is_toc_line(l.strip()))
            if toc_format_lines >= 3:
                # 删除整个目录块（不加入 cleaned）
                pass
            else:
                cleaned.extend(toc_buf)
            toc_buf = []
            in_toc = False
            cleaned.append(line)
            continue

        cleaned.append(line)

    # 文件末尾还在目录模式 → 同样处理
    if in_toc:
        toc_format_lines = sum(1 for l in toc_buf if _is_toc_line(l.strip()))
        if toc_format_lines < 3:
            cleaned.extend(toc_buf)

    lines = cleaned

    # 2. 统计行频次，去除出现 >80% 的重复行（页眉页脚特征）
    if len(lines) > 5:
        stripped = [l.strip() for l in lines]
        threshold = max(3, int(len(lines) * 0.8))
        counts = Counter(stripped)
        frequent = {k for k, v in counts.items() if v >= threshold and len(k) > 0}
        lines = [l for l in lines if l.strip() not in frequent]

    # 3. 去除常见页眉页脚模式
    footer_patterns = [
        re.compile(r"^\s*\d+\s*$"),                          # 纯页码
        re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),               # 页码/总页数
        re.compile(r"^[©®™]\s*\d{4}"),                       # 版权信息
        re.compile(r"https?://"),                            # URL
        re.compile(r"^\s*(第\s*[一二三四五六七八九十\d]+\s*[章节篇])\s*$"),  # 章节目录标题
    ]
    lines = [l for l in lines if not any(p.search(l) for p in footer_patterns)]

    # 4. 合并多余空行
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _inject_page_markers(pdf_path: str, content: str) -> str:
    """用 pdfplumber 对齐后注入 [Page N] 标记。"""
    try:
        import pdfplumber

        markers: list[tuple[int, str]] = []
        with pdfplumber.open(pdf_path) as pdf:
            prev_end = 0
            for i, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if not page_text:
                    continue
                anchor = re.sub(r"\s+", "", page_text)[:80]
                if len(anchor) < 10:
                    continue
                clean_content = re.sub(r"\s+", "", content)
                pos = clean_content.find(anchor, prev_end)
                if pos >= 0:
                    orig_pos = _map_clean_to_original(content, pos)
                    markers.append((orig_pos, f"[Page {i}]"))
                    prev_end = pos + len(anchor)

        markers.sort(reverse=True)
        for pos, marker in markers:
            content = content[:pos] + marker + " " + content[pos:]
    except Exception:
        pass
    return content


def _map_clean_to_original(original: str, clean_pos: int) -> int:
    count = 0
    for i, ch in enumerate(original):
        if not ch.isspace():
            if count == clean_pos:
                return i
            count += 1
    return min(clean_pos, len(original))
