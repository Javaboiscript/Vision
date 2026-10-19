# Vision Spectrum: PO & Bill Data Extraction with Open-Source VLMs

Extract structured data from **Purchase Orders (POs)**, **Bills**, **Invoices**, and **Receipts** using state-of-the-art Hugging Face Open-Source Vision Language Models (**Qwen2.5-VL / Qwen2-VL**).

Dumps the extracted entities, tables, and financial figures into clean, comprehensive **JSON** without rigid schema enforcement.

---

## ✨ Features

- **Schema-Free Dynamic Extraction**: Adapts to any document layout or vendor format without throwing validation errors.
- **Multimodal Document Support**:
  - **JPG / JPEG**: Camera photos of bills and receipts, with automatic EXIF orientation correction.
  - **PNG / WEBP / TIFF**: High-resolution digital scans.
  - **Multi-page PDF**: Automatically renders and analyzes all pages in a document.
- **Deep Entity & Table Recognition**:
  - Document metadata (PO #, Invoice #, Dates, Payment terms, Currency)
  - Buyer & Seller entity information (Names, Addresses, GSTIN/VAT/Tax IDs, Contacts)
  - Full Line Item Tables (Descriptions, SKU/HSN codes, Qty, Unit Price, Taxes, Line totals)
  - Complete financial breakdown (Subtotal, Discounts, Multi-component Taxes, Grand total)
  - Remittance & Banking info (Bank name, Account number, IFSC/SWIFT/IBAN, QR details)
  - Custom & vendor-specific fields preserved in `additional_fields`
- **Cloud-Based Inference**: Powered by Hugging Face's serverless inference router (`Qwen/Qwen2.5-VL-72B-Instruct` or `Qwen/Qwen2-VL-7B-Instruct`). No huge local model weights download required.

---

## 🚀 Quick Start

### 1. Setup Virtual Environment
The virtual environment is located in `.venv`. Activate it:

**On Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```cmd
.\.venv\Scripts\activate.bat
```

### 2. Configure Hugging Face Token
Copy `.env.example` to `.env` and set your Hugging Face User Access Token:
```env
HF_TOKEN=hf_your_actual_token_here
HF_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
```
*(Get a free or pro token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens))*.

---

## 📖 Usage

### Extract a Single Document (JPG photo of a bill or PDF)
```bash
python main.py --input sample_bill.jpg --output output/
```

### Extract a Multi-Page Purchase Order PDF
```bash
python main.py --input po_1049.pdf --output output/
```

### Batch Process an Entire Directory of Documents
```bash
python main.py --input path/to/bills_folder/ --output output/
```

### Options & Flags
- `-i`, `--input`: Path to a single file (JPG, PNG, PDF) or a directory of documents.
- `-o`, `--output`: Destination directory for generated `.json` files (default: `./output`).
- `-m`, `--model`: Hugging Face VLM model name (default: `Qwen/Qwen2.5-VL-72B-Instruct`).
- `--api-key`: Hugging Face access token (overrides `.env`).

---

## 📁 Sample Output JSON Structure

```json
{
  "document_metadata": {
    "document_type": "Tax Invoice",
    "document_number": "INV-2026-0042",
    "issue_date": "2026-10-15",
    "due_date": "2026-11-15",
    "po_reference_number": "PO-9812",
    "payment_terms": "Net 30",
    "currency": "USD"
  },
  "buyer_details": {
    "name": "Acme Industrial Corp",
    "tax_id": "US-EIN-123456789",
    "address": "450 Market Street, San Francisco, CA"
  },
  "seller_details": {
    "name": "Global Components Ltd",
    "tax_id": "US-EIN-987654321",
    "address": "12 Tech Park, Austin, TX"
  },
  "line_items": [
    {
      "item_index": 1,
      "description": "Optical Sensors 4K",
      "quantity": 10,
      "unit_price": 45.0,
      "line_total": 450.0
    }
  ],
  "financial_summary": {
    "subtotal": 450.0,
    "taxes": [
      { "tax_type": "Sales Tax (8%)", "rate": 8.0, "amount": 36.0 }
    ],
    "grand_total": 486.0
  },
  "notes_and_terms": "Goods once sold are subject to manufacturer warranty.",
  "_source_file": {
    "filename": "sample_bill.jpg",
    "pages": 1
  }
}
```
