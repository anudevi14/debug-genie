import json
from openai import OpenAI
from config import Config

class AIAnalyzer:
    def __init__(self):
        if Config.MOCK_MODE:
            self.client = None
        else:
            self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.get_openai_model()


    def analyze_ticket(self, ticket_data):
        """Analyze ticket data and return structured RCA JSON."""
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
            "\n"
            "Do NOT include any commentary or text before or after the JSON block."
        )

        user_content = f"Case Data for Analysis:\n\n{ticket_data}"
        
        if Config.MOCK_MODE:
            mock_json = {
                "impactedService": "Payment Gateway",
                "probableRootCause": "Database connection pool exhaustion due to unoptimized queries in the recent release.",
                "splunkQuerySuggestion": "index=prod_logs service=payment_gateway '504 Gateway Timeout' | stats count by host",
                "recommendedSteps": "1. Increase max connections in the database pool. 2. Revert recent deployment of 'payment-optimization' module. 3. Monitor latency metrics.",
                "confidence": "High"
            }
            return mock_json

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
            required_keys = ["impactedService", "probableRootCause", "splunkQuerySuggestion", "recommendedSteps", "confidence"]
            for key in required_keys:
                if key not in data:
                    data[key] = "N/A"
            return data
        except json.JSONDecodeError:
            raise Exception("AI output was not valid JSON.")
