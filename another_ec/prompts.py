"""
Prompts for Markdown-based Multi-modal Enhanced Captioning
"""

IMAGE_ANALYSIS_SYSTEM = "You are an expert image analyst. Provide detailed, accurate descriptions and output ONLY valid JSON."
TABLE_ANALYSIS_SYSTEM = "You are an expert data analyst. Provide detailed table analysis with specific insights and output ONLY valid JSON."

# 带语境的图片分析
VISION_PROMPT_WITH_CONTEXT = """Please analyze this image in detail, considering the surrounding context. Provide a JSON response:

{{
    "detailed_description": "A direct, clear, and concise description of the image's core subject and its logical connection to the context. DO NOT write long-winded paragraphs. Keep it brief and highly informative. IMPORTANT: If the image is a screenshot of a system interface or feature demonstration containing dummy text (e.g., random articles or data used just for illustration), DO NOT summarize the dummy text. Focus ONLY on describing the UI structure, functionality shown, and elements that directly relate to the provided context.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "image",
        "summary": "concise summary of image and its relationship to context"
    }}
}}

Context from document:
{context}

Image Source: {image_path}
"""

# 基础图片分析
VISION_PROMPT = """Please analyze this image and provide a JSON response:

{{
    "detailed_description": "Detailed visual description of composition, objects, and text.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "image",
        "summary": "concise summary"
    }}
}}

Image Source: {image_path}
"""

# 表格分析提示词
TABLE_PROMPT = """Please analyze this table and provide a JSON response:

{{
    "detailed_description": "Analyze table structure, trends, and key data points.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "table",
        "summary": "concise summary of findings"
    }}
}}
"""

# ---------------------------------------------------------
# 以下为适配传统 RAG 的精简版 (Concise) 提示词
# ---------------------------------------------------------

VISION_PROMPT_CONCISE_WITH_CONTEXT = """Please briefly summarize this image, considering the surrounding context. Provide a concise JSON response:

{{
    "detailed_description": "A very brief summary (under 50 words) of the core message or data shown in the image. Focus only on the most important takeaway. IMPORTANT: Ignore dummy text in UI screenshots; focus solely on the demonstrated functionality relevant to the context.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "image",
        "summary": "1-sentence summary"
    }}
}}

Context from document:
{context}

Image Source: {image_path}
"""

VISION_PROMPT_CONCISE = """Please briefly summarize this image. Provide a concise JSON response:

{{
    "detailed_description": "A very brief summary (under 50 words) of the core content of the image.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "image",
        "summary": "1-sentence summary"
    }}
}}

Image Source: {image_path}
"""

