#!/usr/bin/env python3
"""
CLAUDE CLI ENRICHER
Uses Claude Code CLI (subprocess) - Max quota, no browser automation
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


ENRICHMENT_PROMPT_TEMPLATE = """You are a senior editor at Bali Zero, a business consultancy for foreigners in Bali/Indonesia.

Enrich this article for our intelligence news room. Write in English, editorial style.

<notizia_scraped>
Title: {title}
Source: {source}
Category: {category}
Published: {published_date}
Content: {content}
</notizia_scraped>

<base_legale_certificata>
{nlm_legal_basis}
</base_legale_certificata>

<fonti_web_non_verificate>
{nlm_web_findings}
</fonti_web_non_verificate>

IMPORTANT: The <base_legale_certificata> section contains VERIFIED Indonesian law from our legal database.
The <fonti_web_non_verificate> section may contain errors — use with caution and always
prefer the certified legal basis. Never present web findings as verified law.
If both sections are empty, write based on the news article alone.

OUTPUT FORMAT (strict JSON only, no markdown):
{{
  "headline": "Punchy editorial headline (max 80 chars, no source name)",
  "thirty_second_brief": {{
    "what": "1 sentence: what happened",
    "why_it_matters": "1 sentence: why it matters to expats/investors in Bali",
    "who": "who is affected",
    "risk_level": "low|medium|high"
  }},
  "the_facts": "3-5 paragraphs of pure journalism. Facts only, no opinion. 400-500 words.",
  "bali_zero_take": "2-3 paragraphs: Bali Zero editorial perspective. What does this mean for our clients? 150-200 words.",
  "in_practice": "Practical implications for expats/investors in Bali. Bullet-point style converted to prose. 150-200 words.",
  "next_steps": "Concrete action items for readers. What should they do NOW? 100-150 words.",
  "faq": [
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}}
  ],
  "metadata": {{
    "suggested_slug": "url-friendly-slug-max-60-chars",
    "tags": ["tag1", "tag2", "tag3"],
    "priority": "high|medium|low",
    "reading_time_minutes": 3
  }}
}}

RULES:
- headline: never include the source name, make it punchy and specific
- the_facts: journalism only, no Bali Zero branding, no "our clients"
- bali_zero_take: this is where we add our expert spin
- Output ONLY valid JSON, no explanations or markdown code blocks
"""


def enrich_article_claude_cli(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich article using Claude Code CLI (subprocess call).
    Uses Claude Max subscription quota.
    
    Args:
        article: Dict with keys: title, source, category, published_date, content
        
    Returns:
        Dict with enrichment data
    """
    logger.info(f"Enriching: {article.get('title', 'Unknown')[:50]}...")
    
    # Extract NLM context if available (from step 2.9)
    nlm_ctx = article.get('nlm_context') or {}
    nlm_legal = nlm_ctx.get('legal_basis', '')
    nlm_web = nlm_ctx.get('web_findings', '')
    # nlm_legal and nlm_web default to '' from .get() above — no extra guard needed

    def _escape_for_prompt(s: str) -> str:
        """Escape curly braces (for str.format) and XML tag chars (prevent tag injection)."""
        return s.replace('{', '{{').replace('}', '}}').replace('<', '&lt;').replace('>', '&gt;')

    # Escape NLM output and article content for safe prompt injection
    nlm_legal = _escape_for_prompt(str(nlm_legal or '')[:3000])
    nlm_web = _escape_for_prompt(str(nlm_web or '')[:2000])

    # Build prompt — ALL article fields escaped to prevent XML tag spoofing
    prompt = ENRICHMENT_PROMPT_TEMPLATE.format(
        title=_escape_for_prompt(str(article.get('title') or 'Unknown')[:300]),
        source=_escape_for_prompt(article.get('source_name', article.get('source', 'Unknown'))),
        category=_escape_for_prompt(article.get('qwen_category', article.get('category', 'general'))),
        published_date=_escape_for_prompt(article.get('published_date', 'Unknown')),
        content=_escape_for_prompt(str(article.get('content') or '')[:4000]),
        nlm_legal_basis=nlm_legal,
        nlm_web_findings=nlm_web,
    )
    
    try:
        # Call Claude Code CLI
        logger.info("Calling Claude Code CLI...")
        
        # Remove ANTHROPIC_API_KEY from environment to use OAuth
        env = os.environ.copy()
        env.pop('ANTHROPIC_API_KEY', None)
        
        # Use absolute path so launchd (limited PATH) can find claude
        import shutil
        claude_bin = shutil.which('claude') or '/Users/nuzantara/.local/bin/claude'

        result = subprocess.run(
            [claude_bin, '--print', '--model', 'claude-sonnet-4-6', prompt],
            capture_output=True,
            text=True,
            timeout=180,  # 180s timeout
            check=True,
            env=env
        )
        
        output = result.stdout.strip()
        logger.info(f"Claude response: {len(output)} chars")
        
        # Parse JSON from response
        # Claude might wrap in markdown code blocks, strip those
        if '```json' in output:
            output = output.split('```json')[1].split('```')[0].strip()
        elif '```' in output:
            output = output.split('```')[1].split('```')[0].strip()
        
        # Try to find JSON object
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = output[json_start:json_end]
            enriched = json.loads(json_str)
            
            logger.info("✅ Enrichment successful")
            return {
                'success': True,
                'enrichment': enriched,
                'raw_response': output
            }
        else:
            logger.warning("No JSON found in response")
            return {
                'success': False,
                'error': 'No valid JSON in response',
                'raw_response': output
            }
            
    except subprocess.TimeoutExpired:
        logger.error("Claude CLI timeout (180s)")
        return {
            'success': False,
            'error': 'Timeout after 180s'
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Claude CLI error: {e.stderr}")
        return {
            'success': False,
            'error': f'Claude CLI failed: {e.stderr}'
        }
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return {
            'success': False,
            'error': f'Invalid JSON: {e}',
            'raw_response': output if 'output' in locals() else None
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def batch_enrich_articles(articles: list[Dict[str, Any]], max_articles: int = None) -> list[Dict[str, Any]]:
    """
    Batch enrich multiple articles.
    
    Args:
        articles: List of article dicts
        max_articles: Limit number of articles (for testing)
        
    Returns:
        List of enriched articles
    """
    if max_articles:
        articles = articles[:max_articles]
    
    logger.info(f"Batch enriching {len(articles)} articles...")
    
    enriched_articles = []
    success_count = 0
    error_count = 0
    
    for i, article in enumerate(articles, 1):
        logger.info(f"\n[{i}/{len(articles)}] Processing: {article.get('title', 'Unknown')[:50]}")
        
        result = enrich_article_claude_cli(article)
        
        if result['success']:
            success_count += 1
            enriched_articles.append({
                **article,
                'enrichment': result['enrichment']
            })
        else:
            error_count += 1
            logger.error(f"Failed: {result.get('error')}")
            enriched_articles.append({
                **article,
                'enrichment_error': result.get('error')
            })
    
    logger.info(f"\n{'='*60}")
    logger.info(f"BATCH COMPLETE")
    logger.info(f"  Success: {success_count}/{len(articles)}")
    logger.info(f"  Errors:  {error_count}/{len(articles)}")
    logger.info(f"{'='*60}")
    
    return enriched_articles


if __name__ == "__main__":
    # Test with sample article
    test_article = {
        'title': 'Indonesia Extends Digital Nomad Visa to 5 Years',
        'source': 'Jakarta Post',
        'category': 'immigration',
        'published_date': '2026-02-20',
        'content': '''The Indonesian government announced today that the B211A digital nomad visa 
        will be extended from 1 year to 5 years validity, effective March 2026. This makes Indonesia 
        one of the most attractive destinations for remote workers in Southeast Asia. The visa allows 
        foreigners to live and work remotely from Indonesia while earning income from abroad. 
        Immigration officials stated this change aims to attract high-skilled foreign talent and 
        boost the digital economy.'''
    }
    
    print("="*60)
    print("TEST: Claude CLI Enricher")
    print("="*60)
    print()
    
    result = enrich_article_claude_cli(test_article)
    
    print("\n" + "="*60)
    print("RESULT:")
    print("="*60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result['success']:
        print("\n🎉 TEST PASSED")
        sys.exit(0)
    else:
        print("\n💥 TEST FAILED")
        sys.exit(1)
