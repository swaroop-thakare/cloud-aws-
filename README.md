# Intelligent-Image-Processing-using-Object-Detection-and-OCR

## OCR + Gemini + Validation + Audit Pipeline (LangGraph)

This project provides a modular pipeline to extract text via Tesseract OCR, normalize it with Google Gemini, validate fields, and generate a human-readable audit report. Orchestration is done with LangGraph.

### Setup
1. Install Tesseract (macOS with Homebrew):
   - `brew install tesseract`
   - Optional: set the path if needed: `export TESSERACT_CMD="/opt/homebrew/bin/tesseract"`

2. Python dependencies:
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`

3. Environment variables:
   - Create a `.env` file with:
     - `GEMINI_API_KEY=your_key_here`
     - (Alternative supported) `GOOGLE_AI_API_KEY=your_key_here`
     - Optional: `GEMINI_MODEL=gemini-1.5-pro`
     - Optional: `TESSERACT_CMD=/opt/homebrew/bin/tesseract`

### Usage
```python
from pipeline import run_pipeline

structured, report = run_pipeline("/absolute/path/to/your/image.jpg")
print(structured)
print(report)
```

- Final output includes structured JSON fields (name, dob, id_number, address, etc.) and an explanation string.

### Project Structure
- `agents/ocr_agent.py`: OCR agent using pytesseract
- `agents/gemini_agent.py`: Gemini agent to normalize OCR text to JSON
- `agents/validation_agent.py`: Validates required fields and formats
- `agents/audit_agent.py`: Generates human-readable report
- `pipeline.py`: LangGraph orchestration with `run_pipeline(image_path)`
- `p.py`: Existing Flask demo (unmodified)

### Notes
- The pipeline gracefully requires a valid `GEMINI_API_KEY`/`GOOGLE_AI_API_KEY` for the Gemini step.
- For CI or offline testing, you can mock the Gemini call or set the env var and use a test key.

### TODO
- Excel export and Google Sheets integration hooks in `pipeline.py` (placeholders provided).
# cloud-aws-
