import json
import os
import re
from typing import Any, Dict, Optional, Union

import google.generativeai as genai
import pandas as pd


SYSTEM_PROMPT = (
	"You are a data extraction and KYC assistant. Given OCR text from an ID or document, "
	"you clean, normalize, classify document type, validate key number formats, and return strict JSON."
)

USER_INSTRUCTIONS = (
	"Return ONLY valid JSON with these top-level keys: name, dob, id_number, address, document_type, "
	"and optionally: email, phone, nationality, gst_number. Use ISO date format YYYY-MM-DD for dob if derivable; "
	"otherwise empty string. If a field is missing, set it to empty string. No explanations."
	"\nAlso include a 'validations' object with boolean flags you infer: { 'aadhaar_valid': bool, 'gst_valid': bool }."
)

DOC_TYPE_GUIDE = (
	"Document type should be one of: Aadhaar, PAN, Passport, DriverLicense, GST, Invoice, BankStatement, Other."
)

FORMAT_GUIDE = (
	"Validation rules: Aadhaar is 12 digits; GSTIN is 15 alphanumeric chars; PAN is 10 alphanumeric."
)


def _configure_gemini() -> None:
	api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")
	if not api_key:
		raise RuntimeError(
			"Missing GEMINI_API_KEY (or GOOGLE_AI_API_KEY) environment variable."
		)
	genai.configure(api_key=api_key)


class GeminiNormalizer:
	"""Wrapper around Google Generative AI to normalize OCR text into structured JSON."""

	def __init__(self, model_name: Optional[str] = None) -> None:
		_configure_gemini()
		self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
		self.model = genai.GenerativeModel(self.model_name)

	def _build_prompt(self, raw_text: str) -> str:
		return (
			f"{SYSTEM_PROMPT}\n\n{USER_INSTRUCTIONS}\n\n{DOC_TYPE_GUIDE}\n{FORMAT_GUIDE}\n\n"
			f"OCR_TEXT:\n{raw_text}\n\nJSON:"
		)

	def _extract_json(self, text: str) -> Dict[str, Any]:
		text = text.strip()
		fenced_match = re.search(r"```(?:json)?\n([\s\S]*?)\n```", text)
		if fenced_match:
			text = fenced_match.group(1).strip()
		try:
			data = json.loads(text)
			if isinstance(data, dict):
				return data
		except Exception:
			pass
		json_like = re.search(r"\{[\s\S]*\}", text)
		if json_like:
			try:
				return json.loads(json_like.group(0))
			except Exception:
				pass
		return {
			"name": "",
			"dob": "",
			"id_number": "",
			"address": "",
			"document_type": "",
			"validations": {"aadhaar_valid": False, "gst_valid": False},
		}

	def normalize(self, raw_text: str) -> Dict[str, Any]:
		prompt = self._build_prompt(raw_text)
		response = self.model.generate_content(prompt)
		text = getattr(response, "text", "") or ""
		return self._extract_json(text)

	def ask_gemini(self, question: str, context: Union[Dict[str, Any], pd.DataFrame]) -> str:
		"""Ask a question with contextual grounding in existing results (dict or DataFrame)."""
		if isinstance(context, pd.DataFrame):
			ctx_text = context.to_csv(index=False)
		else:
			ctx_text = json.dumps(context, ensure_ascii=False)
		prompt = (
			f"You are an analytics assistant. Answer the user's question using the provided context.\n"
			f"Return a concise textual answer.\n\nCONTEXT:\n{ctx_text}\n\nQUESTION: {question}\nANSWER:"
		)
		response = self.model.generate_content(prompt)
		return getattr(response, "text", "") or ""
