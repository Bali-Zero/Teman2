#!/usr/bin/env python3
"""
Test Watchdog - Monitors code changes and automatically manages tests

Runs continuously, watching for file changes and triggering test management.
Can run as a background service or be triggered by git hooks.
"""

import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

try:
    from ai_test_agent import AITestAgent
except ImportError:
    print("⚠️  ai_test_agent not found, using basic mode")
    AITestAgent = None


class CodeChangeHandler(FileSystemEventHandler):
    """Handle file system events for code changes"""

    def __init__(self, agent: AITestAgent, debounce_seconds: int = 5):
        self.agent = agent
        self.debounce_seconds = debounce_seconds
        self.last_event_time = {}
        self.pending_files = set()

    def on_modified(self, event):
        """Handle file modification"""
        if event.is_directory:
            return
        
        if not event.src_path.endswith('.py'):
            return
        
        # Debounce: wait for file to stabilize
        file_path = Path(event.src_path)
        self.pending_files.add(file_path)
        
        # Schedule check after debounce period
        import threading
        threading.Timer(
            self.debounce_seconds,
            self._process_pending,
            args=(file_path,)
        ).start()

    def _process_pending(self, file_path: Path):
        """Process pending file after debounce"""
        if file_path not in self.pending_files:
            return
        
        self.pending_files.discard(file_path)
        
        # Check if file is in backend directory
        backend_dir = self.agent.backend_dir
        try:
            file_path.relative_to(backend_dir)
        except ValueError:
            return  # Not in backend directory
        
        print(f"\n🔔 File changed: {file_path}")
        print("   Triggering test analysis...")
        
        # Run agent for this specific file
        # (would need to modify agent to accept specific files)
        # For now, run full analysis
        self.agent.run(dry_run=False)


class TestWatchdog:
    """Watchdog service that monitors code changes"""

    def __init__(self, backend_dir: Path, test_dir: Path):
        self.backend_dir = backend_dir
        self.test_dir = test_dir
        self.agent = AITestAgent(backend_dir, test_dir) if AITestAgent else None
        self.observer = None

    def start(self):
        """Start watching for changes"""
        if not self.agent:
            print("❌ AI Test Agent not available")
            return
        
        print("👀 Starting Test Watchdog...")
        print(f"   Watching: {self.backend_dir}")
        print("   Press Ctrl+C to stop")
        
        event_handler = CodeChangeHandler(self.agent)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.backend_dir), recursive=True)
        self.observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping watchdog...")
            self.stop()

    def stop(self):
        """Stop watching"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        print("✅ Watchdog stopped")


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Watchdog - Monitor code changes")
    parser.add_argument("--backend-dir", default="apps/backend-rag/backend", help="Backend directory")
    parser.add_argument("--test-dir", default="apps/backend-rag/tests", help="Test directory")
    
    args = parser.parse_args()
    
    backend_dir = Path(args.backend_dir)
    test_dir = Path(args.test_dir)
    
    if not backend_dir.exists():
        print(f"❌ Backend directory not found: {backend_dir}")
        return
    
    watchdog = TestWatchdog(backend_dir, test_dir)
    watchdog.start()


if __name__ == "__main__":
    main()

