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
        核心算法：手术刀式提取 (升级版)。
        1. 双向回溯/探测关联标题，支持 | 分隔的路径。
        2. 以 hr 为逻辑边界，提取紧邻的正文段落。
        """
        context_parts = []
        
        # 1. 寻找关联标题 (Heading Association)
        # 搜索策略：优先向上找，若上方紧邻是边界或空，尝试向下找 1-2 行（处理头图场景）
        parent_header = ""
        search_indices = list(range(target_idx - 1, -1, -1))
        # 兜底：如果图片出现在章节的最上方，探测下方最近的标题
        search_indices.extend(list(range(target_idx + 1, min(target_idx + 4, len(tokens)))))

        for i in search_indices:
            # 遇到逻辑边界停止回溯 (仅针对向上回溯)
            if i < target_idx and tokens[i].type == "hr":
                break
                
            if tokens[i].type == "heading_open":
                if i + 1 < len(tokens) and tokens[i+1].type == "inline":
                    raw_content = tokens[i+1].content
                    # 鲁棒性：尝试解析 | 路径，若无则使用原内容
                    parts = [p.strip() for p in raw_content.split('|')]
                    if len(parts) > 1:
                        path = " > ".join(parts[:-1])
                        ctype = parts[-1]
                        parent_header = f"Location Path: {path}\nContent Type: {ctype}"
                    else:
                        parent_header = f"Section: {raw_content}"
                    break
        
        if parent_header:
            context_parts.append(parent_header)

        # 2. 寻找邻近正文 (Context Paragraphs)
        prev_paragraphs = []
        max_paras = 5
        for i in range(target_idx - 1, -1, -1):
            if tokens[i].type == "hr": # 碰到分隔符停止提取，避免跨块语境污染
                break
            if tokens[i].type == "inline" and tokens[i].content.strip():
                # 排除掉已经是标题的内容
                if i > 0 and tokens[i-1].type != "heading_open":
                    prev_paragraphs.append(tokens[i].content.strip())
                    if len(prev_paragraphs) >= max_paras:
                        break
        
        if prev_paragraphs:
            prev_paragraphs.reverse()
            context_parts.append("Background Context:\n" + "\n".join(prev_paragraphs))

        # 3. 组合并截断
        full_context = "\n".join(context_parts)
        return full_context[:self.max_tokens]
