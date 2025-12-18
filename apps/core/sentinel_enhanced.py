#!/usr/bin/env python3
"""
Enhanced Sentinel: Full-Stack Guardian with Deep Analysis
Integrates SonarQube, CodeQL, and Semgrep into the Sentinel ecosystem
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path


class EnhancedSentinel:
    def __init__(self):
        self.root = Path(__file__).parent.parent.parent
        self.results_dir = self.root / "sentinel-results"
        self.results_dir.mkdir(exist_ok=True)

        # Colors for output
        self.RED = "\033[0;31m"
        self.GREEN = "\033[0;32m"
        self.YELLOW = "\033[1;33m"
        self.BLUE = "\033[0;34m"
        self.PURPLE = "\033[0;35m"
        self.CYAN = "\033[0;36m"
        self.NC = "\033[0m"  # No Color

        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status = {
            "backend": "UNKNOWN",
            "frontend": "UNKNOWN",
            "contract": "UNKNOWN",
            "deep_analysis": "UNKNOWN",
            "critical_issues": 0,
            "warnings": 0,
            "recommendations": [],
        }

    def banner(self):
        """Print enhanced sentinel banner"""
        print(
            f"""
{self.CYAN}╔════════════════════════════════════════════╗
║     ENHANCED SENTINEL: ULTIMATE GUARDIAN     ║
║  Now with Deep Analysis & Security Scanning   ║
╚════════════════════════════════════════════╝{self.NC}
{self.CYAN}Time:{self.NC} {self.timestamp}
{self.CYAN}Root:{self.NC} {self.root}
{self.CYAN}Mode:{self.NC} Full Stack + Deep Security Analysis
        """
        )

    def run_original_sentinel(self):
        """Run the original sentinel checks"""
        print(f"{self.BLUE}[PHASE 1] Original Sentinel Checks{self.NC}")
        print("-" * 50)

        try:
            # Run sentinel.py directly to avoid infinite recursion
            sentinel_script = self.root / "apps" / "core" / "sentinel.py"
            os.chdir(self.root)
            result = subprocess.run(
                ["python3", str(sentinel_script)] + sys.argv[1:],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                self.status["backend"] = "HEALTHY"
                print(f"{self.GREEN}✅ Backend Sentinel checks passed{self.NC}")
            else:
                self.status["backend"] = "ISSUES"
                print(f"{self.YELLOW}⚠️ Backend Sentinel found issues{self.NC}")

        except subprocess.TimeoutExpired:
            self.status["backend"] = "TIMEOUT"
            print(f"{self.RED}❌ Backend Sentinel timed out{self.NC}")
        except Exception as e:
            self.status["backend"] = "ERROR"
            print(f"{self.RED}❌ Backend Sentinel error: {e}{self.NC}")

    def run_deep_analysis(self):
        """Run deep security analysis"""
        print(f"\n{self.PURPLE}[PHASE 2] Deep Security Analysis{self.NC}")
        print("-" * 50)

        try:
            # Run deep analysis script
            script_path = self.root / "scripts" / "deep-analysis.sh"
            if script_path.exists():
                result = subprocess.run(
                    [str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minutes
                )

                # Parse results
                self.parse_deep_analysis_results()

                if result.returncode == 0:
                    self.status["deep_analysis"] = "COMPLETED"
                    print(f"{self.GREEN}✅ Deep analysis completed{self.NC}")
                else:
                    self.status["deep_analysis"] = "PARTIAL"
                    print(
                        f"{self.YELLOW}⚠️ Deep analysis completed with warnings{self.NC}"
                    )

            else:
                print(f"{self.RED}❌ Deep analysis script not found{self.NC}")
                self.status["deep_analysis"] = "NOT_FOUND"

        except subprocess.TimeoutExpired:
            self.status["deep_analysis"] = "TIMEOUT"
            print(f"{self.RED}❌ Deep analysis timed out{self.NC}")
        except Exception as e:
            self.status["deep_analysis"] = "ERROR"
            print(f"{self.RED}❌ Deep analysis error: {e}{self.NC}")

    def parse_deep_analysis_results(self):
        """Parse results from deep analysis"""
        results_dir = self.root / "deep-analysis-results"

        # Parse Semgrep results
        semgrep_file = results_dir / "semgrep-auto.json"
        if semgrep_file.exists():
            try:
                with open(semgrep_file) as f:
                    semgrep_results = json.load(f)
                    findings = semgrep_results.get("results", [])

                    # Count by severity
                    for finding in findings:
                        metadata = finding.get("metadata", {})
                        severity = metadata.get("severity", "unknown").lower()

                        if severity == "error":
                            self.status["critical_issues"] += 1
                        elif severity == "warning":
                            self.status["warnings"] += 1

                    # Add specific recommendations
                    if self.status["critical_issues"] > 0:
                        self.status["recommendations"].append(
                            f"🚨 {self.status['critical_issues']} critical security issues found"
                        )

                    print(f"  {self.CYAN}Semgrep:{self.NC} {len(findings)} findings")
                    print(
                        f"    {self.RED}Critical: {self.status['critical_issues']}{self.NC}"
                    )
                    print(
                        f"    {self.YELLOW}Warnings: {self.status['warnings']}{self.NC}"
                    )

            except Exception as e:
                print(f"  {self.RED}Error parsing Semgrep results: {e}{self.NC}")

    def run_contract_sentinel(self):
        """Run contract check"""
        print(f"\n{self.BLUE}[PHASE 3] Contract Verification{self.NC}")
        print("-" * 50)

        try:
            contract_script = self.root / "apps" / "core" / "sentinel_contract.py"
            if contract_script.exists():
                result = subprocess.run(
                    ["python3", str(contract_script)],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )

                if result.returncode == 0:
                    self.status["contract"] = "VALID"
                    print(f"{self.GREEN}✅ Contract check passed{self.NC}")
                else:
                    self.status["contract"] = "BREACH"
                    print(f"{self.RED}❌ Contract breach detected{self.NC}")

        except Exception as e:
            self.status["contract"] = "ERROR"
            print(f"{self.RED}❌ Contract check error: {e}{self.NC}")

    def generate_report(self):
        """Generate comprehensive report"""
        print(f"\n{self.CYAN}📊 ENHANCED SENTINEL REPORT{self.NC}")
        print("=" * 50)

        # Overall status
        health_score = self.calculate_health_score()
        health_color = (
            self.GREEN
            if health_score >= 80
            else self.YELLOW
            if health_score >= 60
            else self.RED
        )

        print(
            f"{self.CYAN}System Health Score:{self.NC} {health_color}{health_score}/100{self.NC}"
        )
        print(f"{self.CYAN}Timestamp:{self.NC} {self.timestamp}")

        print(f"\n{self.BLUE}Component Status:{self.NC}")
        print(f"  Backend:         {self.format_status(self.status['backend'])}")
        print(f"  Contract:        {self.format_status(self.status['contract'])}")
        print(f"  Deep Analysis:   {self.format_status(self.status['deep_analysis'])}")

        print(f"\n{self.BLUE}Security Summary:{self.NC}")
        print(f"  Critical Issues: {self.RED}{self.status['critical_issues']}{self.NC}")
        print(f"  Warnings:        {self.YELLOW}{self.status['warnings']}{self.NC}")

        if self.status["recommendations"]:
            print(f"\n{self.YELLOW}🚨 Recommendations:{self.NC}")
            for rec in self.status["recommendations"]:
                print(f"  {rec}")

        # Save report
        self.save_report()

        # Exit code based on critical issues
        if self.status["critical_issues"] > 0:
            print(
                f"\n{self.RED}❌ CRITICAL ISSUES DETECTED - IMMEDIATE ACTION REQUIRED{self.NC}"
            )
            return 1
        elif health_score < 80:
            print(f"\n{self.YELLOW}⚠️ SYSTEM DEGRADATION DETECTED{self.NC}")
            return 2
        else:
            print(f"\n{self.GREEN}✅ ALL SYSTEMS NOMINAL{self.NC}")
            return 0

    def format_status(self, status: str) -> str:
        """Format status with colors"""
        status_colors = {
            "HEALTHY": f"{self.GREEN}✅ HEALTHY{self.NC}",
            "COMPLETED": f"{self.GREEN}✅ COMPLETED{self.NC}",
            "VALID": f"{self.GREEN}✅ VALID{self.NC}",
            "ISSUES": f"{self.YELLOW}⚠️ ISSUES{self.NC}",
            "BREACH": f"{self.RED}❌ BREACH{self.NC}",
            "ERROR": f"{self.RED}❌ ERROR{self.NC}",
            "TIMEOUT": f"{self.RED}❌ TIMEOUT{self.NC}",
            "UNKNOWN": f"{self.YELLOW}❓ UNKNOWN{self.NC}",
        }
        return status_colors.get(status, f"{self.YELLOW}{status}{self.NC}")

    def calculate_health_score(self) -> int:
        """Calculate overall health score (0-100)"""
        score = 100

        # Deduct points for issues
        if self.status["backend"] not in ["HEALTHY", "COMPLETED"]:
            score -= 20
        if self.status["contract"] != "VALID":
            score -= 20
        if self.status["deep_analysis"] not in ["COMPLETED", "HEALTHY"]:
            score -= 15

        # Deduct for security issues
        score -= min(self.status["critical_issues"] * 10, 30)
        score -= min(self.status["warnings"] * 2, 10)

        return max(0, score)

    def save_report(self):
        """Save detailed report to file"""
        report_file = (
            self.results_dir
            / f"sentinel-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )

        report_data = {
            "timestamp": self.timestamp,
            "health_score": self.calculate_health_score(),
            "status": self.status,
            "findings": {
                "critical_issues": self.status["critical_issues"],
                "warnings": self.status["warnings"],
            },
            "components": {
                "backend": self.status["backend"],
                "contract": self.status["contract"],
                "deep_analysis": self.status["deep_analysis"],
            },
        }

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n{self.CYAN}📁 Report saved: {report_file}{self.NC}")

    def run(self):
        """Run complete enhanced sentinel check"""
        self.banner()

        # Run all phases
        self.run_original_sentinel()
        self.run_deep_analysis()
        self.run_contract_sentinel()

        # Generate final report
        exit_code = self.generate_report()

        return exit_code


if __name__ == "__main__":
    sentinel = EnhancedSentinel()
    exit_code = sentinel.run()
    sys.exit(exit_code)
