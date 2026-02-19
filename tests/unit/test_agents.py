"""
Unit tests for agents
"""
import pytest
from unittest.mock import AsyncMock, patch

from src.agents.state import IncentiveState
from src.agents.router import RouterAgent, router_node
from src.agents.validation import join_node, error_checker_node


class TestRouterAgent:
    """Tests for RouterAgent"""

    def test_parse_state_from_address(self):
        """Test state parsing from address"""
        router = RouterAgent()

        # Test with state code
        assert router._parse_state_from_address("123 Main St, Chicago, IL 60601") == "Illinois"
        assert router._parse_state_from_address("456 Oak Ave, Phoenix, AZ 85001") == "Arizona"
        assert router._parse_state_from_address("789 Pine St, Denver, CO 80202") == "Colorado"

    @pytest.mark.asyncio
    async def test_router_node_returns_government_levels(self, sample_state):
        """Test that router_node returns government levels"""
        with patch.object(RouterAgent, 'analyze', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "city_name": "Chicago",
                "county_name": "Cook County",
                "state_name": "Illinois",
                "government_levels": ["federal", "state", "city"]
            }

            result = await router_node(sample_state)

            assert "government_levels" in result
            assert "federal" in result["government_levels"]
            assert "state" in result["government_levels"]


class TestValidationNodes:
    """Tests for validation nodes"""

    @pytest.mark.asyncio
    async def test_join_node_deduplicates(self, sample_state):
        """Test that join_node deduplicates programs (fuzzy match)"""
        sample_state["programs"] = [
            {"program_name": "WOTC", "id": "1", "government_level": "federal", "confidence": "high", "description": ""},
            {"program_name": "wotc", "id": "2", "government_level": "federal", "confidence": "low", "description": ""},
            {"program_name": "Federal Bonding", "id": "3", "government_level": "federal", "confidence": "high", "description": ""}
        ]

        result = await join_node(sample_state)

        assert len(result["merged_programs"]) == 2
        names = [p["program_name"].lower() for p in result["merged_programs"]]
        assert "wotc" in names
        assert "federal bonding" in names

    @pytest.mark.asyncio
    async def test_error_checker_flags_missing_url(self, sample_state):
        """Test that error_checker flags programs without URLs"""
        sample_state["merged_programs"] = [
            {"program_name": "Good Program", "source_url": "https://example.com", "agency": "Test", "benefit_type": "tax_credit"},
            {"program_name": "Bad Program", "source_url": "", "agency": "Test", "benefit_type": "tax_credit"}
        ]

        result = await error_checker_node(sample_state)

        assert len(result["errors"]) >= 1
        assert any(e["error_type"] == "missing_url" for e in result["errors"])

    @pytest.mark.asyncio
    async def test_error_checker_flags_low_confidence(self, sample_state):
        """Test that error_checker flags low confidence programs"""
        sample_state["merged_programs"] = [
            {"program_name": "Uncertain Program", "source_url": "https://example.com", "confidence": "low", "agency": "Test", "benefit_type": "tax_credit"}
        ]

        result = await error_checker_node(sample_state)

        assert any(e["error_type"] == "low_confidence" for e in result["errors"])
