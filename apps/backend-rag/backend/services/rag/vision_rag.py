"""
Vision RAG Service
RAG multi-modale per documenti con immagini, tabelle, grafici.

UPDATED 2026-03-08:
- Ollama-first (qwen2.5vl:7b vision) with Gemini fallback
- Added _analyze_visual_via_ollama for local vision analysis
"""

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from backend.app.core.config import settings
from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient
from backend.llm.ollama_client import is_ollama_available

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

    def __init__(self) -> None:
        self._genai_client: GenAIClient | None = None
        self.vision_model_name = "gemini-2.0-flash-lite"  # Vision capable
        self.text_model_name = "gemini-2.0-flash-lite"
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared async client for Ollama."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("VisionRAGService HTTP client closed.")

    def _get_genai_client(self) -> GenAIClient | None:
        """Lazy load GenAI client."""
        if self._genai_client is None and settings.google_api_key and GENAI_AVAILABLE:
            try:
                self._genai_client = GenAIClient(api_key=settings.google_api_key)
                if self._genai_client.is_available:
                    logger.debug("✅ VisionRAGService GenAI client loaded")
            except Exception as e:
                logger.warning(f"Failed to initialize VisionRAGService: {e}")
        return self._genai_client

    @property
    def _available(self) -> bool:
        """Check availability dynamically."""
        client = self._get_genai_client()
        return client.is_available if client else False

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
            for _img_idx, img in enumerate(images):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]

                # Analizza con Vision
                element = await self._analyze_visual_element(
                    image_bytes, page_num + 1, "image_{page_num}_{img_idx}",
                )
                if element:
                    visual_elements.append(element)

            # Cerca tabelle (basato su struttura)
            tables = await self._extract_tables(page, page_num + 1)
            visual_elements.extend(tables)

        doc.close()

        logger.info(
            f"📸 [VisionRAG] Processed {{pdf_path.name}}: "
            f"{len(all_text)} pages, {len(visual_elements)} visual elements",
        )

        return MultiModalDocument(
            doc_id=pdf_path.stem,
            text_content="\n\n".join(all_text),
            visual_elements=visual_elements,
            metadata={"source": str(pdf_path), "pages": len(all_text)},
        )

    async def _analyze_visual_element(
        self, image_bytes: bytes, page_num: int, element_id: str,
    ) -> VisualElement | None:
        """
        Analizza un elemento visivo. Ollama-first, Gemini fallback.
        """
        import base64
        import json

        image = Image.open(io.BytesIO(image_bytes))
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode()

        prompt = """Analyze this image from a legal/business document.

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
}"""

        try:
            # Try Ollama first (local, free)
            raw_response = await self._vision_via_ollama(prompt, image_base64)

            # Fallback to Gemini
            if not raw_response:
                raw_response = await self._vision_via_gemini(prompt, image_base64)

            if not raw_response:
                logger.warning(f"Visual analysis failed for {element_id}: no provider available")
                return None

            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
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

        except Exception as e:
            logger.warning(f"Visual analysis failed for {element_id}: {e}")
            return None

    async def _vision_via_ollama(self, prompt: str, image_base64: str) -> str | None:
        """Analyze image using local Ollama vision model (qwen2.5vl:7b)."""
        # NOTE: qwen3.5 Q4_K_M strips vision weights — cannot do vision.
        # qwen2.5vl:7b is the ONLY Ollama model with working vision support.
        vision_model = "qwen2.5vl:7b"
        try:
            if not await is_ollama_available(vision_model):
                return None

            payload = {
                "model": vision_model,
                "messages": [{"role": "user", "content": prompt, "images": [image_base64]}],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 8192},
            }

            client = self._get_client()
            response = await client.post(
                f"{settings.ollama_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "").strip()
            if content:
                logger.info(f"👁️ VisionRAG: Ollama ({vision_model}) responded")
                return content
            return None
        except Exception as e:
            logger.debug(f"VisionRAG Ollama fallback: {e}")
            return None

    async def _vision_via_gemini(self, prompt: str, image_base64: str) -> str | None:
        """Fallback: Analyze image using Gemini Vision API."""
        try:
            client = self._get_genai_client()
            if not client or not client.is_available:
                return None

            contents = [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": image_base64}},
            ]

            result = await client.generate_content(
                contents=contents,
                model=self.vision_model_name,
                max_output_tokens=8192,
            )
            return result.get("text") if result else None
        except Exception as e:
            logger.warning(f"VisionRAG Gemini error: {e}")
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

            for _i, table in enumerate(page_tables):
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
                    ),
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
        self, query: str, documents: list[MultiModalDocument], include_images: bool = True,
    ) -> dict[str, Any]:
        """
        Query che considera sia testo che elementi visuali.
        """
        # 1. Prepara contesto testuale
        text_context = "\n\n".join(
            ["Document: {doc.doc_id}\n{doc.text_content[:5000]}" for doc in documents],
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
            """,
        ]

        # Aggiungi descrizioni elementi visuali
        for _i, visual in enumerate(relevant_visuals[:5]):  # Max 5 immagini
            prompt_parts.append("\n\nVisual {i+1} ({visual.element_type}):")
            prompt_parts.append("Description: {visual.description}")
            prompt_parts.append("Extracted Text: {visual.extracted_text[:500]}")

            if include_images:
                # Aggiungi immagine al prompt
                image = Image.open(io.BytesIO(visual.image_data))
                prompt_parts.append(image)

        prompt_parts.append("\n\nProvide a comprehensive answer using all available information:")

        # 4. Query Gemini Vision
        client = self._get_genai_client()
        if not client or not client.is_available:
            return {
                "answer": "Vision service not available",
                "visuals_used": [],
                "text_context_length": 0,
            }

        # Build content for the new SDK
        import base64

        contents = []
        for part in prompt_parts:
            if isinstance(part, str):
                contents.append({"text": part})
            elif hasattr(part, "save"):  # PIL Image
                buffered = io.BytesIO()
                part.save(buffered, format="PNG")
                image_base64 = base64.b64encode(buffered.getvalue()).decode()
                contents.append({"inline_data": {"mime_type": "image/png", "data": image_base64}})

        result_response = await client.generate_content(
            contents=contents,
            model=self.vision_model_name,
            max_output_tokens=8192,
        )

        return {
            "answer": result_response.get("text", ""),
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
