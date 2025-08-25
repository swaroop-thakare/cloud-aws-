import os
import tempfile
from flask import Flask, request, jsonify, render_template
import cv2
import pytesseract
import re
import google.generativeai as genai
from dotenv import load_dotenv
import numpy as np

# -------------------- App Setup --------------------
app = Flask(__name__)

load_dotenv()

GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")
if GOOGLE_AI_API_KEY:
    genai.configure(api_key=GOOGLE_AI_API_KEY)
    llm = genai.GenerativeModel("gemini-1.5-pro")
else:
    llm = None  # Handle gracefully if no key found

# Static folder to save processed images
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/processed')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# -------------------- Image Processing --------------------
def preprocess_image(image: np.ndarray):
    """Return grayscale, thresholded, and edge-detected versions of the image."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # Edge detection
    edges = cv2.Canny(thresh, 50, 150)

    return gray, thresh, edges


def detect_text_regions(binary_image: np.ndarray):
    """Detect text-like contours and draw boxes on a copy of the input.
    Returns (marked_image, boxes)
    """
    contours, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    marked_image = binary_image.copy()
    marked_image = cv2.cvtColor(marked_image, cv2.COLOR_GRAY2BGR) if len(marked_image.shape) == 2 else marked_image

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > 20 and h > 20:  # Filter small noise
            boxes.append((x, y, w, h))
            cv2.rectangle(marked_image, (x, y), (x + w, y + h), (0, 255, 0), 2)

    return marked_image, boxes


# -------------------- Routes --------------------
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/process_image', methods=['POST'])
def extract_info_from_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    image_file = request.files['image']

    with tempfile.TemporaryDirectory() as temp_dir:
        image_path = os.path.join(temp_dir, "uploaded_image.jpg")
        image_file.save(image_path)

        # Read and process image
        original = cv2.imread(image_path)
        if original is None:
            return jsonify({'error': 'Invalid image or format not supported'}), 400

        gray, thresh, edges = preprocess_image(original)

        # Detect text regions and draw bounding boxes
        marked_image, boxes = detect_text_regions(thresh)

        # Save processing steps
        cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], 'original.jpg'), original)
        cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], 'grayscale.jpg'), gray)
        cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], 'threshold.jpg'), thresh)
        cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], 'edges.jpg'), edges)
        cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], 'text_detection.jpg'), marked_image)

        # Extract text using the enhanced image
        extracted_text = pytesseract.image_to_string(thresh)

        # -------------------- Regex Patterns --------------------
        name_pattern = r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s[A-Z][a-z]+\b'
        company_name_pattern = r'(?<=@)([A-Za-z0-9.-]+)(?=\.)'
        email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}'
        website_pattern = r'(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?'

        # -------------------- Structured Extraction via Regex --------------------
        names = re.findall(name_pattern, extracted_text)
        name = names[0] if names else ""

        email_addresses = re.findall(email_pattern, extracted_text)

        company_name_matches = re.findall(company_name_pattern, extracted_text)
        company_name = company_name_matches[0] if company_name_matches else ""

        websites = re.findall(website_pattern, extracted_text)
        if not websites and company_name:
            # Fallback to company.com if no explicit website found
            default_website = f"{company_name}.com"
            websites = [default_website]

        # -------------------- LLM-assisted Extraction --------------------
        # Phone numbers
        phone_numbers = []
        if llm is not None:
            phone_prompt = f"""
            Extract only valid phone numbers from the following text. Ignore postal codes or any 6-digit numbers that appear to be part of addresses.
            Valid phone numbers typically:
            - Are 10 digits or more (excluding country code)
            - May start with + or country code
            - May contain spaces, hyphens, or parentheses
            - Should not be postal/ZIP codes

            Text: {extracted_text}

            Phone Numbers:
            """
            try:
                phone_response = llm.generate_content(phone_prompt)
                phone_numbers_text = getattr(phone_response, 'text', '')
                phone_numbers_text = (phone_numbers_text or '').strip()
                if phone_numbers_text and phone_numbers_text.lower() != "no phone numbers found":
                    phone_numbers = [line.strip() for line in phone_numbers_text.split('\n') if line.strip()]
            except Exception:
                phone_numbers = []
        else:
            # Basic regex fallback for numbers if no API key
            # Matches sequences that look like phone numbers
            basic_phone_matches = re.findall(r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{3,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}", extracted_text)
            phone_numbers = [p.strip() for p in basic_phone_matches]

        # Clean up phone numbers: remove - . spaces (keep + and digits)
        phone_numbers = [re.sub(r'[-.\s()]', '', phone) for phone in phone_numbers]
        # Deduplicate while preserving order
        phone_numbers = list(dict.fromkeys(phone_numbers))

        # Address
        if llm is not None:
            address_prompt = f"""
            Extract the full address from the following text. The address should include any building name, floor number, street, area, city, and postal code. Format it as a single string.
            If you can't find a full address, return the partial address like city, state, country as a single string.

            Text: {extracted_text}

            Address:
            """
            try:
                address_response = llm.generate_content(address_prompt)
                address_text = getattr(address_response, 'text', '')
                address = (address_text or '').strip() or "Could not extract address"
            except Exception:
                address = "Could not extract address"
        else:
            # Very basic fallback: try to catch PIN-like and city words
            address = ""
            # look for 6-digit PINs
            pin = re.search(r"\b\d{6}\b", extracted_text)
            # naive city/state capture (words after 'City' or 'State' or 'India')
            city_like = re.search(r"(?:City|Mumbai|Pune|Delhi|Bengaluru|Hyderabad|Chennai|Kolkata|Ahmedabad)\b.*", extracted_text, re.IGNORECASE)
            parts = []
            if city_like:
                parts.append(city_like.group(0).strip())
            if pin:
                parts.append(pin.group(0))
            address = ", ".join(parts) or "Could not extract address"

        # Designation
        if llm is not None:
            designation_prompt = f"""
            Extract the job title or designation from the following text and only give the designation in 2 to 3 words. Do not add any extra symbols.

            Text: {extracted_text}

            Designation(s):
            """
            try:
                designation_response = llm.generate_content(designation_prompt)
                desig_text = getattr(designation_response, 'text', '')
                designations = (desig_text or '').strip() or "Could not extract designation"
            except Exception:
                designations = "Could not extract designation"
        else:
            # Fallback heuristic for common titles
            m = re.search(r"\b(CEO|CTO|COO|Founder|Manager|Director|Engineer|Consultant|Analyst|Designer)\b", extracted_text, re.IGNORECASE)
            designations = m.group(0) if m else "Could not extract designation"

        # -------------------- Build Response --------------------
        structured_data = {
            "response": "Thanks! Your lead has been created.",
            "saved_data": {
                "address": address,
                "contact_name": name,
                "information": {
                    "designation": [designations],
                    "email": email_addresses,
                    "number": phone_numbers,
                },
                "name": company_name,
                "session_id": "",
                "user-id": ""
            }
        }

        return jsonify(structured_data), 200


# -------------------- Entry Point --------------------
if __name__ == '__main__':
    # For production, use a proper WSGI server
    app.run(debug=True)
