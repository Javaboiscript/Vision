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

    def test_json_cleaner_missing_comma_recovery(self):
        # Sample with missing comma between objects (like efrapo.jpeg)
        raw_broken = """{
            "parties": {
                "buyer": {
                    "name": "EERA",
                    "contact": "Contact details"
                }
                "seller": {
                    "name": "RR"
                }
            }
        }"""
        data = parse_llm_json(raw_broken)
        self.assertEqual(data["parties"]["buyer"]["name"], "EERA")
        self.assertEqual(data["parties"]["seller"]["name"], "RR")

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

    def test_db_enrichment_mock(self):
        from unittest.mock import MagicMock
        from core.db_connector import SQLServerConnector

        connector = SQLServerConnector(connection_string="fake_conn_str")
        # Mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock row returned by masterdata.mItemMaster
        class MockRow:
            ItemNo = 101
            ItemName = "CARBON PASTE"
            ItemDescription = "Carbon Paste for Electrode"
            Code = "CP01"
            FullCode = "CP010001"
            Grade = "A"
            Size = "STD"
            UnitNo = 2

        mock_cursor.fetchone.return_value = MockRow()
        connector._connection = mock_conn

        sample_po = {
            "line_items": [
                {
                    "item_index": 1,
                    "description": "CARBON PASTE",
                    "quantity": 10.0,
                }
            ]
        }

        enriched = connector.enrich_po_data(sample_po)
        self.assertEqual(enriched["line_items"][0]["item_no"], 101)
        self.assertEqual(enriched["line_items"][0]["matched_item"]["ItemName"], "CARBON PASTE")
        self.assertEqual(enriched["_enrichment"]["matched_items_count"], 1)


if __name__ == "__main__":
    unittest.main()
