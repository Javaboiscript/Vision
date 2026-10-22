"""Database connector for SQL Server (SSMS) to lookup ItemNo from masterdata.mItemMaster."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pyodbc

import config

logger = logging.getLogger(__name__)


class SQLServerConnector:
    """
    Connects to Microsoft SQL Server via pyodbc and enriches extracted
    Purchase Order line items with ItemNo and metadata from masterdata.mItemMaster.
    """

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or config.SQL_SERVER_CONNECTION_STRING
        self._connection: Optional[pyodbc.Connection] = None

    def get_connection(self) -> pyodbc.Connection:
        """Get an active database connection or create a new one."""
        if not self.connection_string:
            raise ValueError(
                "SQL Server connection string is not configured! "
                "Please set SQL_SERVER_CONNECTION_STRING in your .env file."
            )

        if self._connection is None:
            logger.info("Connecting to SQL Server database...")
            self._connection = pyodbc.connect(self.connection_string, autocommit=True)
            logger.info("Successfully connected to SQL Server.")

        return self._connection

    def close(self) -> None:
        """Close the active database connection if open."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def find_item_by_description(self, raw_description: str) -> Optional[Dict[str, Any]]:
        """
        Query masterdata.mItemMaster using hardcoded SQL query with LIKE operator
        to locate the matching ItemNo and master record.
        """
        if not raw_description or not raw_description.strip():
            return None

        clean_text = raw_description.strip()

        # Hardcoded SQL query against masterdata.mItemMaster using ItemDescription LIKE ?
        sql_query_desc = """
            SELECT TOP 1 
                ItemNo, 
                ItemName, 
                ItemDescription, 
                Code, 
                FullCode, 
                Grade, 
                Size, 
                UnitNo
            FROM masterdata.mItemMaster
            WHERE ItemName LIKE ?
        """

        conn = self.get_connection()
        cursor = conn.cursor()

        # Pass 1: Direct ItemDescription LIKE %text%
        like_param = f"%{clean_text}%"
        try:
            cursor.execute(sql_query_desc, (like_param,))
            row = cursor.fetchone()
            if row:
                return {
                    "ItemNo": int(row.ItemNo),
                    "ItemName": row.ItemName,
                    "ItemDescription": row.ItemDescription,
                    "Code": row.Code,
                    "FullCode": row.FullCode,
                    "Grade": row.Grade,
                    "Size": row.Size,
                    "UnitNo": int(row.UnitNo) if row.UnitNo is not None else None,
                }
        except Exception as e:
            logger.warning(f"Error querying mItemMaster for '{clean_text}': {e}")
            return None

        # Pass 1b: If text had trailing/leading quotes, try stripped text
        stripped_text = clean_text.strip("'\"`.,;:-_ ")
        if stripped_text and stripped_text != clean_text:
            try:
                cursor.execute(sql_query_desc, (f"%{stripped_text}%",))
                row = cursor.fetchone()
                if row:
                    return {
                        "ItemNo": int(row.ItemNo),
                        "ItemName": row.ItemName,
                        "ItemDescription": row.ItemDescription,
                        "Code": row.Code,
                        "FullCode": row.FullCode,
                        "Grade": row.Grade,
                        "Size": row.Size,
                        "UnitNo": int(row.UnitNo) if row.UnitNo is not None else None,
                    }
            except Exception as e:
                logger.warning(f"Error querying mItemMaster for stripped '{stripped_text}': {e}")

        # Pass 2: Try ItemName LIKE ?
        sql_query_name = """
            SELECT TOP 1 
                ItemNo, 
                ItemName, 
                ItemDescription, 
                Code, 
                FullCode, 
                Grade, 
                Size, 
                UnitNo
            FROM masterdata.mItemMaster
            WHERE ItemName LIKE ?
        """
        try:
            cursor.execute(sql_query_name, (f"%{stripped_text or clean_text}%",))
            row = cursor.fetchone()
            if row:
                return {
                    "ItemNo": int(row.ItemNo),
                    "ItemName": row.ItemName,
                    "ItemDescription": row.ItemDescription,
                    "Code": row.Code,
                    "FullCode": row.FullCode,
                    "Grade": row.Grade,
                    "Size": row.Size,
                    "UnitNo": int(row.UnitNo) if row.UnitNo is not None else None,
                }
        except Exception:
            pass

        # Pass 3: Clean out noise prefixes ("Supply of", "Purchase of", numbers) and try significant keywords
        stop_words = {"SUPPLY", "OF", "THE", "AND", "WITH", "WITHOUT", "FOR", "NOS", "PCS", "KG", "MTR", "SET"}
        words = [
            w for w in re.findall(r"[A-Za-z0-9]{2,}", (stripped_text or clean_text).upper())
            if w not in stop_words
        ]

        if words:
            # Construct a keyword-based LIKE query using the most significant words
            keyword_phrase = "%" + "%".join(words[:3]) + "%"
            try:
                cursor.execute(sql_query_desc, (keyword_phrase,))
                row = cursor.fetchone()
                if row:
                    return {
                        "ItemNo": int(row.ItemNo),
                        "ItemName": row.ItemName,
                        "ItemDescription": row.ItemDescription,
                        "Code": row.Code,
                        "FullCode": row.FullCode,
                        "Grade": row.Grade,
                        "Size": row.Size,
                        "UnitNo": int(row.UnitNo) if row.UnitNo is not None else None,
                    }
            except Exception as e:
                logger.warning(f"Error executing keyword LIKE query: {e}")

        return None

    def find_company_by_name(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Query masterdata.mCompanyMaster by CompanyName using LIKE operator."""
        if not company_name or not company_name.strip():
            return None

        clean_name = company_name.strip().strip("'\"`")
        compact_name = clean_name.replace(" ", "")
        sql = """
            SELECT TOP 1 
                CompanyNo, CompanyCode, CompanyName, 
                Address1, Address2, Address3, 
                CityNo, StateNo, CountryNo, 
                PhoneNo, FaxNo, Email, ECCNo, GSTINNo, ITPANNo, CINNo
            FROM masterdata.mCompanyMaster
            WHERE CompanyName LIKE ? OR CompanyCode LIKE ?
               OR REPLACE(CompanyName, ' ', '') LIKE ?
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(sql, (f"%{clean_name}%", f"%{clean_name}%", f"%{compact_name}%"))
            row = cursor.fetchone()
            if row:
                return {
                    "CompanyNo": int(row.CompanyNo),
                    "CompanyCode": row.CompanyCode,
                    "CompanyName": row.CompanyName,
                    "Address1": row.Address1,
                    "Address2": row.Address2,
                    "Address3": row.Address3,
                    "CityNo": row.CityNo,
                    "StateNo": row.StateNo,
                    "CountryNo": row.CountryNo,
                    "PhoneNo": row.PhoneNo,
                    "FaxNo": row.FaxNo,
                    "Email": row.Email,
                    "ECCNo": row.ECCNo,
                    "GSTINNo": row.GSTINNo,
                    "ITPANNo": row.ITPANNo,
                    "CINNo": row.CINNo,
                }
        except Exception as e:
            logger.warning(f"Error searching mCompanyMaster for '{clean_name}': {e}")

        return None

    def find_company_by_tax_id(self, tax_id: str) -> Optional[Dict[str, Any]]:
        """Query masterdata.mCompanyMaster by GSTINNo, ECCNo, or ITPANNo."""
        if not tax_id or not tax_id.strip():
            return None

        clean_tax = tax_id.strip().strip("'\"`")
        sql = """
            SELECT TOP 1 
                CompanyNo, CompanyCode, CompanyName, 
                Address1, Address2, Address3, 
                CityNo, StateNo, CountryNo, 
                PhoneNo, FaxNo, Email, ECCNo, GSTINNo, ITPANNo, CINNo
            FROM masterdata.mCompanyMaster
            WHERE GSTINNo LIKE ? OR ECCNo LIKE ? OR ITPANNo LIKE ?
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(sql, (f"%{clean_tax}%", f"%{clean_tax}%", f"%{clean_tax}%"))
            row = cursor.fetchone()
            if row:
                return {
                    "CompanyNo": int(row.CompanyNo),
                    "CompanyCode": row.CompanyCode,
                    "CompanyName": row.CompanyName,
                    "Address1": row.Address1,
                    "Address2": row.Address2,
                    "Address3": row.Address3,
                    "CityNo": row.CityNo,
                    "StateNo": row.StateNo,
                    "CountryNo": row.CountryNo,
                    "PhoneNo": row.PhoneNo,
                    "FaxNo": row.FaxNo,
                    "Email": row.Email,
                    "ECCNo": row.ECCNo,
                    "GSTINNo": row.GSTINNo,
                    "ITPANNo": row.ITPANNo,
                    "CINNo": row.CINNo,
                }
        except Exception as e:
            logger.warning(f"Error searching mCompanyMaster for tax_id '{clean_tax}': {e}")

        return None

    def get_vendor_location_details(self, vendor_no: int) -> Optional[Dict[str, Any]]:
        """Query masterdata.mVendorLocationDetail for complete vendor location info."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT TOP 1 VendorLocationNo, Code, VendorNo, VendorName, MailingName,
                       Address1, Address2, Address3, CityNo, StateNo, CountryNo, Pincode,
                       FullAddress, PhoneNo, FaxNo, Email, WebSite, GSTINNo
                FROM masterdata.mVendorLocationDetail
                WHERE VendorNo = ?
            """, (vendor_no,))
            row = cursor.fetchone()
            if row:
                cols = [c[0] for c in cursor.description]
                return {cols[i]: (row[i].isoformat() if hasattr(row[i], "isoformat") else row[i]) for i in range(len(cols))}
        except Exception as e:
            logger.warning(f"Error querying mVendorLocationDetail for VendorNo {vendor_no}: {e}")
        return None

    def find_vendor_by_name(self, vendor_name: str) -> Optional[Dict[str, Any]]:
        """Query masterdata.mVendorCard and mVendorLocationDetail by Name, MailingName or Alias."""
        if not vendor_name or not vendor_name.strip():
            return None

        clean_name = vendor_name.strip().strip("'\"`")
        compact_name = clean_name.replace(" ", "")
        sql = """
            SELECT TOP 1 
                VendorNo, VendorTypeNo, Code, Name, 
                Alias, MailingName, VendorOfCompanyNo, 
                DocumentStatusNo, CurrencyNo
            FROM masterdata.mVendorCard
            WHERE Name LIKE ? OR MailingName LIKE ? OR Alias LIKE ?
               OR REPLACE(Name, ' ', '') LIKE ?
               OR REPLACE(MailingName, ' ', '') LIKE ?
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(sql, (f"%{clean_name}%", f"%{clean_name}%", f"%{clean_name}%", f"%{compact_name}%", f"%{compact_name}%"))
            row = cursor.fetchone()
            if row:
                v_no = int(row.VendorNo)
                loc = self.get_vendor_location_details(v_no)
                return {
                    "VendorNo": v_no,
                    "VendorTypeNo": int(row.VendorTypeNo) if row.VendorTypeNo is not None else None,
                    "Code": row.Code.strip() if row.Code else None,
                    "Name": row.Name,
                    "Alias": row.Alias,
                    "MailingName": row.MailingName,
                    "VendorOfCompanyNo": int(row.VendorOfCompanyNo) if row.VendorOfCompanyNo is not None else None,
                    "DocumentStatusNo": int(row.DocumentStatusNo) if row.DocumentStatusNo is not None else None,
                    "CurrencyNo": int(row.CurrencyNo) if row.CurrencyNo is not None else None,
                    "VendorLocationNo": loc.get("VendorLocationNo") if loc else None,
                    "GSTINNo": loc.get("GSTINNo") if loc else None,
                    "FullAddress": loc.get("FullAddress") if loc else None,
                    "Address1": loc.get("Address1") if loc else None,
                    "Address2": loc.get("Address2") if loc else None,
                    "Address3": loc.get("Address3") if loc else None,
                    "CityNo": loc.get("CityNo") if loc else None,
                    "StateNo": loc.get("StateNo") if loc else None,
                    "CountryNo": loc.get("CountryNo") if loc else None,
                    "PhoneNo": loc.get("PhoneNo") if loc else None,
                    "Email": loc.get("Email") if loc else None,
                }
        except Exception as e:
            logger.warning(f"Error searching mVendorCard for '{clean_name}': {e}")

        return None

    def find_vendor_by_tax_id(self, tax_id: str) -> Optional[Dict[str, Any]]:
        """Query masterdata.mVendorLocationDetail joined with mVendorCard by GSTINNo."""
        if not tax_id or not tax_id.strip():
            return None

        clean_tax = tax_id.strip().strip("'\"`")
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT TOP 1 l.VendorLocationNo, l.VendorNo, v.Name, v.Code, v.VendorTypeNo,
                       l.FullAddress, l.Address1, l.Address2, l.Address3, l.CityNo, l.StateNo, l.CountryNo,
                       l.PhoneNo, l.Email, l.GSTINNo
                FROM masterdata.mVendorLocationDetail l
                JOIN masterdata.mVendorCard v ON l.VendorNo = v.VendorNo
                WHERE l.GSTINNo LIKE ?
            """, (f"%{clean_tax}%",))
            row = cursor.fetchone()
            if row:
                return {
                    "VendorNo": int(row.VendorNo),
                    "VendorTypeNo": int(row.VendorTypeNo) if row.VendorTypeNo is not None else None,
                    "Code": row.Code.strip() if row.Code else None,
                    "Name": row.Name,
                    "VendorLocationNo": int(row.VendorLocationNo),
                    "FullAddress": row.FullAddress,
                    "Address1": row.Address1,
                    "Address2": row.Address2,
                    "Address3": row.Address3,
                    "CityNo": row.CityNo,
                    "StateNo": row.StateNo,
                    "CountryNo": row.CountryNo,
                    "PhoneNo": row.PhoneNo,
                    "Email": row.Email,
                    "GSTINNo": row.GSTINNo,
                }
        except Exception as e:
            logger.warning(f"Error searching mVendorLocationDetail for tax_id '{clean_tax}': {e}")

        return None


    def find_po_main(self, document_no_yearly: str) -> Optional[Dict[str, Any]]:
        """Query Purchase.POMain by DocumentNoYearly using LIKE operator."""
        if not document_no_yearly or not document_no_yearly.strip():
            return None

        clean_doc_no = document_no_yearly.strip()
        sql = """
            SELECT TOP 1 
                PONo, CompanyNo, YearNo, AmendmentNo, 
                DivisionNo, DocumentSettingNo, DocumentNoYearly, 
                DocumentDate, DocumentStatusNo, PODocumentTypeNo, 
                IndentTypeNo, POPurchaseCategoryNo, PORefDocumentTypeNo, 
                RefDocumentNo, VendorNo, VendorLocationNo, 
                VendorContactNo, ValidityDate, WayBillNo, 
                WaybillDate, ConsigneeNo, ConsigneeLocationNo, 
                FreightTypeNo, FreightRateTypeNo, FreightAmount, 
                ToLocationNo
            FROM Purchase.POMain
            WHERE DocumentNoYearly LIKE ?
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(sql, (f"%{clean_doc_no}%",))
            row = cursor.fetchone()
            if row:
                cols = [c[0] for c in cursor.description]
                res = {}
                for idx, col in enumerate(cols):
                    val = row[idx]
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    elif hasattr(val, "__float__"):
                        val = float(val)
                    res[col] = val
                return res
        except Exception as e:
            logger.warning(f"Error searching Purchase.POMain for '{clean_doc_no}': {e}")

        return None

    def get_po_item_details(self, pono: int) -> List[Dict[str, Any]]:
        """Query Purchase.PoItemDetail for a given PONo joined with masterdata.mItemMaster."""
        sql = """
            SELECT 
                d.POItemDetailNo, d.PONo, d.ItemNo, 
                i.ItemName, i.ItemDescription, 
                d.MakeNo, d.TechSpecification, 
                d.Quantity, d.UnitNo, d.Rate, 
                d.BasicAmount, d.NetAmount, d.Remark, 
                d.StatusNo, d.TechnicalGradeNo, d.ChapterHeadingNo, 
                d.CostCenterNo, d.HSNSACCodeNo
            FROM Purchase.PoItemDetail d
            LEFT JOIN masterdata.mItemMaster i ON d.ItemNo = i.ItemNo
            WHERE d.PONo = ?
            ORDER BY d.POItemDetailNo
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(sql, (pono,))
            rows = cursor.fetchall()
            cols = [c[0] for c in cursor.description]
            items = []
            for row in rows:
                item_dict = {}
                for idx, col in enumerate(cols):
                    val = row[idx]
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    elif hasattr(val, "__float__"):
                        val = float(val)
                    item_dict[col] = val
                items.append(item_dict)
            return items
        except Exception as e:
            logger.warning(f"Error querying Purchase.PoItemDetail for PONo {pono}: {e}")
            return []

    def find_grn_main(self, document_no_yearly: str) -> Optional[Dict[str, Any]]:
        """Query Inventory.GRNMain by DocumentNoYearly using LIKE operator."""
        if not document_no_yearly or not document_no_yearly.strip():
            return None

        clean_doc_no = document_no_yearly.strip()
        slash_variant = clean_doc_no.replace("/", "\\") if "/" in clean_doc_no else clean_doc_no.replace("\\", "/")

        sql = """
            SELECT TOP 1 
                GRNNo, CompanyNo, YearNo, DivisionNo, 
                DocumentSettingNo, DocumentNoYearly, DocumentDate, 
                DocumentStatusNo, GRNSourceNo, VendorLocationNo, 
                VendorBillNo, VendorBillDate, ChallanNo, ChallanDate, 
                DeptNo, ProjectNo, StatusNo, InspectionRequired, 
                Remarks, TransporterNo, DriverName, VehicleNo
            FROM Inventory.GRNMain
            WHERE DocumentNoYearly LIKE ? OR DocumentNoYearly LIKE ?
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(sql, (f"%{clean_doc_no}%", f"%{slash_variant}%"))
            row = cursor.fetchone()
            if row:
                cols = [c[0] for c in cursor.description]
                res = {}
                for idx, col in enumerate(cols):
                    val = row[idx]
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    elif hasattr(val, "__float__"):
                        val = float(val)
                    res[col] = val
                return res
        except Exception as e:
            logger.warning(f"Error searching Inventory.GRNMain for '{clean_doc_no}': {e}")

        return None

    def get_grn_item_details(self, grn_no: int) -> List[Dict[str, Any]]:
        """Query Inventory.GRNItemDetail for a given GRNNo joined with masterdata.mItemMaster."""
        sql = """
            SELECT 
                d.GRNItemDetailNo, d.GRNNo, d.POAmendmentNo, 
                d.GateEntryNo, d.ItemNo, i.ItemName, i.ItemDescription, 
                d.MakeNo, d.UnitNo, d.TechnicalSpecification, 
                d.ChallanQty, d.ReceivedQty, d.RejectedQty, 
                d.ReplaceableQty, d.AcceptedQty, d.FOCQty, 
                d.FOCRate, d.Rate, d.StockQty, d.Remarks, 
                d.BINNo, d.WareHouseNo, d.ExcessQty
            FROM Inventory.GRNItemDetail d
            LEFT JOIN masterdata.mItemMaster i ON d.ItemNo = i.ItemNo
            WHERE d.GRNNo = ?
            ORDER BY d.GRNItemDetailNo
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(sql, (grn_no,))
            rows = cursor.fetchall()
            cols = [c[0] for c in cursor.description]
            items = []
            for row in rows:
                item_dict = {}
                for idx, col in enumerate(cols):
                    val = row[idx]
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    elif hasattr(val, "__float__"):
                        val = float(val)
                    item_dict[col] = val
                items.append(item_dict)
            return items
        except Exception as e:
            logger.warning(f"Error querying Inventory.GRNItemDetail for GRNNo {grn_no}: {e}")
            return []

    def enrich_po_data(self, po_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich extracted document JSON with:
        1. Vendor details from masterdata.mVendorCard
        2. Company details from masterdata.mCompanyMaster
        3. PO details from Purchase.POMain and Purchase.PoItemDetail using DocumentNoYearly
        4. GRN details from Inventory.GRNMain and Inventory.GRNItemDetail using DocumentNoYearly
        5. Line items with ItemNo from masterdata.mItemMaster
        """
        parties = po_data.get("parties", {})
        buyer = parties.get("buyer_or_consignee", {}) if isinstance(parties, dict) else {}
        seller = parties.get("seller_or_supplier", {}) if isinstance(parties, dict) else {}

        buyer_name = buyer.get("name", "") if isinstance(buyer, dict) else ""
        seller_name = seller.get("name", "") if isinstance(seller, dict) else ""
        buyer_tax = buyer.get("tax_id", "") if isinstance(buyer, dict) else ""
        seller_tax = seller.get("tax_id", "") if isinstance(seller, dict) else ""

        doc_meta = po_data.get("document_metadata", {})
        doc_no_yearly = (
            doc_meta.get("document_no_yearly")
            or doc_meta.get("po_number")
            or doc_meta.get("document_number")
            or ""
        )

        # 1. Company Lookup
        company_record = None
        matched_company_party = None
        for party_key, name in [("seller_or_supplier", seller_name), ("buyer_or_consignee", buyer_name)]:
            if name:
                company_record = self.find_company_by_name(name)
                if company_record:
                    matched_company_party = party_key
                    logger.info(f"Matched Company: {company_record['CompanyName']} (CompanyNo: {company_record['CompanyNo']})")
                    break

        if not company_record:
            for party_key, tax in [("seller_or_supplier", seller_tax), ("buyer_or_consignee", buyer_tax)]:
                if tax:
                    company_record = self.find_company_by_tax_id(tax)
                    if company_record:
                        matched_company_party = party_key
                        logger.info(f"Matched Company by TaxID: {company_record['CompanyName']} (CompanyNo: {company_record['CompanyNo']})")
                        break

        # 2. Vendor Lookup
        vendor_record = None
        matched_vendor_party = None
        for party_key, name in [("buyer_or_consignee", buyer_name), ("seller_or_supplier", seller_name)]:
            if name:
                vendor_record = self.find_vendor_by_name(name)
                if vendor_record:
                    matched_vendor_party = party_key
                    logger.info(f"Matched Vendor: {vendor_record['Name']} (VendorNo: {vendor_record['VendorNo']})")
                    break

        if not vendor_record:
            for party_key, tax in [("buyer_or_consignee", buyer_tax), ("seller_or_supplier", seller_tax)]:
                if tax:
                    vendor_record = self.find_vendor_by_tax_id(tax)
                    if vendor_record:
                        matched_vendor_party = party_key
                        logger.info(f"Matched Vendor by TaxID: {vendor_record['Name']} (VendorNo: {vendor_record['VendorNo']})")
                        break

        # Explicitly assign database_company and database_vendor to both parties
        for p_key in ("buyer_or_consignee", "seller_or_supplier"):
            if isinstance(parties.get(p_key), dict):
                parties[p_key]["database_company"] = company_record if matched_company_party == p_key else None
                parties[p_key]["database_vendor"] = vendor_record if matched_vendor_party == p_key else None

        # Also assign at root level
        po_data["database_company"] = company_record
        po_data["database_vendor"] = vendor_record

        # 3. POMain Lookup by DocumentNoYearly
        po_main_record = None
        po_item_details_list = []
        if doc_no_yearly:
            po_main_record = self.find_po_main(doc_no_yearly)
            if po_main_record:
                pono = po_main_record.get("PONo")
                logger.info(f"Matched Purchase.POMain: PONo {pono} for DocumentNoYearly '{doc_no_yearly}'")
                po_item_details_list = self.get_po_item_details(pono)
                logger.info(f"Loaded {len(po_item_details_list)} line items from Purchase.PoItemDetail")
                if isinstance(doc_meta, dict):
                    doc_meta["database_po_main"] = po_main_record

        # 4. GRNMain Lookup by DocumentNoYearly
        grn_main_record = None
        grn_item_details_list = []
        if doc_no_yearly:
            grn_main_record = self.find_grn_main(doc_no_yearly)
            if grn_main_record:
                grn_no = grn_main_record.get("GRNNo")
                logger.info(f"Matched Inventory.GRNMain: GRNNo {grn_no} for DocumentNoYearly '{doc_no_yearly}'")
                grn_item_details_list = self.get_grn_item_details(grn_no)
                logger.info(f"Loaded {len(grn_item_details_list)} line items from Inventory.GRNItemDetail")
                if isinstance(doc_meta, dict):
                    doc_meta["database_grn_main"] = grn_main_record

        # 5. ItemMaster & Detail Lookup for line items
        line_items = po_data.get("line_items", [])
        matched_count = 0
        if isinstance(line_items, list):
            for idx, item in enumerate(line_items):
                if not isinstance(item, dict):
                    continue

                desc = (
                    item.get("description")
                    or item.get("item_name")
                    or item.get("name")
                    or item.get("item_description")
                    or ""
                )

                matched = self.find_item_by_description(str(desc))
                po_detail_match = None
                grn_detail_match = None

                # Correlate with po_item_details_list from POMain if available
                if po_item_details_list:
                    for p_item in po_item_details_list:
                        p_name = (p_item.get("ItemName") or "").upper()
                        if p_name and p_name in str(desc).upper():
                            po_detail_match = p_item
                            break
                    if not po_detail_match and idx < len(po_item_details_list):
                        po_detail_match = po_item_details_list[idx]

                    if not matched and po_detail_match and po_detail_match.get("ItemNo"):
                        matched = {
                            "ItemNo": int(po_detail_match["ItemNo"]),
                            "ItemName": po_detail_match.get("ItemName"),
                            "ItemDescription": po_detail_match.get("ItemDescription"),
                            "Code": None,
                            "FullCode": None,
                            "Grade": None,
                            "Size": None,
                            "UnitNo": int(po_detail_match["UnitNo"]) if po_detail_match.get("UnitNo") is not None else None,
                        }

                # Correlate with grn_item_details_list from GRNMain if available
                if grn_item_details_list:
                    for g_item in grn_item_details_list:
                        g_name = (g_item.get("ItemName") or "").upper()
                        if g_name and g_name in str(desc).upper():
                            grn_detail_match = g_item
                            break
                    if not grn_detail_match and idx < len(grn_item_details_list):
                        grn_detail_match = grn_item_details_list[idx]

                    if not matched and grn_detail_match and grn_detail_match.get("ItemNo"):
                        matched = {
                            "ItemNo": int(grn_detail_match["ItemNo"]),
                            "ItemName": grn_detail_match.get("ItemName"),
                            "ItemDescription": grn_detail_match.get("ItemDescription"),
                            "Code": None,
                            "FullCode": None,
                            "Grade": None,
                            "Size": None,
                            "UnitNo": int(grn_detail_match["UnitNo"]) if grn_detail_match.get("UnitNo") is not None else None,
                        }

                if matched:
                    item["item_no"] = matched["ItemNo"]
                    database_item = dict(matched)
                    if po_detail_match:
                        database_item["po_item_detail"] = {
                            "POItemDetailNo": po_detail_match.get("POItemDetailNo"),
                            "PONo": po_detail_match.get("PONo"),
                            "Quantity": po_detail_match.get("Quantity"),
                            "UnitNo": po_detail_match.get("UnitNo"),
                            "Rate": po_detail_match.get("Rate"),
                            "BasicAmount": po_detail_match.get("BasicAmount"),
                            "NetAmount": po_detail_match.get("NetAmount"),
                            "Remark": po_detail_match.get("Remark"),
                            "TechnicalGradeNo": po_detail_match.get("TechnicalGradeNo"),
                            "HSNSACCodeNo": po_detail_match.get("HSNSACCodeNo"),
                        }
                    if grn_detail_match:
                        database_item["grn_item_detail"] = {
                            "GRNItemDetailNo": grn_detail_match.get("GRNItemDetailNo"),
                            "GRNNo": grn_detail_match.get("GRNNo"),
                            "ChallanQty": grn_detail_match.get("ChallanQty"),
                            "ReceivedQty": grn_detail_match.get("ReceivedQty"),
                            "RejectedQty": grn_detail_match.get("RejectedQty"),
                            "AcceptedQty": grn_detail_match.get("AcceptedQty"),
                            "Rate": grn_detail_match.get("Rate"),
                            "UnitNo": grn_detail_match.get("UnitNo"),
                            "StockQty": grn_detail_match.get("StockQty"),
                            "Remarks": grn_detail_match.get("Remarks"),
                        }
                    item["database_item"] = database_item
                    item["matched_item"] = database_item
                    matched_count += 1
                    logger.info(
                        f"Matched line item '{desc[:40]}...' -> ItemNo: {matched['ItemNo']} ({matched.get('ItemName')})"
                    )
                else:
                    item["item_no"] = None
                    item["database_item"] = None
                    logger.info(f"No ItemNo match found in mItemMaster for: '{desc[:40]}...'")

        # Inject summary metadata
        if "_enrichment" not in po_data:
            po_data["_enrichment"] = {}
        po_data["_enrichment"]["database_lookup"] = "masterdata.mItemMaster, mVendorCard, mCompanyMaster, Purchase.POMain, Purchase.PoItemDetail, Inventory.GRNMain, Inventory.GRNItemDetail"
        po_data["_enrichment"]["matched_items_count"] = matched_count
        po_data["_enrichment"]["total_items_count"] = len(line_items) if isinstance(line_items, list) else 0
        po_data["_enrichment"]["matched_company"] = company_record["CompanyName"] if company_record else None
        po_data["_enrichment"]["matched_vendor"] = vendor_record["Name"] if vendor_record else None
        po_data["_enrichment"]["database_company"] = company_record
        po_data["_enrichment"]["database_vendor"] = vendor_record
        po_data["_enrichment"]["matched_pono"] = po_main_record["PONo"] if po_main_record else None
        po_data["_enrichment"]["matched_grn_no"] = grn_main_record["GRNNo"] if grn_main_record else None

        return po_data

    def find_vendor_location_no(self, vendor_no: int) -> Optional[int]:
        """Query masterdata.mVendorLocationDetail by VendorNo."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT TOP 1 VendorLocationNo FROM masterdata.mVendorLocationDetail WHERE VendorNo = ?",
                (vendor_no,)
            )
            row = cursor.fetchone()
            if row:
                return int(row[0])
        except Exception as e:
            logger.warning(f"Error querying mVendorLocationDetail for VendorNo {vendor_no}: {e}")
        return None

    def find_grn_for_purchase_bill(
        self,
        grn_no_str: Optional[str] = None,
        vendor_bill_no: Optional[str] = None,
        challan_no: Optional[str] = None,
        vendor_location_no: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Locate GRN from Inventory.GRNMain without touching PurchaseBillMain.
        Primary anchor is VendorBillNo (the vendor invoice number printed on the bill),
        followed by DocumentReceiptMain linking, ChallanNo, and direct GRN references.
        """
        # Priority 1: Match by VendorBillNo (Invoice Number from PDF)
        if vendor_bill_no and str(vendor_bill_no).strip():
            grn = self.find_grn_by_vendor_bill_no(str(vendor_bill_no).strip(), vendor_location_no)
            if grn:
                return grn

        # Priority 2: Direct GRN No or Yearly string if explicitly printed
        if grn_no_str and str(grn_no_str).strip():
            grn = self.find_grn_by_grn_no(str(grn_no_str).strip())
            if grn:
                return grn

        # Priority 3: Match by Delivery Challan No / Delivery Note if extracted
        if challan_no and str(challan_no).strip():
            grn = self.find_grn_by_challan_no(str(challan_no).strip(), vendor_location_no)
            if grn:
                return grn

        return None

    def find_grn_by_vendor_bill_no(
        self, vendor_bill_no: str, vendor_location_no: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Query Inventory.GRNMain matching VendorBillNo to find GRN, Challan, and receipt details.
        Also inspects Finance.DocumentReceiptReferenceDetail via DocumentReceiptMain.
        """
        if not vendor_bill_no or not vendor_bill_no.strip():
            return None

        clean_bill = vendor_bill_no.strip().strip("'\"`")
        slash_variant = clean_bill.replace("/", "\\") if "/" in clean_bill else clean_bill.replace("\\", "/")
        conn = self.get_connection()
        cursor = conn.cursor()

        # 1a. Direct exact match in Inventory.GRNMain (with VendorLocationNo if available)
        if vendor_location_no:
            try:
                cursor.execute("""
                    SELECT TOP 1 GRNNo, DocumentNoYearly, DocumentDate, ChallanNo, ChallanDate, 
                           VendorLocationNo, WarehouseNo, CompanyNo, YearNo, StatusNo 
                    FROM Inventory.GRNMain
                    WHERE (VendorBillNo = ? OR VendorBillNo = ?) AND VendorLocationNo = ?
                    ORDER BY GRNNo DESC
                """, (clean_bill, slash_variant, vendor_location_no))
                row = cursor.fetchone()
                if row:
                    cols = [c[0] for c in cursor.description]
                    return {cols[i]: (row[i].isoformat() if hasattr(row[i], "isoformat") else row[i]) for i in range(len(cols))}
            except Exception as e:
                logger.warning(f"Error querying GRNMain by VendorBillNo with location: {e}")

        # 1b. Direct exact match in Inventory.GRNMain (any location)
        try:
            cursor.execute("""
                SELECT TOP 1 GRNNo, DocumentNoYearly, DocumentDate, ChallanNo, ChallanDate, 
                       VendorLocationNo, WarehouseNo, CompanyNo, YearNo, StatusNo 
                FROM Inventory.GRNMain
                WHERE VendorBillNo = ? OR VendorBillNo = ?
                ORDER BY GRNNo DESC
            """, (clean_bill, slash_variant))
            row = cursor.fetchone()
            if row:
                cols = [c[0] for c in cursor.description]
                return {cols[i]: (row[i].isoformat() if hasattr(row[i], "isoformat") else row[i]) for i in range(len(cols))}
        except Exception as e:
            logger.warning(f"Error querying GRNMain by exact VendorBillNo: {e}")

        # 1c. DocumentReceiptReferenceDetail linking (Standard in SpectrumERP)
        try:
            cursor.execute("""
                SELECT TOP 1 r.GRNNo, m.DocumentReceiptNo
                FROM Finance.DocumentReceiptMain m
                JOIN Finance.DocumentReceiptReferenceDetail r ON m.DocumentReceiptNo = r.DocumentReceiptNo
                WHERE m.PartyBIllNo = ? OR m.PartyBIllNo = ? OR m.PartyBIllNo LIKE ?
                ORDER BY m.DocumentReceiptNo DESC
            """, (clean_bill, slash_variant, f"%{clean_bill}%"))
            receipt_row = cursor.fetchone()
            if receipt_row and receipt_row[0]:
                grn_id = receipt_row[0]
                cursor.execute("""
                    SELECT TOP 1 GRNNo, DocumentNoYearly, DocumentDate, ChallanNo, ChallanDate, 
                           VendorLocationNo, WarehouseNo, CompanyNo, YearNo, StatusNo 
                    FROM Inventory.GRNMain WHERE GRNNo = ?
                """, (grn_id,))
                row = cursor.fetchone()
                if row:
                    cols = [c[0] for c in cursor.description]
                    res = {cols[i]: (row[i].isoformat() if hasattr(row[i], "isoformat") else row[i]) for i in range(len(cols))}
                    res["DocumentReceiptNo"] = int(receipt_row[1])
                    return res
        except Exception as e:
            logger.warning(f"Error querying DocumentReceiptReferenceDetail for '{clean_bill}': {e}")

        # 1d. Partial LIKE match on VendorBillNo in Inventory.GRNMain
        try:
            cursor.execute("""
                SELECT TOP 1 GRNNo, DocumentNoYearly, DocumentDate, ChallanNo, ChallanDate, 
                       VendorLocationNo, WarehouseNo, CompanyNo, YearNo, StatusNo 
                FROM Inventory.GRNMain
                WHERE VendorBillNo LIKE ?
                ORDER BY GRNNo DESC
            """, (f"%{clean_bill}%",))
            row = cursor.fetchone()
            if row:
                cols = [c[0] for c in cursor.description]
                return {cols[i]: (row[i].isoformat() if hasattr(row[i], "isoformat") else row[i]) for i in range(len(cols))}
        except Exception as e:
            logger.warning(f"Error querying GRNMain by LIKE VendorBillNo: {e}")

        return None

    def find_grn_by_challan_no(
        self, challan_no: str, vendor_location_no: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Query Inventory.GRNMain matching ChallanNo (Delivery Note / DC No)."""
        if not challan_no or not challan_no.strip():
            return None

        clean_ch = challan_no.strip().strip("'\"`")
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if vendor_location_no:
                cursor.execute("""
                    SELECT TOP 1 GRNNo, DocumentNoYearly, DocumentDate, ChallanNo, ChallanDate, 
                           VendorLocationNo, WarehouseNo, CompanyNo, YearNo, StatusNo 
                    FROM Inventory.GRNMain
                    WHERE ChallanNo = ? AND VendorLocationNo = ?
                    ORDER BY GRNNo DESC
                """, (clean_ch, vendor_location_no))
                row = cursor.fetchone()
                if row:
                    cols = [c[0] for c in cursor.description]
                    return {cols[i]: (row[i].isoformat() if hasattr(row[i], "isoformat") else row[i]) for i in range(len(cols))}

            cursor.execute("""
                SELECT TOP 1 GRNNo, DocumentNoYearly, DocumentDate, ChallanNo, ChallanDate, 
                       VendorLocationNo, WarehouseNo, CompanyNo, YearNo, StatusNo 
                FROM Inventory.GRNMain
                WHERE ChallanNo = ? OR ChallanNo LIKE ?
                ORDER BY GRNNo DESC
            """, (clean_ch, f"%{clean_ch}%"))
            row = cursor.fetchone()
            if row:
                cols = [c[0] for c in cursor.description]
                return {cols[i]: (row[i].isoformat() if hasattr(row[i], "isoformat") else row[i]) for i in range(len(cols))}
        except Exception as e:
            logger.warning(f"Error querying GRNMain by ChallanNo '{clean_ch}': {e}")

        return None

    def find_grn_by_grn_no(self, grn_no_str: str) -> Optional[Dict[str, Any]]:
        """Query Inventory.GRNMain by exact GRNNo integer or DocumentNoYearly string."""
        if not grn_no_str or not grn_no_str.strip():
            return None

        clean_grn = grn_no_str.strip().strip("'\"`")
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if clean_grn.isdigit():
                cursor.execute("""
                    SELECT TOP 1 GRNNo, DocumentNoYearly, DocumentDate, ChallanNo, ChallanDate, 
                           VendorLocationNo, WarehouseNo, CompanyNo, YearNo, StatusNo 
                    FROM Inventory.GRNMain WHERE GRNNo = ?
                """, (int(clean_grn),))
                row = cursor.fetchone()
                if row:
                    cols = [c[0] for c in cursor.description]
                    return {cols[i]: (row[i].isoformat() if hasattr(row[i], "isoformat") else row[i]) for i in range(len(cols))}

            slash_variant = clean_grn.replace("/", "\\") if "/" in clean_grn else clean_grn.replace("\\", "/")
            cursor.execute("""
                SELECT TOP 1 GRNNo, DocumentNoYearly, DocumentDate, ChallanNo, ChallanDate, 
                       VendorLocationNo, WarehouseNo, CompanyNo, YearNo, StatusNo 
                FROM Inventory.GRNMain 
                WHERE DocumentNoYearly LIKE ? OR DocumentNoYearly LIKE ?
                ORDER BY GRNNo DESC
            """, (f"%{clean_grn}%", f"%{slash_variant}%"))
            row = cursor.fetchone()
            if row:
                cols = [c[0] for c in cursor.description]
                return {cols[i]: (row[i].isoformat() if hasattr(row[i], "isoformat") else row[i]) for i in range(len(cols))}
        except Exception as e:
            logger.warning(f"Error querying GRNMain by GRN number '{clean_grn}': {e}")

        return None

    def get_grn_items_with_master(self, grn_no: int) -> List[Dict[str, Any]]:
        """
        Query Inventory.GRNItemDetail joined with masterdata.mItemMaster.
        Restores line items that may be hidden on the printed purchase bill.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        sql = """
            SELECT 
                d.GRNItemDetailNo,
                d.GRNNo,
                d.POAmendmentNo,
                d.ItemNo,
                i.ItemName,
                i.ItemDescription,
                i.Code AS ItemCode,
                i.FullCode AS ItemFullCode,
                d.MakeNo,
                d.UnitNo,
                d.ChallanQty,
                d.ReceivedQty,
                d.RejectedQty,
                d.AcceptedQty,
                d.Rate,
                (d.AcceptedQty * d.Rate) AS BasicAmount,
                d.WareHouseNo,
                i.HSNSACCodeNo
            FROM Inventory.GRNItemDetail d
            LEFT JOIN masterdata.mItemMaster i ON d.ItemNo = i.ItemNo
            WHERE d.GRNNo = ?
            ORDER BY d.GRNItemDetailNo
        """
        try:
            cursor.execute(sql, (grn_no,))
            rows = cursor.fetchall()
            cols = [c[0] for c in cursor.description]
            items = []
            for row in rows:
                item_dict = {}
                for idx, col in enumerate(cols):
                    val = row[idx]
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    elif hasattr(val, "__float__"):
                        val = float(val)
                    item_dict[col] = val
                items.append(item_dict)
            return items
        except Exception as e:
            logger.warning(f"Error querying GRNItemDetail for GRNNo {grn_no}: {e}")
            return []

    def build_purchase_bill_main_form(self, extracted_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assemble the complete Finance.PurchaseBillMain form payload ready for database insert.
        IMPORTANT: ZERO details are fetched from Finance.PurchaseBillMain table,
        since this data represents a new entry to be added.
        Values are derived exclusively from:
        1. Extracted document JSON (invoice/bill header, amounts, dates)
        2. Inventory.GRNMain & Inventory.GRNItemDetail (Challan No/Date, GRN No/Date, hidden items)
        3. Master tables (mCompanyMaster, mVendorCard, mVendorLocationDetail, mItemMaster)
        """
        doc_meta = extracted_json.get("document_metadata", {})
        parties = extracted_json.get("parties", {})
        fin_sum = extracted_json.get("financial_summary", {})
        add_fields = extracted_json.get("additional_fields") or extracted_json.get("additional_details", {})
        party_bill = add_fields.get("party_bill", {}) if isinstance(add_fields, dict) else {}
        challan_details = (
            add_fields.get("challan_details")
            or add_fields.get("challan_and_grn_details")
            or {}
        )

        # 1. Company matching from masterdata.mCompanyMaster
        seller_name = parties.get("seller_or_supplier", {}).get("name", "") if isinstance(parties, dict) else ""
        buyer_name = parties.get("buyer_or_consignee", {}).get("name", "") if isinstance(parties, dict) else ""
        seller_tax = parties.get("seller_or_supplier", {}).get("tax_id", "") if isinstance(parties, dict) else ""
        buyer_tax = parties.get("buyer_or_consignee", {}).get("tax_id", "") if isinstance(parties, dict) else ""

        company_rec = None
        for name in [seller_name, buyer_name]:
            if name:
                company_rec = self.find_company_by_name(name)
                if company_rec:
                    break
        if not company_rec:
            for tax in [seller_tax, buyer_tax]:
                if tax:
                    company_rec = self.find_company_by_tax_id(tax)
                    if company_rec:
                        break
        company_no = company_rec["CompanyNo"] if company_rec else None

        # 2. Vendor matching from masterdata.mVendorCard
        vendor_rec = None
        for name in [buyer_name, seller_name]:
            if name:
                vendor_rec = self.find_vendor_by_name(name)
                if vendor_rec:
                    break
        if not vendor_rec:
            for tax in [buyer_tax, seller_tax]:
                if tax:
                    vendor_rec = self.find_vendor_by_tax_id(tax)
                    if vendor_rec:
                        break
        pay_to_vendor_no = vendor_rec["VendorNo"] if vendor_rec else None

        # 3. Vendor Location from masterdata.mVendorLocationDetail
        vendor_location_no = (
            vendor_rec.get("VendorLocationNo")
            if vendor_rec
            else (self.find_vendor_location_no(pay_to_vendor_no) if pay_to_vendor_no else None)
        )

        def _find_field(container: Any, *target_keys: str) -> Optional[Any]:
            """Recursively search for first non-null scalar matching any target_keys (case-insensitive)."""
            if container is None:
                return None
            target_keys_lower = {k.lower() for k in target_keys}
            if isinstance(container, dict):
                for k, v in container.items():
                    if k.lower() in target_keys_lower and v is not None and v != "":
                        if not isinstance(v, (dict, list)):
                            return v
                        sub = _find_field(v, *target_keys)
                        if sub is not None:
                            return sub
                for v in container.values():
                    if isinstance(v, (dict, list)):
                        sub = _find_field(v, *target_keys)
                        if sub is not None:
                            return sub
            elif isinstance(container, list):
                for item in container:
                    sub = _find_field(item, *target_keys)
                    if sub is not None:
                        return sub
            return None

        # 4. Extract Party Bill Number & Date (Invoice No from PDF)
        party_bill_no = (
            _find_field(
                extracted_json,
                "party_bill_no", "vendor_bill_no", "invoice_no", "invoice_number",
                "bill_no", "party_bill_num", "tax_invoice_no", "invoice_num"
            )
            or doc_meta.get("invoice_or_bill_number")
            or doc_meta.get("document_no_yearly")
            or ""
        )
        party_bill_no = str(party_bill_no).strip()

        party_bill_date_raw = (
            _find_field(extracted_json, "party_bill_date", "vendor_bill_date", "bill_date", "invoice_date")
            or doc_meta.get("issue_date")
            or ""
        )

        party_bill_amt = (
            _find_field(extracted_json, "party_bill_amt", "party_bill_amount", "vendor_bill_amount")
            or fin_sum.get("grand_total")
            or 0.0
        )
        try:
            party_bill_amt = float(party_bill_amt)
        except (ValueError, TypeError):
            party_bill_amt = 0.0

        basic_amt = fin_sum.get("subtotal") or _find_field(extracted_json, "basic_amount") or party_bill_amt
        try:
            basic_amt = float(basic_amt)
        except (ValueError, TypeError):
            basic_amt = party_bill_amt

        net_amt = fin_sum.get("grand_total") or party_bill_amt
        try:
            net_amt = float(net_amt)
        except (ValueError, TypeError):
            net_amt = party_bill_amt

        # 5. Locate GRN from Inventory.GRNMain (NO fetch from PurchaseBillMain)
        # Primary anchor is party_bill_no (the Invoice No printed on the bill matching VendorBillNo)
        grn_candidate_no = _find_field(extracted_json, "grn_no", "grn_number", "mrn_no", "mrn_number", "receipt_no")
        challan_candidate_no = _find_field(
            extracted_json,
            "challan_no", "challan_number", "delivery_challan_no", "dc_no",
            "delivery_note", "dispatch_doc_no", "delivery_note_no"
        )
        challan_candidate_date = _find_field(extracted_json, "challan_date", "delivery_note_date")

        grn_record = self.find_grn_for_purchase_bill(
            vendor_bill_no=party_bill_no,
            challan_no=challan_candidate_no,
            grn_no_str=grn_candidate_no,
            vendor_location_no=vendor_location_no
        )

        # 5b. Locate PO from Purchase.POMain using Buyer's Order No / PO No from PDF
        po_candidate_no = (
            _find_field(
                extracted_json,
                "buyers_order_no", "buyer_order_no", "buyer_order_num", "buyers_order_number",
                "order_no", "po_wo_no", "po_no", "po_number", "po_reference_number", "wo_no", "order_ref"
            )
            or doc_meta.get("po_number")
            or doc_meta.get("po_reference_number")
        )
        po_record = None
        if po_candidate_no and str(po_candidate_no).strip():
            po_record = self.find_po_main(str(po_candidate_no))
            if po_record:
                logger.info(f"Matched Purchase.POMain: PONo {po_record.get('PONo')} for PO / Buyer's Order No '{po_candidate_no}'")

        # 6. Parse Dates
        def _parse_sql_date(val: Any) -> Optional[str]:
            if not val:
                return None
            if isinstance(val, datetime):
                return val.strftime("%Y-%m-%d %H:%M:%S")
            val_str = str(val).strip()
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d.%m.%Y", "%d.%m.%y", "%Y-%m-%dT%H:%M:%S"):
                try:
                    dt = datetime.strptime(val_str, fmt)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            return val_str

        doc_date_raw = doc_meta.get("issue_date") or doc_meta.get("document_date") or party_bill_date_raw
        doc_date = _parse_sql_date(doc_date_raw) or datetime.now().strftime("%Y-%m-%d 00:00:00")
        vendor_bill_date = _parse_sql_date(party_bill_date_raw) or doc_date

        # Determine YearNo (Financial Year)
        year_no = grn_record.get("YearNo") if (grn_record and grn_record.get("YearNo")) else None

        # GRN specifics
        matched_grn_no = grn_record.get("GRNNo") if grn_record else None
        matched_grn_yearly = grn_record.get("DocumentNoYearly") if grn_record else None
        doc_receipt_no = grn_record.get("DocumentReceiptNo") if grn_record else None
        shipped_from_location = grn_record.get("VendorLocationNo") if grn_record else vendor_location_no

        # PDF Challan Qty if extracted
        pdf_challan_qty_raw = _find_field(extracted_json, "challan_qty", "ch_qty")
        pdf_challan_qty = None
        if pdf_challan_qty_raw is not None:
            try:
                pdf_challan_qty = float(pdf_challan_qty_raw)
            except (ValueError, TypeError):
                pdf_challan_qty = None

        # 7. Fetch Line Items: From Inventory.GRNItemDetail if GRN matched, else from document's line_items
        purchase_bill_items = []
        if matched_grn_no:
            grn_items = self.get_grn_items_with_master(matched_grn_no)
            for idx, g_item in enumerate(grn_items):
                raw_qty = g_item.get("AcceptedQty") or g_item.get("ReceivedQty") or g_item.get("ChallanQty")
                qty = float(raw_qty) if raw_qty is not None else None
                rate = float(g_item.get("Rate")) if g_item.get("Rate") is not None else None
                b_amt = float(g_item.get("BasicAmount")) if g_item.get("BasicAmount") is not None else (
                    (qty * rate) if (qty is not None and rate is not None) else None
                )
                item_challan_qty = pdf_challan_qty if pdf_challan_qty is not None else (
                    float(g_item.get("ChallanQty")) if g_item.get("ChallanQty") is not None else None
                )
                po_amend = (
                    g_item.get("POAmendmentNo")
                    or (po_record.get("AmendmentNo") if po_record else None)
                    or (po_record.get("PONo") if po_record else None)
                )
                purchase_bill_items.append({
                    "PurchaseBillItemDetailNo": None,
                    "PurchaseBillNo": None,
                    "ExcisePostingNo": None,
                    "SINNo": None,
                    "GRNNo": matched_grn_no,
                    "POAmendmentNo": po_amend,
                    "ItemNo": g_item.get("ItemNo"),
                    "ItemName": g_item.get("ItemName"),
                    "ItemDescription": g_item.get("ItemDescription"),
                    "ItemCode": g_item.get("ItemCode"),
                    "MakeNo": g_item.get("MakeNo"),
                    "ChallanQty": item_challan_qty,
                    "Qty": qty,
                    "Rate": rate,
                    "BasicAmount": b_amt,
                    "BINNo": None,
                    "WarehouseNo": g_item.get("WareHouseNo") or (grn_record.get("WarehouseNo") if grn_record else None),
                    "Remarks": None,
                    "BillableBasicAmount": b_amt,
                    "MRANo": None,
                    "TechnicalGradeNo": None,
                    "ChapterHeadingNo": None,
                    "ExpiryDate": None,
                    "DispatchChallanNo": None,
                    "SalesOrderNo": None,
                    "GSTTaxRuleNo": None,
                    "HSNSACCodeNo": g_item.get("HSNSACCodeNo"),
                    "TaxableValue": b_amt
                })
        else:
            # When no GRN matched: populate items from extracted document line_items
            extracted_line_items = extracted_json.get("line_items") or []
            if isinstance(extracted_line_items, list) and len(extracted_line_items) > 0:
                for idx, l_item in enumerate(extracted_line_items):
                    if not isinstance(l_item, dict):
                        continue
                    desc = (
                        l_item.get("description")
                        or l_item.get("item_name")
                        or l_item.get("name")
                        or ""
                    )
                    master_item = self.find_item_by_description(str(desc)) if desc else None
                    item_no = master_item["ItemNo"] if master_item else None
                    item_name = master_item.get("ItemName") if master_item else (desc or None)
                    item_desc = master_item.get("ItemDescription") if master_item else (desc or None)
                    item_code = master_item.get("Code") if master_item else None

                    qty_val = l_item.get("quantity") or l_item.get("qty")
                    try:
                        qty = float(qty_val) if qty_val is not None and str(qty_val).strip() != "" else None
                    except (ValueError, TypeError):
                        qty = None

                    rate_val = l_item.get("unit_price") or l_item.get("rate")
                    try:
                        rate = float(rate_val) if rate_val is not None and str(rate_val).strip() != "" else None
                    except (ValueError, TypeError):
                        rate = None

                    amt_val = l_item.get("line_total") or l_item.get("amount") or l_item.get("total")
                    try:
                        b_amt = float(amt_val) if amt_val is not None and str(amt_val).strip() != "" else (
                            (qty * rate) if (qty is not None and rate is not None) else None
                        )
                    except (ValueError, TypeError):
                        b_amt = None

                    item_challan_qty = pdf_challan_qty if pdf_challan_qty is not None else None

                    purchase_bill_items.append({
                        "PurchaseBillItemDetailNo": None,
                        "PurchaseBillNo": None,
                        "ExcisePostingNo": None,
                        "SINNo": None,
                        "GRNNo": None,
                        "POAmendmentNo": po_record.get("AmendmentNo") if po_record else None,
                        "ItemNo": item_no,
                        "ItemName": item_name,
                        "ItemDescription": item_desc,
                        "ItemCode": item_code,
                        "MakeNo": None,
                        "ChallanQty": item_challan_qty,
                        "Qty": qty,
                        "Rate": rate,
                        "BasicAmount": b_amt,
                        "BINNo": None,
                        "WarehouseNo": None,
                        "Remarks": None,
                        "BillableBasicAmount": b_amt,
                        "MRANo": None,
                        "TechnicalGradeNo": None,
                        "ChapterHeadingNo": None,
                        "ExpiryDate": None,
                        "DispatchChallanNo": None,
                        "SalesOrderNo": None,
                        "GSTTaxRuleNo": None,
                        "HSNSACCodeNo": None,
                        "TaxableValue": b_amt
                    })

            # If still no items: create a single blank entry with null values
            if not purchase_bill_items:
                purchase_bill_items.append({
                    "PurchaseBillItemDetailNo": None,
                    "PurchaseBillNo": None,
                    "ExcisePostingNo": None,
                    "SINNo": None,
                    "GRNNo": None,
                    "POAmendmentNo": None,
                    "ItemNo": None,
                    "ItemName": None,
                    "ItemDescription": None,
                    "ItemCode": None,
                    "MakeNo": None,
                    "ChallanQty": None,
                    "Qty": None,
                    "Rate": None,
                    "BasicAmount": None,
                    "BINNo": None,
                    "WarehouseNo": None,
                    "Remarks": None,
                    "BillableBasicAmount": None,
                    "MRANo": None,
                    "TechnicalGradeNo": None,
                    "ChapterHeadingNo": None,
                    "ExpiryDate": None,
                    "DispatchChallanNo": None,
                    "SalesOrderNo": None,
                    "GSTTaxRuleNo": None,
                    "HSNSACCodeNo": None,
                    "TaxableValue": None
                })

        # 8. Build the exact 48 fields for Finance.PurchaseBillMain form (matching SSMS schema screenshots)
        doc_no_yearly = doc_meta.get("document_no_yearly") or doc_meta.get("invoice_or_bill_number") or None

        purchase_bill_main = {
            # Image 1 Fields
            "CompanyNo": company_no,
            "YearNo": year_no,
            "PurchaseBillNo": None,  # Identity column (generated on insert)
            "DocumentSettingNo": 1101,
            "DocumentNoYearly": doc_no_yearly,
            "DocumentDate": doc_date,
            "DocumentStatusNo": 10,  # 10 = Draft / Pending Entry
            "PBSourceDocumentNo": 1 if matched_grn_no else None,
            "VendorLocationNo": vendor_location_no,
            "PayToVendorNo": pay_to_vendor_no,
            "DocumentReceiptNo": doc_receipt_no,
            "VendorBillNo": party_bill_no or None,
            "VendorBillDate": vendor_bill_date,
            "VendorBillAmount": party_bill_amt,
            "UnitTypeNo": 2 if matched_grn_no else None,
            "QtybasedOn": 1 if matched_grn_no else None,
            "PaymentModeNo": 3,
            "NetAmount": net_amt,
            "Remarks": doc_meta.get("remarks") or add_fields.get("remarks") or None,
            "VoucherNo": None,  # Generated upon finance posting
            "CreatedBy": 196,
            "CreatedDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ModifiedBy": None,
            "ModifiedDate": None,
            "AuthorizedBy": None,
            "AuthorizedDate": None,
            "ReleasedBy": None,
            "ReleasedDate": None,
            # Image 2 Fields
            "CurrencyConversionNo": 1,
            "DivisibilityRate": 1.000000,
            "MultiplicativeRate": 1.000000,
            "FBNo": 2 if company_no else None,
            "GSTDNo": None,
            "AdvanceVoucherNo": None,
            "ShippedFromPartyLocationNo": shipped_from_location,
            "ShippedToPartyLocationNo": 1883 if company_no else None,
            "IsExcisePosting": False,
            "IsUpdateStock": False,
            "IsDropshipment": False,
            "ServiceTaxAbatementRuleNo": None,
            "BasicAmount": basic_amt,
            "ImprestAccountNo": None,
            "ImprestAmount": None,
            "ReferenceNos": matched_grn_yearly,
            "eWayBillNo": doc_meta.get("eway_bill_no") or None,
            "eWayBillDate": _parse_sql_date(doc_meta.get("eway_bill_date")),
            "IsGSTExempted": False,
            "InvoiceNo": party_bill_no or None,
            "InvoiceDate": vendor_bill_date
        }

        # 9. Assembled Form Result
        grn_ref = None
        if grn_record:
            grn_ref = {
                "GRNNo": matched_grn_no,
                "GRNNoYearly": matched_grn_yearly,
                "GRNDate": grn_record.get("DocumentDate"),
                "ChallanNo": grn_record.get("ChallanNo"),
                "ChallanDate": grn_record.get("ChallanDate"),
                "VendorLocationNo": grn_record.get("VendorLocationNo"),
                "WarehouseNo": grn_record.get("WarehouseNo")
            }

        return {
            "form_name": "Finance.PurchaseBillMain",
            "table_name": "Finance.PurchaseBillMain",
            "purchase_bill_main": purchase_bill_main,
            "grn_reference": grn_ref,
            "purchase_bill_items": purchase_bill_items,
            "source_metadata": {
                "source_file": extracted_json.get("_source_file", {}).get("filename", "document"),
                "extracted_vendor_name": (vendor_rec.get("Name") if vendor_rec else None) or buyer_name or seller_name or None,
                "extracted_company_name": (company_rec.get("CompanyName") if company_rec else None) or seller_name or buyer_name or None,
                "extracted_party_bill_no": party_bill_no or None,
                "extracted_party_bill_date": party_bill_date_raw or None,
                "matched_grn_no": matched_grn_no,
                "matched_grn_yearly": matched_grn_yearly,
                "matched_challan_no": grn_record.get("ChallanNo") if grn_record else None,
                "matched_challan_date": grn_record.get("ChallanDate") if grn_record else None,
                "hidden_items_restored_count": len(purchase_bill_items) if matched_grn_no else 0,
                "purchase_bill_source": "Newly prepared form data (NO details fetched from Finance.PurchaseBillMain)"
            }
        }


_default_connector: Optional[SQLServerConnector] = None


def get_db_connector(connection_string: Optional[str] = None) -> SQLServerConnector:
    """Get or create singleton database connector instance."""
    global _default_connector
    if _default_connector is None or connection_string is not None:
        _default_connector = SQLServerConnector(connection_string)
    return _default_connector


def enrich_json_with_items(
    po_data: Dict[str, Any], connection_string: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience helper to enrich extracted PO JSON using SQL Server."""
    connector = get_db_connector(connection_string)
    return connector.enrich_po_data(po_data)


def generate_purchase_bill_form(
    extracted_json: Dict[str, Any],
    connection_string: Optional[str] = None,
    output_file: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Generate PurchaseBillMain form payload from extracted invoice/bill data,
    fetching GRN, Challan, and hidden items from Inventory.GRNMain and masters,
    and save to output_purchasebillmainform directory.
    """
    from core.json_cleaner import dump_json_to_file

    connector = get_db_connector(connection_string)
    form_data = connector.build_purchase_bill_main_form(extracted_json)

    if output_file:
        out_p = Path(output_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        dump_json_to_file(form_data, str(out_p))
        logger.info(f"Saved PurchaseBillMain form JSON to: {out_p}")

    return form_data

