"""Monitor ORDERS420 XML generator.

Transforms our internal order model into the ERP XML format
based on the ORDERS420 XML schema.

ROLE MAPPING (verified against ERP output):
    <Supplier> = the company RECEIVING the PO (extracted from the PDF Postadress block).
        - SupplierCodeEdi from 'Leverantörsnummer' field in the PDF
        - Name, Street, ZipCity, Country from extracted supplier_* fields
        - Falls back to SUPPLIER_* env vars only when extraction found nothing
    <Buyer> = The customer company (extracted from the PDF purchase order)
        - Name, Street, ZipCity, Country from order.buyer_* fields

    <DeliveryAddress> = Shipping destination from the PDF
        - CompanyAdressFlag = 1 if delivery == buyer, 0 for third party

Other conventions (from ERP reference):
- Empty optional elements are rendered as self-closing tags.
- Country names are title-cased (Sverige, not SVERIGE).
- Setup fields are empty (self-closing).
- Each fields: populated for RowType=1, empty for RowType=4.
- Newlines in Text nodes are preserved for RowType=4 additional text.
- IncoTermCombiTerm contains a single space.
"""

from __future__ import annotations

from lxml import etree

import structlog

from app.core.exceptions import XMLGenerationError
from app.models.order import Order

logger = structlog.get_logger(__name__)

# ── Country Normalization ────────────────────────────────────────────────
_COUNTRY_NORMALIZATION: dict[str, str] = {
    "SVERIGE": "Sverige",
    "SWEDEN": "Sverige",
    "NORWAY": "Norge",
    "NORGE": "Norge",
    "DENMARK": "Danmark",
    "DANMARK": "Danmark",
    "FINLAND": "Finland",
    "GERMANY": "Tyskland",
    "TYSKLAND": "Tyskland",
}


def _normalize_country(raw: str | None) -> str:
    """Normalize country name to Monitor-style title case.

    Returns empty string for None/empty input.
    """
    if not raw or not raw.strip():
        return ""
    trimmed = raw.strip()
    upper_key = trimmed.upper()
    if upper_key in _COUNTRY_NORMALIZATION:
        return _COUNTRY_NORMALIZATION[upper_key]
    return trimmed.title()


class XMLGeneratorService:
    """Generates Monitor ORDERS420 XML from an Order model.

    Supplier = configured supplier (from settings).
    Buyer = customer from the PDF.

    Requires an injected Settings object to read supplier defaults.
    """

    def __init__(self, settings) -> None:
        """Store the supplier info from config.

        Args:
            settings: Application Settings instance with supplier_* fields.
        """
        self._supplier_name: str = settings.supplier_name
        self._supplier_edi_code: str = settings.supplier_edi_code
        self._supplier_street: str = settings.supplier_street
        self._supplier_zip_city: str = settings.supplier_zip_city
        self._supplier_country: str = settings.supplier_country

    # ── Public API ────────────────────────────────────────────────────────

    def generate(self, order: Order) -> str:
        """Generate an ORDERS420 XML string from an Order model.

        Args:
            order: A fully loaded Order instance with line_items relationship.

        Returns:
            UTF-8 encoded XML string with XML declaration.

        Raises:
            XMLGenerationError: If generation fails due to a technical error.
        """
        try:
            root = self._build_xml(order)
            xml_bytes = etree.tostring(
                root,
                xml_declaration=True,
                encoding="utf-8",
                pretty_print=False,
            )
            xml_string = xml_bytes.decode("utf-8")

            logger.info(
                "xml_generated",
                order_id=order.id,
                order_number=order.order_number,
                line_count=len(order.line_items),
            )
            return xml_string

        except XMLGenerationError:
            raise
        except Exception as exc:
            logger.error("xml_generation_failed", order_id=order.id, error=str(exc))
            raise XMLGenerationError(f"Failed to generate XML: {exc}") from exc

    # ── XML Tree Builder ─────────────────────────────────────────────────

    def _build_xml(self, order: Order) -> etree._Element:
        """Build the full XML element tree."""
        root = etree.Element(
            "ORDERS420",
            SoftwareManufacturer="Monitor ERP System AB",
            SoftwareName="MONITOR",
            SoftwareVersion="25.9.9.2266",
        )

        order_el = etree.SubElement(root, "Order", OrderNumber=order.order_number or "")

        # Head section — order matches ERP element sequence exactly
        head = etree.SubElement(order_el, "Head")
        self._add_supplier(head, order)
        self._add_buyer(head, order)
        self._add_references(head, order)
        self._add_delivery_address(head, order)
        self._add_terms(head, order)
        self._add_export(head, order)

        # Rows section
        rows_el = etree.SubElement(order_el, "Rows")
        for item in order.line_items:
            self._add_line_item_rows(rows_el, item)

        return root

    # ── Head Section Builders ────────────────────────────────────────────

    def _add_supplier(self, head: etree._Element, order: Order) -> None:
        """Add the Supplier element.

        Uses supplier data extracted from the PDF 'Postadress' block.
        Falls back to settings (env vars) only when extraction returned nothing.
        Tag name is <Name> as required by Monitor ERP ORDERS420 schema.
        """
        edi_code = order.supplier_edi_code or self._supplier_edi_code or ""

        # Use extracted supplier data from the PDF.
        # ONLY fall back to env-var defaults when NO supplier data was extracted at all
        # (i.e. the entire supplier block is empty — not just one field missing).
        # This prevents the default supplier address bleeding into other suppliers when
        # GPT-4o extracts the name but leaves zip_city null (e.g. "HJORTSBERGA" has no zip).
        has_extracted_supplier = bool(order.supplier_name)
        if has_extracted_supplier:
            name = order.supplier_name or ""
            street = order.supplier_street or ""
            zip_city = order.supplier_zip_city or ""
            country = order.supplier_country or settings.supplier_country
        else:
            # Full fallback to env vars — only when extraction found nothing at all
            name = self._supplier_name or ""
            street = self._supplier_street or ""
            zip_city = self._supplier_zip_city or ""
            country = self._supplier_country or settings.supplier_country

        supplier = etree.SubElement(head, "Supplier", SupplierCodeEdi=edi_code)
        self._text_el(supplier, "Name", name)
        self._text_el(supplier, "StreetBox1", street)
        self._text_el(supplier, "StreetBox2", "")
        self._text_el(supplier, "ZipCity1", zip_city)
        self._text_el(supplier, "ZipCity2", "")
        self._text_el(supplier, "Country", _normalize_country(country))

    def _add_buyer(self, head: etree._Element, order: Order) -> None:
        """Add the Buyer element — the customer who sent the PO.

        BuyerCodeEdi attribute is ONLY added when buyer_customer_number
        has a value (from 'Vårt kundnr' field). Omitted entirely if blank.

        ERP reference (Doc 2):
            <Buyer BuyerCodeEdi="1792">
            <Name>FORM2 Office AB</Name>
            ...
        """
        buyer_attribs: dict[str, str] = {}
        if order.buyer_customer_number:
            buyer_attribs["BuyerCodeEdi"] = str(order.buyer_customer_number)
        buyer = etree.SubElement(head, "Buyer", **buyer_attribs)
        self._text_el(buyer, "Name", order.buyer_name or "")
        self._text_el(buyer, "StreetBox1", order.buyer_street or "")
        self._text_el(buyer, "StreetBox2", "")
        self._text_el(buyer, "ZipCity1", order.buyer_zip_city or "")
        self._text_el(buyer, "ZipCity2", "")
        self._text_el(buyer, "Country", _normalize_country(order.buyer_country))

    def _add_references(self, head: etree._Element, order: Order) -> None:
        """Add the References element.

        GoodsLabeling Row1 is populated from goods_marking field
        (extracted from 'Godsmärke' on the PO).

        ERP reference:
            <BuyerReference>Marina Thorsén</BuyerReference>
            <BuyerComment />
            <GoodsLabeling><Row1>MKV482502-1 KEE Plastic</Row1><Row2 /></GoodsLabeling>
        """
        refs = etree.SubElement(head, "References")
        self._text_el(refs, "BuyerReference", order.buyer_reference or "")
        self._text_el(refs, "BuyerComment", "")
        goods_label = etree.SubElement(refs, "GoodsLabeling")
        self._text_el(goods_label, "Row1", order.goods_marking or "")
        self._text_el(goods_label, "Row2", "")

    def _add_delivery_address(self, head: etree._Element, order: Order) -> None:
        """Add the DeliveryAddress element — shipping destination from PDF.

        ERP reference:
            <Name>Careco Inredningar AB</Name>
            <StreetBox1>LAS Interör AB</StreetBox1>
            <StreetBox2>Ågatan 5</StreetBox2>
            <ZipCity1>646 30 Gnesta</ZipCity1>
            <Country>{country}</Country>
            <CompanyAdressFlag>1</CompanyAdressFlag>
        """
        delivery = etree.SubElement(head, "DeliveryAddress")
        self._text_el(delivery, "Name", order.delivery_name or "")
        self._text_el(delivery, "StreetBox1", order.delivery_street1 or "")
        self._text_el(delivery, "StreetBox2", order.delivery_street2 or "")
        self._text_el(delivery, "ZipCity1", order.delivery_zip_city or "")
        self._text_el(delivery, "ZipCity2", "")
        self._text_el(delivery, "Country", _normalize_country(order.delivery_country))
        # CompanyAdressFlag: "1" if delivery == buyer (internal), "0" if third party.
        # When delivery_is_buyer_address is None (pre-existing orders), fall back to
        # comparing delivery_name with buyer_name (case-insensitive).
        if order.delivery_is_buyer_address is not None:
            flag = "1" if order.delivery_is_buyer_address else "0"
        else:
            # Fallback: compare names to infer the flag
            d_name = (order.delivery_name or "").strip().lower()
            b_name = (order.buyer_name or "").strip().lower()
            flag = "1" if d_name and b_name and d_name == b_name else "0"
        self._text_el(delivery, "CompanyAdressFlag", flag)

    def _add_terms(self, head: etree._Element, order: Order) -> None:
        """Add the Terms element.

        ERP reference:
            <IncoTermCombiTerm> </IncoTermCombiTerm>
            <DeliveryMethod>Bil</DeliveryMethod>
            <TransportPayer>C</TransportPayer>
            <CustomerTransportTimeDays />
            <CustomerInvoiceCode />
            <OrderDate>2026-02-05</OrderDate>
            <TermsOfPaymentDays>30</TermsOfPaymentDays>
        """
        terms = etree.SubElement(head, "Terms")

        delivery_terms = etree.SubElement(terms, "DeliveryTerms")
        self._text_el(delivery_terms, "IncoTermCombiTerm", " ", strip=False)
        self._text_el(delivery_terms, "DeliveryMethod", order.delivery_method or "")
        self._text_el(
            delivery_terms,
            "TransportPayer",
            order.transport_payer if order.transport_payer else "C",
        )
        self._text_el(delivery_terms, "CustomerTransportTimeDays", "")

        # CustomerInvoiceCode = buyer_customer_number ('Vårt kundnr')
        self._text_el(terms, "CustomerInvoiceCode", order.buyer_customer_number or "")
        self._text_el(terms, "OrderDate", order.order_date or "")

        payment = etree.SubElement(terms, "PaymentTerms")
        days_str = str(order.payment_terms_days) if order.payment_terms_days else ""
        self._text_el(payment, "TermsOfPaymentDays", days_str)

    def _add_export(self, head: etree._Element, order: Order) -> None:
        """Add the Export element.

        ERP reference: <Currency>SEK</Currency>
        """
        export = etree.SubElement(head, "Export")
        self._text_el(export, "Currency", order.currency or "SEK")

    # ── Row Builders ─────────────────────────────────────────────────────

    def _add_line_item_rows(self, rows_el: etree._Element, item) -> None:
        """Add RowType=1 (data) and optionally RowType=4 (text) rows.

        ERP reference for RowType=1:
            <Part PartNumber="101928002070DL" SupplierPartNumber="HA0413" />
            <Text>Sample Product Description</Text>
            <ReferenceNumber />
            <Quantity>96.00</Quantity>
            <Unit>ST</Unit>
            <DeliveryPeriod>2026-02-17</DeliveryPeriod>
            <Each>372.97</Each>
            <Discount>-11.34</Discount>
            <Setup />
            <Alloy>0.00</Alloy>

        ERP reference for RowType=4:
            <Text>Dekor W980 ST2 Platinum White\n2800;2070\nNCS 0502-g50y</Text>
            <Quantity>1.00</Quantity>
            <Unit />
            <Each />
            <Discount>0.00</Discount>
            <Setup />
            <Alloy>0.00</Alloy>
        """
        row_num = str(item.row_number)

        # ── RowType=1: Main data row ─────────────────────────────────────
        row1 = etree.SubElement(rows_el, "Row", RowNumber=row_num, RowType="1")
        part = etree.SubElement(row1, "Part")
        part.set("PartNumber", item.part_number or "")
        part.set("SupplierPartNumber", item.supplier_part_number or "")

        self._text_el(row1, "Text", item.description or "")
        self._text_el(row1, "ReferenceNumber", item.reference_number or "")
        self._text_el(
            row1,
            "Quantity",
            f"{item.quantity:.2f}" if item.quantity is not None else "0.00",
        )
        self._text_el(row1, "Unit", item.unit or "ST")
        self._text_el(row1, "DeliveryPeriod", item.delivery_date or "")
        self._text_el(
            row1,
            "Each",
            f"{item.unit_price:.2f}" if item.unit_price is not None else "0.00",
        )
        self._text_el(
            row1,
            "Discount",
            f"{item.discount:.2f}" if item.discount is not None else "0.00",
        )
        self._text_el(row1, "Setup", "")
        self._text_el(row1, "Alloy", "0.00")

        # ── RowType=4: Additional text row ───────────────────────────────
        if item.additional_text:
            row4 = etree.SubElement(rows_el, "Row", RowNumber=row_num, RowType="4")
            part4 = etree.SubElement(row4, "Part")
            part4.set("PartNumber", item.part_number or "")
            part4.set("SupplierPartNumber", item.supplier_part_number or "")

            # Preserve newlines — Monitor uses multi-line Text nodes
            self._text_el(row4, "Text", item.additional_text)
            self._text_el(row4, "ReferenceNumber", "")
            self._text_el(row4, "Quantity", "1.00")
            self._text_el(row4, "Unit", "")
            self._text_el(row4, "DeliveryPeriod", item.delivery_date or "")
            self._text_el(row4, "Each", "")
            self._text_el(row4, "Discount", "0.00")
            self._text_el(row4, "Setup", "")
            self._text_el(row4, "Alloy", "0.00")

    # ── Utility ──────────────────────────────────────────────────────────

    @staticmethod
    def _text_el(
        parent: etree._Element,
        tag: str,
        text: str,
        *,
        strip: bool = True,
    ) -> etree._Element:
        """Create a child element with text content.

        Empty text produces a self-closing element.
        Newlines in text are preserved as-is (important for RowType=4 spec text).
        strip=True (default) removes leading/trailing whitespace from GPT-4o values.
        strip=False must be used for IncoTermCombiTerm which intentionally holds a single space.
        """
        el = etree.SubElement(parent, tag)
        value = text.strip() if strip else text
        if value:
            el.text = value
        return el