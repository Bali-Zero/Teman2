"""
PDF Vision Service
Usa Gemini Vision per "vedere" e interpretare tabelle complesse nei PDF (es: KBLI).
Integrato con Google Drive per scaricare i file on-demand.
"""

import io
import logging
import os
from typing import Any

import fitz  # PyMuPDF
import google.generativeai as genai
from PIL import Image

from app.core.config import settings
from services.smart_oracle import download_pdf_from_drive

logger = logging.getLogger(__name__)


class PDFVisionService:
    """
    Servizio per analisi multimodale di PDF.
    Estrae immagini delle pagine e le invia a Gemini Pro Vision.
    Supporta download da Google Drive.
    """

    def __init__(self, api_key: str = None, ai_client=None):
        """
        Initialize PDFVisionService.

        Args:
            api_key: Google API key (optional, uses settings if not provided)
            ai_client: Optional AI client (for test compatibility)
        """
        self.ai_client = ai_client
        self.api_key = api_key or settings.google_api_key
        if not self.api_key:
            logger.warning("⚠️ No Gemini API key found for Vision Service")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")  # Use Flash for speed/cost

    async def analyze_page(
        self,
        pdf_path: str,
        page_number: int,
        prompt: str = "Extract the table data from this page.",
        is_drive_file: bool = False,
    ) -> str:
        """
        Analizza una specifica pagina PDF con Gemini Vision.
        Se is_drive_file è True, pdf_path è interpretato come nome file o ID Drive.
        """
        local_path = pdf_path

        try:
            # 1. Download da Drive se necessario
            if is_drive_file:
                # Usa la logica di smart_oracle per scaricare
                downloaded_path = download_pdf_from_drive(pdf_path)
                if not downloaded_path:
                    return f"Error: Could not download file '{pdf_path}' from Drive."
                local_path = downloaded_path

            # 2. Renderizza pagina PDF come immagine
            image = self._render_page_to_image(local_path, page_number)

            # 3. Invia a Gemini Vision
            response = self.model.generate_content([prompt, image])

            logger.info(f"👁️ Vision analysis complete for {local_path} p.{page_number}")

            # Cleanup temp file if downloaded
            if is_drive_file and os.path.exists(local_path):
                os.remove(local_path)

            return response.text

        except Exception as e:
            logger.error(f"❌ Vision analysis failed: {e}")
            return f"Error analyzing page: {str(e)}"

    def _render_page_to_image(self, pdf_path: str, page_number: int) -> Image.Image:
        """Converte pagina PDF in PIL Image"""
        doc = fitz.open(pdf_path)
        if page_number < 1 or page_number > len(doc):
            raise ValueError(f"Invalid page number {page_number}")

        page = doc.load_page(page_number - 1)  # 0-indexed
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for clarity

        img_data = pix.tobytes("png")
        return Image.open(io.BytesIO(img_data))

    async def extract_kbli_table(
        self, pdf_identifier: str, page_range: tuple[int, int], is_drive_file: bool = True
    ) -> str:
        """
        Estrae dati KBLI da un range di pagine.
        Default is_drive_file=True perché le leggi sono su Drive.
        """
        full_extraction = []
        prompt = """
        Analyze this image of a KBLI table.
        Extract the KBLI Code (Kode), Title (Judul), and Description (Uraian).
        Format as JSON list: [{"code": "...", "title": "...", "description": "..."}]
        If no table is visible, return empty list [].
        """

        # Se è un file Drive, lo scarichiamo UNA volta sola per efficienza
        local_path = pdf_identifier
        if is_drive_file:
            local_path = download_pdf_from_drive(pdf_identifier)
            if not local_path:
                return "Error: Could not download KBLI file from Drive."

        try:
            for page_num in range(page_range[0], page_range[1] + 1):
                # Passiamo is_drive_file=False perché ora è locale
                result = await self.analyze_page(local_path, page_num, prompt, is_drive_file=False)
                full_extraction.append(f"--- Page {page_num} ---\n{result}")
        finally:
            # Cleanup
            if is_drive_file and local_path and os.path.exists(local_path):
                os.remove(local_path)

        return "\n".join(full_extraction)

    async def extract_text(self, pdf_data: bytes) -> str:
        """
        Extract text from PDF data (for test compatibility).

        Args:
            pdf_data: PDF file bytes

        Returns:
            Extracted text content
        """
        if self.ai_client and hasattr(self.ai_client, "extract_pdf_text"):
            return await self.ai_client.extract_pdf_text(pdf_data)

        # Fallback: try to extract using PyMuPDF
        try:
            import fitz

            doc = fitz.open(stream=pdf_data, filetype="pdf")
            text = "\n".join([page.get_text() for page in doc])
            doc.close()
            return text
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return f"Error extracting PDF: {str(e)}"

    async def analyze_vision(self, pdf_data: bytes) -> dict[str, Any]:
        """
        Analyze PDF using vision model (for test compatibility).

        Args:
            pdf_data: PDF file bytes

        Returns:
            Analysis result with text and structure
        """
        if self.ai_client and hasattr(self.ai_client, "analyze_pdf_vision"):
            return await self.ai_client.analyze_pdf_vision(pdf_data)

        # Fallback: basic extraction
        text = await self.extract_text(pdf_data)
        return {
            "text": text,
            "structure": {"pages": 1, "sections": 0},
        }
