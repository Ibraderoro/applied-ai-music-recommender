"""
Recommender class delegating scoring to the unified ScoringEngine.
"""

from pathlib import Path
from typing import List, Dict, Any
from src.scoring import ScoringEngine

class Recommender:
    def __init__(self, catalog: List[Dict[str, Any]]):
        self.catalog = catalog

    def rank_tracks(self, constraints: Dict[str, Any], top_k: int = 3) -> List[Dict[str, Any]]:
        """Ranks tracks using the shared ScoringEngine."""
        scored_tracks = []
        for track in self.catalog:
            score = ScoringEngine.calculate_track_score(track, constraints)
            scored_track = track.copy()
            scored_track["score"] = score
            scored_tracks.append(scored_track)

        return ScoringEngine.apply_artist_diversity_penalty(scored_tracks)[:top_k]