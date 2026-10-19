import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from core.document_loader import load_document_images
from core.json_cleaner import clean_json_string, parse_llm_json


class TestComponents(unittest.TestCase):
    def test_json_cleaner_with_markdown_fences(self):
        raw_response = """
        Here is the extracted invoice data:
        ```json
        {
            "document_metadata": {
                "document_type": "Tax Invoice",
                "document_number": "INV-9901"
            },
            "financial_summary": {
                "grand_total": 1250.50,
            }
        }
        ```
        Hope this helps!
        """
        data = parse_llm_json(raw_response)
        self.assertEqual(data["document_metadata"]["document_type"], "Tax Invoice")
        self.assertEqual(data["document_metadata"]["document_number"], "INV-9901")
        self.assertEqual(data["financial_summary"]["grand_total"], 1250.50)

    def test_jpg_image_loading(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_img_path = Path(tmpdir) / "test_bill.jpg"
            img = Image.new("RGB", (600, 800), color="white")
            draw = ImageDraw.Draw(img)
            draw.text((50, 50), "INVOICE # 1001", fill="black")
            draw.text((50, 100), "Total: $150.00", fill="black")
            img.save(test_img_path, format="JPEG")

            pages = load_document_images(test_img_path)
            self.assertEqual(len(pages), 1)
            page_num, data_uri = pages[0]
            self.assertEqual(page_num, 1)
            self.assertTrue(data_uri.startswith("data:image/jpeg;base64,"))


if __name__ == "__main__":
    unittest.main()
