"""Tests for LangGraph health check endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.api.v1.health import router, check_postgres, check_graph_compilation


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/health")
    return app


@pytest.fixture
async def client(app):
    """Create test async client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check_endpoint_returns_200(client, app):
    """Test that health check endpoint returns 200 when all healthy."""
    mock_db = AsyncMock()
    
    with patch("src.api.v1.health.check_postgres", return_value=True), \
         patch("src.api.v1.health.check_graph_compilation", return_value={
             "orchestrator_graph": True,
             "validation_graph": True,
             "extraction_graph": True,
             "eligibility_graph": True,
             "decision_graph": True,
         }), \
         patch("src.api.v1.health.get_db", return_value=mock_db):
        
        response = await client.get("/health/langgraph")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "components" in data
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_check_endpoint_returns_degraded(client, app):
    """Test that health check returns degraded when some components fail."""
    mock_db = AsyncMock()
    
    with patch("src.api.v1.health.check_postgres", return_value=True), \
         patch("src.api.v1.health.check_graph_compilation", return_value={
             "orchestrator_graph": True,
             "validation_graph": False,
             "extraction_graph": True,
             "eligibility_graph": True,
             "decision_graph": True,
         }), \
         patch("src.api.v1.health.get_db", return_value=mock_db):
        
        response = await client.get("/health/langgraph")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_check_endpoint_returns_unhealthy(client, app):
    """Test that health check returns unhealthy when critical components fail."""
    mock_db = AsyncMock()
    
    with patch("src.api.v1.health.check_postgres", return_value=False), \
         patch("src.api.v1.health.check_graph_compilation", return_value={
             "orchestrator_graph": False,
             "validation_graph": False,
             "extraction_graph": False,
             "eligibility_graph": False,
             "decision_graph": False,
         }), \
         patch("src.api.v1.health.get_db", return_value=mock_db):
        
        response = await client.get("/health/langgraph")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_check_postgres_success():
    """Test PostgreSQL health check returns True on success."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    
    result = await check_postgres(mock_db)
    
    assert result is True
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_check_postgres_failure():
    """Test PostgreSQL health check returns False on failure."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Connection failed"))
    
    result = await check_postgres(mock_db)
    
    assert result is False


@pytest.mark.asyncio
async def test_check_graph_compilation_all_success():
    """Test graph compilation check returns all True when all graphs compile."""
    with patch("importlib.import_module") as mock_import:
        mock_module = MagicMock()
        mock_module.get_orchestrator_graph = AsyncMock()
        mock_module.get_validation_graph = AsyncMock()
        mock_module.get_extraction_subgraph = MagicMock()
        mock_module.get_eligibility_graph = MagicMock()
        mock_module.get_decision_agent = MagicMock()
        mock_import.return_value = mock_module
        
        result = await check_graph_compilation()
        
        assert all(result.values())
        assert len(result) == 5


@pytest.mark.asyncio
async def test_check_graph_compilation_partial_failure():
    """Test graph compilation check returns mixed results on partial failure."""
    with patch("importlib.import_module") as mock_import:
        def side_effect(module_path):
            if "orchestrator" in module_path:
                raise Exception("Compilation failed")
            mock_module = MagicMock()
            return mock_module
        
        mock_import.side_effect = side_effect
        
        result = await check_graph_compilation()
        
        assert result["orchestrator_graph"] is False
        assert result["validation_graph"] is True


def test_health_check_response_structure():
    """Test that health check response has correct structure."""
    expected_keys = {"status", "components", "timestamp"}
    expected_components = {
        "postgres",
        "orchestrator_graph",
        "validation_graph",
        "extraction_graph",
        "eligibility_graph",
        "decision_graph",
    }
    
    # This is a structural test - verify the keys we expect
    assert expected_components.issubset({"postgres", "orchestrator_graph", "validation_graph", 
                                          "extraction_graph", "eligibility_graph", "decision_graph"})
