import io
from pdfminer.high_level import extract_text
import logging
from typing import Tuple

def extract_text_from_pdf(pdf_bytes: bytes) -> Tuple[str, str]:
    if not pdf_bytes or len(pdf_bytes) == 0:
        logging.warning("PDF bytes are empty!")
        return "", "file is empty"
    try:
        with io.BytesIO(pdf_bytes) as pdf_buffer:
            text = extract_text(pdf_buffer)
        if not text or text.strip() == "":
            msg = "pdfminer: extracted empty text from buffer"
            logging.warning(msg)
            return "", msg
        logging.info(f"pdfminer extract succeeded ({len(text)} chars)")
        return text.strip(), None
    except Exception as e:
        logging.error(f"pdfminer PDF extract error: {e}")
        return "", str(e)
