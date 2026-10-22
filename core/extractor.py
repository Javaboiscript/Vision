import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

import config
from core.document_loader import load_document_images
from core.json_cleaner import dump_json_to_file, parse_llm_json
from core.prompt import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT

logger = logging.getLogger(__name__)


class VisionExtractor:
    """
    Orchestrates entity recognition and data extraction for POs and Bills
    using OpenRouter Cloud-hosted Vision Language Models (Qwen2.5-VL 7B / 72B).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
    ):
        self.api_key = api_key or config.OPENROUTER_API_KEY
        self.primary_model = model or config.DEFAULT_MODEL
        self.fallback_models = (
            fallback_models if fallback_models is not None else config.FALLBACK_MODELS
        )

        if not self.api_key:
            raise ValueError(
                "OPEN_ROUTER_API_KEY or OPENROUTER_API_KEY not found! "
                "Please add OPEN_ROUTER_API_KEY to your .env file."
            )

    def extract_from_file(
        self,
        file_path: Path,
        output_dir: Optional[Path] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Load a document (JPG/JPEG, PNG, or multi-page PDF), send page images to
        Qwen2.5-VL via OpenRouter, parse the schema-free JSON, and dump to disk.
        """
        file_path = Path(file_path).resolve()
        logger.info(f"Processing document: {file_path.name}")

        # 1. Load and prepare images (supports JPG photos of bills, PNG, multi-page PDFs)
        page_images = load_document_images(file_path)
        logger.info(f"Loaded {len(page_images)} page(s) from {file_path.name}")

        # 2. Build multimodal user content
        user_content: List[Dict[str, Any]] = []

        # Add all page images in sequential order
        for page_num, data_uri in page_images:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": data_uri},
                }
            )

        # Add the extraction instruction
        page_note = (
            f" Note: This document has {len(page_images)} page(s). Extract all entities and line items across all pages."
            if len(page_images) > 1
            else ""
        )
        user_content.append({"type": "text", "text": EXTRACTION_USER_PROMPT + page_note})

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        # 3. Call OpenRouter API with fallback handling
        candidate_models = [self.primary_model] + [
            m for m in self.fallback_models if m != self.primary_model
        ]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Javaboiscript/Vision",
            "X-Title": "Vision Spectrum PO & Bill Extractor",
        }

        last_error = None
        parsed_data = None

        for model_name in candidate_models:
            logger.info(f"Attempting extraction using model: {model_name}")
            payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }

            try:
                response = requests.post(
                    config.OPENROUTER_URL,
                    headers=headers,
                    json=payload,
                    timeout=180,
                )

                if response.status_code == 200:
                    resp_json = response.json()
                    choices = resp_json.get("choices", [])
                    if choices:
                        raw_text = choices[0].get("message", {}).get("content", "")
                        logger.info(f"Successfully received response from {model_name}")
                        try:
                            parsed_data = parse_llm_json(raw_text)
                            break
                        except Exception as parse_err:
                            logger.warning(
                                f"Model '{model_name}' produced unparseable JSON: {parse_err}. Trying fallback..."
                            )
                            last_error = parse_err
                            continue
                    else:
                        raise ValueError(f"No choices returned by {model_name}: {resp_json}")
                else:
                    err_msg = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"Error from {model_name}: {err_msg}")
                    last_error = err_msg

            except Exception as e:
                logger.warning(f"Exception calling model '{model_name}': {e}")
                last_error = e
                continue

        if parsed_data is None:
            raise RuntimeError(
                f"Failed to extract document '{file_path.name}'. Last error: {last_error}"
            )

        # Inject source file metadata
        if isinstance(parsed_data, dict):
            parsed_data["_source_file"] = {
                "filename": file_path.name,
                "pages": len(page_images),
            }

        # 5. Save JSON to disk if output directory specified
        if output_dir:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            output_file = out_dir / f"{file_path.stem}_extracted.json"
            dump_json_to_file(parsed_data, str(output_file))
            logger.info(f"Saved extracted JSON to: {output_file}")

        return parsed_data
