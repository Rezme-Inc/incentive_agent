"""
Integration tests for API endpoints
"""
import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for health check endpoint"""

    @pytest.mark.asyncio
    async def test_health_check(self, async_client: AsyncClient):
        """Test health endpoint returns healthy status"""
        response = await async_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data


class TestDiscoveryEndpoints:
    """Tests for discovery endpoints"""

    @pytest.mark.asyncio
    async def test_discover_returns_session_id(self, async_client: AsyncClient, sample_address):
        """Test that discover endpoint returns a session ID"""
        response = await async_client.post(
            "/api/v1/incentives/discover",
            json={"address": sample_address}
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "started"

    @pytest.mark.asyncio
    async def test_status_endpoint(self, async_client: AsyncClient, sample_address):
        """Test that status endpoint works after discovery starts"""
        # Start discovery
        discover_response = await async_client.post(
            "/api/v1/incentives/discover",
            json={"address": sample_address}
        )
        session_id = discover_response.json()["session_id"]

        # Check status
        status_response = await async_client.get(
            f"/api/v1/incentives/{session_id}/status"
        )

        assert status_response.status_code == 200
        data = status_response.json()
        assert data["session_id"] == session_id
        assert "status" in data
        assert "current_step" in data

    @pytest.mark.asyncio
    async def test_invalid_session_returns_404(self, async_client: AsyncClient):
        """Test that invalid session ID returns 404"""
        response = await async_client.get(
            "/api/v1/incentives/invalid-session-id/status"
        )

        assert response.status_code == 404
