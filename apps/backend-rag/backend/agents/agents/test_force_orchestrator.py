"""
🎭 TEST FORCE ORCHESTRATOR

Central coordinator for all Test Force agents.
Provides unified CLI interface and coordinates agent workflows.

Features:
- Unified CLI for all agents
- Coordinated workflows
- Comprehensive reporting
- Real-time monitoring
- Performance optimization
"""

import asyncio
import json
import logging
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Import Test Force agents and services
try:
    from backend.agents.agents.test_guardian import TestGuardian
    from backend.agents.agents.test_creator import TestCreatorAgent
    from backend.agents.agents.test_maintainer import TestMaintainerAgent
    from backend.agents.agents.test_cleaner import TestCleanerAgent
    from backend.agents.services.llm_adapter import close_llm_adapter
    from backend.agents.services.test_metrics import get_metrics_collector
    TEST_FORCE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Test Force imports failed: {e}")
    TEST_FORCE_AVAILABLE = False

logger = logging.getLogger(__name__)


class TestForceOrchestrator:
    """
    Central orchestrator for the Test Force system.
    
    Coordinates all agents and provides unified interface.
    """
    
    def __init__(
        self,
        repo_path: Path = Path("apps/backend-rag"),
        llm_provider: str = "local",
        coverage_target: float = 99.0
    ):
        self.repo_path = repo_path
        self.llm_provider = llm_provider
        self.coverage_target = coverage_target
        
        # Initialize metrics collector
        if TEST_FORCE_AVAILABLE:
            self.metrics_collector = get_metrics_collector()
            self.orchestrator_metrics = self.metrics_collector.register_agent("Orchestrator")
        else:
            self.metrics_collector = None
            self.orchestrator_metrics = None
        
        # Initialize agents
        self.agents = {}
        self._initialize_agents()
        
        # Runtime state
        self.running = False
        self.shutdown_requested = False
        
        logger.info(f"🎭 TestForce Orchestrator initialized for {repo_path}")
    
    def _initialize_agents(self):
        """Initialize all Test Force agents."""
        if not TEST_FORCE_AVAILABLE:
            logger.error("❌ Test Force not available")
            return
        
        try:
            self.agents = {
                "guardian": TestGuardian(provider=self.llm_provider),
                "creator": TestCreatorAgent(
                    repo_path=self.repo_path,
                    llm_provider=self.llm_provider,
                    coverage_target=self.coverage_target
                ),
                "maintainer": TestMaintainerAgent(
                    repo_path=self.repo_path,
                    llm_provider=self.llm_provider
                ),
                "cleaner": TestCleanerAgent(
                    repo_path=self.repo_path,
                    llm_provider=self.llm_provider,
                    dry_run=True  # Default to safe mode
                )
            }
            logger.info("✅ All Test Force agents initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize agents: {e}")
            self.agents = {}
    
    async def run_full_scan(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Run comprehensive scan with all agents.
        
        Args:
            options: Scan options and configuration
            
        Returns:
            Combined results from all agents
        """
        start_time = time.time()
        options = options or {}
        
        logger.info("🚀 Starting full Test Force scan...")
        
        if not self.agents:
            return {"success": False, "error": "No agents available"}
        
        results = {
            "scan_type": "full",
            "start_time": datetime.now().isoformat(),
            "options": options,
            "agent_results": {},
            "summary": {}
        }
        
        try:
            # Phase 1: Coverage analysis (TestGuardian)
            logger.info("📊 Phase 1: Coverage analysis...")
            if "guardian" in self.agents and options.get("run_guardian", True):
                coverage_gaps = self.agents["guardian"].analyze_coverage()
                results["agent_results"]["guardian"] = {
                    "coverage_gaps": coverage_gaps,
                    "gaps_found": len(coverage_gaps)
                }
            
            # Phase 2: Create tests for new code (TestCreator)
            logger.info("🎯 Phase 2: Test creation...")
            if "creator" in self.agents and options.get("run_creator", True):
                creator_result = await self.agents["creator"].scan_and_generate(
                    max_files=options.get("max_files", 10)
                )
                results["agent_results"]["creator"] = creator_result
            
            # Phase 3: Maintain existing tests (TestMaintainer)
            logger.info("🔧 Phase 3: Test maintenance...")
            if "maintainer" in self.agents and options.get("run_maintainer", True):
                maintainer_result = await self.agents["maintainer"].scan_and_maintain(
                    check_git=options.get("check_git", True)
                )
                results["agent_results"]["maintainer"] = maintainer_result
            
            # Phase 4: Clean up problematic tests (TestCleaner)
            logger.info("🧹 Phase 4: Test cleanup...")
            if "cleaner" in self.agents and options.get("run_cleaner", True):
                cleaner_result = await self.agents["cleaner"].scan_and_clean(
                    aggressive=options.get("aggressive_cleanup", False)
                )
                results["agent_results"]["cleaner"] = cleaner_result
            
            # Generate summary
            duration = time.time() - start_time
            results["duration"] = duration
            results["end_time"] = datetime.now().isoformat()
            results["summary"] = self._generate_summary(results)
            
            # Record metrics
            if self.orchestrator_metrics:
                self.orchestrator_metrics.record_operation(duration, True)
            
            logger.info(f"✅ Full scan completed in {duration:.2f}s")
            self._log_summary(results["summary"])
            
            return results
            
        except Exception as e:
            error_msg = f"Full scan failed: {e}"
            logger.error(f"❌ {error_msg}")
            if self.orchestrator_metrics:
                self.orchestrator_metrics.record_operation(
                    time.time() - start_time,
                    success=False,
                    error=error_msg
                )
            return {"success": False, "error": error_msg}
    
    async def run_coverage_scan(self) -> dict[str, Any]:
        """Run coverage analysis only."""
        if "guardian" not in self.agents:
            return {"success": False, "error": "TestGuardian not available"}
        
        start_time = time.time()
        gaps = self.agents["guardian"].analyze_coverage()
        duration = time.time() - start_time
        
        return {
            "success": True,
            "coverage_gaps": gaps,
            "gaps_found": len(gaps),
            "duration": duration
        }
    
    async def run_test_creation(self, max_files: int = 10) -> dict[str, Any]:
        """Run test creation only."""
        if "creator" not in self.agents:
            return {"success": False, "error": "TestCreatorAgent not available"}
        
        return await self.agents["creator"].scan_and_generate(max_files=max_files)
    
    async def run_test_maintenance(self, check_git: bool = True) -> dict[str, Any]:
        """Run test maintenance only."""
        if "maintainer" not in self.agents:
            return {"success": False, "error": "TestMaintainerAgent not available"}
        
        return await self.agents["maintainer"].scan_and_maintain(check_git=check_git)
    
    async def run_test_cleanup(self, aggressive: bool = False, dry_run: bool = True) -> dict[str, Any]:
        """Run test cleanup only."""
        if "cleaner" not in self.agents:
            return {"success": False, "error": "TestCleanerAgent not available"}
        
        # Update dry run setting
        self.agents["cleaner"].dry_run = dry_run
        return await self.agents["cleaner"].scan_and_clean(aggressive=aggressive)
    
    async def watch_mode(self, interval: int = 300) -> None:
        """
        Run in continuous watch mode.
        
        Args:
            interval: Check interval in seconds (default: 5 minutes)
        """
        logger.info(f"👁️ Starting watch mode with {interval}s interval...")
        self.running = True
        
        # Setup signal handlers
        def signal_handler(_signum, _frame):
            logger.info("🛑 Shutdown signal received")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while self.running and not self.shutdown_requested:
                logger.info("🔄 Running scheduled scan...")
                
                # Run lightweight scan
                result = await self.run_full_scan({
                    "run_guardian": True,
                    "run_creator": True,
                    "run_maintainer": True,
                    "run_cleaner": False,  # Skip cleanup in watch mode
                    "max_files": 5,  # Limit in watch mode
                    "check_git": True
                })
                
                if result.get("success"):
                    logger.info("✅ Scheduled scan completed")
                else:
                    logger.error(f"❌ Scheduled scan failed: {result.get('error')}")
                
                # Wait for next interval or shutdown
                for _ in range(interval):
                    if self.shutdown_requested:
                        break
                    await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"❌ Watch mode error: {e}")
        finally:
            self.running = False
            logger.info("🛑 Watch mode stopped")
    
    def _generate_summary(self, results: dict[str, Any]) -> dict[str, Any]:
        """Generate comprehensive summary."""
        summary = {
            "total_duration": results.get("duration", 0),
            "agents_run": len(results.get("agent_results", {})),
            "overall_success": True
        }
        
        # Summarize agent results
        agent_summary = {}
        for agent_name, agent_result in results.get("agent_results", {}).items():
            agent_summary[agent_name] = {
                "success": agent_result.get("success", True),
                "duration": agent_result.get("duration", 0),
                "key_metrics": self._extract_key_metrics(agent_name, agent_result)
            }
            
            if not agent_result.get("success", True):
                summary["overall_success"] = False
        
        summary["agents"] = agent_summary
        
        # Overall metrics
        if self.metrics_collector:
            summary["metrics"] = self.metrics_collector.get_summary()
        
        return summary
    
    def _extract_key_metrics(self, agent_name: str, agent_result: dict[str, Any]) -> dict[str, Any]:
        """Extract key metrics for an agent."""
        metrics = {}
        
        if agent_name == "guardian":
            metrics["coverage_gaps"] = agent_result.get("gaps_found", 0)
        elif agent_name == "creator":
            stats = agent_result.get("stats", {})
            metrics["tests_generated"] = stats.get("tests_generated", 0)
            metrics["tests_passed"] = stats.get("tests_passed", 0)
        elif agent_name == "maintainer":
            stats = agent_result.get("stats", {})
            metrics["tests_updated"] = stats.get("tests_updated", 0)
            metrics["breaking_changes"] = stats.get("breaking_changes", 0)
        elif agent_name == "cleaner":
            metrics["orphans_found"] = agent_result.get("orphans_found", 0)
            metrics["duplicates_found"] = agent_result.get("duplicates_found", 0)
            metrics["useless_tests"] = agent_result.get("useless_tests_found", 0)
        
        return metrics
    
    def _log_summary(self, summary: dict[str, Any]):
        """Log summary information."""
        logger.info("📊 Test Force Summary:")
        logger.info(f"   Duration: {summary.get('total_duration', 0):.2f}s")
        logger.info(f"   Agents run: {summary.get('agents_run', 0)}")
        logger.info(f"   Overall success: {summary.get('overall_success', False)}")
        
        for agent_name, agent_info in summary.get("agents", {}).items():
            status = "✅" if agent_info["success"] else "❌"
            logger.info(f"   {status} {agent_name}: {agent_info['duration']:.2f}s")
            
            for metric, value in agent_info.get("key_metrics", {}).items():
                logger.info(f"      - {metric}: {value}")
    
    def generate_report(self, results: dict[str, Any], format: str = "markdown") -> str:
        """Generate comprehensive report."""
        if self.metrics_collector:
            return self.metrics_collector.generate_report(format)
        else:
            return self._generate_simple_report(results, format)
    
    def _generate_simple_report(self, results: dict[str, Any], format: str) -> str:
        """Generate simple report."""
        if format == "json":
            return json.dumps(results, indent=2, default=str)
        elif format == "markdown":
            md = f"""# 🎭 Test Force Report

**Generated:** {datetime.now().isoformat()}
**Duration:** {results.get('duration', 0):.2f}s
**Success:** {results.get('summary', {}).get('overall_success', False)}

## Agent Results
"""
            for agent_name, agent_result in results.get("agent_results", {}).items():
                md += f"### {agent_name.title()}\n"
                md += f"- Success: {agent_result.get('success', True)}\n"
                md += f"- Duration: {agent_result.get('duration', 0):.2f}s\n"
                md += "\n"
            
            return md
        else:
            return str(results)
    
    def get_agent_stats(self) -> dict[str, Any]:
        """Get statistics from all agents."""
        stats = {}
        
        for agent_name, agent in self.agents.items():
            if hasattr(agent, 'get_stats'):
                stats[agent_name] = agent.get_stats()
        
        return stats
    
    async def cleanup(self):
        """Cleanup all agents and resources."""
        logger.info("🧹 Cleaning up Test Force Orchestrator...")
        
        # Cleanup individual agents
        for agent_name, agent in self.agents.items():
            try:
                if hasattr(agent, 'cleanup'):
                    await agent.cleanup()
                logger.info(f"✅ Cleaned up {agent_name}")
            except Exception as e:
                logger.error(f"❌ Error cleaning up {agent_name}: {e}")
        
        # Cleanup LLM adapter
        try:
            await close_llm_adapter()
            logger.info("✅ Cleaned up LLM adapter")
        except Exception as e:
            logger.error(f"❌ Error cleaning up LLM adapter: {e}")
        
        logger.info("✅ Test Force Orchestrator cleanup complete")


# CLI interface
async def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Force Orchestrator")
    parser.add_argument("--repo", default="apps/backend-rag", help="Repository path")
    parser.add_argument("--provider", default="local", choices=["local", "gemini", "mock"])
    parser.add_argument("--coverage-target", type=float, default=99.0, help="Coverage target percentage")
    
    # Mode selection
    parser.add_argument("--mode", choices=["scan", "coverage", "create", "maintain", "clean", "watch"], 
                       default="scan", help="Operation mode")
    
    # Scan options
    parser.add_argument("--max-files", type=int, default=10, help="Max files to process")
    parser.add_argument("--no-guardian", action="store_true", help="Skip coverage analysis")
    parser.add_argument("--no-creator", action="store_true", help="Skip test creation")
    parser.add_argument("--no-maintainer", action="store_true", help="Skip test maintenance")
    parser.add_argument("--no-cleaner", action="store_true", help="Skip test cleanup")
    parser.add_argument("--no-git", action="store_true", help="Don't check git for changes")
    parser.add_argument("--aggressive-cleanup", action="store_true", help="Aggressive cleanup mode")
    parser.add_argument("--no-dry-run", action="store_true", help="Perform actual cleanup")
    
    # Watch mode
    parser.add_argument("--interval", type=int, default=300, help="Watch mode interval in seconds")
    
    # Output options
    parser.add_argument("--report", choices=["markdown", "json", "html"], default="markdown", help="Report format")
    parser.add_argument("--output", help="Output file for report")
    parser.add_argument("--save-metrics", action="store_true", help="Save metrics snapshot")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] 🎭 TestForce: %(message)s"
    )
    
    # Create orchestrator
    orchestrator = TestForceOrchestrator(
        repo_path=Path(args.repo),
        llm_provider=args.provider,
        coverage_target=args.coverage_target
    )
    
    try:
        # Run based on mode
        if args.mode == "scan":
            options = {
                "run_guardian": not args.no_guardian,
                "run_creator": not args.no_creator,
                "run_maintainer": not args.no_maintainer,
                "run_cleaner": not args.no_cleaner,
                "max_files": args.max_files,
                "check_git": not args.no_git,
                "aggressive_cleanup": args.aggressive_cleanup
            }
            result = await orchestrator.run_full_scan(options)
            
        elif args.mode == "coverage":
            result = await orchestrator.run_coverage_scan()
            
        elif args.mode == "create":
            result = await orchestrator.run_test_creation(max_files=args.max_files)
            
        elif args.mode == "maintain":
            result = await orchestrator.run_test_maintenance(check_git=not args.no_git)
            
        elif args.mode == "clean":
            result = await orchestrator.run_test_cleanup(
                aggressive=args.aggressive_cleanup,
                dry_run=not args.no_dry_run
            )
            
        elif args.mode == "watch":
            await orchestrator.watch_mode(interval=args.interval)
            return
        
        # Generate and output report
        report = orchestrator.generate_report(result, args.report)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"📄 Report saved to: {args.output}")
        else:
            print("\n" + report)
        
        # Save metrics if requested
        if args.save_metrics and orchestrator.metrics_collector:
            snapshot_file = orchestrator.metrics_collector.save_snapshot()
            print(f"📊 Metrics saved to: {snapshot_file}")
        
        # Print summary
        if args.mode == "scan":
            summary = result.get("summary", {})
            print(f"\n🎭 Test Force Summary:")
            print(f"Duration: {summary.get('total_duration', 0):.2f}s")
            print(f"Agents run: {summary.get('agents_run', 0)}")
            print(f"Success: {summary.get('overall_success', False)}")
            
    finally:
        await orchestrator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
