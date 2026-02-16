import json
from openai import OpenAI
from config import Config

class AIAnalyzer:
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.get_openai_model()
        self.embedding_model = "text-embedding-3-small"

    def get_embedding(self, text):
        """Generate embedding for the given text."""
        if not text:
            return None
        
        # Replace newlines which can negatively affect performance
        text = text.replace("\n", " ")
        
        response = self.client.embeddings.create(
            input=[text],
            model=self.embedding_model
        )
        return response.data[0].embedding

    def analyze_ticket(self, ticket_data, historical_context=None):
        """
        Analyze ticket data and return structured RCA JSON.
        If historical_context is provided, AI will consider if it's a repeated issue.
        """
        system_prompt = (
            "You are a Senior Production Support Engineer with expertise in troubleshooting complex enterprise systems. "
            "Analyze the provided Salesforce Case description and comments to determine the root cause of the issue. "
            "Restrict hallucinations and provide analysis based only on the provided facts. "
            "\n\n"
            "You MUST return the output as a STRICT JSON object with the following keys:\n"
            "- impactedService: The service or component affected.\n"
            "- probableRootCause: A concise explanation of the root cause.\n"
            "- splunkQuerySuggestion: A relevant Splunk query to investigate further.\n"
            "- recommendedSteps: Concrete steps to resolve or mitigate the issue.\n"
            "- confidence: 'Low' | 'Medium' | 'High'\n"
            "- isRepeatedIssue: boolean, true if this current ticket matches the patterns of the provided historical ticket.\n"
            "- similarTicketReference: string, the Ticket Number of the similar historical ticket (if any).\n"
            "- similarityScore: number, the provided similarity score if applicable.\n"
            "\n"
            "Do NOT include any commentary or text before or after the JSON block."
        )

        user_content = f"CURRENT TICKET FOR ANALYSIS:\n\n{ticket_data}\n\n"
        
        if historical_context:
            user_content += (
                "HISTORICAL CONTEXT (SIMILAR TICKET DETECTED):\n"
                f"Previous Ticket Reference: {historical_context['ticket_number']}\n"
                f"Similarity Score: {historical_context['score']}\n"
                f"Previous Content: {historical_context['content']}\n\n"
                "If the current ticket is a repeat of this historical issue, reuse the known resolution if valid and set isRepeatedIssue to true."
            )
        else:
            user_content += "No similar historical tickets were found. Set isRepeatedIssue to false."

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        json_output = response.choices[0].message.content
        return self._validate_and_parse(json_output)

    def _validate_and_parse(self, json_str):
        """Ensure the output is valid JSON and contains required keys."""
        try:
            data = json.loads(json_str)
            required_keys = [
                "impactedService", "probableRootCause", "splunkQuerySuggestion", 
                "recommendedSteps", "confidence", "isRepeatedIssue", 
                "similarTicketReference", "similarityScore"
            ]
            for key in required_keys:
                if key not in data:
                    if key == "isRepeatedIssue":
                        data[key] = False
                    elif key == "similarityScore":
                        data[key] = 0.0
                    else:
                        data[key] = "N/A"
            return data
        except json.JSONDecodeError:
            raise Exception("AI output was not valid JSON.")
