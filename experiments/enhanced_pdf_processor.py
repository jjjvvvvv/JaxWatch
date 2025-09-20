#!/usr/bin/env python3
"""
JaxWatch Enhanced PDF Processor
Handles both text-based and scanned PDFs with OCR fallback
Principles: Robust extraction, graceful degradation, quality validation
"""

import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pdfplumber
import hashlib
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import OCR libraries (optional dependencies)
try:
    import pytesseract
    from PIL import Image
    import pdf2image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

class PDFProcessingResult:
    """Container for PDF processing results"""

    def __init__(self):
        self.success = False
        self.text_content = ""
        self.method_used = ""  # "text_extraction", "ocr", "hybrid"
        self.page_count = 0
        self.quality_score = 0.0  # 0-100, how readable the text is
        self.warnings = []
        self.errors = []
        self.processing_time = 0.0
        self.metadata = {}

class EnhancedPDFProcessor:
    """Enhanced PDF processor with OCR fallback and quality validation"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.logger = logging.getLogger(__name__)

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for PDF processing"""
        return {
            # Text extraction settings
            "min_text_threshold": 50,  # Minimum characters for text-based extraction
            "min_text_quality": 0.3,  # Minimum quality score for text extraction

            # OCR settings
            "ocr_enabled": OCR_AVAILABLE,
            "ocr_language": "eng",
            "ocr_dpi": 300,
            "ocr_threshold": 200,  # Minimum characters for OCR to be considered successful

            # Hybrid mode settings
            "hybrid_enabled": True,
            "text_confidence_threshold": 0.7,

            # Performance settings
            "max_file_size_mb": 50,
            "max_pages": 200,
            "timeout_seconds": 300,

            # Quality validation
            "validate_content": True,
            "expected_patterns": [
                r"agenda",
                r"meeting",
                r"planning commission",
                r"city council",
                r"item \d+"
            ]
        }

    def process_pdf(self, pdf_path: Path) -> PDFProcessingResult:
        """Main PDF processing method with fallback strategies"""

        result = PDFProcessingResult()
        start_time = datetime.now()

        try:
            # Validate input file
            validation = self._validate_pdf_file(pdf_path)
            if not validation["valid"]:
                result.errors.extend(validation["errors"])
                result.warnings.extend(validation["warnings"])
                return result

            result.page_count = validation["page_count"]
            result.metadata.update(validation["metadata"])

            # Try text extraction first
            text_result = self._extract_text_based(pdf_path)

            if text_result["success"] and text_result["quality_score"] >= self.config["min_text_quality"]:
                # Text extraction successful
                result.success = True
                result.text_content = text_result["content"]
                result.method_used = "text_extraction"
                result.quality_score = text_result["quality_score"]
                result.warnings.extend(text_result["warnings"])

                self.logger.info(f"Text extraction successful (quality: {result.quality_score:.2f})")

            elif self.config["ocr_enabled"] and OCR_AVAILABLE:
                # Try OCR fallback
                self.logger.info("Text extraction insufficient, trying OCR...")
                ocr_result = self._extract_with_ocr(pdf_path)

                if ocr_result["success"]:
                    if (self.config["hybrid_enabled"] and
                        text_result["success"] and
                        len(text_result["content"]) > self.config["min_text_threshold"]):
                        # Hybrid mode: combine text and OCR
                        result.text_content = self._combine_text_and_ocr(
                            text_result["content"], ocr_result["content"]
                        )
                        result.method_used = "hybrid"
                        result.quality_score = max(text_result["quality_score"], ocr_result["quality_score"])
                        self.logger.info("Using hybrid text + OCR approach")
                    else:
                        # OCR only
                        result.text_content = ocr_result["content"]
                        result.method_used = "ocr"
                        result.quality_score = ocr_result["quality_score"]
                        self.logger.info("Using OCR only")

                    result.success = True
                    result.warnings.extend(ocr_result["warnings"])
                else:
                    result.errors.extend(ocr_result["errors"])

            else:
                # No OCR available or disabled
                if text_result["success"]:
                    result.success = True
                    result.text_content = text_result["content"]
                    result.method_used = "text_extraction"
                    result.quality_score = text_result["quality_score"]
                    result.warnings.append("OCR not available, using low-quality text extraction")
                else:
                    result.errors.append("Text extraction failed and OCR not available")

            # Validate extracted content
            if result.success and self.config["validate_content"]:
                content_validation = self._validate_content(result.text_content)
                result.quality_score *= content_validation["quality_multiplier"]
                result.warnings.extend(content_validation["warnings"])

                if not content_validation["likely_valid"]:
                    result.warnings.append("Content may not be a municipal document")

        except Exception as e:
            result.errors.append(f"Processing error: {str(e)}")
            self.logger.error(f"PDF processing error: {e}")

        finally:
            result.processing_time = (datetime.now() - start_time).total_seconds()

        return result

    def _validate_pdf_file(self, pdf_path: Path) -> Dict[str, Any]:
        """Validate PDF file before processing"""

        validation = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "page_count": 0,
            "metadata": {}
        }

        try:
            if not pdf_path.exists():
                validation["errors"].append("File does not exist")
                return validation

            file_size = pdf_path.stat().st_size
            validation["metadata"]["file_size"] = file_size

            if file_size == 0:
                validation["errors"].append("File is empty")
                return validation

            if file_size > self.config["max_file_size_mb"] * 1024 * 1024:
                validation["errors"].append(f"File too large (>{self.config['max_file_size_mb']}MB)")
                return validation

            # Check PDF header
            with open(pdf_path, 'rb') as f:
                header = f.read(5)
                if not header.startswith(b'%PDF-'):
                    validation["errors"].append("Not a valid PDF file")
                    return validation

            # Try to open with pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                validation["page_count"] = len(pdf.pages)

                if validation["page_count"] == 0:
                    validation["errors"].append("PDF has no pages")
                    return validation

                if validation["page_count"] > self.config["max_pages"]:
                    validation["errors"].append(f"Too many pages (>{self.config['max_pages']})")
                    return validation

                # Extract basic metadata
                if pdf.metadata:
                    validation["metadata"]["pdf_metadata"] = dict(pdf.metadata)

            validation["valid"] = True

        except Exception as e:
            validation["errors"].append(f"Validation error: {str(e)}")

        return validation

    def _extract_text_based(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract text using pdfplumber"""

        result = {
            "success": False,
            "content": "",
            "quality_score": 0.0,
            "warnings": [],
            "errors": []
        }

        try:
            with pdfplumber.open(pdf_path) as pdf:
                all_text = ""
                page_texts = []

                for i, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            page_texts.append(page_text)
                            all_text += page_text + "\n"
                        else:
                            result["warnings"].append(f"No text extracted from page {i+1}")
                    except Exception as e:
                        result["warnings"].append(f"Error extracting page {i+1}: {str(e)}")

                result["content"] = all_text.strip()

                # Calculate quality score
                if result["content"]:
                    result["quality_score"] = self._calculate_text_quality(result["content"])
                    result["success"] = len(result["content"]) >= self.config["min_text_threshold"]
                else:
                    result["errors"].append("No text content extracted")

        except Exception as e:
            result["errors"].append(f"Text extraction error: {str(e)}")

        return result

    def _extract_with_ocr(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract text using OCR (requires pytesseract and pdf2image)"""

        result = {
            "success": False,
            "content": "",
            "quality_score": 0.0,
            "warnings": [],
            "errors": []
        }

        if not OCR_AVAILABLE:
            result["errors"].append("OCR libraries not available (pytesseract, PIL, pdf2image)")
            return result

        try:
            # Convert PDF to images
            images = pdf2image.convert_from_path(
                pdf_path,
                dpi=self.config["ocr_dpi"],
                fmt='PNG'
            )

            all_text = ""

            for i, image in enumerate(images):
                try:
                    # OCR the image
                    page_text = pytesseract.image_to_string(
                        image,
                        lang=self.config["ocr_language"],
                        config='--oem 3 --psm 6'  # Assume uniform block of text
                    )

                    if page_text.strip():
                        all_text += page_text + "\n"
                    else:
                        result["warnings"].append(f"No text recognized on page {i+1}")

                except Exception as e:
                    result["warnings"].append(f"OCR error on page {i+1}: {str(e)}")

            result["content"] = all_text.strip()

            if result["content"]:
                result["quality_score"] = self._calculate_text_quality(result["content"])
                result["success"] = len(result["content"]) >= self.config["ocr_threshold"]

                if result["success"]:
                    result["warnings"].append("Content extracted using OCR - may contain recognition errors")
            else:
                result["errors"].append("OCR did not recognize any text")

        except Exception as e:
            result["errors"].append(f"OCR processing error: {str(e)}")

        return result

    def _combine_text_and_ocr(self, text_content: str, ocr_content: str) -> str:
        """Combine text extraction and OCR results intelligently"""

        # Simple approach: use text extraction as base, fill gaps with OCR
        # This could be made more sophisticated with alignment algorithms

        if len(text_content) > len(ocr_content) * 0.8:
            # Text extraction seems comprehensive, use it as primary
            return text_content
        else:
            # OCR seems to have captured more, but combine both
            return f"{text_content}\n\n--- OCR SUPPLEMENT ---\n{ocr_content}"

    def _calculate_text_quality(self, text: str) -> float:
        """Calculate quality score for extracted text (0.0 - 1.0)"""

        if not text:
            return 0.0

        score = 0.0

        # Length factor
        length_score = min(1.0, len(text) / 1000)  # Normalize around 1000 chars
        score += length_score * 0.3

        # Character diversity (letters, numbers, punctuation)
        char_types = 0
        if any(c.isalpha() for c in text):
            char_types += 1
        if any(c.isdigit() for c in text):
            char_types += 1
        if any(c in '.,!?;:' for c in text):
            char_types += 1

        diversity_score = char_types / 3.0
        score += diversity_score * 0.3

        # Word structure (spaces, proper word length)
        words = text.split()
        if words:
            avg_word_length = sum(len(word) for word in words) / len(words)
            word_length_score = min(1.0, avg_word_length / 5.0)  # Normalize around 5 chars
            score += word_length_score * 0.2

        # Readability (ratio of readable vs garbage characters)
        readable_chars = sum(1 for c in text if c.isalnum() or c.isspace() or c in '.,!?;:-')
        readability_score = readable_chars / len(text) if text else 0
        score += readability_score * 0.2

        return min(1.0, score)

    def _validate_content(self, text: str) -> Dict[str, Any]:
        """Validate that content looks like a municipal document"""

        validation = {
            "likely_valid": False,
            "quality_multiplier": 1.0,
            "warnings": []
        }

        if not text:
            return validation

        text_lower = text.lower()

        # Check for expected patterns
        pattern_matches = 0
        for pattern in self.config["expected_patterns"]:
            import re
            if re.search(pattern, text_lower):
                pattern_matches += 1

        pattern_score = pattern_matches / len(self.config["expected_patterns"])

        # Look for municipal keywords
        municipal_keywords = [
            "planning", "commission", "council", "city", "county",
            "zoning", "development", "ordinance", "resolution",
            "public", "hearing", "agenda", "minutes"
        ]

        keyword_matches = sum(1 for keyword in municipal_keywords if keyword in text_lower)
        keyword_score = min(1.0, keyword_matches / 5.0)  # Normalize around 5 keywords

        # Overall validation
        overall_score = (pattern_score * 0.6) + (keyword_score * 0.4)
        validation["likely_valid"] = overall_score >= 0.3
        validation["quality_multiplier"] = 0.5 + (overall_score * 0.5)  # 0.5 to 1.0

        if not validation["likely_valid"]:
            validation["warnings"].append(f"Content may not be municipal document (score: {overall_score:.2f})")

        return validation

# Convenience functions for integration
def process_pdf_with_fallback(pdf_path: Path, config: Optional[Dict[str, Any]] = None) -> PDFProcessingResult:
    """Process PDF with automatic fallback strategies"""
    processor = EnhancedPDFProcessor(config)
    return processor.process_pdf(pdf_path)

def extract_text_robust(pdf_path: Path) -> Tuple[str, Dict[str, Any]]:
    """Extract text with robust fallback - returns (text, metadata)"""
    result = process_pdf_with_fallback(pdf_path)

    metadata = {
        "method_used": result.method_used,
        "quality_score": result.quality_score,
        "page_count": result.page_count,
        "success": result.success,
        "warnings": result.warnings,
        "errors": result.errors,
        "processing_time": result.processing_time
    }

    return result.text_content, metadata

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Enhanced PDF Processor with OCR fallback')
    parser.add_argument('pdf_file', help='PDF file to process')
    parser.add_argument('--config', help='JSON config file')
    parser.add_argument('--output', help='Output file for extracted text')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    # Load config if provided
    config = None
    if args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)

    # Process PDF
    pdf_path = Path(args.pdf_file)
    result = process_pdf_with_fallback(pdf_path, config)

    print(f"📄 Processing: {pdf_path}")
    print(f"✅ Success: {result.success}")
    print(f"🔧 Method: {result.method_used}")
    print(f"⭐ Quality: {result.quality_score:.2f}")
    print(f"📊 Pages: {result.page_count}")
    print(f"⏱️  Time: {result.processing_time:.2f}s")
    print(f"📝 Text length: {len(result.text_content)} characters")

    if result.warnings:
        print(f"⚠️  Warnings: {len(result.warnings)}")
        for warning in result.warnings:
            print(f"   • {warning}")

    if result.errors:
        print(f"❌ Errors: {len(result.errors)}")
        for error in result.errors:
            print(f"   • {error}")

    # Save output if requested
    if args.output and result.success:
        with open(args.output, 'w') as f:
            f.write(result.text_content)
        print(f"💾 Text saved to: {args.output}")

    # Print OCR availability
    if OCR_AVAILABLE:
        print("🔍 OCR libraries available")
    else:
        print("❌ OCR libraries not available (install: pip install pytesseract pillow pdf2image)")