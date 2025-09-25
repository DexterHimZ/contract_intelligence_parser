import fitz  # PyMuPDF
import cv2
import numpy as np
import pytesseract
from typing import List, Dict, Tuple, Optional
import hashlib
from pathlib import Path
import logging
from PIL import Image
import io

logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDF processing service for text extraction with OCR fallback"""

    def __init__(self):
        self.min_text_length = 100  # Minimum text length to consider page as digital

    def extract_text_from_pdf(self, pdf_path: str) -> Tuple[List[Dict], bool]:
        """
        Extract text from PDF with OCR fallback for scanned pages
        Returns: (pages_data, ocr_used)
        """
        pages_data = []
        ocr_used = False

        try:
            # Open PDF document
            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Try digital text extraction first
                text = page.get_text("text")

                # Check if page has enough digital text
                if len(text.strip()) < self.min_text_length:
                    # Page might be scanned, use OCR
                    logger.info(f"Page {page_num + 1} appears to be scanned, using OCR")
                    ocr_text = self._ocr_page(page)
                    if ocr_text:
                        text = ocr_text
                        ocr_used = True

                pages_data.append({
                    "page": page_num + 1,
                    "content": self._normalize_text(text)
                })

            doc.close()

        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            raise

        return pages_data, ocr_used

    def _ocr_page(self, page) -> str:
        """Perform OCR on a PDF page"""
        try:
            # Render page to image
            mat = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for better OCR
            img_data = mat.tobytes("png")

            # Convert to PIL Image
            img = Image.open(io.BytesIO(img_data))

            # Convert to OpenCV format
            open_cv_image = np.array(img)
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)

            # Apply image preprocessing for better OCR
            # Denoise
            denoised = cv2.fastNlMeansDenoising(gray)

            # Apply threshold to get binary image
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Perform OCR
            text = pytesseract.image_to_string(thresh, lang='eng')

            return text

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""

    def _normalize_text(self, text: str) -> str:
        """Normalize extracted text"""
        # Remove excessive whitespace while preserving paragraph breaks
        lines = text.split('\n')
        normalized_lines = []

        for line in lines:
            line = line.strip()
            if line:
                # Replace multiple spaces with single space
                line = ' '.join(line.split())
                normalized_lines.append(line)

        # Join with single newline
        return '\n'.join(normalized_lines)

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def get_pdf_metadata(self, pdf_path: str) -> Dict:
        """Extract PDF metadata"""
        try:
            doc = fitz.open(pdf_path)
            metadata = doc.metadata
            page_count = len(doc)
            doc.close()

            return {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
                "creation_date": str(metadata.get("creationDate", "")),
                "modification_date": str(metadata.get("modDate", "")),
                "page_count": page_count
            }
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {}

    def validate_pdf(self, file_path: str, max_size_mb: int = 50) -> Tuple[bool, str]:
        """Validate PDF file"""
        try:
            # Check file size
            file_size = Path(file_path).stat().st_size
            if file_size > max_size_mb * 1024 * 1024:
                return False, f"File size exceeds {max_size_mb}MB limit"

            # Try to open as PDF
            doc = fitz.open(file_path)
            if doc.is_pdf:
                page_count = len(doc)
                doc.close()

                if page_count == 0:
                    return False, "PDF has no pages"

                return True, "Valid PDF"
            else:
                doc.close()
                return False, "File is not a valid PDF"

        except Exception as e:
            return False, f"Invalid PDF: {str(e)}"