import json
import re
import logging

logger = logging.getLogger(__name__)

def try_parse_json(json_str: str) -> dict:
    if not json_str or not json_str.strip():
        return None
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None

def basic_json_cleanup(json_str: str) -> str:
    json_str = json_str.strip()
    json_str = json_str.replace('“', '"').replace('”', '"')
    json_str = json_str.replace("‘", "'").replace("’", "'")
    json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)
    return json_str

def progressive_quote_fix(json_str: str) -> str:
    json_str = re.sub(r'(?<!\\)\\(?=")', r"\\\\", json_str)
    def fix_string_content(match):
        content = match.group(1)
        content = re.sub(r"\\(?=[a-zA-Z])", r"\\\\", content)
        return f'"{content}"'
    json_str = re.sub(r'"([^"]*(?:\\.[^"]*)*)"', fix_string_content, json_str)
    return json_str

def extract_all_json_candidates(response: str) -> list:
    candidates = []
    cleaned_response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL | re.IGNORECASE)
    json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned_response, re.DOTALL)
    candidates.extend(json_blocks)
    brace_count = 0
    start_pos = -1
    for i, char in enumerate(cleaned_response):
        if char == "{":
            if brace_count == 0: start_pos = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start_pos != -1:
                candidates.append(cleaned_response[start_pos : i + 1])
    return candidates

def robust_json_parse(response: str) -> dict:
    candidates = extract_all_json_candidates(response)
    for json_candidate in candidates:
        result = try_parse_json(json_candidate)
        if result: return result
    for json_candidate in candidates:
        cleaned = basic_json_cleanup(json_candidate)
        result = try_parse_json(cleaned)
        if result: return result
    return {} # 简化版暂不放正则提取，保证轻量
