import json
from openai import OpenAI
from config import Config

class AIAnalyzer:
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        # Upgrade to GPT-4o for Phase 4 (Multimodal)
        self.model = "gpt-4o"
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

    def vision_extract(self, image_base64):
        """Extract structured technical details from a screenshot using GPT-4o Vision."""
        if not image_base64:
            return None

        prompt = (
            "You are a technical support engineer. Extract structured details from this screenshot. "
            "Return a JSON object with these keys: error_message, error_code, service_name, stack_trace, "
            "visible_timestamp, environment, additional_observations. "
            "Only include information that is EXPLICITLY visible. If a field is not found, leave it empty."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                            },
                        ],
                    }
                ],
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Vision Extraction Failed: {e}")
            return None

    def analyze_ticket(self, ticket_data, historical_context=None, vision_data=None):
        """
        Analyze ticket data and return structured RCA JSON.
        If historical_context is provided, AI will consider if it's a repeated issue.
        If vision_data is provided, AI will incorporate screenshot insights.
        """
        system_prompt = (
            "You are a Senior Production Support Engineer with expertise in troubleshooting complex enterprise systems. "
            "Analyze the provided Salesforce Case description, comments, and screenshot data to determine the root cause. "
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
            "- visualEvidenceUsed: boolean, set to true if screenshot insights contributed to this RCA.\n"
            "\n"
            "Do NOT include any commentary or text before or after the JSON block."
        )

        user_content = f"CURRENT TICKET FOR ANALYSIS:\n\n{ticket_data}\n\n"
        
        if vision_data:
            user_content += (
                "VISUAL EVIDENCE (FROM SCREENSHOT):\n"
                f"{json.dumps(vision_data, indent=2)}\n\n"
            )

        if historical_context:
            user_content += (
                "HISTORICAL CONTEXT (SIMILAR TICKET DETECTED):\n"
                f"Previous Ticket Reference: {historical_context['ticket_number']}\n"
                f"Similarity Score: {historical_context['score']}\n"
                f"Previous Content: {historical_context['content']}\n\n"
                "If the current ticket is a repeat of this historical issue, reuse the known resolution if valid."
            )

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
                "similarTicketReference", "similarityScore", "visualEvidenceUsed"
            ]
            for key in required_keys:
                if key not in data:
                    if key == "isRepeatedIssue":
                        data[key] = False
                    elif key == "similarityScore":
                        data[key] = 0.0
                    elif key == "visualEvidenceUsed":
                        data[key] = False
                    else:
                        data[key] = "N/A"
            return data
        except json.JSONDecodeError:
            raise Exception("AI output was not valid JSON.")
