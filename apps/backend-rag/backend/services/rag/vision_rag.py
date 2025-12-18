"""
Vision RAG Service
RAG multi-modale per documenti con immagini, tabelle, grafici.
"""

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import google.generativeai as genai
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VisualElement:
    element_type: str  # "table", "chart", "diagram", "image", "form"
    page_number: int
    bounding_box: tuple[int, int, int, int]  # x1, y1, x2, y2
    image_data: bytes
    extracted_text: str
    description: str
    embedding: list[float] | None = None


@dataclass
class MultiModalDocument:
    doc_id: str
    text_content: str
    visual_elements: list[VisualElement]
    metadata: dict


class VisionRAGService:
    """
    Servizio per RAG su documenti multi-modali.
    Estrae e indicizza elementi visuali (tabelle, grafici, form).
    """

    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.vision_model = genai.GenerativeModel(
            "gemini-2.5-flash"
        )  # Vision capable - Updated to 2.5-flash
        self.text_model = genai.GenerativeModel("gemini-2.5-flash")  # Updated to 2.5-flash

    async def process_pdf(self, pdf_path: str | Path) -> MultiModalDocument:
        """
        Processa un PDF estraendo testo e elementi visuali.
        Requires: pymupdf (fitz)
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF not installed. Cannot process visual elements.")
            return MultiModalDocument(Path(pdf_path).stem, "", [], {})

        pdf_path = Path(pdf_path)
        doc = fitz.open(pdf_path)

        all_text = []
        visual_elements = []

        for page_num, page in enumerate(doc):
            # Estrai testo
            all_text.append(page.get_text())

            # Estrai immagini
            images = page.get_images(full=True)
            for img_idx, img in enumerate(images):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]

                # Analizza con Vision
                element = await self._analyze_visual_element(
                    image_bytes, page_num + 1, "image_{page_num}_{img_idx}"
                )
                if element:
                    visual_elements.append(element)

            # Cerca tabelle (basato su struttura)
            tables = await self._extract_tables(page, page_num + 1)
            visual_elements.extend(tables)

        doc.close()

        logger.info(
            f"📸 [VisionRAG] Processed {{pdf_path.name}}: "
            f"{len(all_text)} pages, {len(visual_elements)} visual elements"
        )

        return MultiModalDocument(
            doc_id=pdf_path.stem,
            text_content="\n\n".join(all_text),
            visual_elements=visual_elements,
            metadata={"source": str(pdf_path), "pages": len(all_text)},
        )

    async def _analyze_visual_element(
        self, image_bytes: bytes, page_num: int, element_id: str
    ) -> VisualElement | None:
        """
        Analizza un elemento visivo con Gemini Vision.
        """
        try:
            # Converti in formato Gemini
            image = Image.open(io.BytesIO(image_bytes))

            # Prompt per classificazione e estrazione
            prompt = """
            Analyze this image from a legal/business document.

            1. Classify the type: TABLE, CHART, DIAGRAM, FORM, PHOTO, or OTHER
            2. Extract any text visible in the image
            3. Describe what the image shows in 2-3 sentences
            4. If it's a table, extract the data in markdown format

            Output JSON:
            {
                "type": "TABLE|CHART|DIAGRAM|FORM|PHOTO|OTHER",
                "extracted_text": "Any text found...",
                "description": "What the image shows...",
                "table_markdown": "| Col1 | Col2 |..." (only for tables)
            }
            """

            response = await self.vision_model.generate_content_async([prompt, image])

            import json

            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean_json)

            return VisualElement(
                element_type=result.get("type", "OTHER").lower(),
                page_number=page_num,
                bounding_box=(0, 0, image.width, image.height),
                image_data=image_bytes,
                extracted_text=result.get("extracted_text", "")
                + "\n"
                + result.get("table_markdown", ""),
                description=result.get("description", ""),
            )

        except Exception:
            logger.warning("Visual analysis failed for {element_id}: {e}")
            return None

    async def _extract_tables(self, page, page_num: int) -> list[VisualElement]:
        """
        Estrae tabelle da una pagina usando rilevamento strutturale.
        """
        import fitz

        tables = []

        # Usa PyMuPDF table detection (v1.23+)
        try:
            page_tables = page.find_tables()

            for i, table in enumerate(page_tables):
                # Converti tabella in markdown
                markdown = self._table_to_markdown(table)

                # Screenshot dell'area della tabella
                rect = table.bbox
                clip = fitz.Rect(rect)
                pix = page.get_pixmap(clip=clip, dpi=150)
                image_bytes = pix.tobytes("png")

                tables.append(
                    VisualElement(
                        element_type="table",
                        page_number=page_num,
                        bounding_box=tuple(rect),
                        image_data=image_bytes,
                        extracted_text=markdown,
                        description=f"Table with {len(table.cells)} cells",
                    )
                )
        except Exception:
            logger.warning("Table extraction failed: {e}")

        return tables

    def _table_to_markdown(self, table) -> str:
        """Converte tabella PyMuPDF in markdown"""
        rows = table.extract()
        if not rows:
            return ""

        lines = []
        # Header
        lines.append("| " + " | ".join(str(cell) for cell in rows[0]) + " |")
        lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
        # Body
        for row in rows[1:]:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

        return "\n".join(lines)

    async def query_with_vision(
        self, query: str, documents: list[MultiModalDocument], include_images: bool = True
    ) -> dict[str, Any]:
        """
        Query che considera sia testo che elementi visuali.
        """
        # 1. Prepara contesto testuale
        text_context = "\n\n".join(
            ["Document: {doc.doc_id}\n{doc.text_content[:5000]}" for doc in documents]
        )

        # 2. Trova elementi visuali rilevanti
        relevant_visuals = []
        for doc in documents:
            for element in doc.visual_elements:
                # Check rilevanza basata su keyword nella descrizione
                if self._is_relevant(query, element):
                    relevant_visuals.append(element)

        # 3. Prepara prompt multi-modale
        prompt_parts = [
            f"""
            Answer this question using both text and visual information provided.

            Question: {query}

            Text Context:
            {{text_context[:10000]}}

            Visual Elements Found: {len(relevant_visuals)}
            """
        ]

        # Aggiungi descrizioni elementi visuali
        for i, visual in enumerate(relevant_visuals[:5]):  # Max 5 immagini
            prompt_parts.append("\n\nVisual {i+1} ({visual.element_type}):")
            prompt_parts.append("Description: {visual.description}")
            prompt_parts.append("Extracted Text: {visual.extracted_text[:500]}")

            if include_images:
                # Aggiungi immagine al prompt
                image = Image.open(io.BytesIO(visual.image_data))
                prompt_parts.append(image)

        prompt_parts.append("\n\nProvide a comprehensive answer using all available information:")

        # 4. Query Gemini Vision
        response = await self.vision_model.generate_content_async(prompt_parts)

        return {
            "answer": response.text,
            "visuals_used": [
                {"type": v.element_type, "page": v.page_number, "description": v.description}
                for v in relevant_visuals[:5]
            ],
            "text_context_length": len(text_context),
        }

    def _is_relevant(self, query: str, element: VisualElement) -> bool:
        """Check se un elemento visivo è rilevante per la query"""
        query_lower = query.lower()
        searchable = (element.description + " " + element.extracted_text).lower()

        # Keyword match semplice
        query_words = query_lower.split()
        matches = sum(1 for word in query_words if word in searchable)

        return matches >= len(query_words) * 0.3  # Almeno 30% match
