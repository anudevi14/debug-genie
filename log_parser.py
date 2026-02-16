import re
from collections import Counter
from datetime import datetime

class LogParser:
    def __init__(self):
        # Common log patterns
        self.exception_pattern = re.compile(r'([a-zA-Z0-9.]+Exception|Error): (.*)')
        self.timestamp_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)')
        self.service_pattern = re.compile(r'service=["\']?([a-zA-Z0-9_-]+)["\']?')
        self.env_pattern = re.compile(r'env=["\']?([a-zA-Z0-9_-]+)["\']?')

    def parse(self, log_text):
        """
        Parses raw log text and returns a structured summary of patterns.
        """
        lines = log_text.splitlines()
        if not lines:
            return None

        exceptions = []
        timestamps = []
        services = set()
        envs = set()
        error_lines = []

        for line in lines:
            # 1. Extract Timestamps
            ts_match = self.timestamp_pattern.search(line)
            if ts_match:
                timestamps.append(ts_match.group(1))

            # 2. Detect Errors/Exceptions
            if "ERROR" in line.upper() or "FATAL" in line.upper() or "EXCEPTION" in line.upper():
                error_lines.append(line)
                exc_match = self.exception_pattern.search(line)
                if exc_match:
                    exceptions.append(exc_match.group(1))

            # 3. Detect Metadata (Service, Env)
            svc_match = self.service_pattern.search(line)
            if svc_match:
                services.add(svc_match.group(1))
            
            env_match = self.env_pattern.search(line)
            if env_match:
                envs.add(env_match.group(1))

        if not error_lines and not exceptions:
            return {
                "status": "No clear errors detected",
                "line_count": len(lines)
            }

        # clustering & summarization
        exc_counts = Counter(exceptions)
        top_exception = exc_counts.most_common(1)[0] if exceptions else ("Unknown Pattern", 0)
        
        # Time Window
        time_window = "Unknown"
        if timestamps:
            try:
                # Basic string sort works for ISO formats
                timestamps.sort()
                time_window = f"{timestamps[0]} to {timestamps[-1]}"
            except:
                pass

        # Identify Dominant Error Pattern
        # Group lines that are similar (very basic clustering for MVP)
        unique_error_patterns = Counter([l[:100] for l in error_lines]).most_common(3)

        return {
            "top_exception": top_exception[0],
            "exception_count": top_exception[1],
            "total_error_lines": len(error_lines),
            "time_window": time_window,
            "detected_services": list(services),
            "environments": list(envs),
            "dominant_patterns": [p[0] for p in unique_error_patterns],
            "line_count": len(lines)
        }

    def format_for_ai(self, summary):
        """Converts the summary dict into a text block for prompt injection."""
        if not summary or "top_exception" not in summary:
            return "No structured log insights available."

        text = (
            f"Log Analysis Summary:\n"
            f"- Top Exception: {summary['top_exception']} (Occurrences: {summary['exception_count']})\n"
            f"- Total Error Lines Detected: {summary['total_error_lines']}\n"
            f"- Time Window: {summary['time_window']}\n"
            f"- Services Identified: {', '.join(summary['detected_services']) or 'Unknown'}\n"
            f"- Environment(s): {', '.join(summary['environments']) or 'Unknown'}\n"
            f"- Dominant Pattern: {summary['dominant_patterns'][0] if summary['dominant_patterns'] else 'N/A'}"
        )
        return text
