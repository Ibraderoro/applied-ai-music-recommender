"""
Agent module for parsing user intent into structured audio feature targets using Gemini.
"""

import os
import json
from typing import Dict, Any
from google import genai

GEMINI_MODEL_NAME = "gemini-2.5-flash"

class MusicAgent:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable not found.")
        self.client = genai.Client(api_key=api_key)

    def parse_user_query(self, query: str) -> Dict[str, Any]:
        """
        Parses a natural language query into audio target features.
        """
        prompt = f"""
You are an expert music feature parser for a recommendation system.
Extract feature targets from the user request and return ONLY a raw JSON object (no markdown, no backticks).

Available dataset features and ranges:
- genre: string or null (e.g. "pop", "lofi", "rock")
- mood: string or null (e.g. "happy", "chill", "intense")
- target_energy: float 0.0 to 1.0 or null
- target_valence: float 0.0 to 1.0 or null
- target_danceability: float 0.0 to 1.0 or null
- target_tempo_bpm: integer or null (e.g., 120)

User Request: "{query}"

JSON Output:
"""
        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
                config={"temperature": 0.0}
            )
            raw_text = (response.text or "").strip()
            # Clean possible markdown formatting
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
            
            parsed = json.loads(raw_text)
            return parsed
        except Exception as e:
            print(f"[Agent Warning] Failed to parse query via LLM: {e}")
            return {}

    def synthesize_explanation(self, query: str, recommendations: list) -> str:
        """
        Generates a personalized summary explaining why these songs fit the user request.
        """
        song_list_str = "\n".join(
            [f"- {s['title']} by {s['artist']} (Genre: {s['genre']}, Mood: {s['mood']})" for s in recommendations]
        )
        prompt = f"""
You are a friendly music concierge assistant.
User requested: "{query}"

Recommended Tracks:
{song_list_str}

Briefly explain (in 2-3 sentences) why this playlist fits their mood and request. 
Rely strictly on the provided track details and do not invent other songs.
"""
        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
                config={"temperature": 0.2}
            )
            return (response.text or "").strip()
        except Exception as e:
            return "Here are your personalized track recommendations based on your preferences."
