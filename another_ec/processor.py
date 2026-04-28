import logging
import base64
from typing import Dict, Any, Optional, Callable, Awaitable, List
from pathlib import Path

# 内部引用
from .context_extractor import MarkdownContextExtractor
from .json_utils import robust_json_parse
from .image_utils import create_image_resolver
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
        caption_mode: str = "detailed"  # 支持 "detailed" (适合 GraphRAG) 或 "concise" (适合传统 RAG)
    ):
        self.vlm_func = vlm_func
        self.extractor = context_extractor or MarkdownContextExtractor()
        self.caption_mode = caption_mode

    async def process_document(
        self, 
        md_content: str, 
        image_resolver: Callable[[str], bytes] = None,
        base_dir: str | Path = "."
    ) -> List[Dict[str, Any]]:
        """
        自动扫描并处理 Markdown 中的所有多模态元素（图片和表格）
        
        Args:
            md_content: Markdown 全文
            image_resolver: 接收 URL 返回字节流的函数。若未提供，将使用内置支持网络/本地路径的全能解析器。
            base_dir: 若使用内置解析器，请传入 Markdown 文件所在的物理目录以确保相对路径正确。
        """
        # 如果用户没有注入自己的解析器，启用我们写的内置强力解析器
        if image_resolver is None:
            image_resolver = create_image_resolver(base_dir)

        tokens = self.extractor.md.parse(md_content)
        results = []

        for i, token in enumerate(tokens):
            # 1. 处理图片 (Inline 里的 Image)
            if token.type == "inline" and token.children:
                for child in token.children:
                    if child.type == "image":
                        img_url = child.attrGet("src")
                        img_bytes = image_resolver(img_url) if image_resolver else None
                        
                        if img_bytes:
                            res = await self.process_image_in_markdown(md_content, img_url, img_bytes)
                            results.append({"type": "image", "data": res})
                        else:
                            logger.warning(f"Could not resolve bytes for image: {img_url}")

            # 2. 处理表格 (markdown-it 的 table_open)
            if token.type == "table_open":
                # 简单处理：抓取表格的原始 Markdown（通过 token 的 map 范围）
                if token.map:
                    lines = md_content.splitlines()
                    table_md = "\n".join(lines[token.map[0]:token.map[1]])
                    res = await self.process_table_in_markdown(md_content, table_md)
                    results.append({"type": "table", "data": res})

        return results

    async def process_image_in_markdown(
        self, 
        md_content: str, 
        image_url: str, 
        image_bytes: bytes,
        entity_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """处理单张图片"""
        context = self.extractor.extract_context(md_content, image_url)
        
        # 3. 选择模板并格式化
        if self.caption_mode == "concise":
            if context:
                user_prompt = prompts.VISION_PROMPT_CONCISE_WITH_CONTEXT.format(
                    context=context,
                    entity_name=entity_name or Path(image_url).stem,
                    image_path=image_url
                )
            else:
                user_prompt = prompts.VISION_PROMPT_CONCISE.format(
                    entity_name=entity_name or Path(image_url).stem,
                    image_path=image_url
                )
        else:
            if context:
                user_prompt = prompts.VISION_PROMPT_WITH_CONTEXT.format(
                    context=context,
                    entity_name=entity_name or Path(image_url).stem,
                    image_path=image_url
                )
            else:
                user_prompt = prompts.VISION_PROMPT.format(
                    entity_name=entity_name or Path(image_url).stem,
                    image_path=image_url
                )

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        try:
            # 记录即将调用的 VLM 参数长度，确认图片是否正常传入
            logger.debug(f"Calling VLM for {image_url}. Prompt len: {len(user_prompt)}, Base64 len: {len(image_base64)}")
            
            raw_response = await self.vlm_func(
                user_prompt, 
                prompts.IMAGE_ANALYSIS_SYSTEM, 
                image_base64
            )
            
            # 关键诊断日志：打印 VLM 返回的原始字符串
            logger.info(f"[Diagnostics] VLM Raw Response for {image_url}:\n{raw_response}")
            
            if not raw_response or not raw_response.strip():
                logger.warning(f"VLM returned empty string for {image_url}")
                
            result = robust_json_parse(raw_response)
            
            # 诊断日志：如果解析结果为空，说明 robust_json_parse 失败了
            if not result:
                logger.warning(f"[Diagnostics] JSON parsing failed or returned empty dict for {image_url}. Raw string was: {raw_response[:200]}...")
            
            return {
                "url": image_url,
                "enhanced_caption": result.get("detailed_description", ""),
                "entity_info": result.get("entity_info", {}),
                "context_used": context,
                "success": True
            }
        except Exception as e:
            logger.error(f"VLM call failed: {e}")
            return {"url": image_url, "success": False, "error": str(e)}

    async def process_table_in_markdown(
        self,
        md_content: str,
        table_markdown: str,
        entity_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """处理单个表格"""
        # 注意：这里我们可以复用 extractor 逻辑来获取表格上方的标题
        # 为了保持简洁，这里演示直接调用
        user_prompt = prompts.TABLE_PROMPT.format(
            entity_name=entity_name or "table_entity",
            table_body=table_markdown
        )

        try:
            # 表格不需要图片数据，传 None
            raw_response = await self.vlm_func(user_prompt, prompts.TABLE_ANALYSIS_SYSTEM, None)
            result = robust_json_parse(raw_response)
            return {
                "enhanced_caption": result.get("detailed_description", ""),
                "entity_info": result.get("entity_info", {}),
                "success": True
            }
        except Exception as e:
            logger.error(f"Table analysis failed: {e}")
            return {"success": False, "error": str(e)}
