import logging
import base64
from typing import Dict, Any, Optional, Callable, Awaitable, List
from pathlib import Path

# 内部引用
from .context_extractor import MarkdownContextExtractor
from .json_utils import robust_json_parse
from .image_utils import create_image_resolver
from .markdown_utils import format_as_collapsible_block
from . import prompts

logger = logging.getLogger("another_ec.processor")

class MarkdownMultimodalProcessor:
    """
    Markdown 多模态处理器 (功能完备版)
    能够自动扫描并处理 Markdown 文档中的所有多模态元素。
    """

    def __init__(
        self, 
        vlm_func: Callable[[str, str, Optional[str]], Awaitable[str]],
        context_extractor: Optional[MarkdownContextExtractor] = None,
        caption_mode: str = "detailed"  # 支持 "detailed" 或 "concise"
    ):
        self.vlm_func = vlm_func
        self.extractor = context_extractor or MarkdownContextExtractor()
        self.caption_mode = caption_mode

    async def enrich_markdown(
        self, 
        md_content: str, 
        image_resolver: Optional[Callable[[str], bytes]] = None,
        base_dir: str | Path = "."
    ) -> str:
        """
        在 Markdown 原文的图片/表格下方直接注入 AI 解析折叠块。
        """
        if image_resolver is None:
            image_resolver = create_image_resolver(base_dir)

        tokens = self.extractor.md.parse(md_content)
        lines = md_content.splitlines()
        insertions = []

        for i, token in enumerate(tokens):
            # 1. 处理图片
            if token.type == "inline" and token.children:
                for child in token.children:
                    if child.type == "image":
                        img_url = child.attrGet("src")
                        img_bytes = image_resolver(img_url)
                        
                        if img_bytes:
                            target_line = token.map[1] if token.map else -1
                            if i > 0 and tokens[i-1].type == "paragraph_open" and tokens[i-1].map:
                                target_line = tokens[i-1].map[1]

                            if target_line != -1:
                                logger.info(f"Processing image: {img_url}")
                                res = await self.process_image(md_content, img_url, img_bytes)
                                block = format_as_collapsible_block(res)
                                if block:
                                    insertions.append((target_line, block))

            # 2. 处理表格
            if token.type == "table_open" and token.map:
                target_line = token.map[1]
                table_md = "\n".join(lines[token.map[0]:token.map[1]])
                
                logger.info(f"Processing table at line {token.map[0]}")
                res = await self.process_table(md_content, table_md, target_idx=i)
                block = format_as_collapsible_block(res)
                if block:
                    insertions.append((target_line, block))

        # 按行号倒序插入
        insertions.sort(key=lambda x: x[0], reverse=True)
        enriched_lines = list(lines)
        for line_idx, block in insertions:
            content = "\n" + block + "\n"
            if line_idx < len(enriched_lines):
                enriched_lines.insert(line_idx, content)
            else:
                enriched_lines.append(content)

        return "\n".join(enriched_lines)

    async def _analyze_element(
        self, 
        user_prompt: str, 
        system_prompt: str, 
        image_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """统一的 VLM 分析与解析逻辑"""
        image_base64 = base64.b64encode(image_bytes).decode("utf-8") if image_bytes else None
        try:
            raw_response = await self.vlm_func(user_prompt, system_prompt, image_base64)
            result = robust_json_parse(raw_response)
            return {
                "enhanced_caption": result.get("detailed_description", ""),
                "entity_info": result.get("entity_info", {}),
                "success": True
            }
        except Exception as e:
            logger.error(f"VLM analysis failed: {e}")
            return {"success": False, "error": str(e)}

    async def process_image(
        self, 
        md_content: str, 
        image_url: str, 
        image_bytes: bytes,
        entity_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """处理单张图片"""
        context = self.extractor.extract_context(md_content, target_image_url=image_url)
        
        # 选择 Prompt 模板
        is_concise = self.caption_mode == "concise"
        if context:
            tpl = prompts.VISION_PROMPT_CONCISE_WITH_CONTEXT if is_concise else prompts.VISION_PROMPT_WITH_CONTEXT
            user_prompt = tpl.format(context=context, entity_name=entity_name or Path(image_url).stem, image_path=image_url)
        else:
            tpl = prompts.VISION_PROMPT_CONCISE if is_concise else prompts.VISION_PROMPT
            user_prompt = tpl.format(entity_name=entity_name or Path(image_url).stem, image_path=image_url)

        res = await self._analyze_element(user_prompt, prompts.IMAGE_ANALYSIS_SYSTEM, image_bytes)
        res["url"] = image_url
        res["context_used"] = context
        return res

    async def process_table(
        self,
        md_content: str,
        table_markdown: str,
        entity_name: Optional[str] = None,
        target_idx: int = -1
    ) -> Dict[str, Any]:
        """处理单个表格"""
        # 尝试为表格提取语境
        context = ""
        if target_idx != -1:
            context = self.extractor.extract_context(md_content, target_idx=target_idx)

        # 目前表格暂未在 prompts.py 中区分 concise 模式，此处保持原样
        user_prompt = prompts.TABLE_PROMPT.format(
            entity_name=entity_name or "table_entity",
            table_body=table_markdown
        )
        # 如果将来 TABLE_PROMPT 支持 context，可以在此处注入
        
        return await self._analyze_element(user_prompt, prompts.TABLE_ANALYSIS_SYSTEM)
