from difflib import SequenceMatcher

class SimilarityEngine:
    def __init__(self, threshold=0.65):
        self.threshold = threshold

    def _calculate_score(self, text1, text2):
        """Returns a similarity score between 0 and 1."""
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def find_most_similar(self, current_text, historical_tickets, sf_client):
        """
        Compares current ticket text with a list of historical tickets.
        Returns the best match record and its score if above threshold.
        """
        best_match = None
        best_score = 0.0

        for ticket in historical_tickets:
            past_text = sf_client.get_ticket_text_for_comparison(ticket)
            score = self._calculate_score(current_text, past_text)

            if score > best_score:
                best_score = score
                best_match = ticket

        if best_score >= self.threshold:
            return best_match, best_score
        
        return None, 0.0
