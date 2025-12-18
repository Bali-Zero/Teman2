"""
RAGAS Evaluation Script for Nuzantara RAG System
Evaluates RAG quality using Ragas with Google Gemini as judge
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from datasets import Dataset
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas import evaluate
from ragas.metrics import answer_relevancy, faithfulness

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / "backend-rag" / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.config import settings

# Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or settings.google_api_key
RAG_API_URL = os.getenv("RAG_API_URL", "https://nuzantara-rag.fly.dev")
API_KEY = os.getenv("JUDGEMENT_DAY_API_KEY")  # API Key for testing

# Test questions about Indonesian Law - Topics that should be in knowledge base
# Based on retrieved contexts: KITAS, BPJS, PT PMA, OSS, visa, investment
TEST_QUESTIONS = [
    "Apa itu KITAS dan bagaimana cara mendapatkannya?",
    "Bagaimana proses registrasi BPJS Kesehatan untuk expat?",
    "Apa persyaratan untuk mendirikan PT PMA di Indonesia?",
]


async def query_nuzantara_api(question: str) -> dict[str, Any]:
    """
    Query the Nuzantara RAG API and extract answer and contexts.

    Args:
        question: The question to ask

    Returns:
        Dictionary with 'question', 'answer', and 'contexts'
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Call the Oracle query endpoint
            response = await client.post(
                f"{RAG_API_URL}/api/oracle/query",
                json={
                    "query": question,
                    "limit": 5,
                    "use_ai": True,
                    "language_override": "id",  # Indonesian
                },
                headers={"x-api-key": API_KEY},
            )
            response.raise_for_status()
            data = response.json()

            # Extract answer
            answer = data.get("answer", "")
            if not answer:
                answer = data.get("response", {}).get("answer", "")

            # Extract contexts from sources
            sources = data.get("sources", [])
            contexts = []
            for source in sources:
                content = source.get("content", "")
                if content:
                    contexts.append(content)

            # Fallback: use documents if sources not available
            if not contexts:
                documents = data.get("documents", [])
                contexts = documents[:5]  # Limit to 5 contexts

            return {
                "question": question,
                "answer": answer,
                "contexts": contexts,
            }

        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP error querying API: {e.response.status_code}")
            print(f"Response: {e.response.text}")
            return {
                "question": question,
                "answer": f"Error: {e.response.status_code}",
                "contexts": [],
            }
        except Exception as e:
            print(f"❌ Error querying API: {e}")
            return {
                "question": question,
                "answer": f"Error: {str(e)}",
                "contexts": [],
            }


async def collect_evaluation_data() -> list[dict[str, Any]]:
    """
    Collect evaluation data by querying the RAG API for each test question.

    Returns:
        List of dictionaries with question, answer, and contexts
    """
    print("🔍 Collecting evaluation data from Nuzantara RAG API...")
    results = []

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"\n[{i}/{len(TEST_QUESTIONS)}] Querying: {question}")
        result = await query_nuzantara_api(question)
        results.append(result)
        print(f"✅ Answer length: {len(result['answer'])} chars")
        print(f"✅ Contexts found: {len(result['contexts'])}")

    return results


def create_ragas_dataset(evaluation_data: list[dict[str, Any]]) -> Dataset:
    """
    Create a Ragas Dataset from evaluation data.

    Args:
        evaluation_data: List of dicts with question, answer, contexts

    Returns:
        Ragas Dataset
    """
    # Prepare data in Ragas format
    # Ragas expects: question, answer, contexts (list of strings), ground_truth (optional)
    dataset_dict = {
        "question": [item["question"] for item in evaluation_data],
        "answer": [item["answer"] for item in evaluation_data],
        "contexts": [item["contexts"] for item in evaluation_data],
        # Ground truth not available, so we'll skip it
    }

    # Create Dataset
    dataset = Dataset.from_dict(dataset_dict)
    return dataset


async def run_evaluation(dataset: Dataset) -> pd.DataFrame:
    """
    Run Ragas evaluation with Google Gemini as judge.

    Args:
        dataset: Ragas Dataset

    Returns:
        DataFrame with evaluation results
    """
    print("\n⚖️  Initializing Google Gemini as judge...")

    # Initialize Google Gemini LLM
    # Use gemini-2.5-flash (Nuzantara's production model for heavy work)
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GOOGLE_API_KEY,
            temperature=0,
        )
        # Test if model is accessible
        await llm.ainvoke("Hello")
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize gemini-2.5-flash: {e}")
        print("   Trying gemini-1.5-pro as fallback...")
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-pro",
                google_api_key=GOOGLE_API_KEY,
                temperature=0,
            )
            await llm.ainvoke("Hello")
        except Exception as e_pro:
            print(f"❌ Error: Could not initialize any Gemini LLM: {e_pro}")
            raise RuntimeError(
                "Failed to initialize Gemini LLM for Ragas evaluation."
            ) from e_pro

    # Initialize Google Gemini Embeddings
    # Use embedding-001 (stable, widely available)
    # Note: text-embedding-004 may not be available in all regions
    try:
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=GOOGLE_API_KEY,
        )
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize embeddings: {e}")
        print("   Trying alternative model...")
        # Try without model specification (uses default)
        embeddings = GoogleGenerativeAIEmbeddings(
            google_api_key=GOOGLE_API_KEY,
        )

    print("✅ Gemini initialized")

    # Define metrics with Gemini LLM and embeddings
    print("\n📊 Running evaluation metrics...")
    print("  - faithfulness: Checks if answer is grounded in contexts")
    print("  - answer_relevancy: Checks if answer is relevant to question")

    # Run evaluation
    # Ragas accepts llm and embeddings as parameters to evaluate()
    # These will be used by the metrics that need them
    print("   Starting evaluation (this may take a few minutes)...")
    try:
        result = evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=llm,
            embeddings=embeddings,
        )
    except Exception as e:
        print(f"\n❌ Error during evaluation: {e}")
        print("   This might be due to:")
        print("   - Invalid Gemini model name")
        print("   - API rate limits")
        print("   - Network issues")
        raise

    # Convert to DataFrame
    df = result.to_pandas()
    return df


async def main():
    """Main execution function"""
    print("=" * 60)
    print("⚖️  RAGAS JUDGEMENT DAY - Nuzantara RAG Evaluation")
    print("=" * 60)

    # Check API key
    if not GOOGLE_API_KEY:
        print("❌ ERROR: GOOGLE_API_KEY not found in environment")
        print("   Please set GOOGLE_API_KEY environment variable")
        sys.exit(1)

    print(f"\n🔑 Using Google API Key: {GOOGLE_API_KEY[:10]}...")
    print(f"🌐 RAG API URL: {RAG_API_URL}")

    # Step 1: Collect evaluation data
    evaluation_data = await collect_evaluation_data()

    if not evaluation_data:
        print("❌ No evaluation data collected. Exiting.")
        sys.exit(1)

    # Step 2: Filter out invalid data (no contexts or error answers)
    valid_data = [
        item
        for item in evaluation_data
        if item["contexts"] and not item["answer"].startswith("Error:")
    ]

    if not valid_data:
        print(
            "\n⚠️  WARNING: No valid evaluation data (all queries failed or have no contexts)"
        )
        print("   Creating empty report with error information...")

        # Create report with error info
        error_df = pd.DataFrame(evaluation_data)
        output_path = Path(__file__).parent / "report.csv"
        error_df.to_csv(output_path, index=False)
        print(f"💾 Error report saved to: {output_path}")
        print("\n❌ Cannot run evaluation without valid data. Please check:")
        print("   1. RAG API is running and accessible")
        print("   2. Embedding service is available")
        print("   3. Qdrant is connected and has documents")
        sys.exit(1)

    print(f"\n✅ Valid samples: {len(valid_data)}/{len(evaluation_data)}")

    # Step 3: Create Ragas Dataset
    print("\n📦 Creating Ragas Dataset...")
    dataset = create_ragas_dataset(valid_data)
    print(f"✅ Dataset created with {len(dataset)} samples")

    # Step 4: Run evaluation
    results_df = await run_evaluation(dataset)

    # Step 5: Save results
    output_path = Path(__file__).parent / "report.csv"
    results_df.to_csv(output_path, index=False)
    print(f"\n💾 Results saved to: {output_path}")

    # Display summary
    print("\n" + "=" * 60)
    print("📊 EVALUATION SUMMARY")
    print("=" * 60)
    print(results_df.to_string())
    print("\n" + "=" * 60)

    # Calculate averages (skip NaN values)
    if "faithfulness" in results_df.columns:
        avg_faithfulness = results_df["faithfulness"].mean(skipna=True)
        if pd.notna(avg_faithfulness):
            print(f"\n📈 Average Faithfulness: {avg_faithfulness:.3f}")
        else:
            print("\n⚠️  Could not calculate average faithfulness (all NaN)")
    if "answer_relevancy" in results_df.columns:
        avg_relevancy = results_df["answer_relevancy"].mean(skipna=True)
        if pd.notna(avg_relevancy):
            print(f"📈 Average Answer Relevancy: {avg_relevancy:.3f}")
        else:
            print("⚠️  Could not calculate average answer relevancy (all NaN)")

    print("\n✅ Evaluation complete!")


if __name__ == "__main__":
    asyncio.run(main())
