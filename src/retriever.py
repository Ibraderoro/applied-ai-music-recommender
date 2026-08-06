"""
Multi-source retriever with resilient row parsing and inverted index pre-filtering.
"""

import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any
from src.scoring import ScoringEngine

logger = logging.getLogger(__name__)

class MultiSourceRetriever:
    def __init__(self, data_sources: List[Path]):
        self.data_sources = data_sources
        self.catalog: List[Dict[str, Any]] = []
        self.genre_index: Dict[str, List[Dict[str, Any]]] = {}
        self.mood_index: Dict[str, List[Dict[str, Any]]] = {}
        self.load_and_index_data()

    def load_and_index_data(self) -> None:
        """Loads catalog tracks from CSV and JSON files with row-level fault tolerance."""
        self.catalog.clear()
        self.genre_index.clear()
        self.mood_index.clear()

        for source in self.data_sources:
            if not source.exists():
                logger.warning(f"Data source file not found: {source}")
                continue

            # Load CSV Source
            if source.suffix.lower() == ".csv":
                with open(source, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row_num, row in enumerate(reader, start=1):
                        try:
                            track = {
                                "id": int(row["id"]),
                                "title": row["title"].strip(),
                                "artist": row["artist"].strip(),
                                "genre": row["genre"].strip().lower(),
                                "mood": row["mood"].strip().lower(),
                                "energy": float(row["energy"]),
                                "tempo_bpm": float(row["tempo_bpm"]),
                                "valence": float(row.get("valence", 0.5)),
                                "danceability": float(row.get("danceability", 0.5)),
                                "source": source.name
                            }
                            self.catalog.append(track)
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Skipping malformed row {row_num} in {source.name}: {e}")
                            continue

            # Load JSON Source
            elif source.suffix.lower() == ".json":
                with open(source, mode="r", encoding="utf-8") as f:
                    try:
                        items = json.load(f)
                        for item in items:
                            try:
                                item["genre"] = item["genre"].strip().lower()
                                item["mood"] = item["mood"].strip().lower()
                                item["source"] = source.name
                                self.catalog.append(item)
                            except (KeyError, AttributeError):
                                continue
                    except json.JSONDecodeError as e:
                        logger.warning(f"Error parsing JSON source {source.name}: {e}")
                        continue

        # Build In-Memory Inverted Index
        for track in self.catalog:
            self.genre_index.setdefault(track["genre"], []).append(track)
            self.mood_index.setdefault(track["mood"], []).append(track)

    def retrieve(self, constraints: Dict[str, Any], top_k: int = 3) -> List[Dict[str, Any]]:
        """Pre-filters candidate pool using inverted index and scores tracks via ScoringEngine."""
        target_genre = constraints.get("genre", "").lower()

        # Inverted Index Pre-filtering ($O(1)$ candidate retrieval)
        if target_genre in self.genre_index:
            candidate_pool = self.genre_index[target_genre]
        else:
            candidate_pool = self.catalog

        scored_candidates = []
        for track in candidate_pool:
            score = ScoringEngine.calculate_track_score(track, constraints)
            scored_track = track.copy()
            scored_track["score"] = score
            scored_candidates.append(scored_track)

        # Apply Dynamic Artist Diversity Saturation
        diverse_candidates = ScoringEngine.apply_artist_diversity_penalty(scored_candidates)
        return diverse_candidates[:top_k]