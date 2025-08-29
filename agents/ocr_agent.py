import os
from typing import Optional

import cv2
import pytesseract
from PIL import Image


def _ensure_tesseract_cmd_from_env() -> None:
	"""Optionally set the tesseract binary path from the TESSERACT_CMD env var.

	On macOS with Homebrew: export TESSERACT_CMD="/opt/homebrew/bin/tesseract"
	"""
	tesseract_cmd = os.getenv("TESSERACT_CMD")
	if tesseract_cmd:
		pytesseract.pytesseract.tesseract_cmd = tesseract_cmd


def _load_image(image_path: str) -> Optional[Image.Image]:
	try:
		return Image.open(image_path)
	except Exception:
		return None


def _preprocess_for_ocr(image_path: str) -> Optional[Image.Image]:
	"""Lightweight preprocessing: grayscale + threshold for OCR robustness."""
	try:
		img_bgr = cv2.imread(image_path)
		if img_bgr is None:
			return None
		gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
		# Adaptive thresholding tends to help on uneven lighting
		thresh = cv2.adaptiveThreshold(
			gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2
		)
		# Convert back to PIL for pytesseract
		pil_img = Image.fromarray(thresh)
		return pil_img
	except Exception:
		return _load_image(image_path)


def ocr_extract(image_path: str) -> str:
	"""Extract raw text from an image using Tesseract OCR via pytesseract.

	- Reads Tesseract binary path from env `TESSERACT_CMD` if provided.
	- Applies simple preprocessing to improve OCR quality.
	- Returns the raw extracted string (may include newlines and noise).
	"""
	_ensure_tesseract_cmd_from_env()

	# Try preprocessed image first, fall back to original
	preprocessed = _preprocess_for_ocr(image_path)
	if preprocessed is not None:
		try:
			text = pytesseract.image_to_string(preprocessed)
			if text and text.strip():
				return text
		except Exception:
			pass

	original = _load_image(image_path)
	if original is None:
		return ""

	try:
		return pytesseract.image_to_string(original)
	except Exception:
		return ""
