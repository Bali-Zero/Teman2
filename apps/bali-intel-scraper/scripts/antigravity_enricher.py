#!/usr/bin/env python3
"""
ANTIGRAVITY ENRICHER
Uses Claude Opus via Google AI Pro (free, unlimited, working OAuth)
"""

import json
import requests
import sys
from pathlib import Path
from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# OpenClaw gateway URL
OPENCLAW_GATEWAY = "http://localhost:19009/v1/chat/completions"

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

OUTPUT FORMAT (JSON only):
{{
  "executive_brief": "...",
  "key_facts": ["...", "..."],
  "insights": ["...", "..."],
  "legal_analysis": "..."
}}"""


def enrich_article_antigravity(article: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich via Antigravity (Google AI Pro Claude Opus)"""
    
    logger.info(f"Enriching: {article.get('title', 'Unknown')[:50]}...")
    
    prompt = ENRICHMENT_PROMPT_TEMPLATE.format(
        title=article.get('title', 'Unknown'),
        source=article.get('source', 'Unknown'),
        category=article.get('category', 'general'),
        content=article.get('content', '')[:2000]
    )
    
    try:
        response = requests.post(
            OPENCLAW_GATEWAY,
            json={
                "model": "google-antigravity/claude-opus-4-5-thinking",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
                "temperature": 0.7
            },
            timeout=30
        )
        
        response.raise_for_status()
        data = response.json()
        
        content = data['choices'][0]['message']['content']
        logger.info(f"Response: {len(content)} chars")
        
        # Parse JSON
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            enriched = json.loads(content[json_start:json_end])
            logger.info("✅ Enrichment successful")
            return {
                'success': True,
                'enrichment': enriched,
                'raw_response': content
            }
        else:
            logger.warning("No JSON in response")
            return {
                'success': False,
                'error': 'No valid JSON',
                'raw_response': content
            }
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == "__main__":
    test_article = {
        'title': 'Indonesia Extends Digital Nomad Visa to 5 Years',
        'source': 'Jakarta Post',
        'category': 'immigration',
        'content': '''The Indonesian government announced the B211A digital nomad visa 
        will be extended from 1 year to 5 years validity, effective March 2026.'''
    }
    
    print("="*60)
    print("TEST: Antigravity Enricher (Google AI Pro)")
    print("="*60)
    
    result = enrich_article_antigravity(test_article)
    
    print("\n" + "="*60)
    print("RESULT:")
    print("="*60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    sys.exit(0 if result['success'] else 1)
