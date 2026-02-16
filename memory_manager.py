import json
import os

class MemoryManager:
    def __init__(self, storage_path="ticket_memory.json"):
        self.storage_path = storage_path
        self.memory = self._load_memory()

    def _load_memory(self):
        """Load memory from JSON file if it exists."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading memory: {e}")
                return []
        return []

    def save_memory(self, entries):
        """Save new entries to memory, avoiding duplicates by case_number."""
        existing_numbers = {e["case_number"] for e in self.memory}
        
        for entry in entries:
            if entry["case_number"] not in existing_numbers:
                self.memory.append(entry)
                existing_numbers.add(entry["case_number"])
        
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            print(f"Error saving memory: {e}")

    def get_all_entries(self):
        """Return all entries currently in memory."""
        return self.memory

    def get_memory_stats(self):
        """Return basic stats about the memory."""
        return {
            "entry_count": len(self.memory),
            "file_exists": os.path.exists(self.storage_path)
        }
