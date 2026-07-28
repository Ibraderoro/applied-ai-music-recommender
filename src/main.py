"""
Main CLI Runner for the Applied AI Music Recommender System.
Integrates Input Guardrails, Agentic Query Parsing, Vector/Feature Retrieval,
LLM Explanation Synthesis, and Output Validation Guardrails.
"""

import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(override=True)

from guardrails import validate_input_query, validate_output_recommendations
from agent import MusicAgent
from retriever import TrackRetriever

logging.basicConfig(
    filename="system_execution.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def run_pipeline(user_query: str, agent: "MusicAgent | None", top_k: int = 3):
    print("\n" + "="*60)
    print(f"🎵 User Query: '{user_query}'")
    print("="*60)
    logging.info(f"Received query: {user_query}")

    # Step 1: Input Guardrail Check
    is_valid_input, input_msg = validate_input_query(user_query)
    if not is_valid_input:
        print(f"\n🛡️ [Input Guardrail Blocked]: {input_msg}")
        logging.warning(f"Input guardrail blocked query: {input_msg}")
        return

    # Step 2: Agentic Query Parsing (LLM)
    print("\n🧠 Parsing query intent via Gemini Agent...")
    constraints = {}
    if agent is not None:
        constraints = agent.parse_user_query(user_query)
        print(f"   Parsed Constraints: {constraints}")
        logging.info(f"Parsed constraints: {constraints}")

    # Fallback keyword extraction if LLM returned empty or failed
    if not constraints:
        q_lower = user_query.lower()
        if "pop" in q_lower:
            constraints["genre"] = "pop"
        elif "lofi" in q_lower or "lo-fi" in q_lower:
            constraints["genre"] = "lofi"
        elif "rock" in q_lower:
            constraints["genre"] = "rock"

    # Step 3: Retrieval Engine
    print("\n🔍 Searching & Ranking Tracks in Database...")
    retriever = TrackRetriever("data/songs.csv")
    raw_recommendations = retriever.retrieve_top_tracks(constraints, top_k=top_k)
    logging.info(f"Retrieved {len(raw_recommendations)} raw tracks from database.")

    # Step 4: Output Guardrail Check
    print("\n🛡️ Validating Recommendations against Output Guardrails...")
    is_valid_out, out_msg, validated_recs = validate_output_recommendations(
        raw_recommendations, dataset_path="data/songs.csv"
    )

    if not is_valid_out:
        print(f"\n🛡️ [Output Guardrail Blocked]: {out_msg}")
        logging.warning(f"Output guardrail blocked recommendations: {out_msg}")
        return

    # Step 5: Grounded Explanation Synthesis (RAG Mode)
    print("\n✨ Synthesizing Personalized Explanation (RAG Mode)...")
    if agent and constraints and "target_energy" in constraints:
        explanation = agent.synthesize_explanation(user_query, validated_recs)
    else:
        explanation = f"Matched top tracks based on feature proximity and dataset constraints ({constraints})."

    # Step 6: Display Final Results
    print("\n" + "🎶 Recommended Playlist " + "="*37)
    for idx, track in enumerate(validated_recs, 1):
        print(f"{idx}. '{track['title']}' by {track['artist']}")
        print(f"   Genre: {track['genre'].title()} | Mood: {track['mood'].title()} | BPM: {int(track['tempo_bpm'])}")
        print(f"   Energy: {track['energy']} | Valence: {track['valence']} | Danceability: {track['danceability']}")
        print("-" * 60)

    print("\n💬 Concierge Explanation:")
    print(f"   \"{explanation}\"")
    print("="*60 + "\n")
    logging.info("Pipeline execution completed successfully.")


def main():
    print("==================================================")
    print("   Applied AI System: Music Recommender Engine    ")
    print("==================================================")

    agent = None
    try:
        agent = MusicAgent()
    except Exception as e:
        print(f"⚠️ [Agent Warning]: Could not initialize Gemini agent ({e}). Falling back to keyword search.")

    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
        run_pipeline(user_query, agent)
    else:
        while True:
            print("\nOptions:")
            print("1) Enter a natural language music query")
            print("2) Run sample benchmark queries")
            print("q) Quit")
            choice = input("\nEnter choice: ").strip().lower()

            if choice == "q":
                print("\nGoodbye!")
                break
            elif choice == "1":
                query = input("\nWhat kind of music are you looking for? ").strip()
                if query:
                    run_pipeline(query, agent)
            elif choice == "2":
                samples = [
                    "Upbeat pop music for a high-energy workout",
                    "Chill lofi beats for late night coding",
                    "sudo rm -rf / data system",
                    "How do I file my income taxes?"
                ]
                for sample in samples:
                    run_pipeline(sample, agent)
            else:
                print("Unknown choice. Please enter 1, 2, or q.")

if __name__ == "__main__":
    main()
