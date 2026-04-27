import logging
from typing import List, Optional, Dict, Any

from markdown_it import MarkdownIt
from markdown_it.token import Token


logger = logging.getLogger("another_ec")

class MarkdownContextExtractor:
    """
    基于 markdown-it-py 的语境提取器。
    从 Markdown Token 流中手术刀式地提取多模态元素（图片/表格）的语境。
    """

    def __init__(self, max_tokens: int = 1000):
        self.md = MarkdownIt()
        self.max_tokens = max_tokens

    def extract_context(self, md_content: str, target_image_url: str) -> str:
        """
        根据图片 URL 提取其在 Markdown 中的语境。
        
        Args:
            md_content: 原始 Markdown 字符串
            target_image_url: 目标图片的 URL (用于定位)
            
        Returns:
            提取出的语境字符串（包含父章节标题和紧邻段落）
        """
        tokens = self.md.parse(md_content)
        target_idx = self._find_image_token_index(tokens, target_image_url)
        
        if target_idx == -1:
            logger.warning(f"Image with URL {target_image_url} not found in tokens.")
            return ""

        return self._get_surgical_context(tokens, target_idx)

    def _find_image_token_index(self, tokens: List[Token], url: str) -> int:
        """在 Token 流中寻找包含目标图片 URL 的 Token 索引"""
        for i, token in enumerate(tokens):
            # markdown-it 的图片通常在 inline token 的 children 中
            if token.type == "inline" and token.children:
                for child in token.children:
                    if child.type == "image" and child.attrGet("src") == url:
                        return i
            # 也有可能直接是 image 类型（取决于插件配置）
            if token.type == "image" and token.attrGet("src") == url:
                return i
        return -1

    def _get_surgical_context(self, tokens: List[Token], target_idx: int) -> str:
        """
        核心算法：手术刀式提取。
        1. 向上回溯最近的标题。
        2. 抓取紧邻的上文段落。
        """
        context_parts = []
        
        # 1. 寻找父章节标题 (Heading Ancestry)
        parent_header = ""
        for i in range(target_idx - 1, -1, -1):
            if tokens[i].type == "heading_open":
                # 标题内容通常在下一个 inline token 中
                if i + 1 < len(tokens) and tokens[i+1].type == "inline":
                    level = tokens[i].tag  # h1, h2...
                    parent_header = f"Section({level}): {tokens[i+1].content}"
                    break
        if parent_header:
            context_parts.append(parent_header)

        # 2. 寻找紧邻的上文段落 (Immediate Context)
        # 我们寻找距离目标最近的一个非空的 inline 文本
        prev_paragraph = ""
        for i in range(target_idx - 1, -1, -1):
            if tokens[i].type == "inline" and tokens[i].content.strip():
                # 排除掉标题（因为上面已经抓过了）
                if tokens[i-1].type != "heading_open":
                    prev_paragraph = f"Direct Context: {tokens[i].content}"
                    break
        if prev_paragraph:
            context_parts.append(prev_paragraph)

        # 3. 组合并截断
        full_context = "\n".join(context_parts)
        return full_context[:self.max_tokens]
