"""
NUZANTARA PRIME - Unified Ingestion CLI

Provides a single command-line interface for all ingestion operations.
Replaces fragmented ingestion scripts.

Usage:
    python -m cli.ingestion_cli ingest team-members
    python -m cli.ingestion_cli ingest conversations --source /path/to/data
    python -m cli.ingestion_cli ingest laws --file /path/to/law.pdf
    python -m cli.ingestion_cli list
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from services.ingestion_service import IngestionService
from services.legal_ingestion_service import LegalIngestionService

logger = logging.getLogger(__name__)


class IngestionCLI:
    """
    Unified Ingestion CLI

    Provides commands for:
    - Team members ingestion
    - Conversations ingestion
    - Legal documents ingestion
    - General document ingestion
    - List available ingestion types
    """

    def __init__(self):
        self.ingestion_service = IngestionService()
        self.legal_ingestion_service = LegalIngestionService()

    async def ingest_team_members(self, source: str | None = None) -> dict[str, Any]:
        """
        Ingest team members data.

        Args:
            source: Path to team_members.json file (default: data/team_members.json)

        Returns:
            Dictionary with ingestion results
        """
        try:
            import json
            import uuid
            from pathlib import Path

            from core.embeddings import create_embeddings_generator
            from core.qdrant_db import QdrantClient

            # Determine source path
            if source:
                data_path = Path(source)
            else:
                backend_path = Path(__file__).parent.parent
                data_path = backend_path / "data" / "team_members.json"

            if not data_path.exists():
                return {"success": False, "error": f"Data file not found: {data_path}"}

            # Load data
            with open(data_path, encoding="utf-8") as f:
                team_data = json.load(f)

            logger.info(f"Ingesting {len(team_data)} team members...")

            # Initialize services
            embedder = create_embeddings_generator()
            qdrant = QdrantClient(collection_name="bali_zero_team")

            # Prepare documents
            documents = []
            metadatas = []
            ids = []

            for member in team_data:
                text_parts = [
                    f"Name: {member['name']}",
                    f"Role: {member['role']}",
                    f"Department: {member['department']}",
                    f"Email: {member['email']}",
                ]
                if member.get("bio"):
                    text_parts.append(f"Bio: {member['bio']}")

                full_text = "\n".join(text_parts)
                documents.append(full_text)
                metadatas.append(member)
                member_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, member.get("id", member["email"])))
                ids.append(member_uuid)

            # Generate embeddings
            embeddings = [embedder.generate_single_embedding(doc) for doc in documents]

            # Upsert to Qdrant
            points = [
                {"id": id_val, "vector": emb, "payload": meta}
                for id_val, emb, meta in zip(ids, embeddings, metadatas)
            ]

            result = qdrant.upsert_points(points)

            return {
                "success": True,
                "ingested": len(team_data),
                "collection": "bali_zero_team",
                "details": result,
            }
        except Exception as e:
            logger.error(f"Team members ingestion failed: {e}")
            return {"success": False, "error": str(e)}

    async def ingest_conversations(
        self, source: str, collection: str = "conversations"
    ) -> dict[str, Any]:
        """
        Ingest conversation data.

        Args:
            source: Path to conversations file/directory
            collection: Qdrant collection name

        Returns:
            Dictionary with ingestion results
        """
        try:
            import json
            import uuid
            from pathlib import Path

            from core.embeddings import create_embeddings_generator
            from core.qdrant_db import QdrantClient

            source_path = Path(source)
            if not source_path.exists():
                return {"success": False, "error": f"Source not found: {source}"}

            logger.info(f"Ingesting conversations from {source}...")

            # Load conversations
            if source_path.is_file():
                with open(source_path, encoding="utf-8") as f:
                    conversations = json.load(f)
            else:
                # Directory - load all JSON files
                conversations = []
                for json_file in source_path.glob("*.json"):
                    with open(json_file, encoding="utf-8") as f:
                        conversations.extend(json.load(f))

            # Initialize services
            embedder = create_embeddings_generator()
            qdrant = QdrantClient(collection_name=collection)

            # Process conversations
            documents = []
            metadatas = []
            ids = []

            for idx, conv in enumerate(conversations):
                # Build text from conversation
                if "messages" in conv:
                    text = "\n".join(
                        f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                        for msg in conv["messages"]
                    )
                elif "question" in conv and "answer" in conv:
                    text = f"Question: {conv['question']}\nAnswer: {conv['answer']}"
                else:
                    text = str(conv)

                documents.append(text)
                metadatas.append(conv)
                ids.append(str(uuid.uuid4()))

            # Generate embeddings
            embeddings = [embedder.generate_single_embedding(doc) for doc in documents]

            # Upsert to Qdrant
            points = [
                {"id": id_val, "vector": emb, "payload": meta}
                for id_val, emb, meta in zip(ids, embeddings, metadatas)
            ]

            result = qdrant.upsert_points(points)

            return {
                "success": True,
                "ingested": len(conversations),
                "collection": collection,
                "details": result,
            }
        except Exception as e:
            logger.error(f"Conversations ingestion failed: {e}")
            return {"success": False, "error": str(e)}

    async def ingest_laws(
        self, file_path: str | None = None, directory: str | None = None
    ) -> dict[str, Any]:
        """
        Ingest legal documents.

        Args:
            file_path: Path to single legal document
            directory: Path to directory containing legal documents

        Returns:
            Dictionary with ingestion results
        """
        try:
            if file_path:
                logger.info(f"Ingesting legal document: {file_path}")
                result = await self.legal_ingestion_service.ingest_legal_document(file_path)
                return {
                    "success": True,
                    "ingested": 1,
                    "collection": "legal_intelligence",
                    "details": result,
                }
            elif directory:
                logger.info(f"Ingesting legal documents from directory: {directory}")
                dir_path = Path(directory)
                files = list(dir_path.glob("*.pdf")) + list(dir_path.glob("*.txt"))

                results = []
                for file in files:
                    try:
                        result = await self.legal_ingestion_service.ingest_legal_document(str(file))
                        results.append({"file": str(file), "result": result})
                    except Exception as e:
                        logger.error(f"Failed to ingest {file}: {e}")
                        results.append({"file": str(file), "error": str(e)})

                successful = sum(1 for r in results if "error" not in r)
                return {
                    "success": successful > 0,
                    "ingested": successful,
                    "total": len(files),
                    "collection": "legal_intelligence",
                    "details": results,
                }
            else:
                return {"success": False, "error": "Either file_path or directory required"}

        except Exception as e:
            logger.error(f"Legal documents ingestion failed: {e}")
            return {"success": False, "error": str(e)}

    async def ingest_document(
        self,
        file_path: str,
        title: str | None = None,
        author: str | None = None,
        collection: str | None = None,
    ) -> dict[str, Any]:
        """
        Ingest a general document.

        Args:
            file_path: Path to document file
            title: Optional document title
            author: Optional author name
            collection: Optional collection name override

        Returns:
            Dictionary with ingestion results
        """
        try:
            logger.info(f"Ingesting document: {file_path}")

            result = await self.ingestion_service.ingest_book(
                file_path=str(file_path),
                title=title,
                author=author,
            )

            return {
                "success": True,
                "ingested": 1,
                "collection": collection or result.get("collection", "knowledge_base"),
                "details": result,
            }
        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            return {"success": False, "error": str(e)}

    def list_types(self) -> dict[str, Any]:
        """
        List available ingestion types.

        Returns:
            Dictionary with available ingestion types and their descriptions
        """
        return {
            "types": {
                "team-members": {
                    "description": "Ingest team member profiles",
                    "source": "data/team_members.json or --source",
                    "collection": "bali_zero_team",
                },
                "conversations": {
                    "description": "Ingest conversation data",
                    "source": "Required: --source",
                    "collection": "conversations (default)",
                },
                "laws": {
                    "description": "Ingest legal documents (UU, PP, etc.)",
                    "source": "--file or --directory",
                    "collection": "legal_intelligence",
                },
                "document": {
                    "description": "Ingest general documents (PDF, EPUB)",
                    "source": "Required: --file",
                    "collection": "knowledge_base (default)",
                },
            }
        }


async def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="NUZANTARA Unified Ingestion CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List available ingestion types")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest data")
    ingest_parser.add_argument(
        "type",
        choices=["team-members", "conversations", "laws", "document"],
        help="Type of data to ingest",
    )
    ingest_parser.add_argument("--source", help="Source file or directory")
    ingest_parser.add_argument("--file", help="Single file to ingest")
    ingest_parser.add_argument("--directory", help="Directory containing files to ingest")
    ingest_parser.add_argument("--title", help="Document title (for document type)")
    ingest_parser.add_argument("--author", help="Author name (for document type)")
    ingest_parser.add_argument("--collection", help="Qdrant collection name")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    cli = IngestionCLI()

    if args.command == "list":
        types = cli.list_types()
        logger.info("\nAvailable Ingestion Types:")
        logger.info("=" * 60)
        for type_name, info in types["types"].items():
            logger.info(f"\n{type_name}:")
            logger.info(f"  Description: {info['description']}")
            logger.info(f"  Source: {info['source']}")
            logger.info(f"  Collection: {info['collection']}")
        return 0

    elif args.command == "ingest":
        if args.type == "team-members":
            result = await cli.ingest_team_members(source=args.source)
        elif args.type == "conversations":
            if not args.source:
                logger.error("Error: --source required for conversations ingestion")
                return 1
            result = await cli.ingest_conversations(source=args.source, collection=args.collection)
        elif args.type == "laws":
            result = await cli.ingest_laws(file_path=args.file, directory=args.directory)
        elif args.type == "document":
            if not args.file:
                logger.error("Error: --file required for document ingestion")
                return 1
            result = await cli.ingest_document(
                file_path=args.file,
                title=args.title,
                author=args.author,
                collection=args.collection,
            )
        else:
            logger.error(f"Error: Unknown ingestion type: {args.type}")
            return 1

        # Print results
        if result.get("success"):
            logger.info("\n✅ Ingestion successful!")
            logger.info(f"   Ingested: {result.get('ingested', 0)} items")
            logger.info(f"   Collection: {result.get('collection', 'unknown')}")
        else:
            logger.error(f"\n❌ Ingestion failed: {result.get('error', 'Unknown error')}")
            return 1

        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
