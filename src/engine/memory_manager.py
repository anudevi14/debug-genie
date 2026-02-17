import json
import os
from datetime import datetime

class MemoryManager:
    def __init__(self, storage_path="data/ticket_memory.json", feedback_path="data/feedback_memory.json"):
        self.storage_path = storage_path
        self.feedback_path = feedback_path
        self.memory = self._load_memory()

    def _load_memory(self):
        """Load memory from JSON file if it exists."""
        if os.path.exists(self.storage_path):
            if os.path.getsize(self.storage_path) == 0:
                return []
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    # Migrating schema for older entries if necessary
                    for entry in data:
                        if "ai_root_cause" not in entry:
                            entry["ai_root_cause"] = entry.get("root_cause", "N/A")
                        if "ai_resolution" not in entry:
                            entry["ai_resolution"] = entry.get("resolution", "N/A")
                        if "analyst_root_cause" not in entry:
                            entry["analyst_root_cause"] = None
                        if "analyst_resolution" not in entry:
                            entry["analyst_resolution"] = None
                        if "verified" not in entry:
                            entry["verified"] = False
                        if "reliability_score" not in entry:
                            entry["reliability_score"] = 0.7 # Default starting score
                        if "feedback_count" not in entry:
                            entry["feedback_count"] = 0
                    return data
            except Exception as e:
                print(f"Error loading memory: {e}")
                return []
        return []

    def reload(self):
        """Force reload from disk to sync with manual file changes."""
        self.memory = self._load_memory()

    def save_memory(self, entries):
        """Save new entries to memory, avoiding duplicates by case_number."""
        existing_numbers = {e["case_number"] for e in self.memory}
        
        for entry in entries:
            if entry["case_number"] not in existing_numbers:
                # Ensure new entries follow the Phase 5 schema
                new_entry = {
                    "case_number": entry["case_number"],
                    "text": entry["text"],
                    "embedding": entry["embedding"],
                    "ai_root_cause": entry.get("root_cause", "N/A"),
                    "ai_resolution": entry.get("resolution", "N/A"),
                    "analyst_root_cause": None,
                    "analyst_resolution": None,
                    "verified": False,
                    "reliability_score": 0.7,
                    "feedback_count": 0
                }
                self.memory.append(new_entry)
                existing_numbers.add(entry["case_number"])
        
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            print(f"Error saving memory: {e}")

    def submit_feedback(self, case_number, feedback_type, ai_output, analyst_correction=None, confidence_score=None, text=None, embedding=None):
        """
        Record analyst feedback and update memory reliability.
        feedback_type: 'correct' | 'incorrect' | 'edited'
        """
        # 1. Update feedback_memory.json (Append-only Audit Trail)
        feedback_entry = {
            "case_number": case_number,
            "timestamp": datetime.now().isoformat(),
            "feedback_type": feedback_type,
            "ai_root_cause": ai_output.get("probableRootCause"),
            "ai_resolution": ai_output.get("recommendedSteps"),
            "analyst_root_cause": analyst_correction.get("root_cause") if analyst_correction else None,
            "analyst_resolution": analyst_correction.get("resolution") if analyst_correction else None,
            "confidence_score_at_time": confidence_score
        }
        
        feedbacks = []
        if os.path.exists(self.feedback_path) and os.path.getsize(self.feedback_path) > 0:
            with open(self.feedback_path, "r") as f:
                feedbacks = json.load(f)
        
        feedbacks.append(feedback_entry)
        with open(self.feedback_path, "w") as f:
            json.dump(feedbacks, f, indent=2)

        # 2. Update primary memory state for future similarity
        found = False
        for entry in self.memory:
            if entry["case_number"] == case_number:
                found = True
                entry["feedback_count"] += 1
                entry["last_feedback_at"] = datetime.now().date().isoformat()
                
                if feedback_type == "correct":
                    entry["verified"] = True
                    entry["reliability_score"] = min(1.0, entry["reliability_score"] + 0.05)
                elif feedback_type == "incorrect":
                    entry["verified"] = False
                    entry["reliability_score"] = max(0.3, entry["reliability_score"] - 0.20)
                elif feedback_type == "edited" and analyst_correction:
                    entry["verified"] = True
                    entry["reliability_score"] = 1.0 # Human correction is gold standard
                    entry["analyst_root_cause"] = analyst_correction.get("root_cause")
                    entry["analyst_resolution"] = analyst_correction.get("resolution")
                
                # If this entry didn't have AI outputs (from backfill), save them now
                if entry["ai_root_cause"] == "N/A":
                    entry["ai_root_cause"] = ai_output.get("probableRootCause")
                    entry["ai_resolution"] = ai_output.get("recommendedSteps")
                
                break
        
        if not found and text and embedding:
            # Create new memory entry if it didn't exist
            new_entry = {
                "case_number": case_number,
                "text": text,
                "embedding": embedding,
                "ai_root_cause": ai_output.get("probableRootCause", "N/A"),
                "ai_resolution": ai_output.get("recommendedSteps", "N/A"),
                "analyst_root_cause": analyst_correction.get("root_cause") if analyst_correction else None,
                "analyst_resolution": analyst_correction.get("resolution") if analyst_correction else None,
                "verified": feedback_type in ["correct", "edited"],
                "reliability_score": 1.0 if feedback_type == "edited" else (0.75 if feedback_type == "correct" else 0.5),
                "feedback_count": 1,
                "last_feedback_at": datetime.now().date().isoformat()
            }
            self.memory.append(new_entry)

        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            print(f"Error saving updated memory: {e}")

    def get_all_entries(self):
        """Return all entries currently in memory."""
        return self.memory

    def get_memory_stats(self):
        """Return basic stats about the memory."""
        verified_count = sum(1 for e in self.memory if e.get("verified"))
        return {
            "entry_count": len(self.memory),
            "verified_count": verified_count,
            "avg_reliability": sum(e.get("reliability_score", 0.7) for e in self.memory) / len(self.memory) if self.memory else 0
        }
