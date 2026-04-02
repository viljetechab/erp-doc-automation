"""PDF extraction service — converts PDF to images, sends to GPT-4o Vision, returns structured data.

Pipeline:
    PDF file → magic-bytes check → PyMuPDF renders pages as images → base64 encode →
    OpenAI GPT-4o Vision API (standard or Azure) → JSON response → Pydantic validation → ExtractedOrderData

Provider selection (auto-detected from config):
    - AZURE_OPENAI_ENDPOINT is set  →  AsyncAzureOpenAI client
    - AZURE_OPENAI_ENDPOINT is blank →  AsyncOpenAI client (standard)

Both clients share the identical call interface after __init__, so all extraction
logic is untouched regardless of which provider is active.

Quality notes (unchanged):
    - Magic bytes validation — crashes on non-PDF files are clean 400 errors
    - Page cap at MAX_PAGES (10) — prevents hanging on catalogue uploads
    - response_format=json_object — forces clean JSON, no markdown fence stripping
    - DPI, image size, detail level kept at original quality settings
      because this processes financial invoices where digit accuracy is critical
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import fitz  # PyMuPDF
import structlog
from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion_content_part_param import (
    ChatCompletionContentPartParam,
)
from openai.types.chat.chat_completion_content_part_image_param import (
    ChatCompletionContentPartImageParam,
)
from openai.types.chat.chat_completion_content_part_text_param import (
    ChatCompletionContentPartTextParam,
)

from app.config import Settings
from app.core.exceptions import ExtractionError, FileValidationError
from app.prompts.order_extraction import SYSTEM_PROMPT, USER_PROMPT
from app.schemas.extraction import ExtractedOrderData

logger = structlog.get_logger(__name__)

# ── Tuning constants ──────────────────────────────────────────────────────────

# 300 DPI — upgraded from 200. At 200 DPI, small characters like l/1/I, B/8,
# C/0 are visually ambiguous for GPT-4o Vision. 300 DPI renders sub-pixel
# details (serifs, stroke width) that distinguish these glyphs reliably.
# Impact: PNG size increases ~2.25x but accuracy gain on financial data is
# critical (part numbers, postal codes, product names, delivery dates).
PDF_RENDER_DPI = 300

# Minimum character count per page to consider the text layer usable.
# Pages with fewer characters are likely scanned images with no real text layer.
MIN_TEXT_CHARS_PER_PAGE = 50

# Hard cap on pages sent to the Vision API.
# Real purchase orders are 1-5 pages. This only fires if someone accidentally
# uploads a 30-page product catalogue — prevents a multi-minute API hang.
MAX_PAGES = 10


class PDFExtractionService:
    """Orchestrates PDF → structured order data extraction via OpenAI Vision.

    Supports both standard OpenAI and Azure OpenAI. The active provider is
    determined by Settings.use_azure_openai (auto-detected from config).
    All extraction logic is identical for both providers.
    """

    def __init__(self, settings: Settings) -> None:
        if settings.use_azure_openai:
            # ── Azure OpenAI ──────────────────────────────────────────────
            # AsyncAzureOpenAI accepts the same call interface as AsyncOpenAI.
            # The deployment name is passed as the `model` parameter on every
            # chat.completions.create() call — Azure routes it to the correct
            # deployed model internally.
            self._client: AsyncOpenAI = AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
                timeout=300.0,
            )
            self._model = settings.azure_openai_deployment
            logger.info(
                "pdf_extraction_provider_azure",
                endpoint=settings.azure_openai_endpoint,
                deployment=settings.azure_openai_deployment,
                api_version=settings.azure_openai_api_version,
            )
        else:
            # ── Standard OpenAI ───────────────────────────────────────────
            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=300.0,
            )
            self._model = settings.openai_model
            logger.info("pdf_extraction_provider_openai", model=settings.openai_model)

        self._max_tokens = settings.openai_max_tokens

    async def extract(self, pdf_path: str | Path) -> ExtractedOrderData:
        """Extract structured order data from a PDF file.

        Args:
            pdf_path: Absolute path to the PDF file on disk.

        Returns:
            Validated ExtractedOrderData with all extracted fields.

        Raises:
            FileValidationError: If the file is not a valid PDF.
            ExtractionError: If rendering, the API call, or schema parsing fails.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise ExtractionError(f"PDF file not found: {pdf_path}")

        # Validate PDF magic bytes — catches renamed non-PDF files before fitz sees them
        self._validate_pdf_magic_bytes(pdf_path)

        logger.info("extraction_started", pdf_path=str(pdf_path))

        # Step 1a: Extract raw text layer — character-perfect for text-based PDFs.
        # This is the primary defence against B/8, 0/C, l/1 vision confusions.
        # Returns None if the PDF has no usable text layer (scanned image PDFs).
        pdf_text_layer = self._pdf_to_text(pdf_path)
        if pdf_text_layer:
            logger.info("pdf_text_layer_extracted", char_count=len(pdf_text_layer))
        else:
            logger.info("pdf_text_layer_unavailable_falling_back_to_vision_only")

        # Step 1b: Convert PDF pages to base64-encoded images
        page_images = self._pdf_to_base64_images(pdf_path)
        if not page_images:
            raise ExtractionError("PDF contains no renderable pages")

        logger.info("pdf_pages_rendered", page_count=len(page_images))

        # Step 2: Call OpenAI GPT-4o Vision API
        raw_json = await self._call_openai(page_images, pdf_text_layer)

        # Step 3: Parse and validate the response
        extracted_data = self._parse_response(raw_json)

        logger.info(
            "extraction_completed",
            order_number=extracted_data.order_number,
            line_item_count=len(extracted_data.line_items),
        )

        return extracted_data

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _validate_pdf_magic_bytes(pdf_path: Path) -> None:
        """Read the first 5 bytes and confirm the file starts with '%PDF-'.

        This catches renamed images, Office docs, or corrupted files before
        PyMuPDF ever tries to open them, preventing cryptic fitz crashes.

        Raises:
            FileValidationError: If the file doesn't carry a PDF magic header.
        """
        try:
            with pdf_path.open("rb") as f:
                header = f.read(5)
        except OSError as exc:
            raise FileValidationError(f"Cannot read uploaded file: {exc}") from exc

        if header != b"%PDF-":
            raise FileValidationError(
                "The uploaded file is not a valid PDF. "
                "Only genuine PDF files are accepted (file must start with '%PDF-')."
            )

    def _pdf_to_base64_images(self, pdf_path: Path) -> list[str]:
        """Convert each page of a PDF to a base64-encoded PNG string.

        Uses PyMuPDF (fitz) for rendering at full 300 DPI.
        PNG (lossless) is kept — JPEG would introduce compression artefacts
        that can distort digits in financial tables.
        Caps at MAX_PAGES to avoid hanging on accidentally uploaded catalogues.
        """
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as exc:
            raise FileValidationError(f"Invalid or corrupted PDF file: {exc}") from exc

        total_pages = len(doc)
        pages_to_render = min(total_pages, MAX_PAGES)

        if total_pages > MAX_PAGES:
            logger.warning(
                "pdf_page_count_exceeds_limit",
                total_pages=total_pages,
                pages_rendered=pages_to_render,
                max_pages=MAX_PAGES,
            )

        images: list[str] = []
        try:
            matrix = fitz.Matrix(PDF_RENDER_DPI / 72, PDF_RENDER_DPI / 72)
            for page_num in range(pages_to_render):
                page = doc[page_num]
                pixmap = page.get_pixmap(matrix=matrix)
                png_bytes = pixmap.tobytes("png")
                b64_string = base64.b64encode(png_bytes).decode("utf-8")
                images.append(b64_string)
        finally:
            doc.close()

        return images

    def _pdf_to_text(self, pdf_path: Path) -> str | None:
        """Extract the raw embedded text layer from the PDF.

        PyMuPDF can pull the actual characters stored in the PDF — not OCR,
        not vision guessing, but the exact bytes the PDF encoder wrote.
        This eliminates B/8, 0/C, l/1 confusions entirely for text-based PDFs.

        Returns:
            Concatenated page text if the document has a usable text layer
            (at least MIN_TEXT_CHARS_PER_PAGE characters on any page).
            Returns None for scanned/image-only PDFs where there is no text layer.
        """
        try:
            doc = fitz.open(str(pdf_path))
        except Exception:
            return None

        pages_text: list[str] = []
        try:
            for page_num in range(min(len(doc), MAX_PAGES)):
                page = doc[page_num]
                # get_text("text") always returns str, but PyMuPDF stubs type it
                # as list | dict | str depending on the output parameter.
                # str() cast gives Pyright the concrete type it needs.
                text: str = str(page.get_text("text"))
                stripped = text.strip()
                if stripped and len(stripped) >= MIN_TEXT_CHARS_PER_PAGE:
                    pages_text.append(f"[Page {page_num + 1}]\n{stripped}")
        finally:
            doc.close()

        if not pages_text:
            return None

        return "\n\n".join(pages_text)

    async def _call_openai(self, page_images: list[str], pdf_text_layer: str | None) -> str:
        """Send page images (and optional text layer) to GPT-4o Vision.

        When the PDF has an embedded text layer we prepend it to the user message
        as the authoritative source for every character. The model is told:
        "trust the text layer — it has no OCR ambiguity". This eliminates
        B/8, 0/C, l/1 misreads that occasionally slip through even with
        prompt-level warnings, because those warnings address vision inference
        whereas the text layer bypasses inference entirely.

        detail: "high" is kept — it tells OpenAI to use full resolution tiles,
        which matters for layout understanding, table structure, and fields
        that may only appear visually (e.g. stamps, handwriting).

        response_format=json_object forces clean JSON output.
        """
        # Build user content: text layer first (ground truth), then images
        content: list[ChatCompletionContentPartParam] = []

        if pdf_text_layer:
            ground_truth_preamble = (
                "IMPORTANT — RAW TEXT LAYER (authoritative source):\n"
                "The following text was extracted directly from the PDF's embedded text layer.\n"
                "It contains the EXACT characters encoded in the file — no OCR, no vision inference.\n"
                "For EVERY field you extract, if the value appears in this text, copy it EXACTLY "
                "as written here. Do NOT substitute characters based on visual appearance.\n"
                "Examples: '20B' in this text means the letter B, not the digit 8. "
                "'20C' means the letter C, not zero.\n\n"
                f"{pdf_text_layer}\n\n"
                "END OF TEXT LAYER — now use the images below for layout context and any fields "
                "not found in the text above."
            )
            content.append(
                ChatCompletionContentPartTextParam(type="text", text=ground_truth_preamble)
            )

        content.append(
            ChatCompletionContentPartTextParam(type="text", text=USER_PROMPT),
        )
        for b64_img in page_images:
            content.append(
                ChatCompletionContentPartImageParam(
                    type="image_url",
                    image_url={
                        "url": f"data:image/png;base64,{b64_img}",
                        "detail": "high",  # Full resolution tiles — required for financial docs
                    },
                )
            )

        # Explicitly typed so Pyright resolves the ChatCompletionMessageParam
        # union correctly instead of inferring dict[str, Unknown].
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=self._max_tokens,
                temperature=0.0,  # Deterministic extraction
                response_format={"type": "json_object"},  # Forces clean JSON — no markdown fences
            )
        except Exception as exc:
            logger.error("openai_api_error", error=str(exc))
            raise ExtractionError(f"OpenAI API call failed: {exc}") from exc

        raw_text = response.choices[0].message.content
        if not raw_text:
            raise ExtractionError("OpenAI returned an empty response")

        return raw_text.strip()

    def _parse_response(self, raw_json: str) -> ExtractedOrderData:
        """Parse the raw JSON string from GPT-4o into a validated Pydantic model.

        response_format=json_object means the response is always clean JSON.
        Markdown fence stripping is kept as a safety net only.
        """
        cleaned = raw_json
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("json_parse_error", raw_response=raw_json[:500])
            raise ExtractionError(
                f"Failed to parse extraction response as JSON: {exc}"
            ) from exc

        try:
            return ExtractedOrderData.model_validate(data)
        except Exception as exc:
            logger.error(
                "schema_validation_error", error=str(exc), raw_data=str(data)[:500]
            )
            raise ExtractionError(
                f"Extraction response failed schema validation: {exc}"
            ) from exc