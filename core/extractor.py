# -*- coding: utf-8 -*-
"""
PDF Extractor: Cross-platform (Linux, Windows, macOS) extractor for text, page count, and images from PDF.
Supports Poppler CLI (pdftotext/pdfinfo/pdfimages), PyMuPDF (fitz), and pypdf.
"""

import os
import shutil
import subprocess


class PDFExtractor:
    @staticmethod
    def get_info(pdf_path):
        """Returns dict with page_count, file_size, etc. Works on Windows & Linux."""
        info = {
            "path": pdf_path,
            "filename": os.path.basename(pdf_path),
            "size_kb": os.path.getsize(pdf_path) / 1024 if os.path.exists(pdf_path) else 0,
            "pages": 1
        }
        # 1. Try pdfinfo if available
        if shutil.which("pdfinfo"):
            try:
                out = subprocess.check_output(["pdfinfo", pdf_path], text=True, stderr=subprocess.DEVNULL)
                for line in out.splitlines():
                    if line.startswith("Pages:"):
                        info["pages"] = int(line.split(":")[1].strip())
                        return info
            except Exception:
                pass

        # 2. Fallback to PyMuPDF (fitz)
        try:
            import fitz
            with fitz.open(pdf_path) as doc:
                info["pages"] = len(doc)
                return info
        except Exception:
            pass

        # 3. Fallback to pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            info["pages"] = len(reader.pages)
            return info
        except Exception:
            pass

        return info

    @staticmethod
    def extract_text(pdf_path):
        """Extracts complete text (pages separated by \\f). Works on Windows & Linux."""
        # 1. Try pdftotext if available
        if shutil.which("pdftotext"):
            try:
                return subprocess.check_output(["pdftotext", pdf_path, "-"], text=True)
            except Exception:
                pass

        # 2. Fallback to PyMuPDF (fitz) - fast & accurate on Windows
        try:
            import fitz
            pages_text = []
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    pages_text.append(page.get_text("text"))
            return "\f".join(pages_text)
        except Exception:
            pass

        # 3. Fallback to pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            pages_text = [p.extract_text() or "" for p in reader.pages]
            return "\f".join(pages_text)
        except Exception as e:
            return f"Error extracting text: {e}"

    @staticmethod
    def extract_images(pdf_path, output_dir):
        """Extracts embedded images as PNG files. Works on Windows & Linux."""
        prefix = os.path.join(output_dir, "img")
        if shutil.which("pdfimages"):
            try:
                subprocess.run(["pdfimages", "-png", pdf_path, prefix], check=True, stderr=subprocess.DEVNULL)
                images = sorted([
                    os.path.join(output_dir, f)
                    for f in os.listdir(output_dir)
                    if f.startswith("img-") and f.endswith(".png")
                ])
                return images
            except Exception:
                pass

        # Fallback to PyMuPDF (fitz) on Windows
        try:
            import fitz
            images = []
            img_idx = 0
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    for img in page.get_images(full=True):
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n - pix.alpha >= 4:
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        out_p = os.path.join(output_dir, f"img-{img_idx:03d}.png")
                        pix.save(out_p)
                        images.append(out_p)
                        img_idx += 1
            return images
        except Exception:
            return []
