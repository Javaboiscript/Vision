import base64
import io
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageOps
import pypdfium2 as pdfium

from config import MAX_IMAGE_DIMENSION, IMAGE_JPEG_QUALITY

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}
ALL_SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_PDF_EXTENSIONS


def is_supported_file(file_path: Path) -> bool:
    """Check if the given file has a supported document or image extension."""
    return file_path.suffix.lower() in ALL_SUPPORTED_EXTENSIONS


def optimize_and_encode_image(image: Image.Image) -> str:
    """
    Standardize, resize, and convert a PIL Image to a base64 JPEG data URI.
    Handles EXIF orientation and downscales excessive dimensions while preserving legibility.
    """
    # 1. Correct image orientation based on camera EXIF data (crucial for phone-captured bills/receipts)
    image = ImageOps.exif_transpose(image)

    # 2. Convert to RGB (in case of RGBA, palette, or grayscale images)
    if image.mode != "RGB":
        image = image.convert("RGB")

    # 3. Resize proportionally if larger than maximum dimension
    width, height = image.size
    max_dim = max(width, height)
    if max_dim > MAX_IMAGE_DIMENSION:
        scale = MAX_IMAGE_DIMENSION / max_dim
        new_width = int(width * scale)
        new_height = int(height * scale)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # 4. Save to in-memory buffer as high-quality JPEG
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=IMAGE_JPEG_QUALITY, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded}"


def load_document_images(file_path: Path) -> List[Tuple[int, str]]:
    """
    Load a document (JPG/JPEG, PNG, WEBP, or multi-page PDF) and return a list of
    (page_number, base64_data_uri) tuples.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = path.suffix.lower()

    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        # Load single image (e.g. JPG photo of a bill or scanned receipt)
        with Image.open(path) as img:
            data_uri = optimize_and_encode_image(img)
            return [(1, data_uri)]

    elif ext in SUPPORTED_PDF_EXTENSIONS:
        # Load multi-page PDF
        pdf = pdfium.PdfDocument(path)
        pages = []
        for i, page in enumerate(pdf):
            # Render page at 200 DPI for crisp text and table line recognition
            # Scale 200/72 ≈ 2.77
            scale = 200 / 72
            pil_image = page.render(scale=scale).to_pil()
            data_uri = optimize_and_encode_image(pil_image)
            pages.append((i + 1, data_uri))
        return pages

    else:
        raise ValueError(
            f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(ALL_SUPPORTED_EXTENSIONS))}"
        )
