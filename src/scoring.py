"""
Unified scoring engine providing a single source of truth for proximity, 
categorical matching, and dynamic artist diversity filtering.
"""

from typing import List, Dict, Any

class ScoringEngine:
    @staticmethod
    def calculate_track_score(track: Dict[str, Any], constraints: Dict[str, Any]) -> float:
        """Calculates proximity and match score for a track against constraints."""
        score = 0.0
        
        target_genre = constraints.get("genre", "").lower()
        target_mood = constraints.get("mood", "").lower()
        target_energy = constraints.get("target_energy", 0.5)
        target_tempo = constraints.get("target_tempo_bpm", 120)

        # Categorical Match Rewards
        if track.get("genre", "").lower() == target_genre:
            score += 3.0
        if track.get("mood", "").lower() == target_mood:
            score += 2.0

        # Acoustic Attribute Delta Penalties
        energy_delta = abs(track.get("energy", 0.5) - target_energy)
        score -= energy_delta * 4.0

        tempo_delta = abs(track.get("tempo_bpm", 120) - target_tempo)
        score -= tempo_delta * 0.02

        return round(score, 2)

    @staticmethod
    def apply_artist_diversity_penalty(
        tracks: List[Dict[str, Any]], penalty_factor: float = 1.50
    ) -> List[Dict[str, Any]]:
        """Applies a dynamic saturation penalty to penalize duplicate artists sequentially."""
        artist_counts: Dict[str, int] = {}
        adjusted_tracks = []

        for track in tracks:
            artist = track.get("artist", "Unknown")
            count = artist_counts.get(artist, 0)
            
            # Penalty increases with each additional track from the same artist
            penalty = penalty_factor * count
            
            updated_track = track.copy()
            updated_track["score"] = round(track.get("score", 0.0) - penalty, 2)
            adjusted_tracks.append(updated_track)

            artist_counts[artist] = count + 1

        # Re-sort after applying diversity penalty
        adjusted_tracks.sort(key=lambda x: x["score"], reverse=True)
        return adjusted_tracks