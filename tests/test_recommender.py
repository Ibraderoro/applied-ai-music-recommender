import pytest

from src.recommender import (
    Song,
    UserProfile,
    Recommender,
    score_song,
    recommend_songs,
    load_songs,
)

def make_small_recommender() -> Recommender:
    songs = [
        Song(
            id=1,
            title="Test Pop Track",
            artist="Test Artist",
            genre="pop",
            mood="happy",
            energy=0.8,
            tempo_bpm=120,
            valence=0.9,
            danceability=0.8,
            acousticness=0.2,
        ),
        Song(
            id=2,
            title="Chill Lofi Loop",
            artist="Test Artist",
            genre="lofi",
            mood="chill",
            energy=0.4,
            tempo_bpm=80,
            valence=0.6,
            danceability=0.5,
            acousticness=0.9,
        ),
    ]
    return Recommender(songs)


def test_recommend_returns_songs_sorted_by_score():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert len(results) == 2
    # Starter expectation: the pop, happy, high energy song should score higher
    assert results[0].genre == "pop"
    assert results[0].mood == "happy"


def test_explain_recommendation_returns_non_empty_string():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    song = rec.songs[0]

    explanation = rec.explain_recommendation(user, song)
    assert isinstance(explanation, str)
    assert explanation.strip() != ""


def perfect_match_song(**overrides):
    song = {
        "genre": "pop",
        "mood": "happy",
        "energy": 0.5,
        "valence": 0.5,
        "danceability": 0.5,
        "tempo_bpm": 100.0,
        "acousticness": 0.3,
    }
    song.update(overrides)
    return song


def perfect_match_user_prefs(**overrides):
    prefs = {
        "genre": "pop",
        "mood": "happy",
        "energy": 0.5,
        "valence": 0.5,
        "danceability": 0.5,
        "tempo": 100.0,
        "likes_acoustic": False,
    }
    prefs.update(overrides)
    return prefs


class TestScoreSong:
    def test_perfect_balanced_match_scores_all_bonuses_no_penalties(self):
        score, reasons = score_song(perfect_match_user_prefs(), perfect_match_song(), strategy="balanced")
        assert score == pytest.approx(5.0)  # 3.0 genre + 2.0 mood
        assert "genre match (+3.0)" in reasons
        assert "mood match (+2.0)" in reasons
        assert "energy match (-0.00 penalty)" in reasons
        assert "valence fit (-0.00 penalty)" in reasons
        assert "groove fit (-0.00 penalty)" in reasons
        assert "tempo pace fit (-0.00 penalty)" in reasons

    def test_genre_mismatch_gives_no_bonus_in_balanced_strategy(self):
        song = perfect_match_song(genre="rock")
        score, reasons = score_song(perfect_match_user_prefs(), song, strategy="balanced")
        # No genre bonus, but also no penalty in balanced mode; mood still matches.
        assert score == pytest.approx(2.0)
        assert not any("genre" in r for r in reasons)

    def test_strict_genre_mismatch_applies_lockout_penalty(self):
        song = perfect_match_song(genre="rock")
        score, reasons = score_song(perfect_match_user_prefs(), song, strategy="strict_genre")
        # -50 lockout + 2.0 mood match, no other penalties.
        assert score == pytest.approx(-48.0)
        assert "genre mismatch lockout (-50.0)" in reasons

    def test_strict_genre_match_uses_higher_weight(self):
        score, reasons = score_song(perfect_match_user_prefs(), perfect_match_song(), strategy="strict_genre")
        assert score == pytest.approx(7.0)  # 5.0 genre + 2.0 mood
        assert "genre match (+5.0)" in reasons

    def test_acoustic_strategy_uses_lighter_weights_and_bonus(self):
        song = perfect_match_song(acousticness=0.9)
        prefs = perfect_match_user_prefs(likes_acoustic=True)
        score, reasons = score_song(prefs, song, strategy="acoustic")
        # 1.5 genre + 1.0 mood + 3.0 acoustic bonus
        assert score == pytest.approx(5.5)
        assert "genre match (+1.5)" in reasons
        assert "mood match (+1.0)" in reasons
        assert "acoustic texture match (+3.0)" in reasons

    def test_acoustic_strategy_penalizes_texture_mismatch(self):
        song = perfect_match_song(acousticness=0.9)
        prefs = perfect_match_user_prefs(likes_acoustic=False)
        score, reasons = score_song(prefs, song, strategy="acoustic")
        assert "acoustic mismatch penalty (-1.5)" in reasons
        assert score == pytest.approx(1.5 + 1.0 - 1.5)

    def test_energy_penalty_scales_with_delta(self):
        song = perfect_match_song(energy=0.9)  # delta 0.4 from prefs' 0.5
        score, reasons = score_song(perfect_match_user_prefs(), song, strategy="balanced")
        assert score == pytest.approx(5.0 - (0.4 * 4.0))
        assert "energy drift (-1.60 penalty)" in reasons

    def test_tempo_penalty_is_capped_at_two(self):
        song = perfect_match_song(tempo_bpm=400.0)  # delta 300 from prefs' 100
        score, reasons = score_song(perfect_match_user_prefs(), song, strategy="balanced")
        assert score == pytest.approx(5.0 - 2.0)
        assert not any("tempo pace fit" in r for r in reasons)

    def test_valence_and_danceability_beyond_threshold_omit_fit_reason(self):
        song = perfect_match_song(valence=0.9, danceability=0.9)  # deltas of 0.4 each
        score, reasons = score_song(perfect_match_user_prefs(), song, strategy="balanced")
        expected = 5.0 - (0.4 * 2.0) - (0.4 * 2.0)
        assert score == pytest.approx(expected)
        assert not any("valence fit" in r for r in reasons)
        assert not any("groove fit" in r for r in reasons)


class TestRecommendSongs:
    def _same_artist_songs(self):
        return [
            perfect_match_song(energy=0.5) | {"artist": "Same Artist", "title": "First"},
            perfect_match_song(energy=0.75) | {"artist": "Same Artist", "title": "Second"},
            perfect_match_song(energy=1.0) | {"artist": "Same Artist", "title": "Third"},
        ]

    def test_applies_progressive_fairness_penalty_per_artist(self):
        songs = self._same_artist_songs()
        results = recommend_songs(perfect_match_user_prefs(), songs, k=3, strategy="balanced")

        titles_and_scores = [(song["title"], score) for song, score, _ in results]
        assert titles_and_scores == [
            ("First", pytest.approx(5.0)),
            ("Second", pytest.approx(2.5)),   # 4.0 baseline - 1.50 penalty
            ("Third", pytest.approx(0.0)),    # 3.0 baseline - 3.00 penalty
        ]
        assert "artist saturation penalty" in results[1][2]
        assert "artist saturation penalty" in results[2][2]
        assert "artist saturation penalty" not in results[0][2]

    def test_respects_k_truncation(self):
        songs = self._same_artist_songs()
        results = recommend_songs(perfect_match_user_prefs(), songs, k=2, strategy="balanced")
        assert len(results) == 2

    def test_fairness_penalty_can_reorder_below_other_artists(self):
        songs = self._same_artist_songs() + [
            perfect_match_song(energy=0.6) | {"artist": "Other Artist", "title": "Rival"}
        ]
        # Rival's baseline score (energy delta 0.1 -> penalty 0.4) is 4.6, which
        # beats "Second" (4.0) and "Third" (3.0) before fairness penalties, but
        # should also beat them after Same Artist's 2nd/3rd picks get penalized.
        results = recommend_songs(perfect_match_user_prefs(), songs, k=4, strategy="balanced")
        titles = [song["title"] for song, _, _ in results]
        assert titles == ["First", "Rival", "Second", "Third"]

    def test_explanation_is_pipe_joined_reason_string(self):
        songs = [perfect_match_song() | {"artist": "Solo", "title": "Only"}]
        results = recommend_songs(perfect_match_user_prefs(), songs, k=1)
        _, _, explanation = results[0]
        assert " | " in explanation
        assert "genre match" in explanation


class TestLoadSongs:
    def test_loads_valid_rows_with_lowercased_genre_and_mood(self, tmp_path):
        csv_path = tmp_path / "songs.csv"
        csv_path.write_text(
            "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness\n"
            "1,Track One,Artist X, POP , HAPPY ,0.5,100,0.5,0.5,0.5\n"
        )
        songs = load_songs(str(csv_path))
        assert len(songs) == 1
        assert songs[0]["genre"] == "pop"
        assert songs[0]["mood"] == "happy"
        assert isinstance(songs[0]["energy"], float)

    def test_missing_file_returns_empty_list_without_raising(self, capsys):
        songs = load_songs("does/not/exist.csv")
        assert songs == []
        captured = capsys.readouterr()
        assert "Error parsing local CSV dataset path" in captured.out

    def test_malformed_row_stops_parsing_but_keeps_prior_rows(self, tmp_path, capsys):
        csv_path = tmp_path / "songs.csv"
        csv_path.write_text(
            "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness\n"
            "1,Track One,Artist X,pop,happy,0.5,100,0.5,0.5,0.5\n"
            "2,Track Two,Artist Y,pop,happy,not-a-number,100,0.5,0.5,0.5\n"
            "3,Track Three,Artist Z,pop,happy,0.5,100,0.5,0.5,0.5\n"
        )
        songs = load_songs(str(csv_path))
        assert len(songs) == 1
        assert songs[0]["title"] == "Track One"
        captured = capsys.readouterr()
        assert "Error parsing local CSV dataset path" in captured.out
