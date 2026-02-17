import json
from openai import OpenAI
from src.config import Config


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

    def vision_extract(self, image_base64, content_type="image/jpeg"):
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
                                "image_url": {"url": f"data:{content_type};base64,{image_base64}"}
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
        # Calculate Confidence Signals for the AI
        similarity_score = historical_context['score'] if historical_context else 0.0
        has_vision = vision_data is not None

        # Phase 5: Reliability & Analyst Correction Signals
        is_verified = False
        reliability_score = 0.7
        historical_is_analyst_corrected = False

        if historical_context:
            match_entry = historical_context.get("full_entry", {})
            is_verified = match_entry.get("verified", False)
            reliability_score = match_entry.get("reliability_score", 0.7)
            historical_is_analyst_corrected = match_entry.get("analyst_root_cause") is not None

        system_prompt = (
            "You are a Senior Production Support Engineer with expertise in troubleshooting complex enterprise systems. "
            "Analyze the provided Salesforce Case description, comments, and screenshot data to determine the root cause. "
            "Restrict hallucinations and provide analysis based only on the provided facts. "
            "\n\n"
            "### INTELLIGENCE SOURCES:\n"
            "1. **Analyst Corrections**: If the historical context is 'Analyst Corrected', treat that explanation as the Gold Standard truth.\n"
            "2. **Verified Matches**: If a historical match is 'Verified', it has a higher weight than unverified AI guesses.\n"
            "3. **Visual Evidence**: Screenshot data helps confirm technical errors (error codes, stack traces).\n"
            "\n"
            "You MUST return the output as a STRICT JSON object with the following keys:\n"
            "- impactedService: The service or component affected.\n"
            "- probableRootCause: A concise explanation of the root cause.\n"
            "- splunkQuerySuggestion: A relevant Splunk query to investigate further.\n"
            "- recommendedSteps: Concrete steps to resolve or mitigate the issue.\n"
            "- confidence: 'Low' | 'Medium' | 'High' (Categorical level)\n"
            "- confidence_score: number (0 to 100), quantify your trust in this RCA.\n"
            "- confidence_reasoning: string, a human-readable explanation referencing similarity matches, reliability of truth sources, and visual evidence.\n"
            "- isRepeatedIssue: boolean, true if this current ticket matches the patterns of the provided historical ticket.\n"
            "- similarTicketReference: string, the Ticket Number of the similar historical ticket (if any).\n"
            "- similarityScore: number, the provided similarity score if applicable.\n"
            "- visualEvidenceUsed: boolean, set to true if screenshot insights contributed to this RCA.\n"
            "\n"
            "Do NOT include any commentary or text before or after the JSON block."
        )

        user_content = f"CURRENT TICKET FOR ANALYSIS:\n\n{ticket_data}\n\n"

        user_content += "INTELLIGENCE SIGNALS:\n"
        user_content += f"- Semantic Similarity Match: {similarity_score}\n"
        user_content += f"- VISUAL EVIDENCE Found: {has_vision}\n"
        user_content += f"- Historical Match Verified: {is_verified}\n"
        user_content += f"- Historical Memory Reliability: {reliability_score}\n"
        user_content += f"- Historical is Analyst Corrected: {historical_is_analyst_corrected}\n"

        if vision_data:
            user_content += f"- Visual Extraction: {json.dumps(vision_data)}\n"
        user_content += "\n"

        if historical_context:
            title = "HISTORICAL CONTEXT (ANALYST CORRECTED)" if historical_is_analyst_corrected else "HISTORICAL CONTEXT (AI GENERATED)"

            # Prioritize Analyst Content
            h_rc = match_entry.get("analyst_root_cause") or match_entry.get("ai_root_cause") or "N/A"
            h_res = match_entry.get("analyst_resolution") or match_entry.get("ai_resolution") or "N/A"

            user_content += (
                f"{title}:\n"
                f"Previous Ticket Reference: {historical_context['ticket_number']}\n"
                f"Previous Root Cause: {h_rc}\n"
                f"Previous Resolution: {h_res}\n"
                f"Previous Raw Content: {historical_context['content'][:1000]}\n\n"
                "If the current ticket is a repeat of this historical issue, reuse the known resolution if valid. "
                "Prioritize the 'Analyst Corrected' details over everything else."
            )

        response = self.client.chat.completions.create(
            # Force gpt-4o for complex reasoning in Phase 5
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        json_output = response.choices[0].message.content
        return self._validate_and_parse(json_output)

    def reanalyze_with_logs(self, ticket_data, initial_rca, log_summary_text, vision_data=None, historical_context=None):
        """
        Phase 7: Performs an enhanced re-analysis using log evidence.
        """
        system_prompt = (
            "You are a Senior Production Support Engineer performing a Phase 2 Deep Dive. "
            "You already have an Initial RCA, but now you have been provided with real-time Splunk Log Evidence. "
            "Your goal is to provide an ENHANCED RCA that correlates the logs with the ticket description, "
            "screenshots, and historical memory."
            "\n\n"
            "### RE-ANALYSIS RULES:\n"
            "1. **Confirm or Contradict**: If logs confirm the initial suspicious service, increase confidence. If they contradict, pivot the RCA.\n"
            "2. **Precision**: Use specific details from logs (exception names, specific timestamps, error counts) to refine the probable root cause.\n"
            "3. **Recalibrate Confidence**: Follow these logic rules for the `enhanced_confidence_score`:\n"
            "   - If logs confirm the memory match: +10% score.\n"
            "   - If logs confirm visual evidence: +5% score.\n"
            "   - If logs contradict memory: -10% score.\n"
            "   - If exceptions in logs don't match the ticket context: -15% score.\n"
            "\n"
            "You MUST return the output as a STRICT JSON object with these keys:\n"
            "- enhanced_root_cause: Refined explanation using log evidence.\n"
            "- enhanced_resolution: Specific mitigation steps based on specific log findings.\n"
            "- log_correlation_summary: Briefly explain how the logs matched (or didn't) the initial findings.\n"
            "- enhanced_confidence_score: number (0-100).\n"
            "- confidence_change_reason: string explanation of the score movement.\n"
            "- dominant_exception: The main error found in logs.\n"
            "- impactedService: Final confirmed service.\n"
            "\n"
            "Do NOT include any commentary outside the JSON block."
        )

        user_content = (
            "--- CONTEXT ---\n"
            f"TICKET DATA: {ticket_data}\n"
            f"INITIAL RCA: {json.dumps(initial_rca)}\n"
            f"LOG EVIDENCE SUMMARY: {log_summary_text}\n"
        )

        if vision_data:
            user_content += f"VISION FINDINGS: {json.dumps(vision_data)}\n"

        if historical_context:
            user_content += f"HISTORICAL MATCH: {historical_context['ticket_number']} (Verified: {historical_context.get('full_entry', {}).get('verified')})\n"

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        json_output = response.choices[0].message.content
        return self._validate_and_parse(json_output, mode="enhanced")

    def _validate_and_parse(self, json_str, mode="initial"):
        """Ensure the output is valid JSON and contains required keys."""
        try:
            data = json.loads(json_str)
            if mode == "initial":
                required_keys = [
                    "impactedService", "probableRootCause", "splunkQuerySuggestion",
                    "recommendedSteps", "confidence", "confidence_score", "confidence_reasoning",
                    "isRepeatedIssue", "similarTicketReference", "similarityScore", "visualEvidenceUsed"
                ]
            else:
                required_keys = [
                    "enhanced_root_cause", "enhanced_resolution", "log_correlation_summary",
                    "enhanced_confidence_score", "confidence_change_reason", "dominant_exception",
                    "impactedService"
                ]

            for key in required_keys:
                if key not in data or data[key] is None:
                    if key == "isRepeatedIssue":
                        data[key] = False
                    elif "score" in key:
                        data[key] = 50.0
                    elif "similarity" in key:
                        data[key] = 0.0
                    else:
                        data[key] = "N/A"
            return data
        except json.JSONDecodeError:
            raise Exception("AI output was not valid JSON.")
