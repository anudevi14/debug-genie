import json
from typing import TypedDict, List, Optional, Annotated, Union
from langgraph.graph import StateGraph, END
from src.agents.ai_analyzer import AIAnalyzer
from src.engine.similarity_engine import SimilarityEngine
from src.engine.memory_manager import MemoryManager
from src.utils.log_parser import LogParser
from src.clients.salesforce_client import SalesforceClient

# Define the shared state for the investigation
class InvestigationState(TypedDict):
    ticket_id: str
    ticket_data: Optional[dict]
    case_obj: Optional[dict]
    vision_data: Optional[dict]
    similarity_context: Optional[dict]
    text_for_embedding: Optional[str]
    current_embedding: Optional[List[float]]
    initial_rca: Optional[dict]
    log_data: Optional[str]
    log_summary: Optional[dict]
    enhanced_rca: Optional[dict]
    confidence_score: float
    status_updates: List[str]

class InvestigationGraph:
    def __init__(self, sf_client, ai_analyzer, similarity_engine, memory_manager, log_parser):
        self.sf_client = sf_client
        self.ai_analyzer = ai_analyzer
        self.similarity_engine = similarity_engine
        self.memory_manager = memory_manager
        self.log_parser = log_parser
        self.workflow = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(InvestigationState)

        # Add Nodes
        graph.add_node("ingest_ticket", self.node_ingest_ticket)
        graph.add_node("extract_visuals", self.node_extract_visuals)
        graph.add_node("query_memory", self.node_query_memory)
        graph.add_node("generate_rca", self.node_generate_rca)
        graph.add_node("analyze_logs", self.node_analyze_logs)
        graph.add_node("synthesize_findings", self.node_synthesize_findings)

        # Define Edges
        graph.set_entry_point("ingest_ticket")
        
        graph.add_edge("ingest_ticket", "extract_visuals")
        graph.add_edge("extract_visuals", "query_memory")
        graph.add_edge("query_memory", "generate_rca")
        
        # Intermediate routing: Should we do a log deep dive immediately if logs provided 
        # or if confidence is low? For now, let's make it a sequence that can be triggered.
        # In a real agentic flow, we might loop.
        
        graph.add_conditional_edges(
            "generate_rca",
            self.route_after_rca,
            {
                "log_deep_dive": "analyze_logs",
                "finalize": "synthesize_findings"
            }
        )
        
        graph.add_edge("analyze_logs", "synthesize_findings")
        graph.add_edge("synthesize_findings", END)

        return graph.compile()

    # --- Nodes ---

    def node_ingest_ticket(self, state: InvestigationState):
        ticket_id = state["ticket_id"]
        updates = state.get("status_updates", [])
        updates.append("🔍 Fetching Ticket Data...")
        
        ticket_data, case_obj = self.sf_client.get_full_ticket_data(ticket_id)
        if not ticket_data:
            raise ValueError(f"Ticket #{ticket_id} not found.")
            
        return {
            "ticket_data": ticket_data, 
            "case_obj": case_obj,
            "status_updates": updates
        }

    def node_extract_visuals(self, state: InvestigationState):
        case_obj = state["case_obj"]
        updates = state["status_updates"]
        updates.append("📸 Inspecting Attachments & Screenshots...")
        
        vision_data = None
        attachments = self.sf_client.fetch_case_attachments(case_obj["Id"])
        if attachments:
            attach = attachments[0]
            img_base64 = self.sf_client.get_attachment_content(attach["Id"], source=attach.get("Source", "Attachment"))
            vision_data = self.ai_analyzer.vision_extract(img_base64, content_type=attach.get("ContentType", "image/jpeg"))
            
        return {"vision_data": vision_data, "status_updates": updates}

    def node_query_memory(self, state: InvestigationState):
        case_obj = state["case_obj"]
        vision_data = state["vision_data"]
        updates = state["status_updates"]
        updates.append("🧠 Querying Semantic Memory...")
        
        text_for_embedding = self.sf_client.get_ticket_text_for_comparison(case_obj)
        if vision_data:
            text_for_embedding += f"\nVisual Markers: {json.dumps(vision_data)}"
        
        current_embedding = self.ai_analyzer.get_embedding(text_for_embedding)
        similar_match, score = self.similarity_engine.find_most_similar_semantic(
            current_embedding, self.memory_manager.get_all_entries()
        )
        
        similarity_context = None
        if similar_match:
            similarity_context = {
                "ticket_number": similar_match['case_number'],
                "score": round(float(score), 2),
                "content": similar_match['text'],
                "full_entry": similar_match
            }
            
        return {
            "text_for_embedding": text_for_embedding,
            "current_embedding": current_embedding,
            "similarity_context": similarity_context,
            "status_updates": updates
        }

    def node_generate_rca(self, state: InvestigationState):
        updates = state["status_updates"]
        updates.append("🤖 Generating Autonomous RCA...")
        
        initial_rca = self.ai_analyzer.analyze_ticket(
            state["ticket_data"], 
            historical_context=state["similarity_context"], 
            vision_data=state["vision_data"]
        )
        
        # Auto-save to memory
        self.memory_manager.save_memory([{
            "case_number": state["ticket_id"],
            "text": state["text_for_embedding"],
            "embedding": state["current_embedding"],
            "root_cause": initial_rca.get("probableRootCause"),
            "resolution": initial_rca.get("recommendedSteps")
        }])
        
        return {
            "initial_rca": initial_rca, 
            "confidence_score": initial_rca.get("confidence_score", 0.0),
            "status_updates": updates
        }

    def node_analyze_logs(self, state: InvestigationState):
        updates = state["status_updates"]
        updates.append("🔍 Correlating Log Evidence...")
        
        log_txt = state["log_data"]
        summary = self.log_parser.parse(log_txt)
        enhanced_rca = self.ai_analyzer.reanalyze_with_logs(
            state["ticket_data"], 
            state["initial_rca"],
            self.log_parser.format_for_ai(summary), 
            vision_data=state["vision_data"],
            historical_context=state["similarity_context"]
        )
        
        return {
            "log_summary": summary,
            "enhanced_rca": enhanced_rca,
            "confidence_score": enhanced_rca.get("enhanced_confidence_score", state["confidence_score"]),
            "status_updates": updates
        }

    def node_synthesize_findings(self, state: InvestigationState):
        updates = state["status_updates"]
        updates.append("💾 Finalizing Deep Investigation...")
        return {"status_updates": updates}

    # --- Routing ---

    def route_after_rca(self, state: InvestigationState):
        # If logs are already provided in the state (e.g. from user input during multi-step), go to log analysis
        # Or if confidence is critically low (< 40) we might want to flag for log deep dive
        if state.get("log_data"):
            return "log_deep_dive"
        
        # Example of agentic decision making: 
        # if state["confidence_score"] < 50:
        #    return "log_deep_dive" # in a real world, this would trigger an automated splunk fetch
        
        return "finalize"

    def run(self, ticket_id: str, log_data: Optional[str] = None):
        initial_state = {
            "ticket_id": ticket_id,
            "log_data": log_data,
            "status_updates": [],
            "confidence_score": 0.0
        }
        return self.workflow.invoke(initial_state)
