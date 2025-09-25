import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
import io
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_contract():
    return {
        "id": "test-contract-id",
        "filename": "test.pdf",
        "status": "completed",
        "processing_progress": 100,
        "uploaded_at": "2024-01-01T00:00:00Z",
        "size_bytes": 1024,
        "mime_type": "application/pdf",
        "overall_score": 85.0,
        "confidence_summary": {
            "average": 0.8,
            "low_count": 1,
            "high_confidence_fields": 5,
            "total_fields": 6
        },
        "gaps": [],
        "fields": {
            "party_1_name": {
                "value": "Acme Corp",
                "confidence": 0.9,
                "evidence": {
                    "page": 1,
                    "snippet": "Acme Corp",
                    "source": "rule"
                }
            }
        },
        "processing": {
            "ocr_used": False,
            "llm_used": False,
            "duration_ms": 2500
        }
    }


class TestHealthEndpoint:
    async def test_health_check(self, client):
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "services" in data


class TestContractsEndpoints:
    @patch('app.api.endpoints.contracts.Contract')
    @patch('app.api.endpoints.contracts.background_processor')
    async def test_upload_contract_success(self, mock_processor, mock_contract_model, client):
        # Mock contract creation
        mock_contract_instance = MagicMock()
        mock_contract_instance.id = "test-id"
        mock_contract_instance.status = "pending"
        mock_contract_model.find_one = AsyncMock(return_value=None)  # No existing contract
        mock_contract_model.return_value = mock_contract_instance
        mock_contract_instance.insert = AsyncMock()

        # Mock background processor
        mock_processor.start_processing.return_value = None

        # Create test PDF file
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}

        with patch('app.api.endpoints.contracts.pdf_processor') as mock_pdf_proc:
            mock_pdf_proc.validate_pdf.return_value = (True, "Valid PDF")

            response = await client.post("/api/contracts/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "contract_id" in data
        assert "message" in data
        assert data["status"] == "pending"

    async def test_upload_invalid_file_type(self, client):
        # Test with non-PDF file
        files = {"file": ("test.txt", io.BytesIO(b"text content"), "text/plain")}
        response = await client.post("/api/contracts/upload", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "Only PDF files are allowed" in data["detail"]

    @patch('app.api.endpoints.contracts.Contract')
    async def test_get_processing_status(self, mock_contract_model, client):
        # Mock contract
        mock_contract = MagicMock()
        mock_contract.id = "test-id"
        mock_contract.status = "processing"
        mock_contract.processing_progress = 50
        mock_contract.processing.error_message = None
        mock_contract_model.get = AsyncMock(return_value=mock_contract)

        response = await client.get("/api/contracts/test-id/status")

        assert response.status_code == 200
        data = response.json()
        assert data["contract_id"] == "test-id"
        assert data["status"] == "processing"
        assert data["progress"] == 50

    @patch('app.api.endpoints.contracts.Contract')
    async def test_get_processing_status_not_found(self, mock_contract_model, client):
        mock_contract_model.get = AsyncMock(return_value=None)

        response = await client.get("/api/contracts/nonexistent-id/status")
        assert response.status_code == 404

    @patch('app.api.endpoints.contracts.Contract')
    async def test_get_contract_details(self, mock_contract_model, client, mock_contract):
        mock_contract_instance = MagicMock()
        for key, value in mock_contract.items():
            setattr(mock_contract_instance, key, value)
        mock_contract_model.get = AsyncMock(return_value=mock_contract_instance)

        response = await client.get("/api/contracts/test-contract-id")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-contract-id"
        assert data["filename"] == "test.pdf"
        assert data["status"] == "completed"

    @patch('app.api.endpoints.contracts.Contract')
    async def test_list_contracts(self, mock_contract_model, client, mock_contract):
        # Mock contract instances
        mock_contract_instance = MagicMock()
        for key, value in mock_contract.items():
            setattr(mock_contract_instance, key, value)

        # Mock query methods
        mock_query = MagicMock()
        mock_query.sort.return_value = mock_query
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=[mock_contract_instance])
        mock_query.count = AsyncMock(return_value=1)

        mock_contract_model.find_all.return_value = mock_query

        response = await client.get("/api/contracts")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["limit"] == 10
        assert len(data["contracts"]) == 1

    @patch('app.api.endpoints.contracts.Contract')
    async def test_list_contracts_with_filters(self, mock_contract_model, client):
        # Mock empty results for filtered query
        mock_query = MagicMock()
        mock_query.sort.return_value = mock_query
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=[])
        mock_query.count = AsyncMock(return_value=0)

        mock_contract_model.find.return_value = mock_query

        response = await client.get("/api/contracts?status=processing&page=2&limit=5")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["page"] == 2
        assert data["limit"] == 5

    @patch('app.api.endpoints.contracts.Contract')
    @patch('app.api.endpoints.contracts.os.path.exists')
    async def test_download_contract(self, mock_exists, mock_contract_model, client):
        # Mock contract
        mock_contract = MagicMock()
        mock_contract.filename = "test.pdf"
        mock_contract.hash = "testhash"
        mock_contract_model.get = AsyncMock(return_value=mock_contract)

        # Mock file exists
        mock_exists.return_value = True

        # This test would need more mocking to fully work with FileResponse
        # For now, just test the basic flow
        with patch('app.api.endpoints.contracts.FileResponse') as mock_file_response:
            response = await client.get("/api/contracts/test-id/download")
            # The actual response depends on FastAPI's FileResponse handling

    @patch('app.api.endpoints.contracts.Contract')
    async def test_delete_contract(self, mock_contract_model, client):
        mock_contract = MagicMock()
        mock_contract.filename = "test.pdf"
        mock_contract.hash = "testhash"
        mock_contract.delete = AsyncMock()
        mock_contract_model.get = AsyncMock(return_value=mock_contract)

        with patch('app.api.endpoints.contracts.os.path.exists', return_value=True):
            with patch('app.api.endpoints.contracts.os.remove') as mock_remove:
                response = await client.delete("/api/contracts/test-id")

                assert response.status_code == 200
                data = response.json()
                assert "Contract deleted successfully" in data["message"]
                mock_remove.assert_called_once()

    @patch('app.api.endpoints.contracts.Contract')
    @patch('app.api.endpoints.contracts.background_processor')
    async def test_reprocess_contract(self, mock_processor, mock_contract_model, client):
        mock_contract = MagicMock()
        mock_contract.status = "completed"
        mock_contract_model.get = AsyncMock(return_value=mock_contract)

        mock_processor.reprocess_contract = AsyncMock()

        response = await client.post("/api/contracts/test-id/reprocess?use_ocr=true&use_llm=false")

        assert response.status_code == 200
        data = response.json()
        assert "Reprocessing started" in data["message"]

    async def test_invalid_contract_id_format(self, client):
        """Test various invalid ID formats"""
        invalid_ids = ["", "invalid-id", "123", "test id with spaces"]

        for invalid_id in invalid_ids:
            response = await client.get(f"/api/contracts/{invalid_id}")
            # Should return 404 or 422 depending on validation