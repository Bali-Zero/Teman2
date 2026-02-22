#!/usr/bin/env python3
"""
Gemini Article Enricher
Deep enrichment with: Executive brief, key facts, insights, legal analysis

Input: data/validated/*.json (approved only)
Output: data/enriched/*.json
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
VALIDATED_DIR = PROJECT_ROOT / 'data' / 'validated'
ENRICHED_DIR = PROJECT_ROOT / 'data' / 'enriched'
ENRICHED_DIR.mkdir(exist_ok=True, parents=True)

# Config
TIMEOUT = 120  # 2 minutes per article (complex analysis)


class GeminiEnricher:
    def __init__(self):
        self.stats = {
            'total': 0,
            'enriched': 0,
            'failed': 0
        }
    
    def log(self, message: str, level: str = 'INFO'):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f'[{timestamp}] [{level}] {message}')
        sys.stdout.flush()
    
    def clean_gemini_output(self, raw: str) -> str:
        """Clean Gemini CLI debug output"""
        lines = raw.strip().split('\n')
        cleaned = []
        
        for line in lines:
            if not line.strip():
                continue
            if any(line.strip().startswith(p) for p in [
                'Prompts updated', 'Tools updated', 'I will', "I'll", 'Let me', 'I am going'
            ]):
                continue
            cleaned.append(line)
        
        # Return last substantial paragraph
        if cleaned:
            full_text = '\n'.join(cleaned)
            paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]
            if paragraphs:
                return paragraphs[-1]
        
        return raw
    
    def enrich_article(self, article: Dict) -> Optional[Dict]:
        """Enrich article with AI analysis"""
        
        title = article.get('title', '')
        summary = article.get('summary', '')
        text = article.get('text', '')
        category = article.get('category', '')
        
        prompt = f"""Analyze this {category} article for Bali business consulting.

ARTICLE:
Title: {title}
Summary: {summary}
Text: {text[:1500]}

Provide JSON with:
{{
  "executive_brief": "<200 word summary for busy executives>",
  "key_facts": ["<fact 1>", "<fact 2>", "<fact 3>"],
  "actionable_insights": ["<insight 1>", "<insight 2>"],
  "legal_implications": "<regulatory/legal impact>",
  "target_audience": ["<audience 1>", "<audience 2>"],
  "urgency_level": "<low|medium|high|critical>",
  "expiry_date": "<YYYY-MM-DD if time-sensitive, null otherwise>"
}}

Be specific, factual, and consulting-focused."""

        try:
            self.log(f'  Enriching: {title[:60]}...')
            
            result = subprocess.run(
                ['gemini', prompt],
                capture_output=True,
                text=True,
                timeout=TIMEOUT
            )
            
            if result.returncode == 0:
                output = self.clean_gemini_output(result.stdout)
                
                # Extract JSON
                import re
                json_match = re.search(r'\{.*\}', output, re.DOTALL)
                if json_match:
                    enrichment = json.loads(json_match.group())
                    self.log(f'  ✅ Enriched ({len(output)} chars)')
                    return enrichment
        
        except subprocess.TimeoutExpired:
            self.log('  ⏱️  Timeout', 'WARN')
        except Exception as e:
            self.log(f'  ❌ Error: {e}', 'ERROR')
        
        return None
    
    def enrich_batch(self, articles: List[Dict]) -> List[Dict]:
        """Enrich batch of articles"""
        self.log('='*60)
        self.log('GEMINI ENRICHER STARTED')
        self.log('='*60)
        
        # Filter approved articles only
        approved = [a for a in articles if a.get('validation_status') == 'approved']
        self.stats['total'] = len(approved)
        
        self.log(f'Enriching {len(approved)} approved articles (from {len(articles)} total)')
        
        enriched = []
        
        for i, article in enumerate(approved, 1):
            self.log(f'\n[{i}/{len(approved)}]')
            
            try:
                enrichment = self.enrich_article(article)
                
                if enrichment:
                    article['enrichment'] = enrichment
                    article['enriched_at'] = datetime.now().isoformat()
                    article['enriched_by'] = 'gemini-3-pro'
                    self.stats['enriched'] += 1
                else:
                    article['enrichment_status'] = 'failed'
                    self.stats['failed'] += 1
                
                enriched.append(article)
            
            except Exception as e:
                self.log(f'  Error: {e}', 'ERROR')
                article['enrichment_status'] = 'error'
                article['enrichment_error'] = str(e)
                enriched.append(article)
                self.stats['failed'] += 1
        
        return enriched
    
    def save_results(self, articles: List[Dict], source_file: Path):
        """Save enriched articles"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = ENRICHED_DIR / f'{timestamp}_enriched.json'
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'source_file': str(source_file),
            'stats': self.stats,
            'articles': articles
        }
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        self.log(f'\n💾 Saved: {output_file}')
        return output_file
    
    def print_summary(self):
        """Print enrichment summary"""
        self.log('\n' + '='*60)
        self.log('ENRICHMENT COMPLETE')
        self.log('='*60)
        self.log(f"""
📊 STATS:
   Approved articles: {self.stats['total']}
   Enriched:          {self.stats['enriched']} ({self.stats['enriched']/self.stats['total']*100 if self.stats['total'] > 0 else 0:.1f}%)
   Failed:            {self.stats['failed']}
""")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Gemini Article Enricher')
    parser.add_argument('input_file', nargs='?',
                       help='Input validated articles JSON file')
    parser.add_argument('--latest', action='store_true',
                       help='Use latest validated file')
    
    args = parser.parse_args()
    
    # Find input file
    if args.latest or not args.input_file:
        validated_files = sorted(VALIDATED_DIR.glob('*.json'), reverse=True)
        if not validated_files:
            print('No validated files found in data/validated/')
            return 1
        input_file = validated_files[0]
        print(f'Using latest: {input_file.name}')
    else:
        input_file = Path(args.input_file)
        if not input_file.exists():
            print(f'File not found: {input_file}')
            return 1
    
    # Load articles
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    articles = data.get('articles', [])
    if not articles:
        print('No articles found in input file')
        return 1
    
    print(f'Loaded {len(articles)} articles')
    
    # Enrich
    enricher = GeminiEnricher()
    enriched = enricher.enrich_batch(articles)
    output_file = enricher.save_results(enriched, input_file)
    enricher.print_summary()
    
    print(f'\n✅ Output: {output_file}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
