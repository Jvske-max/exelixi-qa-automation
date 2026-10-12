"""Tests for OCR API service integration."""
import httpx
import pytest

from apiclients.ocr_client import OCRClient
from mocks.ocr_service import app


@pytest.fixture
def ocr_client():
    """Fixture providing an OCRClient wired to the in-memory FastAPI mock application."""
    client = OCRClient(app=app)
    yield client
    client.close()


@pytest.mark.api
@pytest.mark.smoke
def test_ocr_extract_document_success(ocr_client: OCRClient):
    """Positive test: Verify successful document extraction with valid data and high confidence."""
    response = ocr_client.extract_document()

    assert response.status_code == 200
    payload = response.json()
    assert "cedula" in payload
    assert payload["cedula"].startswith("V-")
    assert payload.get("confianza", 0.0) >= 0.9


@pytest.mark.api
@pytest.mark.smoke
def test_ocr_extract_illegible_document_negative(ocr_client: OCRClient):
    """Negative test: Verify that an illegible document returns 422 Unprocessable Entity."""
    response = ocr_client.extract_illegible_document()

    assert response.status_code == 422
    payload = response.json()
    assert "detail" in payload
    assert "ilegible" in payload["detail"].lower() or "no se pudo" in payload["detail"].lower()


@pytest.mark.api
@pytest.mark.smoke
def test_ocr_extract_timeout_negative(ocr_client: OCRClient):
    """Negative test: Verify that a slow provider properly triggers client timeout without hanging."""
    with pytest.raises(httpx.TimeoutException):
        ocr_client.extract_with_timeout(timeout=0.1)
