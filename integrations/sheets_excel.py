import os
from typing import Any, Dict, List

import pandas as pd
import openpyxl  # noqa: F401 - imported for engine registration
import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
	"https://www.googleapis.com/auth/spreadsheets",
	"https://www.googleapis.com/auth/drive",
]


def _get_gspread_client() -> gspread.Client:
	"""Authenticate with Google Sheets via service account JSON pointed by env.

	Set GOOGLE_SHEETS_CREDENTIALS_JSON=/absolute/path/creds.json
	"""
	creds_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
	if not creds_path or not os.path.exists(creds_path):
		raise RuntimeError("Missing GOOGLE_SHEETS_CREDENTIALS_JSON or file not found")
	creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
	client = gspread.authorize(creds)
	return client


def save_to_excel(data: Dict[str, Any], file_path: str) -> None:
	"""Append a row to a local Excel file with normalized keys.

	If the file doesn't exist, create it with headers.
	"""
	df = pd.DataFrame([data])
	if not os.path.exists(file_path):
		with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
			df.to_excel(writer, index=False, sheet_name="data")
		return

	# Append mode
	existing = pd.read_excel(file_path, sheet_name="data")
	combined = pd.concat([existing, df], ignore_index=True)
	with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
		combined.to_excel(writer, index=False, sheet_name="data")


def save_to_google_sheets(data: Dict[str, Any], sheet_id: str) -> None:
	"""Append a row to a Google Sheet (first worksheet by default)."""
	client = _get_gspread_client()
	sh = client.open_by_key(sheet_id)
	ws = sh.get_worksheet(0) or sh.sheet1
	# Ensure headers
	headers = ws.row_values(1)
	if not headers:
		headers = list(data.keys())
		ws.append_row(headers)
	# Reorder values according to headers, adding new headers if needed
	new_keys = [k for k in data.keys() if k not in headers]
	if new_keys:
		# extend headers
		headers.extend(new_keys)
		ws.update("1:1", [headers])
	row = [data.get(h, "") for h in headers]
	ws.append_row(row)


def read_reference_data(sheet_id: str) -> List[Dict[str, Any]]:
	"""Read reference data from the second worksheet or named 'reference'."""
	client = _get_gspread_client()
	sh = client.open_by_key(sheet_id)
	ws = None
	for w in sh.worksheets():
		if w.title.lower() in ("reference", "refs", "rules"):
			ws = w
			break
	if ws is None:
		ws = sh.sheet1 if sh.worksheets() else None
		if ws is None:
			return []
	records = ws.get_all_records()
	return records
