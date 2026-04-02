"""Unit tests for the PDF Extraction Service.

Includes mocking PyMuPDF (fitz) and the AsyncOpenAI client to simulate
both successful parsing and various failure constraints without real APIs.
"""

import base64
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.pdf_extraction import PDFExtractionService
from app.core.exceptions import FileValidationError, ExtractionError


@pytest.fixture
def extraction_service(mock_settings):
    """Fixture to provide a PDFExtractionService instance without real OpenAI calls."""
    with patch("app.services.pdf_extraction.AsyncOpenAI") as MockClient:
        # Mock API setup
        mock_instance = MockClient.return_value
        mock_instance.chat.completions.create = AsyncMock()
        service = PDFExtractionService(mock_settings)
        service._client = mock_instance
        yield service


def test_validate_pdf_magic_bytes_valid(tmp_path):
    """Test correctly identifying a real PDF by magic bytes."""
    valid_pdf = tmp_path / "test.pdf"
    valid_pdf.write_bytes(b"%PDF-1.4\n...")
    
    # Should not raise exception
    PDFExtractionService._validate_pdf_magic_bytes(valid_pdf)


def test_validate_pdf_magic_bytes_invalid(tmp_path):
    """Test rejecting files that do not start with %PDF- (e.g., zip files)."""
    invalid_file = tmp_path / "fake.pdf"
    invalid_file.write_bytes(b"PK\x03\x04")  # Zip file magic bytes
    
    with pytest.raises(FileValidationError, match="not a valid PDF"):
        PDFExtractionService._validate_pdf_magic_bytes(invalid_file)


def test_validate_pdf_magic_bytes_os_error(tmp_path):
    """Test handling of unreadable files."""
    unreadable = tmp_path / "unreadable.pdf"
    # Do not create the file
    
    with pytest.raises(FileValidationError, match="Cannot read uploaded file"):
        PDFExtractionService._validate_pdf_magic_bytes(unreadable)


@pytest.mark.asyncio
@patch("app.services.pdf_extraction.fitz.open")
async def test_extract_success(mock_fitz_open, extraction_service, sample_extraction_data, tmp_path):
    """Test a fully successful end-to-end extraction."""
    # Build pseudo PDF
    test_pdf = tmp_path / "valid.pdf"
    test_pdf.write_bytes(b"%PDF-1.4...\n")
    
    # Mock PyMuPDF fitz Document and Page
    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 1
    mock_page = MagicMock()
    mock_pixmap = MagicMock()
    mock_pixmap.tobytes.return_value = b"fake_png_data"
    mock_page.get_pixmap.return_value = mock_pixmap
    mock_doc.__getitem__.return_value = mock_page
    mock_fitz_open.return_value = mock_doc
    
    # Mock OpenAI response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(sample_extraction_data)
    extraction_service._client.chat.completions.create.return_value = mock_response

    # Execute
    result = await extraction_service.extract(test_pdf)
    
    # Assert return object is populated properly
    assert result.order_number == "G73216"
    assert result.buyer_name == "Careco Inredningar AB"
    assert len(result.line_items) == 1
    
    # Validate calls
    mock_fitz_open.assert_called_once_with(str(test_pdf))
    extraction_service._client.chat.completions.create.assert_called_once()
    
    kwargs = extraction_service._client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "ZmFrZV9wbmdfZGF0YQ==" in str(kwargs["messages"][1]["content"][1]["image_url"]["url"])


@pytest.mark.asyncio
@patch("app.services.pdf_extraction.fitz.open")
async def test_extract_json_parse_error(mock_fitz_open, extraction_service, tmp_path):
    """Test handling malformed JSON string from OpenAI."""
    test_pdf = tmp_path / "valid.pdf"
    test_pdf.write_bytes(b"%PDF-...\n")
    
    # Mock PyMuPDF fitz Document
    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 1
    mock_page = MagicMock()
    mock_pixmap = MagicMock()
    mock_pixmap.tobytes.return_value = b"fake_png_data"
    mock_page.get_pixmap.return_value = mock_pixmap
    mock_doc.__getitem__.return_value = mock_page
    mock_fitz_open.return_value = mock_doc
    
    # Mock OpenAI response returning malformed json
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"broken": json'
    extraction_service._client.chat.completions.create.return_value = mock_response

    with pytest.raises(ExtractionError, match="Failed to parse extraction response as JSON"):
        await extraction_service.extract(test_pdf)


@pytest.mark.asyncio
@patch("app.services.pdf_extraction.fitz.open")
async def test_extract_schema_validation_error(mock_fitz_open, extraction_service, tmp_path):
    """Test handling invalid payload structure from OpenAI (missing required fields)."""
    test_pdf = tmp_path / "valid.pdf"
    test_pdf.write_bytes(b"%PDF-...\n")
    
    # Mock PyMuPDF
    mock_doc = MagicMock()
    mock_doc.__len__.return_value = 1
    mock_page = MagicMock()
    mock_pixmap = MagicMock()
    mock_pixmap.tobytes.return_value = b"fake_png_data"
    mock_page.get_pixmap.return_value = mock_pixmap
    mock_doc.__getitem__.return_value = mock_page
    mock_fitz_open.return_value = mock_doc
    
    # Mock OpenAI response returning missing required fields
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"line_items": [{"description": "Missing required row number and quantity"}]}'
    extraction_service._client.chat.completions.create.return_value = mock_response

    with pytest.raises(ExtractionError, match="Extraction response failed schema validation"):
        await extraction_service.extract(test_pdf)


@pytest.mark.asyncio
async def test_extract_file_not_found(extraction_service):
    """Test handling a non-existent PDF file path."""
    with pytest.raises(ExtractionError, match="PDF file not found"):
        await extraction_service.extract(Path("/tmp/does_not_exist_at_all.pdf"))
