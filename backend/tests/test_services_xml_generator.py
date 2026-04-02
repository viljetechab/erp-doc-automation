"""Unit tests for the XML Generator Service.

Tests output correctness, environment variables fallbacks, and handling of blank fields.
"""

import pytest
from lxml import etree
import xml.etree.ElementTree as ET

from app.services.xml_generator import XMLGeneratorService, _normalize_country
from app.core.exceptions import XMLGenerationError


def test_normalize_country():
    assert _normalize_country("SVERIGE") == "Demo Country"
    assert _normalize_country("SWEDEN") == "Demo Country"
    assert _normalize_country("GERMANY") == "Tyskland"
    assert _normalize_country("random country") == "Random Country"
    assert _normalize_country("") == ""
    assert _normalize_country(None) == ""


def test_xml_generator_success_extracted_supplier(mock_settings, sample_order):
    """Test generating XML when supplier is successfully extracted from PDF."""
    generator = XMLGeneratorService(mock_settings)
    xml_string = generator.generate(sample_order)

    assert "<?xml version='1.0' encoding='utf-8'?>" in xml_string
    assert "<ORDERS420 SoftwareManufacturer" in xml_string
    
    # Parse to assert structure
    root = ET.fromstring(xml_string.encode('utf-8'))
    
    # Assert Order Head Supplier
    supplier = root.find(".//Supplier")
    assert supplier is not None
    assert supplier.attrib["SupplierCodeEdi"] == "DL123"
    assert supplier.find("Name").text == "Demo Supplier Ltd"
    
    # Assert Row count (2 rows: RowType 1 and RowType 4)
    rows = root.findall(".//Row")
    assert len(rows) == 2
    assert rows[0].attrib["RowType"] == "1"
    assert rows[1].attrib["RowType"] == "4"
    assert rows[1].find(".//Text").text == "Dekor W980 ST2 Platinum White\n2800;2070\nNCS 0502-g50y"


def test_xml_generator_supplier_fallback(mock_settings, sample_order):
    """Test generating XML when supplier is missing and env vars are used."""
    generator = XMLGeneratorService(mock_settings)
    
    # Clear supplier on the order object
    sample_order.supplier_name = None
    sample_order.supplier_edi_code = None
    sample_order.supplier_street = None
    sample_order.supplier_zip_city = None
    sample_order.supplier_country = None
    
    xml_string = generator.generate(sample_order)
    root = ET.fromstring(xml_string.encode('utf-8'))
    
    supplier = root.find(".//Supplier")
    # Should fallback to mock_settings
    assert supplier.find("Name").text == "Test Supplier"
    assert supplier.attrib["SupplierCodeEdi"] == "1234"
    

def test_xml_generator_company_address_flag_inference(mock_settings, sample_order):
    """Test inference of CompanyAdressFlag when delivery_is_buyer_address is None."""
    generator = XMLGeneratorService(mock_settings)
    
    # Not set explicitly, matching names.
    sample_order.delivery_is_buyer_address = None
    sample_order.delivery_name = "Careco Inredningar AB"
    sample_order.buyer_name = "Careco Inredningar AB"
    
    xml_1 = generator.generate(sample_order)
    root_1 = ET.fromstring(xml_1.encode('utf-8'))
    assert root_1.find(".//CompanyAdressFlag").text == "1"

    # Not set explicitly, differing names.
    sample_order.delivery_name = "Some Other Place"
    xml_2 = generator.generate(sample_order)
    root_2 = ET.fromstring(xml_2.encode('utf-8'))
    assert root_2.find(".//CompanyAdressFlag").text == "0"


def test_xml_generator_escapes_special_chars(mock_settings, sample_order):
    """Test that XML generation properly escapes special characters."""
    generator = XMLGeneratorService(mock_settings)
    
    sample_order.buyer_name = "Tom & Jerry <Company>"
    xml_string = generator.generate(sample_order)
    
    assert "Tom &amp; Jerry &lt;Company&gt;" in xml_string


from unittest.mock import patch
def test_xml_generator_error_handling(mock_settings, sample_order):
    """Test throwing XMLGenerationError for invalid input."""
    generator = XMLGeneratorService(mock_settings)
    
    with patch.object(generator, "_build_xml", side_effect=Exception("Fake error")):
        with pytest.raises(XMLGenerationError):
            generator.generate(sample_order)
