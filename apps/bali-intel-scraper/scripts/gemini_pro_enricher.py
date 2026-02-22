#!/usr/bin/env python3
"""
Gemini 3 Pro Enricher - Production Ready
Uses Gemini CLI with AI Ultra OAuth (antonellosiano@gmail.com)
Successfully tested with ~30s per article, no subprocess blocking issues
"""

import subprocess
import json
import time
from pathlib import Path
from datetime import datetime

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SOURCES_FILE = PROJECT_ROOT / "config" / "unified_sources.json"
LOG_FILE = PROJECT_ROOT / "logs" / f"enrichment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Config
TIMEOUT = 120  # 2 minutes per article (test avg: 30s)
MAX_RETRIES = 2
BATCH_SIZE = 10  # Process in batches for progress tracking

class GeminiEnricher:
    def __init__(self):
        self.log_file = LOG_FILE
        self.log_file.parent.mkdir(exist_ok=True)
        self.stats = {
            'total': 0,
            'enriched': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': datetime.now()
        }
    
    def clean_gemini_output(self, raw_output):
        """Clean Gemini CLI debug output to extract real summary"""
        # Filter out debug lines
        debug_patterns = [
            'Prompts updated for server:',
            'Tools updated for server:',
            'I will',
            'I am going to',
            'Let me',
            'I\'ll',
        ]
        
        lines = raw_output.strip().split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip empty lines and debug patterns
            if not line.strip():
                continue
            if any(line.strip().startswith(pattern) for pattern in debug_patterns):
                continue
            cleaned_lines.append(line)
        
        # Return the last substantial paragraph (usually the real summary)
        if cleaned_lines:
            # Join all cleaned lines, then take the last paragraph
            full_text = '\n'.join(cleaned_lines)
            paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]
            if paragraphs:
                return paragraphs[-1]  # Last paragraph is usually the summary
        
        return raw_output  # Fallback to original if cleanup fails
    
    def log(self, message, level="INFO"):
        """Log to file and console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"
        print(log_line)
        with open(self.log_file, 'a') as f:
            f.write(log_line + '\n')
    
    def enrich_source(self, url, title, retries=0):
        """Enrich single source with Gemini 3 Pro"""
        
        prompt = f"""Analyze this web source for Bali business intelligence:

URL: {url}
Title: {title}

Provide a concise 2-3 sentence summary of:
1. What information this source contains
2. Why it's valuable for Bali business/visa/immigration consulting

Be specific and factual."""

        try:
            start = time.time()
            
            result = subprocess.run(
                ['gemini', prompt],
                capture_output=True,
                text=True,
                timeout=TIMEOUT
            )
            
            elapsed = time.time() - start
            
            if result.returncode == 0:
                raw_summary = result.stdout.strip()
                summary = self.clean_gemini_output(raw_summary)
                self.log(f"✅ Enriched in {elapsed:.1f}s: {url[:60]}...")
                self.log(f"   Summary length: {len(summary)} chars (cleaned from {len(raw_summary)})")
                return summary
            else:
                self.log(f"❌ Gemini failed (exit {result.returncode}): {result.stderr[:100]}", "ERROR")
                if retries < MAX_RETRIES:
                    self.log(f"🔄 Retry {retries+1}/{MAX_RETRIES}...", "WARN")
                    time.sleep(2)
                    return self.enrich_source(url, title, retries + 1)
                return None
                
        except subprocess.TimeoutExpired:
            self.log(f"⏱️ Timeout after {TIMEOUT}s: {url[:60]}...", "WARN")
            if retries < MAX_RETRIES:
                self.log(f"🔄 Retry {retries+1}/{MAX_RETRIES}...", "WARN")
                return self.enrich_source(url, title, retries + 1)
            return None
        except Exception as e:
            self.log(f"💥 Error: {e}", "ERROR")
            return None
    
    def process_sources(self, limit=None, test_mode=False):
        """Process sources from unified_sources.json"""
        
        self.log("=" * 60)
        self.log("GEMINI 3 PRO ENRICHMENT STARTED")
        self.log("=" * 60)
        
        # Load sources
        with open(SOURCES_FILE, 'r') as f:
            data = json.load(f)
        
        # Extract all sources from categories
        all_sources = []
        categories = data.get('categories', {})
        for category_name, category_data in categories.items():
            for source in category_data.get('sources', []):
                source['category'] = category_name  # Track which category
                all_sources.append(source)
        
        # Filter sources needing enrichment
        # Assume all sources with URL are valid unless marked otherwise
        to_enrich = [
            s for s in all_sources 
            if s.get('url') and not s.get('ai_summary')
        ]
        
        if test_mode:
            to_enrich = to_enrich[:limit or 10]
            self.log(f"🧪 TEST MODE: Processing {len(to_enrich)} sources")
        else:
            if limit:
                to_enrich = to_enrich[:limit]
            self.log(f"📊 Found {len(to_enrich)} sources to enrich (out of {len(all_sources)} total)")
        
        self.stats['total'] = len(to_enrich)
        
        # Process in batches
        for i, source in enumerate(to_enrich, 1):
            self.log(f"\n[{i}/{len(to_enrich)}] Processing: {source.get('name', 'Unknown')}")
            
            summary = self.enrich_source(
                source.get('url', ''),
                source.get('name', '')
            )
            
            if summary:
                source['ai_summary'] = summary
                source['enriched_at'] = datetime.now().isoformat()
                source['enriched_by'] = 'gemini-3-pro'
                self.stats['enriched'] += 1
            else:
                self.stats['failed'] += 1
            
            # Save progress every 10 sources
            if i % 10 == 0 or i == len(to_enrich):
                self.save_sources(data, test_mode)
                self.print_stats()
        
        # Final save
        self.save_sources(data, test_mode)
        self.print_final_report()
    
    def save_sources(self, data, test_mode=False):
        """Save updated sources to JSON"""
        data['last_updated'] = datetime.now().isoformat()
        data['last_enriched'] = datetime.now().isoformat()
        data['enriched_by'] = 'gemini-3-pro'
        
        if test_mode:
            test_file = SOURCES_FILE.parent / f"unified_sources_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(test_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.log(f"💾 Test results saved: {test_file.name}")
        else:
            # Backup original first
            backup_file = SOURCES_FILE.parent / f"unified_sources_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(SOURCES_FILE, 'r') as f:
                backup_data = json.load(f)
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            with open(SOURCES_FILE, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.log(f"💾 Backup saved: {backup_file.name}")
            self.log("💾 Progress saved to unified_sources.json")
    
    def print_stats(self):
        """Print current progress stats"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        rate = self.stats['enriched'] / (elapsed / 60) if elapsed > 0 else 0
        
        self.log(f"""
📊 PROGRESS:
   Total:    {self.stats['total']}
   Enriched: {self.stats['enriched']} ✅
   Failed:   {self.stats['failed']} ❌
   Rate:     {rate:.1f} sources/min
   Time:     {elapsed/60:.1f} minutes
""")
    
    def print_final_report(self):
        """Print final summary report"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        
        self.log("=" * 60)
        self.log("ENRICHMENT COMPLETE")
        self.log("=" * 60)
        self.log(f"""
📊 FINAL STATS:
   Total sources:     {self.stats['total']}
   Successfully enriched: {self.stats['enriched']} ({self.stats['enriched']/self.stats['total']*100 if self.stats['total'] > 0 else 0:.1f}%)
   Failed:            {self.stats['failed']} ({self.stats['failed']/self.stats['total']*100 if self.stats['total'] > 0 else 0:.1f}%)
   
⏱️  PERFORMANCE:
   Total time:        {elapsed/60:.1f} minutes
   Avg per source:    {elapsed/self.stats['enriched'] if self.stats['enriched'] > 0 else 0:.1f}s
   Rate:              {self.stats['enriched']/(elapsed/60) if elapsed > 0 else 0:.1f} sources/min
   
📝 Log file:          {self.log_file}
""")


if __name__ == "__main__":
    import sys
    
    enricher = GeminiEnricher()
    
    # Parse args
    test_mode = '--test' in sys.argv
    
    limit = None
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])
    
    # Run
    enricher.process_sources(limit=limit, test_mode=test_mode)
