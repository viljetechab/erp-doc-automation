"""Azure Blob Storage helper — thin wrapper used by the orders pipeline.

When AZURE_STORAGE_CONNECTION_STRING is set, uploaded PDFs are stored in
Azure Blob Storage instead of the local filesystem. Local filesystem
is still used for development (when the connection string is empty).

Blob name == the unique filename generated at upload time (e.g. ``abc123_order.pdf``).
This is what gets stored in Order.source_filepath for blob-backed orders.
"""

from __future__ import annotations

import io

import structlog
from azure.storage.blob import BlobServiceClient, ContainerClient

from app.config import Settings

logger = structlog.get_logger(__name__)


def _get_container(settings: Settings) -> ContainerClient:
    """Return an authenticated ContainerClient."""
    service = BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    )
    return service.get_container_client(settings.azure_storage_container_name)


def upload_blob(settings: Settings, blob_name: str, data: bytes) -> None:
    """Upload *data* to blob storage under *blob_name*, overwriting if it exists."""
    container = _get_container(settings)
    container.upload_blob(name=blob_name, data=data, overwrite=True)
    logger.info("blob_uploaded", blob_name=blob_name, size_bytes=len(data))


def download_blob(settings: Settings, blob_name: str) -> bytes:
    """Download and return the full content of *blob_name*."""
    container = _get_container(settings)
    blob = container.download_blob(blob_name)
    data: bytes = blob.readall()
    logger.info("blob_downloaded", blob_name=blob_name, size_bytes=len(data))
    return data


def download_blob_stream(settings: Settings, blob_name: str) -> io.BytesIO:
    """Download *blob_name* and return a seekable BytesIO stream."""
    return io.BytesIO(download_blob(settings, blob_name))


def delete_blob(settings: Settings, blob_name: str) -> None:
    """Delete *blob_name* from storage (no-op if it does not exist)."""
    try:
        container = _get_container(settings)
        container.delete_blob(blob_name)
        logger.info("blob_deleted", blob_name=blob_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("blob_delete_failed", blob_name=blob_name, error=str(exc))