#!/usr/bin/env python3
"""
GEMINI ENRICHER
Uses Gemini 3 Pro via gemini CLI (Google AI Pro, free, unlimited)
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ENRICHMENT_PROMPT_TEMPLATE = """Analyze this article and provide structured enrichment:

ARTICLE:
Title: {title}
Source: {source}
Category: {category}
Content: {content}

TASK:
1. Executive Brief (max 200 words): High-level summary
2. Key Facts (5-7 bullets): Core information
3. Actionable Insights (3-5 points): What to do with this info
4. Legal Analysis (if applicable): Legal implications

OUTPUT FORMAT (JSON only, no markdown):
{{
  "executive_brief": "...",
  "key_facts": ["...", "..."],
  "insights": ["...", "..."],
  "legal_analysis": "..."
}}"""


def enrich_article_gemini(article: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich via Gemini 3 Pro CLI"""
    
    logger.info(f"Enriching: {article.get('title', 'Unknown')[:50]}...")
    
    prompt = ENRICHMENT_PROMPT_TEMPLATE.format(
        title=article.get('title', 'Unknown'),
        source=article.get('source', 'Unknown'),
        category=article.get('category', 'general'),
        content=article.get('content', '')[:2000]
    )
    
    try:
        logger.info("Calling Gemini CLI...")
        result = subprocess.run(
            ['gemini', prompt],
            capture_output=True,
            text=True,
            timeout=30,
            check=True
        )
        
        output = result.stdout.strip()
        logger.info(f"Response: {len(output)} chars")
        
        # Parse JSON
        if '```json' in output:
            output = output.split('```json')[1].split('```')[0].strip()
        elif '```' in output:
            output = output.split('```')[1].split('```')[0].strip()
        
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            enriched = json.loads(output[json_start:json_end])
            logger.info("✅ Enrichment successful")
            return {
                'success': True,
                'enrichment': enriched,
                'raw_response': output
            }
        else:
            logger.warning("No JSON in response")
            return {
                'success': False,
                'error': 'No valid JSON',
                'raw_response': output
            }
            
    except subprocess.TimeoutExpired:
        logger.error("Gemini CLI timeout (30s)")
        return {'success': False, 'error': 'Timeout after 30s'}
    except subprocess.CalledProcessError as e:
        logger.error(f"Gemini CLI error: {e.stderr}")
        return {'success': False, 'error': f'Gemini failed: {e.stderr}'}
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return {
            'success': False,
            'error': f'Invalid JSON: {e}',
            'raw_response': output if 'output' in locals() else None
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    test_article = {
        'title': 'Indonesia Extends Digital Nomad Visa to 5 Years',
        'source': 'Jakarta Post',
        'category': 'immigration',
        'content': '''The Indonesian government announced the B211A digital nomad visa 
        will be extended from 1 year to 5 years validity, effective March 2026.'''
    }
    
    print("="*60)
    print("TEST: Gemini Enricher (Google AI Pro)")
    print("="*60)
    
    result = enrich_article_gemini(test_article)
    
    print("\n" + "="*60)
    print("RESULT:")
    print("="*60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    sys.exit(0 if result['success'] else 1)
