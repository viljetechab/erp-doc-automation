"""Tests for the XML generator service.

Tests verified against ERP reference XML (G73216.xml):
- Supplier = Demo Supplier Ltd (from config) with SupplierCodeEdi=0000000
- Buyer = Customer (from PDF)
- DeliveryAddress from PDF, CompanyAdressFlag=1
- TransportPayer from extraction
"""

from __future__ import annotations

import os

import pytest
from lxml import etree

# Set minimal env vars so Settings can be constructed
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

from app.config import get_settings
from app.models.order import Order, OrderLineItem, OrderStatus
from app.services.xml_generator import XMLGeneratorService


@pytest.fixture
def xml_service() -> XMLGeneratorService:
    return XMLGeneratorService(get_settings())


@pytest.fixture
def sample_order() -> Order:
    """Create a sample Order model matching the G73216 test data."""
    order = Order(
        id="test-order-1",
        status=OrderStatus.EXTRACTED,
        source_filename="test.pdf",
        source_filepath="/tmp/test.pdf",
        order_number="G73216",
        order_date="2026-02-05",
        buyer_name="Careco Inredningar AB",
        buyer_street="Box 95",
        buyer_zip_city="283 22 OSBY",
        buyer_country="Demo Country",
        buyer_reference="Marina Thorsén",
        delivery_name="Careco Inredningar AB",
        delivery_street1="LAS Interör AB",
        delivery_street2="Ågatan 5",
        delivery_zip_city="646 30 Gnesta",
        delivery_country="Demo Country",
        delivery_method="Bil",
        transport_payer="C",
        payment_terms_days=30,
        currency="SEK",
    )

    order.line_items = [
        OrderLineItem(
            id="line-1",
            order_id="test-order-1",
            row_number=10,
            part_number="101928002070DL",
            supplier_part_number="HA0413",
            description="Sample Panel Oak 19mm",
            additional_text="Dekor W980 ST2 Platinum White\n2800;2070\nNCS 0502-g50y",
            quantity=96.00,
            unit="ST",
            delivery_date="2026-02-17",
            unit_price=372.97,
            discount=-11.34,
        ),
        OrderLineItem(
            id="line-2",
            order_id="test-order-1",
            row_number=20,
            part_number="101628002070DL",
            supplier_part_number="HA0414",
            description="Sample Panel Oak 16mm",
            additional_text="Dekor W980 ST2 Platinum White\n2800;2070\nNCS 0502-g50y",
            quantity=24.00,
            unit="ST",
            delivery_date="2026-02-17",
            unit_price=343.01,
            discount=-11.34,
        ),
    ]

    return order


class TestXMLGenerator:
    """Tests for Monitor ORDERS420 XML generation.

    All assertions verified against G73216.xml from ERP System.
    """

    def test_generates_valid_xml(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Should produce valid, parseable XML."""
        xml_string = xml_service.generate(sample_order)
        assert xml_string.startswith("<?xml")
        root = etree.fromstring(xml_string.encode("utf-8"))
        assert root.tag == "ORDERS420"

    def test_order_number_in_xml(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """The OrderNumber attribute should match."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        order_el = root.find("Order")
        assert order_el is not None
        assert order_el.get("OrderNumber") == "G73216"

    def test_supplier_is_direktlaminat(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Supplier should be Demo Supplier Ltd (our company), per ERP reference."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        supplier = root.find(".//Supplier")
        assert supplier is not None
        assert supplier.get("SupplierCodeEdi") == "0000000"
        assert supplier.find("Name").text == "Demo Supplier Ltd"
        assert supplier.find("StreetBox1").text == "1 Business Street"
        assert supplier.find("ZipCity1").text == "00000 DEMO CITY"
        assert supplier.find("Country").text == "Demo Country"

    def test_buyer_is_customer(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Buyer should be the customer from the PDF, per ERP reference."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        buyer = root.find(".//Buyer")
        assert buyer is not None
        assert buyer.find("Name").text == "Careco Inredningar AB"
        assert buyer.find("StreetBox1").text == "Box 95"
        assert buyer.find("ZipCity1").text == "283 22 OSBY"
        assert buyer.find("Country").text == "Demo Country"

    def test_supplier_and_buyer_different(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Supplier and Buyer should be different entities."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        supplier_name = root.find(".//Supplier/Name").text
        buyer_name = root.find(".//Buyer/Name").text
        assert supplier_name == "Demo Supplier Ltd"
        assert buyer_name == "Careco Inredningar AB"
        assert supplier_name != buyer_name

    def test_delivery_address_fields(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Delivery address from PDF, per ERP reference."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        da = root.find(".//DeliveryAddress")
        assert da is not None
        assert da.find("Name").text == "Careco Inredningar AB"
        assert da.find("StreetBox1").text == "LAS Interör AB"
        assert da.find("StreetBox2").text == "Ågatan 5"
        assert da.find("ZipCity1").text == "646 30 Gnesta"
        assert da.find("Country").text == "Demo Country"

    def test_company_address_flag_is_1(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """CompanyAdressFlag should be 1 per ERP reference."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        flag = root.find(".//DeliveryAddress/CompanyAdressFlag")
        assert flag is not None
        assert flag.text == "1"

    def test_transport_payer(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """TransportPayer should match ERP reference (C)."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        tp = root.find(".//DeliveryTerms/TransportPayer")
        assert tp is not None
        assert tp.text == "C"

    def test_delivery_method(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """DeliveryMethod should match ERP reference (Bil)."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        dm = root.find(".//DeliveryTerms/DeliveryMethod")
        assert dm is not None
        assert dm.text == "Bil"

    def test_line_items_row_type_1_and_4(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Each line item with additional_text should generate RowType=1 and RowType=4."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        rows = root.findall(".//Row")
        assert len(rows) == 4

        row_types = [(r.get("RowNumber"), r.get("RowType")) for r in rows]
        assert ("10", "1") in row_types
        assert ("10", "4") in row_types
        assert ("20", "1") in row_types
        assert ("20", "4") in row_types

    def test_quantity_format(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Quantity should be formatted with 2 decimal places."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        qty = root.find(".//Row[@RowType='1']/Quantity")
        assert qty is not None
        assert qty.text == "96.00"

    def test_delivery_period(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """DeliveryPeriod should be populated from line item delivery_date."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        dp = root.find(".//Row[@RowType='1']/DeliveryPeriod")
        assert dp is not None
        assert dp.text == "2026-02-17"

    def test_setup_is_empty(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Setup should be empty (self-closing) per ERP reference."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        setup = root.find(".//Row[@RowType='1']/Setup")
        assert setup is not None
        assert setup.text is None

    def test_each_values(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Each: populated for RowType=1, empty for RowType=4."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        # RowType=1 should have unit price
        each1 = root.find(".//Row[@RowType='1']/Each")
        assert each1.text == "372.97"
        # RowType=4 should be empty
        each4 = root.find(".//Row[@RowType='4']/Each")
        assert each4.text is None

    def test_country_normalization_uppercase(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """SVERIGE should be normalized to Demo Country."""
        sample_order.buyer_country = "SVERIGE"
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        buyer_country = root.find(".//Buyer/Country")
        assert buyer_country is not None
        assert buyer_country.text == "Demo Country"

    def test_buyer_reference(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """BuyerReference should match ERP reference."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        ref = root.find(".//References/BuyerReference")
        assert ref is not None
        assert ref.text == "Marina Thorsén"

    def test_payment_terms(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Payment terms should be included."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        terms = root.find(".//PaymentTerms/TermsOfPaymentDays")
        assert terms is not None
        assert terms.text == "30"

    def test_additional_text_preserves_newlines(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Newlines in additional_text should be preserved in RowType=4."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        row4_text = root.find(".//Row[@RowType='4']/Text")
        assert row4_text is not None
        assert "\n" in row4_text.text
        assert "Dekor W980" in row4_text.text

    def test_order_date(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """OrderDate should match ERP reference."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        od = root.find(".//Terms/OrderDate")
        assert od is not None
        assert od.text == "2026-02-05"

    def test_currency(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Currency should match ERP reference."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        curr = root.find(".//Export/Currency")
        assert curr is not None
        assert curr.text == "SEK"

    def test_part_attributes(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Part element should have correct PartNumber and SupplierPartNumber."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        part = root.find(".//Row[@RowType='1']/Part")
        assert part is not None
        assert part.get("PartNumber") == "101928002070DL"
        assert part.get("SupplierPartNumber") == "HA0413"

    def test_discount_format(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """Discount should preserve sign per ERP reference (-11.34)."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        disc = root.find(".//Row[@RowType='1']/Discount")
        assert disc is not None
        assert disc.text == "-11.34"

    def test_inco_term_space(
        self, xml_service: XMLGeneratorService, sample_order: Order
    ) -> None:
        """IncoTermCombiTerm should contain a single space per ERP reference."""
        xml_string = xml_service.generate(sample_order)
        root = etree.fromstring(xml_string.encode("utf-8"))
        inco = root.find(".//DeliveryTerms/IncoTermCombiTerm")
        assert inco is not None
        assert inco.text == " "
