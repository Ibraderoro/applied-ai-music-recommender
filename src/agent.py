"""
Agent module supporting Baseline (Zero-Shot) vs Specialized (Few-Shot) prompt construction
and user query intent parsing into structured audio constraints.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Fallback keyword parser in case Gemini API is offline or missing key
def fallback_keyword_parser(query: str) -> Dict[str, Any]:
    q = query.lower()
    genre = "pop"
    if "lofi" in q or "chill" in q:
        genre = "lofi"
    elif "rock" in q:
        genre = "rock"
    elif "indie" in q:
        genre = "indie"

    mood = "energetic" if "workout" in q or "upbeat" in q else "chill"
    target_energy = 0.9 if "workout" in q or "high-energy" in q else 0.4
    target_tempo = 130 if "workout" in q else 80

    return {
        "genre": genre,
        "mood": mood,
        "target_energy": target_energy,
        "target_tempo_bpm": target_tempo
    }

class MusicAgent:
    def __init__(self, use_few_shot: bool = True):
        self.use_few_shot = use_few_shot
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}")

    def construct_prompt(self, query: str) -> str:
        """Constructs the prompt payload for Gemini parameter parsing."""
        system_instruction = (
            "Extract audio constraints as JSON with keys: "
            "'genre' (str), 'mood' (str), 'target_energy' (float 0.0-1.0), "
            "and 'target_tempo_bpm' (int). Respond ONLY with valid raw JSON."
        )

        if not self.use_few_shot:
            return f"{system_instruction}\n\nUser Query: {query}"

        exemplars = """
Few-Shot Examples:
Query: "Chill lofi beats for late night coding"
JSON: {"genre": "lofi", "mood": "chill", "target_energy": 0.30, "target_tempo_bpm": 78}

Query: "Upbeat pop music for a high-energy workout"
JSON: {"genre": "pop", "mood": "energetic", "target_energy": 0.90, "target_tempo_bpm": 132}

Query: "Acoustic coffee shop vibes on a rainy Sunday"
JSON: {"genre": "acoustic", "mood": "calm", "target_energy": 0.25, "target_tempo_bpm": 82}
"""
        return f"{system_instruction}\n{exemplars}\nUser Query: {query}"

    def parse_user_query(self, query: str) -> Dict[str, Any]:
        """Parses user query into structured audio parameter JSON."""
        if not self.client:
            logger.info("Gemini client offline or API key missing. Using fallback keyword parser.")
            return fallback_keyword_parser(query)

        prompt = self.construct_prompt(query)
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            text = response.text.strip()
            # Strip markdown code blocks if returned
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("\n", 1)[0].replace("json", "").strip()
            return json.loads(text)
        except Exception as e:
            logger.warning(f"Gemini API parsing failed ({e}). Falling back to keyword parser.")
            return fallback_keyword_parser(query)