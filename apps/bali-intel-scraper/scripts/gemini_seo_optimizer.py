#!/usr/bin/env python3
"""
Gemini SEO Optimizer
Generates: Meta tags, Schema.org JSON-LD, FAQ schema, Open Graph

Input: data/enriched/*.json
Output: data/seo_ready/*.json with full HTML
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENRICHED_DIR = PROJECT_ROOT / 'data' / 'enriched'
SEO_DIR = PROJECT_ROOT / 'data' / 'seo_ready'
SEO_DIR.mkdir(exist_ok=True, parents=True)

TIMEOUT = 60


class SEOOptimizer:
    def __init__(self):
        self.stats = {'total': 0, 'optimized': 0, 'failed': 0}
    
    def log(self, msg: str, level: str = 'INFO'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f'[{timestamp}] [{level}] {msg}')
        sys.stdout.flush()
    
    def optimize_article(self, article: Dict) -> Optional[Dict]:
        """Generate SEO metadata with Gemini 3 Pro"""
        
        title = article.get('title', '')
        summary = article.get('enrichment', {}).get('executive_brief', '')
        category = article.get('category', '')
        
        prompt = f"""Generate SEO metadata for this article:

Title: {title}
Category: {category}
Summary: {summary[:300]}

Provide JSON:
{{
  "meta_title": "<60 chars max, keyword-optimized>",
  "meta_description": "<155 chars max>",
  "keywords": ["<kw1>", "<kw2>", "<kw3>"],
  "schema_org": {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "<title>",
    "description": "<description>",
    "articleBody": "<summary>"
  }},
  "og_title": "<Open Graph title>",
  "og_description": "<Open Graph description>"
}}"""

        try:
            result = subprocess.run(
                ['gemini', prompt],
                capture_output=True,
                text=True,
                timeout=TIMEOUT
            )
            
            if result.returncode == 0:
                import re
                json_match = re.search(r'\{.*\}', result.stdout, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            self.log(f'  SEO error: {e}', 'WARN')
        
        return None
    
    def optimize_batch(self, articles: list) -> list:
        self.log('='*60)
        self.log('SEO OPTIMIZER STARTED')
        self.log('='*60)
        
        optimized = []
        self.stats['total'] = len(articles)
        
        for i, article in enumerate(articles, 1):
            self.log(f'\n[{i}/{len(articles)}] {article.get("title", "")[:50]}...')
            
            seo = self.optimize_article(article)
            if seo:
                article['seo'] = seo
                article['seo_optimized_at'] = datetime.now().isoformat()
                self.stats['optimized'] += 1
                self.log('  ✅ SEO metadata generated')
            else:
                self.stats['failed'] += 1
                self.log('  ❌ SEO failed')
            
            optimized.append(article)
        
        return optimized
    
    def save_results(self, articles: list, source_file: Path):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = SEO_DIR / f'{timestamp}_seo_ready.json'
        
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'source_file': str(source_file),
                'stats': self.stats,
                'articles': articles
            }, f, indent=2, ensure_ascii=False)
        
        self.log(f'\n💾 Saved: {output_file}')
        return output_file
    
    def print_summary(self):
        self.log(f"""
📊 SEO OPTIMIZATION COMPLETE:
   Total:     {self.stats['total']}
   Optimized: {self.stats['optimized']}
   Failed:    {self.stats['failed']}
""")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', nargs='?')
    parser.add_argument('--latest', action='store_true')
    args = parser.parse_args()
    
    if args.latest or not args.input_file:
        files = sorted(ENRICHED_DIR.glob('*.json'), reverse=True)
        if not files:
            print('No enriched files found')
            return 1
        input_file = files[0]
    else:
        input_file = Path(args.input_file)
    
    with open(input_file) as f:
        data = json.load(f)
    
    articles = data.get('articles', [])
    optimizer = SEOOptimizer()
    optimized = optimizer.optimize_batch(articles)
    output_file = optimizer.save_results(optimized, input_file)
    optimizer.print_summary()
    
    print(f'\n✅ Output: {output_file}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
