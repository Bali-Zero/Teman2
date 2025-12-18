"""
Legal Document Chunker - Stage 4: The Butcher
Pasal-aware semantic chunking with context injection
"""

import logging
import math
from typing import Any

from core.embeddings import create_embeddings_generator

from .constants import MAX_PASAL_TOKENS, PASAL_PATTERN

logger = logging.getLogger(__name__)


class SemanticSplitter:
    """
    Helper class to split text based on semantic similarity.
    Groups sentences that are semantically close.
    """

    def __init__(self, embeddings_generator, similarity_threshold: float = 0.7):
        self.embedder = embeddings_generator
        self.threshold = similarity_threshold

    def split_text(self, text: str, max_tokens: int) -> list[str]:
        """
        Split text into semantically coherent chunks.
        """
        # 1. Split into sentences
        sentences = self._split_sentences(text)
        if not sentences:
            return []

        if len(sentences) == 1:
            return sentences

        # 2. Generate embeddings for all sentences
        embeddings = self.embedder.generate_embeddings(sentences)

        # 3. Group sentences
        chunks = []
        current_chunk = [sentences[0]]
        current_chunk_len = len(sentences[0])

        for i in range(1, len(sentences)):
            sentence = sentences[i]
            sentence_len = len(sentence)

            # Calculate similarity with previous sentence
            similarity = self._cosine_similarity(embeddings[i - 1], embeddings[i])

            # If similar enough AND fits in chunk, group it
            if similarity >= self.threshold and (current_chunk_len + sentence_len) < max_tokens:
                current_chunk.append(sentence)
                current_chunk_len += sentence_len
            else:
                # Start new chunk
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_chunk_len = sentence_len

        # Add last chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Simple sentence splitter (can be improved with NLTK/Spacy)"""
        # Split by common delimiters but keep them attached to previous sentence if possible
        # For now, simple split by ". "
        return [s.strip() + "." for s in text.split(". ") if s.strip()]

    def _cosine_similarity(self, v1: list[float], v2: list[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = sum(a * b for a, b in zip(v1, v2, strict=False))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        return dot_product / (norm_a * norm_b) if norm_a and norm_b else 0.0


class LegalChunker:
    """
    Semantic chunker for Indonesian legal documents.
    Uses Pasal-aware splitting with context injection.
    """

    def __init__(self, max_pasal_tokens: int = None):
        """
        Initialize legal chunker.

        Args:
            max_pasal_tokens: Maximum tokens per Pasal before splitting by Ayat
        """
        self.max_pasal_tokens = max_pasal_tokens or MAX_PASAL_TOKENS

        # Initialize Embeddings Generator for Semantic Splitting
        self.embedder = create_embeddings_generator()
        self.semantic_splitter = SemanticSplitter(self.embedder)

        logger.info(f"LegalChunker initialized (max_pasal_tokens={self.max_pasal_tokens})")

    def chunk(
        self,
        text: str,
        metadata: dict[str, Any],
        structure: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Chunk legal document with Pasal-aware strategy and context injection.

        Args:
            text: Cleaned legal document text
            metadata: Document metadata (type, number, year, topic)
            structure: Parsed structure (optional, for better context)

        Returns:
            List of chunk dictionaries with injected context
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to legal chunker")
            return []

        chunks = []
        char_limit = self.max_pasal_tokens * 4

        # Strategy: Split by Pasal first
        pasal_chunks = self._split_by_pasal(text)

        # Check if we actually found Pasals (if only 1 chunk and it doesn't match pattern, likely unstructured)
        has_pasal_structure = False
        if len(pasal_chunks) > 1:
            has_pasal_structure = True
        elif len(pasal_chunks) == 1:
            if PASAL_PATTERN.match(pasal_chunks[0]):
                has_pasal_structure = True

        if not has_pasal_structure:
            logger.info("No Pasal structure detected, using fallback semantic chunking")
            return self._fallback_chunking(text, metadata)

        for pasal_chunk in pasal_chunks:
            # Check if this is a Pasal or just a block of text (like preamble)
            pasal_match = PASAL_PATTERN.match(pasal_chunk)
            
            if not pasal_match:
                # Handle blocks without Pasal marker (e.g. Preamble)
                chunk_text = pasal_chunk.strip()
                if not chunk_text:
                    continue
                    
                # If too large, split semantically
                if len(chunk_text) > char_limit:
                    logger.debug(f"Non-Pasal block too large ({len(chunk_text)} chars), splitting semantically")
                    semantic_subchunks = self.semantic_splitter.split_text(
                        chunk_text, self.max_pasal_tokens
                    )
                    for sub in semantic_subchunks:
                        context = self._build_context(metadata)
                        chunks.append(self._create_chunk(sub, context, metadata))
                else:
                    context = self._build_context(metadata)
                    chunks.append(self._create_chunk(chunk_text, context, metadata))
                continue

            pasal_num = pasal_match.group(1)
            pasal_text = pasal_match.group(2).strip()

            # Find BAB context if structure provided
            bab_context = None
            if structure:
                bab_context = self._find_bab_for_pasal(structure, pasal_num)

            # Check if Pasal is too large (using character length as proxy for tokens)
            # Safe limit: 4000 chars ~ 1000 tokens
            pasal_length = len(pasal_text)
            
            if pasal_length > char_limit:
                # Split by Ayat first
                logger.debug(
                    f"Pasal {pasal_num} too large ({pasal_length} chars), splitting by Ayat"
                )
                ayat_chunks = self._split_by_ayat(pasal_text, pasal_num)

                for ayat_chunk in ayat_chunks:
                    # If Ayat itself is still huge (or no Ayat were found), use Semantic Splitting
                    if len(ayat_chunk) > char_limit:
                        semantic_subchunks = self.semantic_splitter.split_text(
                            ayat_chunk, self.max_pasal_tokens
                        )
                        for sub in semantic_subchunks:
                            context = self._build_context(
                                metadata, bab=bab_context, pasal=f"Pasal {pasal_num}"
                            )
                            chunks.append(self._create_chunk(sub, context, metadata, pasal_num))
                    else:
                        context = self._build_context(
                            metadata, bab=bab_context, pasal=f"Pasal {pasal_num}"
                        )
                        chunks.append(self._create_chunk(ayat_chunk, context, metadata, pasal_num))
            else:
                # Keep Pasal as single chunk
                context = self._build_context(metadata, bab=bab_context, pasal=f"Pasal {pasal_num}")
                chunks.append(self._create_chunk(pasal_text, context, metadata, pasal_num))

        logger.info(f"Created {len(chunks)} legal chunks (Pasal-aware + Semantic)")

        # Add chunk indices
        for idx, chunk in enumerate(chunks):
            chunk["chunk_index"] = idx
            chunk["total_chunks"] = len(chunks)

        return chunks

    def _fallback_chunking(self, text: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Fallback chunking for unstructured text (non-Pasal).
        Uses Semantic Splitting instead of arbitrary paragraphs.
        """
        chunks = []

        # Use Semantic Splitter
        semantic_chunks = self.semantic_splitter.split_text(text, self.max_pasal_tokens)

        for chunk_text in semantic_chunks:
            context = self._build_context(metadata)
            chunks.append(self._create_chunk(chunk_text, context, metadata))

        logger.info(f"Created {len(chunks)} chunks using fallback semantic strategy")

        # Add chunk indices
        for idx, chunk in enumerate(chunks):
            chunk["chunk_index"] = idx
            chunk["total_chunks"] = len(chunks)

        return chunks

    def _split_by_pasal(self, text: str) -> list[str]:
        """
        Split text by Pasal markers.

        Args:
            text: Document text

        Returns:
            List of Pasal text chunks
        """
        # Split by Pasal pattern
        splits = PASAL_PATTERN.split(text)

        # First split is usually preamble (before first Pasal)
        pasal_chunks = []
        if splits[0].strip():
            pasal_chunks.append(splits[0].strip())

        # Process Pasal pairs (number, text)
        for i in range(1, len(splits), 2):
            if i + 1 < len(splits):
                pasal_num = splits[i]
                pasal_text = splits[i + 1]
                pasal_chunk = f"Pasal {pasal_num}\n{pasal_text}"
                pasal_chunks.append(pasal_chunk.strip())

        return pasal_chunks

    def _split_by_ayat(self, pasal_text: str, pasal_num: str) -> list[str]:
        """
        Split Pasal text by Ayat (clauses).

        Args:
            pasal_text: Pasal text content
            pasal_num: Pasal number

        Returns:
            List of Ayat text chunks
        """
        # Split by Ayat pattern: (1), (2), etc.
        import re

        ayat_pattern = re.compile(r"\((\d+)\)\s*(.+?)(?=\(\d+\)|$)", re.MULTILINE | re.DOTALL)
        ayat_matches = list(ayat_pattern.finditer(pasal_text))

        if not ayat_matches:
            # No Ayat found, return whole Pasal
            return [pasal_text]

        ayat_chunks = []
        for i, match in enumerate(ayat_matches):
            ayat_num = match.group(1)
            ayat_text = match.group(2).strip()

            # Include Pasal number in Ayat chunk
            ayat_chunk = f"Pasal {pasal_num} Ayat ({ayat_num})\n{ayat_text}"
            ayat_chunks.append(ayat_chunk)

        return ayat_chunks

    def _build_context(
        self,
        metadata: dict[str, Any],
        bab: str | None = None,
        pasal: str | None = None,
    ) -> str:
        """
        Build context string for chunk injection.

        Args:
            metadata: Document metadata
            bab: BAB context (optional)
            pasal: Pasal number (optional)

        Returns:
            Context string to prepend to chunk
        """
        type_abbrev = metadata.get("type_abbrev", "UNKNOWN")
        number = metadata.get("number", "UNKNOWN")
        year = metadata.get("year", "UNKNOWN")
        topic = metadata.get("topic", "UNKNOWN")

        # Build context parts
        context_parts = [type_abbrev, f"NO {number}", f"TAHUN {year}", f"TENTANG {topic}"]

        if bab:
            context_parts.append(bab)

        if pasal:
            context_parts.append(pasal)

        context_str = " - ".join(context_parts)

        return f"[CONTEXT: {context_str}]"

    def _create_chunk(
        self,
        content: str,
        context: str,
        metadata: dict[str, Any],
        pasal_num: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a chunk dictionary with context injection.

        Args:
            content: Chunk content text
            context: Context string to prepend
            metadata: Base metadata
            pasal_num: Pasal number (optional)

        Returns:
            Chunk dictionary
        """
        # Inject context at the beginning
        chunk_text = f"{context}\n\n{content}"

        chunk = {
            "text": chunk_text,
            "chunk_length": len(chunk_text),
            "content_length": len(content),
            "has_context": True,
        }

        # Add metadata
        chunk.update(metadata)

        # Add Pasal info if available
        if pasal_num:
            chunk["pasal_number"] = pasal_num

        return chunk

    def _find_bab_for_pasal(self, structure: dict[str, Any], pasal_num: str) -> str | None:
        """
        Find which BAB a Pasal belongs to from structure.

        Args:
            structure: Parsed structure dictionary
            pasal_num: Pasal number

        Returns:
            BAB context string or None
        """
        batang_tubuh = structure.get("batang_tubuh", [])

        for bab in batang_tubuh:
            pasal_list = bab.get("pasal", [])
            for pasal in pasal_list:
                if pasal.get("number") == pasal_num:
                    return f"BAB {bab.get('number')} - {bab.get('title', '')}"

        return None
