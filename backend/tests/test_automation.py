"""
Tests for automation engine and API endpoints.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.automation_engine import _evaluate_keywords_trigger, _substitute_markers


class TestKeywordsTrigger:
    def test_single_match(self):
        config = {"keywords": ["preu", "pressupost"]}
        assert _evaluate_keywords_trigger(config, "quin preu te?") is True

    def test_no_match(self):
        config = {"keywords": ["preu", "pressupost"]}
        assert _evaluate_keywords_trigger(config, "hola que tal") is False

    def test_empty_body(self):
        config = {"keywords": ["preu"]}
        assert _evaluate_keywords_trigger(config, "") is False

    def test_empty_keywords(self):
        config = {"keywords": []}
        assert _evaluate_keywords_trigger(config, "preu") is False

    def test_case_insensitive(self):
        config = {"keywords": ["preu"]}
        assert _evaluate_keywords_trigger(config, "PREU si us plau") is True

    def test_partial_match(self):
        config = {"keywords": ["preu"]}
        assert _evaluate_keywords_trigger(config, "quin pressupost teniu?") is False


class TestMarkerSubstitution:
    @pytest.mark.asyncio
    async def test_agent_name_default(self):
        """When no supabase, defaults to 'el nostre equip'"""
        result = await _substitute_markers(
            "Hola {{agent_name}}", None, None, {}, None
        )
        assert "el nostre equip" in result

    @pytest.mark.asyncio
    async def test_no_markers(self):
        result = await _substitute_markers(
            "Hola, com et podem ajudar?", None, None, {}, None
        )
        assert result == "Hola, com et podem ajudar?"

    @pytest.mark.asyncio
    async def test_business_name_default(self):
        result = await _substitute_markers(
            "Benvingut a {{business_name}}", None, None, {}, None
        )
        assert "el nostre equip" in result

    @pytest.mark.asyncio
    async def test_contact_name_from_phone(self):
        result = await _substitute_markers(
            "Hola {{contact_name}}", None, None, {"phone": "34606919022"}, None
        )
        assert "34606919022" in result
