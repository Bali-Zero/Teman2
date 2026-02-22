#!/usr/bin/env python3
"""
Gemini Article Validator - Anti-Duplicate Check
Uses Gemini 3 Pro CLI to detect duplicate articles

Input: data/scraped/*.json
Output: data/validated/*.json (with duplicate flags)
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SCRAPED_DIR = PROJECT_ROOT / 'data' / 'scraped'
VALIDATED_DIR = PROJECT_ROOT / 'data' / 'validated'
VALIDATED_DIR.mkdir(exist_ok=True, parents=True)

PUBLISHED_FILE = PROJECT_ROOT / 'data' / 'published_articles.json'

# Config
TIMEOUT = 60
KEYWORD_OVERLAP_THRESHOLD = 0.6  # 60% keyword overlap = likely duplicate


class GeminiValidator:
    def __init__(self):
        self.stats = {
            'total': 0,
            'validated': 0,
            'duplicates': 0,
            'approved': 0,
            'failed': 0
        }
        self.published_articles = self.load_published_articles()
    
    def log(self, message: str, level: str = 'INFO'):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f'[{timestamp}] [{level}] {message}')
        sys.stdout.flush()
    
    def load_published_articles(self) -> List[Dict]:
        """Load previously published articles"""
        if not PUBLISHED_FILE.exists():
            self.log('No published articles file found - starting fresh')
            return []
        
        try:
            with open(PUBLISHED_FILE, 'r') as f:
                data = json.load(f)
            articles = data.get('articles', [])
            self.log(f'Loaded {len(articles)} published articles for comparison')
            return articles
        except Exception as e:
            self.log(f'Error loading published articles: {e}', 'ERROR')
            return []
    
    def quick_duplicate_check(self, article: Dict) -> bool:
        """Quick keyword overlap check before AI validation"""
        title = article.get('title', '').lower()
        title_words = set(title.split())
        
        for published in self.published_articles[-50:]:  # Check last 50
            pub_title = published.get('title', '').lower()
            pub_words = set(pub_title.split())
            
            # Calculate Jaccard similarity
            if title_words and pub_words:
                intersection = title_words & pub_words
                union = title_words | pub_words
                overlap = len(intersection) / len(union)
                
                if overlap >= KEYWORD_OVERLAP_THRESHOLD:
                    return True  # Likely duplicate
        
        return False
    
    def gemini_semantic_check(self, article: Dict, candidates: List[Dict]) -> Dict:
        """Use Gemini 3 Pro to determine if article is duplicate"""
        
        # Build comparison prompt
        article_title = article.get('title', '')
        candidate_titles = '\n'.join([
            f"{i+1}. {c.get('title', '')}"
            for i, c in enumerate(candidates[:10])  # Limit to 10 candidates
        ])
        
        prompt = f"""Is this new article a duplicate of any previously published article?

NEW ARTICLE:
Title: {article_title}
Summary: {article.get('summary', '')[:200]}

PREVIOUSLY PUBLISHED:
{candidate_titles}

Respond in JSON format:
{{
  "is_duplicate": true/false,
  "match_number": <number if duplicate, null otherwise>,
  "confidence": <0-100>,
  "reason": "<brief explanation>"
}}"""

        try:
            result = subprocess.run(
                ['gemini', prompt],
                capture_output=True,
                text=True,
                timeout=TIMEOUT
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                
                # Clean Gemini debug output (same as pro enricher)
                lines = output.split('\n')
                cleaned = []
                for line in lines:
                    if line.strip() and not any(line.startswith(p) for p in [
                        'Prompts updated', 'Tools updated', 'I will', "I'll", 'Let me'
                    ]):
                        cleaned.append(line)
                
                # Find JSON in output
                import re
                json_match = re.search(r'\{.*\}', '\n'.join(cleaned), re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        
        except subprocess.TimeoutExpired:
            self.log('  Gemini timeout', 'WARN')
        except Exception as e:
            self.log(f'  Gemini check error: {e}', 'WARN')
        
        # Default: assume not duplicate on error
        return {
            'is_duplicate': False,
            'confidence': 0,
            'reason': 'Validation failed'
        }
    
    def validate_article(self, article: Dict) -> Dict:
        """Validate single article"""
        self.log(f'\nValidating: {article.get("title", "Unknown")[:60]}...')
        
        # Quick check first
        if self.quick_duplicate_check(article):
            self.log('  Quick check: Likely duplicate (high keyword overlap)')
            
            # Semantic check with Gemini
            validation = self.gemini_semantic_check(article, self.published_articles[-50:])
            
            if validation.get('is_duplicate'):
                self.log(f'  ❌ DUPLICATE (confidence: {validation.get("confidence", 0)}%)')
                self.log(f'     Reason: {validation.get("reason", "N/A")}')
                article['validation_status'] = 'duplicate'
                article['validation_result'] = validation
                self.stats['duplicates'] += 1
                return article
        
        # Passed validation
        self.log('  ✅ APPROVED (not a duplicate)')
        article['validation_status'] = 'approved'
        article['validated_at'] = datetime.now().isoformat()
        self.stats['approved'] += 1
        
        return article
    
    def validate_batch(self, articles: List[Dict]) -> List[Dict]:
        """Validate batch of articles"""
        self.log('='*60)
        self.log('GEMINI VALIDATOR STARTED')
        self.log('='*60)
        
        self.stats['total'] = len(articles)
        validated = []
        
        for i, article in enumerate(articles, 1):
            self.log(f'\n[{i}/{len(articles)}]')
            
            try:
                validated_article = self.validate_article(article)
                validated.append(validated_article)
                self.stats['validated'] += 1
            except Exception as e:
                self.log(f'  Error: {e}', 'ERROR')
                article['validation_status'] = 'error'
                article['validation_error'] = str(e)
                validated.append(article)
                self.stats['failed'] += 1
        
        return validated
    
    def save_results(self, articles: List[Dict], source_file: Path):
        """Save validated articles"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = VALIDATED_DIR / f'{timestamp}_validated.json'
        
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
        """Print validation summary"""
        self.log('\n' + '='*60)
        self.log('VALIDATION COMPLETE')
        self.log('='*60)
        self.log(f"""
📊 STATS:
   Total articles:    {self.stats['total']}
   Validated:         {self.stats['validated']}
   Approved:          {self.stats['approved']} ({self.stats['approved']/self.stats['total']*100 if self.stats['total'] > 0 else 0:.1f}%)
   Duplicates:        {self.stats['duplicates']} ({self.stats['duplicates']/self.stats['total']*100 if self.stats['total'] > 0 else 0:.1f}%)
   Failed:            {self.stats['failed']}
""")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Gemini Article Validator')
    parser.add_argument('input_file', nargs='?',
                       help='Input scraped articles JSON file')
    parser.add_argument('--latest', action='store_true',
                       help='Use latest scraped file')
    
    args = parser.parse_args()
    
    # Find input file
    if args.latest or not args.input_file:
        scraped_files = sorted(SCRAPED_DIR.glob('*.json'), reverse=True)
        if not scraped_files:
            print('No scraped files found in data/scraped/')
            return 1
        input_file = scraped_files[0]
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
    
    # Validate
    validator = GeminiValidator()
    validated = validator.validate_batch(articles)
    output_file = validator.save_results(validated, input_file)
    validator.print_summary()
    
    print(f'\n✅ Output: {output_file}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
