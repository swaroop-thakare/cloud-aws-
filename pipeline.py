import os
from typing import Any, Dict, Tuple, List

from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph

from agents import (
	GeminiNormalizer,
	ocr_extract,
	validate_document_fields,
	generate_audit_report,
)
from agents.kyc_agent import run_kyc, KycDecision
from integrations.sheets_excel import save_to_excel, save_to_google_sheets, read_reference_data


load_dotenv()


class PipelineState(dict):
	"""Simple dict-backed state for LangGraph."""


def node_document_agent(state: PipelineState) -> PipelineState:
	image_path = state.get("image_path", "")
	text = ocr_extract(image_path)
	state["ocr_text"] = text

	normalizer = GeminiNormalizer()
	structured = normalizer.normalize(text)
	state["structured_json"] = structured

	# Write initial structured data to Excel/Sheets
	excel_path = os.getenv("EXCEL_OUTPUT_PATH")
	sheet_id = os.getenv("GOOGLE_SHEETS_ID")
	payload = dict(structured)
	payload["source_image"] = image_path
	if excel_path:
		save_to_excel(payload, excel_path)
	if sheet_id:
		save_to_google_sheets(payload, sheet_id)

	return state


def node_validate(state: PipelineState) -> PipelineState:
	structured = state.get("structured_json", {})
	parsed, validation = validate_document_fields(structured)
	state["parsed"] = parsed
	state["validation"] = validation
	return state


def node_kyc(state: PipelineState) -> PipelineState:
	parsed = state.get("parsed")
	sheet_id = os.getenv("GOOGLE_SHEETS_ID")
	reference_rules: List[Dict[str, Any]] = []
	if sheet_id:
		try:
			reference_rules = read_reference_data(sheet_id)
		except Exception:
			reference_rules = []

	id_face_path = state.get("id_face_path")
	selfie_path = state.get("selfie_path")
	decision, issues, meta = run_kyc(parsed, reference_rules, id_face_path, selfie_path)
	state["kyc_decision"] = decision
	state["kyc_issues"] = issues
	state["kyc_meta"] = meta

	# Log KYC decision to Excel/Sheets
	excel_path = os.getenv("EXCEL_OUTPUT_PATH")
	sheet_id = os.getenv("GOOGLE_SHEETS_ID")
	log_row = {
		"id_number": parsed.id_number,
		"name": parsed.name,
		"kyc_decision": decision,
		"kyc_issues": "; ".join(issues) if issues else "",
	}
	if excel_path:
		save_to_excel(log_row, excel_path)
	if sheet_id:
		save_to_google_sheets(log_row, sheet_id)

	return state


def node_audit(state: PipelineState) -> PipelineState:
	parsed = state.get("parsed")
	validation = state.get("validation")
	kyc_decision = state.get("kyc_decision")
	kyc_issues = state.get("kyc_issues", [])
	report = generate_audit_report(parsed, validation)
	if kyc_decision:
		report += f"\nKYC Decision: {kyc_decision}"
		if kyc_issues:
			report += "\nKYC Issues: " + "; ".join(kyc_issues)
	state["audit_report"] = report
	return state


def node_human_review(state: PipelineState) -> PipelineState:
	decision = state.get("kyc_decision")
	if decision == KycDecision.PENDING:
		# Placeholder for routing to human review queue/system
		state["human_review_required"] = True
	else:
		state["human_review_required"] = False
	return state


def build_graph():
	graph = StateGraph(PipelineState)
	graph.add_node("document", RunnableLambda(node_document_agent))
	graph.add_node("validate", RunnableLambda(node_validate))
	graph.add_node("kyc", RunnableLambda(node_kyc))
	graph.add_node("audit", RunnableLambda(node_audit))
	graph.add_node("human_review", RunnableLambda(node_human_review))

	graph.set_entry_point("document")
	graph.add_edge("document", "validate")
	graph.add_edge("validate", "kyc")
	graph.add_edge("kyc", "audit")
	graph.add_edge("audit", "human_review")
	graph.add_edge("human_review", END)

	return graph.compile()


def run_pipeline(image_path: str, id_face_path: str = None, selfie_path: str = None) -> Tuple[Dict[str, Any], str, str]:
	"""Execute extended pipeline and return (json, report, kyc_status).

	Env vars:
	- EXCEL_OUTPUT_PATH: local Excel file path for logging.
	- GOOGLE_SHEETS_ID: target Google Sheet ID for logging and reference data.
	- GOOGLE_SHEETS_CREDENTIALS_JSON: path to service account creds JSON.
	"""
	app = build_graph()
	initial_state: PipelineState = {
		"image_path": image_path,
		"id_face_path": id_face_path,
		"selfie_path": selfie_path,
	}
	final_state: PipelineState = app.invoke(initial_state)

	structured = final_state.get("structured_json", {})
	report = final_state.get("audit_report", "")
	kyc_status = final_state.get("kyc_decision", "")
	return structured, report, kyc_status


# TODOs for future-proofing:
# - Payment Agent (UPI/Stripe) post-KYC success
# - Multimodal Queries (image + text Q&A with Gemini)
# - Dashboard (Streamlit/React) for KYC status
# - Compliance reports export (PDF/Excel)
# - Webhook endpoints for external CRM integrations
# - LangGraph state memory for past KYC verifications
