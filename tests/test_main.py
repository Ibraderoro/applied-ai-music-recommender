import logging

import pytest

import src.main as main_module
from src.main import run_pipeline


@pytest.fixture(autouse=True)
def isolate_logging(tmp_path):
    """run_pipeline logs to the real system_execution.log via module-level
    logging.basicConfig; redirect the root logger's handlers to a scratch
    file for the duration of each test so tests never mutate the tracked
    project log file."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    root.handlers = []
    root.addHandler(logging.FileHandler(tmp_path / "test_execution.log"))
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)


class FakeAgent:
    def __init__(self, parse_result=None, explanation_text="fake explanation"):
        self.parse_result = parse_result or {}
        self.explanation_text = explanation_text
        self.synthesize_calls = []

    def parse_user_query(self, query):
        return self.parse_result

    def synthesize_explanation(self, query, recs):
        self.synthesize_calls.append((query, recs))
        return self.explanation_text


class FakeRetriever:
    def __init__(self, dataset_path, tracks=None):
        self.dataset_path = dataset_path
        self._tracks = tracks if tracks is not None else []

    def retrieve_top_tracks(self, constraints, top_k=3):
        return self._tracks


def test_command_injection_query_is_blocked_before_retrieval(capsys):
    run_pipeline("sudo rm -rf / everything", agent=None)
    captured = capsys.readouterr()
    assert "[Input Guardrail Blocked]" in captured.out
    assert "Recommended Playlist" not in captured.out


def test_out_of_scope_query_is_blocked_before_retrieval(capsys):
    run_pipeline("what stock should I buy today?", agent=None)
    captured = capsys.readouterr()
    assert "[Input Guardrail Blocked]" in captured.out


def test_valid_query_without_agent_uses_keyword_fallback_and_completes(capsys):
    run_pipeline("Give me some upbeat pop music", agent=None)
    captured = capsys.readouterr()
    assert "[Input Guardrail Blocked]" not in captured.out
    assert "[Output Guardrail Blocked]" not in captured.out
    assert "Recommended Playlist" in captured.out
    # No agent means the static fallback explanation is used, which echoes
    # the parsed constraints dict directly.
    assert "'genre': 'pop'" in captured.out


@pytest.mark.parametrize("query,expected_genre", [
    ("something lofi for studying", "lofi"),
    ("lo-fi beats please", "lofi"),
    ("play me some rock", "rock"),
])
def test_keyword_fallback_extracts_expected_genre(capsys, query, expected_genre):
    run_pipeline(query, agent=None)
    captured = capsys.readouterr()
    assert f"'genre': '{expected_genre}'" in captured.out


def test_agent_constraints_trigger_rag_explanation(monkeypatch, capsys):
    fake_agent = FakeAgent(
        parse_result={"genre": "pop", "target_energy": 0.8},
        explanation_text="These upbeat tracks match your workout energy.",
    )
    run_pipeline("upbeat workout music", fake_agent)
    captured = capsys.readouterr()

    assert len(fake_agent.synthesize_calls) == 1
    called_query, called_recs = fake_agent.synthesize_calls[0]
    assert called_query == "upbeat workout music"
    assert len(called_recs) > 0
    assert "These upbeat tracks match your workout energy." in captured.out


def test_agent_constraints_without_target_energy_uses_static_explanation(capsys):
    fake_agent = FakeAgent(parse_result={"genre": "pop"})
    run_pipeline("some pop music", fake_agent)
    captured = capsys.readouterr()

    assert len(fake_agent.synthesize_calls) == 0
    assert "'genre': 'pop'" in captured.out


def test_output_guardrail_blocks_recommendations_not_in_dataset(monkeypatch, capsys):
    bogus_track = {
        "title": "Totally Fabricated Track",
        "artist": "Nobody",
        "genre": "x",
        "mood": "y",
        "tempo_bpm": 100,
        "energy": 0.5,
        "valence": 0.5,
        "danceability": 0.5,
    }
    monkeypatch.setattr(
        main_module,
        "TrackRetriever",
        lambda dataset_path: FakeRetriever(dataset_path, tracks=[bogus_track]),
    )

    run_pipeline("some pop music", agent=None)
    captured = capsys.readouterr()

    assert "[Output Guardrail Blocked]" in captured.out
    assert "Recommended Playlist" not in captured.out


def test_output_guardrail_blocks_when_retriever_returns_nothing(monkeypatch, capsys):
    monkeypatch.setattr(
        main_module,
        "TrackRetriever",
        lambda dataset_path: FakeRetriever(dataset_path, tracks=[]),
    )

    run_pipeline("some pop music", agent=None)
    captured = capsys.readouterr()

    assert "[Output Guardrail Blocked]" in captured.out
    assert "I do not know based on the available dataset." in captured.out
