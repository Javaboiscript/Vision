import argparse
import io
import logging
import sys
from pathlib import Path

# Ensure UTF-8 output encoding on Windows terminals (handles ₹, €, £, etc.)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import DEFAULT_MODEL, DEFAULT_OUTPUT_DIR
from core.document_loader import ALL_SUPPORTED_EXTENSIONS, is_supported_file
from core.extractor import VisionExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Vision_Spectrum")


def process_single_file(extractor: VisionExtractor, file_path: Path, output_dir: Path) -> bool:
    """Process a single document file and dump JSON output."""
    try:
        result = extractor.extract_from_file(file_path=file_path, output_dir=output_dir)

        # Print quick summary
        doc_meta = result.get("document_metadata", {})
        fin_sum = result.get("financial_summary", {})
        line_items = result.get("line_items", [])

        doc_type = doc_meta.get("document_type", "Unknown Document")
        doc_no_yearly = doc_meta.get("document_no_yearly") or "N/A"
        doc_num = doc_meta.get("document_number") or doc_no_yearly
        po_num = (
            doc_meta.get("po_number")
            or doc_meta.get("po_reference_number")
            or (doc_no_yearly if "po" in str(doc_type).lower() or "purchase" in str(doc_type).lower() else "N/A")
        )
        total = fin_sum.get("grand_total") or fin_sum.get("total_amount") or "N/A"
        currency = doc_meta.get("currency", "")

        summary_text = (
            "\n" + "=" * 60 + "\n"
            f" EXTRACTED: {file_path.name}\n"
            + "=" * 60 + "\n"
            f"  • Document Type    : {doc_type}\n"
            f"  • Doc No Yearly    : {doc_no_yearly}\n"
            f"  • PO Number        : {po_num}\n"
            f"  • Document Number  : {doc_num}\n"
            f"  • Total Amount     : {currency} {total}\n"
            f"  • Line Items Count : {len(line_items) if isinstance(line_items, list) else 'N/A'}\n"
            f"  • JSON Output      : {output_dir / f'{file_path.stem}_extracted.json'}\n"
            + "=" * 60 + "\n"
        )
        sys.stdout.write(summary_text)
        sys.stdout.flush()
        return True
    except Exception as e:
        logger.error(f"Failed to process {file_path.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Vision Language Model (Qwen-VL via OpenRouter) Data Extraction for Purchase Orders & Bills"
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        type=str,
        help="Path to an input document (JPG, PNG, PDF) or a directory containing documents.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_OUTPUT_DIR),
        type=str,
        help=f"Directory to save output JSON files (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=DEFAULT_MODEL,
        type=str,
        help=f"Vision Language Model (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        type=str,
        help="OpenRouter API key (overrides OPENROUTER_API_KEY from .env).",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        logger.error(f"Input path does not exist: {input_path}")
        sys.exit(1)

    # Initialize Vision Extractor
    extractor = VisionExtractor(
        api_key=args.api_key,
        model=args.model,
    )

    if input_path.is_file():
        if not is_supported_file(input_path):
            logger.error(
                f"File format '{input_path.suffix}' is not supported. Supported: {ALL_SUPPORTED_EXTENSIONS}"
            )
            sys.exit(1)
        success = process_single_file(extractor, input_path, output_dir)
        sys.exit(0 if success else 1)

    elif input_path.is_dir():
        supported_files = [f for f in input_path.iterdir() if f.is_file() and is_supported_file(f)]
        if not supported_files:
            logger.warning(
                f"No supported documents found in {input_path}. Supported formats: {ALL_SUPPORTED_EXTENSIONS}"
            )
            sys.exit(0)

        logger.info(f"Found {len(supported_files)} document(s) to process in {input_path}")
        success_count = 0
        for f in supported_files:
            if process_single_file(extractor, f, output_dir):
                success_count += 1

        logger.info(f"Completed batch processing: {success_count}/{len(supported_files)} successful.")
        sys.exit(0 if success_count == len(supported_files) else 1)


if __name__ == "__main__":
    main()
