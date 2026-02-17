import unittest
from unittest.mock import patch, MagicMock
from src.engine.similarity_engine import SimilarityEngine
from src.engine.memory_manager import MemoryManager
import numpy as np
import os
import json

class TestDebugGeniePhase3(unittest.TestCase):

    def test_cosine_similarity(self):
        engine = SimilarityEngine()
        vec1 = [1, 0, 0]
        vec2 = [1, 0, 0]  # Identical
        vec3 = [0, 1, 0]  # Orthogonal
        vec4 = [0.8, 0.6, 0] # High similarity

        self.assertAlmostEqual(engine.cosine_similarity(vec1, vec2), 1.0)
        self.assertAlmostEqual(engine.cosine_similarity(vec1, vec3), 0.0)
        self.assertGreater(engine.cosine_similarity(vec1, vec4), 0.7)

    def test_memory_manager_save_load(self):
        test_file = "test_memory.json"
        if os.path.exists(test_file):
            os.remove(test_file)
            
        manager = MemoryManager(storage_path=test_file)
        entries = [
            {"case_number": "101", "text": "Test 1", "embedding": [0.1, 0.2]},
            {"case_number": "102", "text": "Test 2", "embedding": [0.3, 0.4]}
        ]
        
        manager.save_memory(entries)
        
        # Reload
        new_manager = MemoryManager(storage_path=test_file)
        all_entries = new_manager.get_all_entries()
        
        self.assertEqual(len(all_entries), 2)
        self.assertEqual(all_entries[0]["case_number"], "101")
        
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)

    @patch('src.agents.ai_analyzer.OpenAI')
    @patch('config.Config.OPENAI_API_KEY', 'fake_key')
    def test_ai_analyzer_get_embedding(self, mock_openai_class):
        from src.agents.ai_analyzer import AIAnalyzer
        mock_client = mock_openai_class.return_value
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
        )

        analyzer = AIAnalyzer()
        emb = analyzer.get_embedding("Hello world")
        
        self.assertEqual(emb, [0.1, 0.2, 0.3])
        mock_client.embeddings.create.assert_called_once()

if __name__ == '__main__':
    unittest.main()
