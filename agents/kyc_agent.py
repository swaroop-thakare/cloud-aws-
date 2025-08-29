import re
from typing import Any, Dict, List, Optional, Tuple

import cv2

from .validation_agent import DocumentFields


AADHAAR_RE = re.compile(r"^\d{12}$")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]{1}$", re.IGNORECASE)
GST_RE = re.compile(r"^[0-9A-Z]{15}$", re.IGNORECASE)


class KycDecision:
	APPROVED = "verified"
	PENDING = "pending_review"
	REJECTED = "failed"


def _check_id_rules(fields: DocumentFields, reference_rules: Optional[List[Dict[str, Any]]]) -> List[str]:
	issues: List[str] = []
	id_num = (fields.id_number or "").replace(" ", "")
	if AADHAAR_RE.match(id_num) is None and GST_RE.match(id_num) is None and PAN_RE.match(id_num) is None:
		issues.append("id_number does not match Aadhaar(12d)/GST(15)/PAN(10) formats")
	if reference_rules:
		# Example rule: disallow IDs present in a blacklist
		blacklisted = {str(r.get("blacklist_id")).strip() for r in reference_rules if r.get("blacklist_id")}
		if id_num in blacklisted:
			issues.append("id_number is blacklisted in reference data")
	return issues


def _mock_api_check(fields: DocumentFields) -> Tuple[bool, str]:
	"""Stub external verification. Returns (ok, note)."""
	id_num = (fields.id_number or "").strip()
	if id_num.endswith("0000"):
		return False, "mock api: suspicious pattern"
	return True, "mock api: ok"


def _optional_face_match(id_image_path: Optional[str], selfie_image_path: Optional[str]) -> Tuple[Optional[bool], str]:
	"""Optional face match using OpenCV as a stub (placeholder for DeepFace)."""
	if not id_image_path or not selfie_image_path:
		return None, "no face images provided"
	try:
		img1 = cv2.imread(id_image_path, cv2.IMREAD_GRAYSCALE)
		img2 = cv2.imread(selfie_image_path, cv2.IMREAD_GRAYSCALE)
		if img1 is None or img2 is None:
			return None, "face images unreadable"
		# Very naive histogram correlation as a placeholder
		score = cv2.compareHist(cv2.calcHist([img1],[0],None,[256],[0,256]), cv2.calcHist([img2],[0],None,[256],[0,256]), cv2.HISTCMP_CORREL)
		return (score > 0.9), f"face_match_score={score:.3f}"
	except Exception as e:
		return None, f"face match error: {e}"


def run_kyc(fields: DocumentFields, reference_rules: Optional[List[Dict[str, Any]]] = None, id_face_path: Optional[str] = None, selfie_path: Optional[str] = None) -> Tuple[str, List[str], Dict[str, Any]]:
	"""Run KYC checks and return (decision, issues, metadata)."""
	issues: List[str] = []
	meta: Dict[str, Any] = {}

	issues.extend(_check_id_rules(fields, reference_rules))

	ok, note = _mock_api_check(fields)
	if not ok:
		issues.append("external verification failed: " + note)
	meta["external_note"] = note

	match, fm_note = _optional_face_match(id_face_path, selfie_path)
	if match is False:
		issues.append("face match failed")
	meta["face_match_note"] = fm_note

	if issues:
		# If issues but not critical, send to pending review
		decision = KycDecision.PENDING if any("blacklisted" not in i for i in issues) else KycDecision.REJECTED
	else:
		decision = KycDecision.APPROVED

	return decision, issues, meta
