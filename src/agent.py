"""
Agent module for parsing user intent into structured audio feature targets using Gemini.
"""

import os
import re
import json
import logging
from typing import Dict, Any
from google import genai
from dotenv import load_dotenv

load_dotenv(override=True)

# Standardized active model name for the google-genai SDK
GEMINI_MODEL_NAME = "gemini-flash-latest"

class MusicAgent:
    def __init__(self):
        raw_key = os.getenv("GEMINI_API_KEY", "")
        api_key = raw_key.strip().strip("'").strip('"')
        
        self.client = None
        self.llm_available = False

        if api_key:
            try:
                self.client = genai.Client(api_key=api_key)
                self.llm_available = True
            except Exception as e:
                logging.warning(f"Failed to initialize Gemini Client: {e}")
                print(f"[Agent Warning] Could not initialize Gemini API: {e}")
        else:
            logging.info("No GEMINI_API_KEY provided. Operating in Fallback Mode.")

    def parse_user_query(self, query: str) -> Dict[str, Any]:
        """
        Parses a natural language query into structured audio target features.
        Utilizes few-shot exemplars for precise parameter mapping.
        """
        if not self.llm_available or not self.client:
            return {}

        prompt = f"""
You are an expert music feature parser for a recommendation system.
Extract feature targets from the user request and return ONLY a raw JSON object.

Available dataset features and ranges:
- genre: string or null (e.g. "pop", "lofi", "rock")
- mood: string or null (e.g. "happy", "chill", "intense")
- target_energy: float 0.0 to 1.0 or null
- target_valence: float 0.0 to 1.0 or null
- target_danceability: float 0.0 to 1.0 or null
- target_tempo_bpm: integer or null (e.g., 120)

### FEW-SHOT EXAMPLES FOR SPECIALIZATION:
User Request: "upbeat songs for a high-energy gym session"
JSON Output: {{"genre": "pop", "mood": "intense", "target_energy": 0.90, "target_valence": 0.80, "target_danceability": 0.85, "target_tempo_bpm": 130}}

User Request: "calm acoustic tracks for late night study"
JSON Output: {{"genre": "lofi", "mood": "chill", "target_energy": 0.35, "target_valence": 0.50, "target_danceability": 0.40, "target_tempo_bpm": 75}}

User Request: "{query}"
JSON Output:
"""
        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
                config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json"
                }
            )
            raw_text = (response.text or "").strip()
            
            # Fence cleanup fallback
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
            
            parsed = json.loads(raw_text)
            return parsed if isinstance(parsed, dict) else {}
        except Exception as e:
            self.llm_available = False
            logging.warning(f"Gemini intent parsing failed: {e}")
            print(f"[Agent Warning] Gemini call failed, disabling LLM parsing for this session: {e}")
            return {}

    def synthesize_explanation(self, query: str, recommendations: list) -> str:
        """
        Generates a personalized summary explaining why these songs fit the user request.
        """
        if not self.llm_available or not self.client:
            return "Here are your personalized track recommendations based on your preferences."

        song_list_str = "\n".join(
            [f"- {s.get('title', 'Unknown')} by {s.get('artist', 'Unknown')} (Genre: {s.get('genre', 'N/A')}, Mood: {s.get('mood', 'N/A')})" for s in recommendations]
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
            self.llm_available = False
            logging.warning(f"Gemini explanation synthesis failed: {e}")
            print(f"[Agent Warning] Gemini explanation synthesis failed: {e}")
            return "Here are your personalized track recommendations based on your preferences."