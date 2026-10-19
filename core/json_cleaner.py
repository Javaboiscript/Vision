import json
import re
from typing import Any, Dict


def clean_json_string(raw_text: str) -> str:
    """
    Sanitize raw LLM response by stripping markdown fences, conversational text,
    and trailing commas.
    """
    text = raw_text.strip()

    # 1. Strip markdown code blocks (e.g. ```json ... ``` or ``` ... ```)
    if "```" in text:
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            text = match.group(1).strip()

    # 2. Extract outermost JSON object { ... }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]

    # 3. Clean common trailing commas before closing braces/brackets (e.g. [1, 2,] or {"a": 1,})
    text = re.sub(r",\s*([\]}])", r"\1", text)

    return text


def parse_llm_json(raw_text: str) -> Dict[str, Any]:
    """
    Parse the LLM generated string into a Python dictionary.
    Attempts multiple recovery strategies if standard json.loads fails.
    """
    cleaned = clean_json_string(raw_text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as primary_err:
        # Fallback 1: Replace unescaped newlines/tabs inside strings
        try:
            # Replace raw control characters
            fixed_text = re.sub(r"[\x00-\x1f]", lambda m: f"\\u{ord(m.group()):04x}", cleaned)
            return json.loads(fixed_text)
        except Exception:
            pass

        # Fallback 2: If everything fails, preserve raw text in a fallback dict
        raise ValueError(
            f"Failed to parse LLM response as JSON. Error: {primary_err}.\nRaw cleaned output:\n{cleaned[:500]}..."
        )


def dump_json_to_file(data: Dict[str, Any], output_path: str, indent: int = 2) -> None:
    """Save dictionary to a formatted JSON file on disk."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
