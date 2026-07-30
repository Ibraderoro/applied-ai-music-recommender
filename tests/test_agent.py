import json
from unittest.mock import MagicMock

import pytest

import src.agent as agent_module
from src.agent import MusicAgent


class FakeResponse:
    def __init__(self, text):
        self.text = text


@pytest.fixture
def api_key_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key")


@pytest.fixture
def fake_client(monkeypatch):
    """Prevents any real network call: genai.Client() always returns this mock."""
    client = MagicMock()
    monkeypatch.setattr(agent_module.genai, "Client", MagicMock(return_value=client))
    return client


class TestMusicAgentInit:
    def test_disables_llm_without_api_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        music_agent = MusicAgent()
        assert music_agent.llm_available is False
        assert music_agent.client is None

    def test_strips_quotes_and_whitespace_from_api_key(self, monkeypatch, fake_client):
        monkeypatch.setenv("GEMINI_API_KEY", '  "wrapped-key"  ')
        MusicAgent()
        agent_module.genai.Client.assert_called_once_with(api_key="wrapped-key")

    def test_initializes_client_successfully(self, api_key_env, fake_client):
        music_agent = MusicAgent()
        assert music_agent.llm_available is True
        assert music_agent.client is fake_client


class TestParseUserQuery:
    def test_parses_valid_json_response(self, api_key_env, fake_client):
        fake_client.models.generate_content.return_value = FakeResponse(
            json.dumps({"genre": "pop", "target_energy": 0.8})
        )
        music_agent = MusicAgent()
        result = music_agent.parse_user_query("upbeat pop for a workout")
        assert result == {"genre": "pop", "target_energy": 0.8}

    def test_strips_markdown_code_fences(self, api_key_env, fake_client):
        fake_client.models.generate_content.return_value = FakeResponse(
            "```json\n{\"genre\": \"lofi\"}\n```"
        )
        music_agent = MusicAgent()
        result = music_agent.parse_user_query("chill lofi")
        assert result == {"genre": "lofi"}

    def test_disables_llm_on_exception_and_returns_empty_dict(self, api_key_env, fake_client, capsys):
        fake_client.models.generate_content.side_effect = RuntimeError("network down")
        music_agent = MusicAgent()
        result = music_agent.parse_user_query("anything")
        assert result == {}
        assert music_agent.llm_available is False
        captured = capsys.readouterr()
        assert "Gemini call failed" in captured.out

    def test_skips_call_entirely_once_llm_disabled(self, api_key_env, fake_client):
        music_agent = MusicAgent()
        music_agent.llm_available = False
        result = music_agent.parse_user_query("anything")
        assert result == {}
        fake_client.models.generate_content.assert_not_called()

    def test_invalid_json_disables_llm_and_returns_empty_dict(self, api_key_env, fake_client):
        fake_client.models.generate_content.return_value = FakeResponse("not json at all")
        music_agent = MusicAgent()
        result = music_agent.parse_user_query("garbled")
        assert result == {}
        assert music_agent.llm_available is False


class TestSynthesizeExplanation:
    def test_returns_stripped_llm_text_on_success(self, api_key_env, fake_client):
        fake_client.models.generate_content.return_value = FakeResponse(
            "  These tracks match your upbeat mood.  "
        )
        music_agent = MusicAgent()
        recs = [{"title": "Sunrise City", "artist": "Neon Echo", "genre": "pop", "mood": "happy"}]
        explanation = music_agent.synthesize_explanation("upbeat pop", recs)
        assert explanation == "These tracks match your upbeat mood."

    def test_falls_back_to_default_text_on_exception(self, api_key_env, fake_client):
        fake_client.models.generate_content.side_effect = RuntimeError("boom")
        music_agent = MusicAgent()
        explanation = music_agent.synthesize_explanation("anything", [])
        assert explanation == "Here are your personalized track recommendations based on your preferences."
        assert music_agent.llm_available is False

    def test_skips_call_entirely_once_llm_disabled(self, api_key_env, fake_client):
        music_agent = MusicAgent()
        music_agent.llm_available = False
        explanation = music_agent.synthesize_explanation("anything", [])
        assert explanation == "Here are your personalized track recommendations based on your preferences."
        fake_client.models.generate_content.assert_not_called()
