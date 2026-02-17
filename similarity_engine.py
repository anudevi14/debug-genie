import numpy as np

class SimilarityEngine:
    def __init__(self, threshold=0.80):
        self.threshold = threshold

    def cosine_similarity(self, vec1, vec2):
        """Calculate cosine similarity between two vectors."""
        if vec1 is None or vec2 is None:
            return 0.0
        
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
            
        return dot_product / (norm_v1 * norm_v2)

    def find_most_similar_semantic(self, current_embedding, memory_entries):
        """
        Compares current ticket embedding with stored memory embeddings.
        Returns the best match record and its score if above threshold.
        """
        best_match = None
        best_score = 0.0

        for entry in memory_entries:
            past_embedding = entry.get("embedding")
            score = self.cosine_similarity(current_embedding, past_embedding)

            if score > best_score:
                best_score = score
                best_match = entry

        if best_score >= self.threshold:
            return best_match, best_score
        
        return None, 0.0

    # Retaining old method for backward compatibility/hybrid if needed
    def find_most_similar_text(self, current_text, historical_tickets, sf_client):
        from difflib import SequenceMatcher
        best_match = None
        best_score = 0.0

        for ticket in historical_tickets:
            past_text = sf_client.get_ticket_text_for_comparison(ticket)
            score = SequenceMatcher(None, current_text.lower(), past_text.lower()).ratio()

            if score > best_score:
                best_score = score
                best_match = ticket

        if best_score >= 0.65:  # Original threshold
            return best_match, best_score

        return None, 0.0

    def find_most_similar(self, current_text, historical_tickets, sf_client):
        """Deprecated alias for find_most_similar_text used by older tests."""
        return self.find_most_similar_text(current_text, historical_tickets, sf_client)

    def _calculate_score(self, text1, text2):
        """Internal helper for text similarity used by older tests."""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
