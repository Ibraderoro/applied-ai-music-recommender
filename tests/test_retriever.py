import pytest

from src.retriever import TrackRetriever

CSV_HEADER = "id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness\n"


@pytest.fixture
def small_dataset(tmp_path):
    rows = [
        "1,Sunny Days,Artist A,pop,happy,0.80,120,0.85,0.80,0.20\n",
        "2,Late Night Study,Artist B,lofi,chill,0.40,80,0.55,0.60,0.75\n",
        "3,Rock Anthem,Artist C,rock,intense,0.90,150,0.45,0.65,0.10\n",
        "4,Sunny Reprise,Artist A,pop,happy,0.78,118,0.82,0.79,0.22\n",
    ]
    csv_path = tmp_path / "songs.csv"
    csv_path.write_text(CSV_HEADER + "".join(rows))
    return str(csv_path)


class TestLoadDataset:
    def test_loads_all_rows_with_correct_types(self, small_dataset):
        retriever = TrackRetriever(small_dataset)
        assert len(retriever.tracks) == 4
        first = retriever.tracks[0]
        assert first["title"] == "Sunny Days"
        assert first["genre"] == "pop"
        assert isinstance(first["energy"], float)
        assert isinstance(first["tempo_bpm"], float)

    def test_genre_and_mood_are_lowercased(self, tmp_path):
        csv_path = tmp_path / "songs.csv"
        csv_path.write_text(
            CSV_HEADER + "1,Track,Artist,POP,HAPPY,0.5,100,0.5,0.5,0.5\n"
        )
        retriever = TrackRetriever(str(csv_path))
        assert retriever.tracks[0]["genre"] == "pop"
        assert retriever.tracks[0]["mood"] == "happy"

    def test_missing_dataset_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            TrackRetriever(str(tmp_path / "missing.csv"))


class TestScoreTrack:
    def test_matching_genre_increases_score_over_baseline(self, small_dataset):
        retriever = TrackRetriever(small_dataset)
        pop_track = next(t for t in retriever.tracks if t["genre"] == "pop")
        rock_track = next(t for t in retriever.tracks if t["genre"] == "rock")

        pop_score = retriever.score_track(pop_track, {"genre": "pop"})
        rock_score = retriever.score_track(rock_track, {"genre": "pop"})

        assert pop_score == pytest.approx(5.0 + 3.0)
        assert rock_score == pytest.approx(5.0 - 1.0)

    def test_genre_matches_against_mood_field_too(self, small_dataset):
        retriever = TrackRetriever(small_dataset)
        chill_track = next(t for t in retriever.tracks if t["mood"] == "chill")
        score = retriever.score_track(chill_track, {"genre": "chill"})
        assert score == pytest.approx(5.0 + 3.0)

    def test_mood_match_adds_bonus(self, small_dataset):
        retriever = TrackRetriever(small_dataset)
        happy_track = next(t for t in retriever.tracks if t["mood"] == "happy")
        score = retriever.score_track(happy_track, {"mood": "happy"})
        assert score == pytest.approx(5.0 + 2.0)

    def test_energy_proximity_rewards_closer_match(self, small_dataset):
        retriever = TrackRetriever(small_dataset)
        track = retriever.tracks[0]  # energy=0.80
        close_score = retriever.score_track(track, {"target_energy": 0.80})
        far_score = retriever.score_track(track, {"target_energy": 0.0})
        assert close_score > far_score

    def test_tempo_proximity_rewards_closer_match(self, small_dataset):
        retriever = TrackRetriever(small_dataset)
        track = retriever.tracks[0]  # tempo_bpm=120
        close_score = retriever.score_track(track, {"target_tempo_bpm": 120})
        far_score = retriever.score_track(track, {"target_tempo_bpm": 320})
        assert close_score > far_score
        # tempo diff of 320-120=200 -> diff_bpm=1.0 -> max(0, 1.0-1.0)=0 contribution
        assert far_score == pytest.approx(5.0)

    def test_no_constraints_returns_baseline_score(self, small_dataset):
        retriever = TrackRetriever(small_dataset)
        track = retriever.tracks[0]
        assert retriever.score_track(track, {}) == 5.0


class TestRetrieveTopTracks:
    def test_respects_top_k(self, small_dataset):
        retriever = TrackRetriever(small_dataset)
        results = retriever.retrieve_top_tracks({"genre": "pop"}, top_k=2)
        assert len(results) == 2

    def test_orders_best_match_first(self, small_dataset):
        retriever = TrackRetriever(small_dataset)
        results = retriever.retrieve_top_tracks({"genre": "rock"}, top_k=1)
        assert results[0]["genre"] == "rock"

    def test_applies_artist_diversity_penalty(self, tmp_path):
        # Three Artist A tracks and one Artist B track are all equally strong
        # matches for the query (identical genre/mood). Without a diversity
        # penalty, the 2nd and 3rd Artist A tracks would rank above Artist B's
        # track by raw score alone (stable-sort insertion order). The retriever
        # should instead let Artist B's single track overtake the repeated
        # Artist A picks after the 1st one.
        rows = [
            "1,A Track One,Artist A,pop,happy,0.5,100,0.5,0.5,0.5\n",
            "2,A Track Two,Artist A,pop,happy,0.5,100,0.5,0.5,0.5\n",
            "3,A Track Three,Artist A,pop,happy,0.5,100,0.5,0.5,0.5\n",
            "4,B Track One,Artist B,pop,happy,0.5,100,0.5,0.5,0.5\n",
        ]
        csv_path = tmp_path / "songs.csv"
        csv_path.write_text(CSV_HEADER + "".join(rows))
        retriever = TrackRetriever(str(csv_path))

        results = retriever.retrieve_top_tracks({"genre": "pop", "mood": "happy"}, top_k=2)

        assert [t["title"] for t in results] == ["A Track One", "B Track One"]

    def test_empty_constraints_returns_top_k_by_baseline(self, small_dataset):
        retriever = TrackRetriever(small_dataset)
        results = retriever.retrieve_top_tracks({}, top_k=4)
        assert len(results) == 4
