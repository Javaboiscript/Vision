import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

try:
    from json_repair import repair_json
    HAS_JSON_REPAIR = True
except ImportError:
    HAS_JSON_REPAIR = False


def clean_json_string(raw_text: str) -> str:
    """
    Sanitize raw LLM response by stripping markdown fences, conversational text,
    trailing commas, and repairing missing commas between JSON elements.
    """
    text = raw_text.strip()

    # 1. Strip markdown code blocks (e.g. ```json ... ``` or ``` ... ```)
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            text = match.group(1).strip()

    # 2. Extract outermost JSON object { ... }
    first_brace = text.find("{")
    if first_brace != -1:
        last_brace = text.rfind("}")
        if last_brace != -1 and last_brace > first_brace:
            text = text[first_brace : last_brace + 1]
        else:
            text = text[first_brace:]

    # 3. Clean common trailing commas before closing braces/brackets (e.g. [1, 2,] or {"a": 1,})
    text = re.sub(r",\s*([\]}])", r"\1", text)

    return text


def repair_json_heuristics(text: str) -> str:
    """
    Apply regex-based repairs for common LLM JSON syntax errors:
    - Missing commas between properties / objects / array elements
    - Trailing commas
    - Control characters
    - Unbalanced brackets/braces from token truncation
    """
    # 1. Insert missing commas before newline followed by a new key or object
    pattern_missing_comma = (
        r'("(?:[^"\\]|\\.)*"|\b(?:true|false|null|\d+(?:\.\d+)?)\b|[\}\]])\s*\n\s*("|\{|\d+|\[)'
    )
    repaired = re.sub(pattern_missing_comma, r"\1,\n\2", text)

    # 2. Re-clean trailing commas that might have been introduced or existed
    repaired = re.sub(r",\s*([\]}])", r"\1", repaired)

    # 3. Replace raw control characters except standard whitespace
    repaired = re.sub(
        r"[\x00-\x1f]",
        lambda m: f"\\u{ord(m.group()):04x}" if m.group() not in "\r\n\t" else m.group(),
        repaired,
    )

    # 4. Auto-balance unclosed braces / brackets if truncated
    open_curly = repaired.count("{") - repaired.count("}")
    open_square = repaired.count("[") - repaired.count("]")
    if open_curly > 0 or open_square > 0:
        quotes = len(re.findall(r'(?<!\\)"', repaired))
        if quotes % 2 != 0:
            repaired += '"'
        repaired += ("]" * max(0, open_square)) + ("}" * max(0, open_curly))

    return repaired


def parse_llm_json(raw_text: str) -> Dict[str, Any]:
    """
    Parse the LLM generated string into a Python dictionary.
    Attempts multiple recovery strategies if standard json.loads fails:
    1. Standard json.loads on cleaned text
    2. Heuristic regex repair (missing commas, trailing commas, bracket balancing)
    3. json-repair library (if installed)
    """
    cleaned = clean_json_string(raw_text)

    # Pass 1: Standard JSON load
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
        elif isinstance(result, list) and result:
            return {"items": result}
    except json.JSONDecodeError as primary_err:
        last_error = primary_err

    # Pass 2: Heuristic regex repair
    try:
        repaired_text = repair_json_heuristics(cleaned)
        result = json.loads(repaired_text)
        if isinstance(result, dict):
            logger.info("Successfully recovered JSON using heuristic repair rules.")
            return result
    except Exception as heuristic_err:
        last_error = heuristic_err

    # Pass 3: json-repair library
    if HAS_JSON_REPAIR:
        try:
            result = repair_json(cleaned, return_objects=True)
            if isinstance(result, dict):
                logger.info("Successfully recovered JSON using json-repair library.")
                return result
        except Exception as jr_err:
            last_error = jr_err

    # Pass 4: Failure with contextual snippet around error position
    err_context = ""
    if isinstance(last_error, json.JSONDecodeError):
        start = max(0, last_error.pos - 50)
        end = min(len(cleaned), last_error.pos + 50)
        err_context = (
            f"\nError at position {last_error.pos} (line {last_error.lineno}, col {last_error.colno}):\n"
            f"...{cleaned[start:last_error.pos]}>>>HERE>>>{cleaned[last_error.pos:end]}..."
        )

    raise ValueError(
        f"Failed to parse LLM response as JSON. Error: {last_error}.{err_context}\n"
        f"Raw preview:\n{cleaned[:400]}..."
    )


def dump_json_to_file(data: Dict[str, Any], output_path: str, indent: int = 2) -> None:
    """Save dictionary to a formatted JSON file on disk."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
