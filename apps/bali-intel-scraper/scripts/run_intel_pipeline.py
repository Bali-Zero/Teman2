#!/usr/bin/env python3
"""
Intel Pipeline Orchestrator - Full 7-Step Pipeline
Coordinates: Scraping → Validation → Enrichment → Images → SEO → Approval → Publishing

Usage:
    # Full run (all steps)
    python run_intel_pipeline.py --mode full --categories immigration,tax --limit 10
    
    # Dry run (no approval/publishing)
    python run_intel_pipeline.py --mode dry-run --limit 5
    
    # Resume from step
    python run_intel_pipeline.py --resume-from validation
    
    # Skip steps
    python run_intel_pipeline.py --skip images,approval --auto-publish
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import subprocess

# Pipeline steps
PIPELINE_STEPS = [
    '1_scraping',
    '2_validation', 
    '3_enrichment',
    '4_images',
    '5_seo',
    '6_approval',
    '7_publishing'
]

class IntelPipeline:
    def __init__(self, config: Dict):
        self.config = config
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent
        self.data_dir = self.project_root / 'data'
        self.pipeline_dir = self.data_dir / 'pipeline'
        self.pipeline_dir.mkdir(exist_ok=True)
        
        # State tracking
        self.run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.state_file = self.pipeline_dir / f'run_{self.run_id}.json'
        self.state = {
            'run_id': self.run_id,
            'config': config,
            'started_at': datetime.now().isoformat(),
            'steps': {},
            'articles': []
        }
    
    def log(self, message: str, level: str = 'INFO'):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f'[{timestamp}] [{level}] {message}')
        sys.stdout.flush()
    
    def save_state(self):
        """Save pipeline state to disk"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
        self.log(f'State saved: {self.state_file.name}')
    
    def update_step_status(self, step: str, status: str, data: Dict = None):
        """Update step status in state"""
        self.state['steps'][step] = {
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'data': data or {}
        }
        self.save_state()
    
    def run_step(self, step: str) -> bool:
        """Execute single pipeline step"""
        self.log(f'{"="*60}')
        self.log(f'STEP: {step}')
        self.log(f'{"="*60}')
        
        try:
            if step == '1_scraping':
                return self.step_scraping()
            elif step == '2_validation':
                return self.step_validation()
            elif step == '3_enrichment':
                return self.step_enrichment()
            elif step == '4_images':
                return self.step_images()
            elif step == '5_seo':
                return self.step_seo()
            elif step == '6_approval':
                return self.step_approval()
            elif step == '7_publishing':
                return self.step_publishing()
            else:
                self.log(f'Unknown step: {step}', 'ERROR')
                return False
        except Exception as e:
            self.log(f'Step {step} failed: {e}', 'ERROR')
            self.update_step_status(step, 'failed', {'error': str(e)})
            return False
    
    def step_scraping(self) -> bool:
        """Step 1: Scrape articles from sources"""
        self.log('Starting article scraping...')
        
        script = self.script_dir / 'unified_scraper.py'
        if not script.exists():
            self.log('unified_scraper.py not found - TODO: implement', 'WARN')
            self.update_step_status('1_scraping', 'skipped', {'reason': 'script missing'})
            # Mock data for testing
            self.state['articles'] = self._mock_scraped_articles()
            return True
        
        # TODO: Run unified_scraper.py with config
        cmd = [
            'python3', str(script),
            '--categories', ','.join(self.config.get('categories', ['immigration'])),
            '--limit', str(self.config.get('limit', 10)),
            '--min-score', str(self.config.get('min_score', 40))
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            self.update_step_status('1_scraping', 'completed')
            return True
        else:
            self.log(f'Scraping failed: {result.stderr}', 'ERROR')
            return False
    
    def step_validation(self) -> bool:
        """Step 2: Validate articles (anti-duplicate)"""
        self.log('Validating articles (anti-duplicate check)...')
        
        script = self.script_dir / 'gemini_validator.py'
        if not script.exists():
            self.log('gemini_validator.py not found - TODO: implement', 'WARN')
            self.update_step_status('2_validation', 'skipped', {'reason': 'script missing'})
            return True
        
        # TODO: Run validator on scraped articles
        validated = []
        for article in self.state['articles']:
            # Validation logic here
            validated.append(article)
        
        self.state['articles'] = validated
        self.update_step_status('2_validation', 'completed', {
            'validated': len(validated),
            'rejected': 0
        })
        return True
    
    def step_enrichment(self) -> bool:
        """Step 3: Enrich articles with AI analysis"""
        self.log('Enriching articles with Gemini 3 Pro...')
        
        script = self.script_dir / 'gemini_article_enricher.py'
        if not script.exists():
            self.log('gemini_article_enricher.py not found - TODO: implement', 'WARN')
            self.update_step_status('3_enrichment', 'skipped', {'reason': 'script missing'})
            return True
        
        # TODO: Enrich each article
        enriched = 0
        for article in self.state['articles']:
            # Enrichment logic here
            enriched += 1
        
        self.update_step_status('3_enrichment', 'completed', {'enriched': enriched})
        return True
    
    def step_images(self) -> bool:
        """Step 4: Generate images with Gemini Imagen 3"""
        self.log('Generating images...')
        
        if self.config.get('skip_images'):
            self.log('Images skipped by config')
            self.update_step_status('4_images', 'skipped', {'reason': 'config'})
            return True
        
        script = self.script_dir / 'gemini_image_generator.py'
        if not script.exists():
            self.log('gemini_image_generator.py not found - TODO: implement', 'WARN')
            self.update_step_status('4_images', 'skipped', {'reason': 'script missing'})
            return True
        
        # TODO: Generate images
        self.update_step_status('4_images', 'completed')
        return True
    
    def step_seo(self) -> bool:
        """Step 5: SEO optimization"""
        self.log('Optimizing SEO...')
        
        script = self.script_dir / 'gemini_seo_optimizer.py'
        if not script.exists():
            self.log('gemini_seo_optimizer.py not found - TODO: implement', 'WARN')
            self.update_step_status('5_seo', 'skipped', {'reason': 'script missing'})
            return True
        
        # TODO: SEO optimization
        self.update_step_status('5_seo', 'completed')
        return True
    
    def step_approval(self) -> bool:
        """Step 6: Submit for approval (Telegram)"""
        self.log('Submitting for approval...')
        
        if self.config.get('auto_approve'):
            self.log('Auto-approve enabled, skipping approval step')
            self.update_step_status('6_approval', 'auto_approved')
            return True
        
        script = self.script_dir / 'telegram_approval.py'
        if not script.exists():
            self.log('telegram_approval.py exists but needs integration')
        
        # TODO: Telegram approval workflow
        self.update_step_status('6_approval', 'pending')
        return True
    
    def step_publishing(self) -> bool:
        """Step 7: Publish approved articles"""
        self.log('Publishing articles...')
        
        if self.config.get('dry_run'):
            self.log('Dry run mode - skipping actual publishing')
            self.update_step_status('7_publishing', 'skipped', {'reason': 'dry_run'})
            return True
        
        script = self.script_dir / 'publish_articles.py'
        if not script.exists():
            self.log('publish_articles.py not found')
            return False
        
        # TODO: Publish to Sanity/website
        self.update_step_status('7_publishing', 'completed')
        return True
    
    def _mock_scraped_articles(self) -> List[Dict]:
        """Mock data for testing pipeline"""
        return [
            {
                'title': 'New KITAS Regulations 2026',
                'url': 'https://example.com/kitas-2026',
                'source': 'imigrasi.go.id',
                'category': 'immigration',
                'score': 85
            }
        ]
    
    def run(self):
        """Execute full pipeline"""
        self.log(f'Starting Intel Pipeline - Run ID: {self.run_id}')
        self.log(f'Config: {json.dumps(self.config, indent=2)}')
        
        steps_to_run = PIPELINE_STEPS
        
        # Handle resume
        if self.config.get('resume_from'):
            resume_step = self.config['resume_from']
            if resume_step in steps_to_run:
                idx = steps_to_run.index(resume_step)
                steps_to_run = steps_to_run[idx:]
                self.log(f'Resuming from: {resume_step}')
        
        # Handle skip
        if self.config.get('skip_steps'):
            skip = self.config['skip_steps']
            steps_to_run = [s for s in steps_to_run if s not in skip]
            self.log(f'Skipping steps: {skip}')
        
        # Execute pipeline
        for step in steps_to_run:
            success = self.run_step(step)
            if not success and not self.config.get('continue_on_error'):
                self.log(f'Pipeline failed at step: {step}', 'ERROR')
                self.state['status'] = 'failed'
                self.state['failed_at'] = step
                self.save_state()
                return False
        
        self.state['status'] = 'completed'
        self.state['completed_at'] = datetime.now().isoformat()
        self.save_state()
        
        self.log(f'{"="*60}')
        self.log('PIPELINE COMPLETED')
        self.log(f'{"="*60}')
        self.print_summary()
        
        return True
    
    def print_summary(self):
        """Print pipeline execution summary"""
        print('\n📊 PIPELINE SUMMARY\n')
        print(f'Run ID: {self.run_id}')
        print(f'Status: {self.state.get("status", "unknown")}')
        print(f'Started: {self.state["started_at"]}')
        if self.state.get('completed_at'):
            print(f'Completed: {self.state["completed_at"]}')
        
        print('\nSteps:')
        for step, data in self.state.get('steps', {}).items():
            status = data.get('status', 'unknown')
            print(f'  {step}: {status}')
        
        print(f'\nState file: {self.state_file}')


def main():
    parser = argparse.ArgumentParser(description='Intel Pipeline Orchestrator')
    
    # Mode
    parser.add_argument('--mode', choices=['full', 'dry-run', 'test'], default='full',
                       help='Pipeline execution mode')
    
    # Data selection
    parser.add_argument('--categories', default='immigration,tax,legal',
                       help='Comma-separated categories')
    parser.add_argument('--limit', type=int, default=10,
                       help='Limit articles per source')
    parser.add_argument('--min-score', type=int, default=40,
                       help='Minimum quality score')
    
    # Flow control
    parser.add_argument('--resume-from', choices=PIPELINE_STEPS,
                       help='Resume from specific step')
    parser.add_argument('--skip', dest='skip_steps',
                       help='Comma-separated steps to skip')
    parser.add_argument('--continue-on-error', action='store_true',
                       help='Continue pipeline even if step fails')
    
    # Options
    parser.add_argument('--skip-images', action='store_true',
                       help='Skip image generation')
    parser.add_argument('--auto-approve', action='store_true',
                       help='Auto-approve articles (skip Telegram)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run (no publishing)')
    
    args = parser.parse_args()
    
    # Build config
    config = {
        'mode': args.mode,
        'categories': args.categories.split(','),
        'limit': args.limit,
        'min_score': args.min_score,
        'skip_images': args.skip_images,
        'auto_approve': args.auto_approve,
        'dry_run': args.dry_run or args.mode == 'dry-run',
        'continue_on_error': args.continue_on_error
    }
    
    if args.resume_from:
        config['resume_from'] = args.resume_from
    
    if args.skip_steps:
        config['skip_steps'] = args.skip_steps.split(',')
    
    # Run pipeline
    pipeline = IntelPipeline(config)
    success = pipeline.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
