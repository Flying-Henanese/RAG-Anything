def format_as_collapsible_block(vlm_result: dict) -> str:
    """
    将 VLM 的解析结果格式化为带有 XML 标签的 Markdown 折叠块。
    专门为 LightRAG 实体提取和人类舒适阅读设计。
    """
    if not vlm_result.get("success"):
        return ""

    caption = vlm_result.get("enhanced_caption", "").strip()
    entity_info = vlm_result.get("entity_info", {})
    
    # 提取实体名称或摘要
    entities = entity_info.get("entity_name", "")
    if isinstance(entities, list):
        entities = ", ".join(entities)

    # 提取实体摘要补充信息
    summary = entity_info.get("summary", "")

    # 构建折叠块，内部包裹 <image_analysis> 标签供大模型精准抓取
    formatted_block = f"""
<details>
<summary>🤖 <b>AI 图像/表格解析</b></summary>

<image_analysis>
- **核心总结**: {caption}
- **关键实体**: {entities}
- **简短摘要**: {summary}
</image_analysis>
</details>
"""
    return formatted_block
