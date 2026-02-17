import unittest
import os
import json
from src.engine.memory_manager import MemoryManager

class TestDebugGeniePhase5(unittest.TestCase):
    def setUp(self):
        self.test_storage = "test_memory.json"
        self.test_feedback = "test_feedback.json"
        if os.path.exists(self.test_storage): os.remove(self.test_storage)
        if os.path.exists(self.test_feedback): os.remove(self.test_feedback)
        self.mm = MemoryManager(self.test_storage, self.test_feedback)

    def tearDown(self):
        if os.path.exists(self.test_storage): os.remove(self.test_storage)
        if os.path.exists(self.test_feedback): os.remove(self.test_feedback)

    def test_feedback_correct_boosts_reliability(self):
        # Setup initial memory
        entry = {
            "case_number": "00001001",
            "text": "test content",
            "embedding": [0.1, 0.2]
        }
        self.mm.save_memory([entry])
        
        initial_reliability = self.mm.memory[0]["reliability_score"]
        
        # Mark as correct
        self.mm.submit_feedback("00001001", "correct", {"probableRootCause": "RC", "recommendedSteps": "RES"})
        
        new_reliability = self.mm.memory[0]["reliability_score"]
        self.assertTrue(new_reliability > initial_reliability)
        self.assertTrue(self.mm.memory[0]["verified"])
        self.assertEqual(len(self.mm.memory), 1)

    def test_feedback_edited_prioritizes_analyst(self):
        entry = {
            "case_number": "00001002",
            "text": "test content",
            "embedding": [0.1, 0.2]
        }
        self.mm.save_memory([entry])
        
        # Analyst correction
        correction = {"root_cause": "Analyst RC", "resolution": "Analyst RES"}
        self.mm.submit_feedback("00001002", "edited", {"probableRootCause": "AI RC", "recommendedSteps": "AI RES"}, analyst_correction=correction)
        
        self.assertEqual(self.mm.memory[0]["analyst_root_cause"], "Analyst RC")
        self.assertEqual(self.mm.memory[0]["reliability_score"], 1.0)
        self.assertTrue(self.mm.memory[0]["verified"])

    def test_audit_trail_recorded(self):
        entry = {"case_number": "00001003", "text": "...", "embedding": [0]}
        self.mm.save_memory([entry])
        self.mm.submit_feedback("00001003", "incorrect", {"probableRootCause": "X", "recommendedSteps": "Y"})
        
        with open(self.test_feedback, "r") as f:
            feedbacks = json.load(f)
        
        self.assertEqual(len(feedbacks), 1)
        self.assertEqual(feedbacks[0]["feedback_type"], "incorrect")

if __name__ == '__main__':
    unittest.main()
