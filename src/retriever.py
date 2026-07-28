"""
Retriever engine for scoring tracks against extracted user constraints.
"""

import csv
import math
from typing import List, Dict, Any

class TrackRetriever:
    def __init__(self, dataset_path: str = "data/songs.csv"):
        self.dataset_path = dataset_path
        self.tracks = self._load_dataset()

    def _load_dataset(self) -> List[Dict[str, Any]]:
        tracks = []
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tracks.append({
                    "id": row["id"],
                    "title": row["title"],
                    "artist": row["artist"],
                    "genre": row["genre"].lower(),
                    "mood": row["mood"].lower(),
                    "energy": float(row["energy"]),
                    "tempo_bpm": float(row["tempo_bpm"]),
                    "valence": float(row["valence"]),
                    "danceability": float(row["danceability"]),
                    "acousticness": float(row["acousticness"])
                })
        return tracks

    def score_track(self, track: Dict[str, Any], constraints: Dict[str, Any]) -> float:
        """
        Computes a similarity score (0.0 to 10.0) based on proximity to target features.
        """
        score = 5.0  # Base score

        # Genre Match
        target_genre = constraints.get("genre")
        if target_genre and target_genre.lower() == track["genre"]:
            score += 2.5
        elif target_genre and target_genre.lower() not in track["genre"]:
            score -= 1.5

        # Mood Match
        target_mood = constraints.get("mood")
        if target_mood and target_mood.lower() == track["mood"]:
            score += 2.0

        # Numeric Proximity (Energy)
        if constraints.get("target_energy") is not None:
            diff = abs(track["energy"] - float(constraints["target_energy"]))
            score += (1.0 - diff) * 1.5

        # Numeric Proximity (Tempo)
        if constraints.get("target_tempo_bpm") is not None:
            target_bpm = float(constraints["target_tempo_bpm"])
            diff_bpm = abs(track["tempo_bpm"] - target_bpm) / 200.0
            score += max(0, (1.0 - diff_bpm)) * 1.5

        return round(score, 2)

    def retrieve_top_tracks(self, constraints: Dict[str, Any], top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Ranks tracks by score and applies artist diversity penalties.
        """
        scored_tracks = []
        for track in self.tracks:
            score = self.score_track(track, constraints)
            scored_tracks.append((track, score))

        scored_tracks.sort(key=lambda x: x[1], reverse=True)

        # Apply artist diversity penalty
        seen_artists = {}
        diverse_tracks = []
        for track, score in scored_tracks:
            artist = track["artist"]
            count = seen_artists.get(artist, 0)
            adjusted_score = score - (count * 1.0)  # Diversity penalty
            seen_artists[artist] = count + 1
            diverse_tracks.append((track, adjusted_score))

        diverse_tracks.sort(key=lambda x: x[1], reverse=True)
        return [t[0] for t in diverse_tracks[:top_k]]
