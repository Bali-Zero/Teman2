#!/usr/bin/env python3
"""
Monitor Intel Router Prometheus metrics.

This script fetches and analyzes Prometheus metrics for Intel services,
checking for anomalies and performance issues.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests

# Colors for terminal output
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"

METRICS_URL = "https://nuzantara-rag.fly.dev/metrics"
INTEL_METRICS_PREFIXES = [
    "zantara_intel_articles",
    "zantara_intel_classification",
    "zantara_intel_scraper",
    "zantara_intel_staging",
    "zantara_intel_bulk",
    "zantara_intel_filter",
    "zantara_intel_sort",
    "zantara_intel_search",
    "zantara_intel_analytics",
    "zantara_intel_user_actions",
]


def fetch_metrics() -> str:
    """Fetch metrics from Prometheus endpoint."""
    try:
        response = requests.get(METRICS_URL, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"{RED}Error fetching metrics: {e}{RESET}")
        return ""


def parse_metrics(metrics_text: str) -> Dict:
    """Parse Prometheus metrics text format."""
    metrics = {}
    current_help = ""
    current_type = ""
    
    for line in metrics_text.split("\n"):
        line = line.strip()
        
        if line.startswith("# HELP"):
            # Extract help text
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                current_help = parts[2]
        
        elif line.startswith("# TYPE"):
            # Extract type
            parts = line.split(" ")
            if len(parts) >= 3:
                current_type = parts[2]
        
        elif line and not line.startswith("#"):
            # Parse metric line
            if " " in line or "\t" in line:
                parts = line.split()
                if len(parts) >= 2:
                    metric_name = parts[0]
                    metric_value = parts[1]
                    
                    # Extract labels if present
                    labels = {}
                    if "{" in metric_name:
                        name_part, label_part = metric_name.split("{", 1)
                        metric_name = name_part
                        if "}" in label_part:
                            label_part = label_part.rstrip("}")
                            for label_pair in label_part.split(","):
                                if "=" in label_pair:
                                    key, value = label_pair.split("=", 1)
                                    labels[key] = value.strip('"')
                    
                    metrics[metric_name] = {
                        "value": float(metric_value) if metric_value != "NaN" else 0,
                        "type": current_type,
                        "help": current_help,
                        "labels": labels,
                    }
    
    return metrics


def analyze_intel_metrics(metrics: Dict) -> Dict:
    """Analyze Intel-specific metrics."""
    intel_metrics = {}
    analysis = {
        "total_articles_submitted": 0,
        "total_duplicates": 0,
        "total_classifications": 0,
        "classification_by_type": {},
        "staging_queue_sizes": {},
        "service_health": {},
    }
    
    for metric_name, metric_data in metrics.items():
        for prefix in INTEL_METRICS_PREFIXES:
            if metric_name.startswith(prefix):
                intel_metrics[metric_name] = metric_data
                
                # Analyze specific metrics
                if "articles_submitted_total" in metric_name:
                    analysis["total_articles_submitted"] += metric_data["value"]
                
                elif "articles_duplicates_total" in metric_name:
                    analysis["total_duplicates"] += metric_data["value"]
                
                elif "classification_total" in metric_name:
                    analysis["total_classifications"] += metric_data["value"]
                    # Extract classification type from labels
                    if "labels" in metric_data and "classified_as" in metric_data["labels"]:
                        classified_as = metric_data["labels"]["classified_as"]
                        analysis["classification_by_type"][classified_as] = (
                            analysis["classification_by_type"].get(classified_as, 0) + metric_data["value"]
                        )
                
                elif "staging_queue_size" in metric_name:
                    if "labels" in metric_data and "intel_type" in metric_data["labels"]:
                        intel_type = metric_data["labels"]["intel_type"]
                        analysis["staging_queue_sizes"][intel_type] = metric_data["value"]
                
                break
    
    # Calculate health indicators
    if analysis["total_articles_submitted"] > 0:
        duplicate_rate = (analysis["total_duplicates"] / analysis["total_articles_submitted"]) * 100
        analysis["duplicate_rate_percent"] = round(duplicate_rate, 2)
    else:
        analysis["duplicate_rate_percent"] = 0
    
    return {
        "metrics": intel_metrics,
        "analysis": analysis,
        "metrics_count": len(intel_metrics),
    }


def print_report(result: Dict):
    """Print formatted metrics report."""
    analysis = result["analysis"]
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Intel Router Metrics Report{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Metrics found: {result['metrics_count']}")
    print()

    # Articles submitted
    print(f"{BLUE}📊 Articles Submitted:{RESET}")
    print(f"  Total: {analysis['total_articles_submitted']:.0f}")
    print(f"  Duplicates: {analysis['total_duplicates']:.0f}")
    if analysis['total_articles_submitted'] > 0:
        print(f"  Duplicate Rate: {analysis['duplicate_rate_percent']:.2f}%")
    print()

    # Classifications
    print(f"{BLUE}🔍 Classifications:{RESET}")
    print(f"  Total: {analysis['total_classifications']:.0f}")
    if analysis['classification_by_type']:
        for classified_as, count in analysis['classification_by_type'].items():
            print(f"  • {classified_as}: {count:.0f}")
    print()

    # Staging queue sizes
    print(f"{BLUE}📦 Staging Queue Sizes:{RESET}")
    if analysis['staging_queue_sizes']:
        for intel_type, size in analysis['staging_queue_sizes'].items():
            status = f"{GREEN}✅{RESET}" if size < 50 else f"{YELLOW}⚠️{RESET}" if size < 100 else f"{RED}🔴{RESET}"
            print(f"  {status} {intel_type}: {size:.0f} items")
    else:
        print(f"  {GREEN}✅ No items in staging{RESET}")
    print()

    # Health summary
    print(f"{BLUE}{'='*60}{RESET}")
    if analysis['staging_queue_sizes']:
        max_queue_size = max(analysis['staging_queue_sizes'].values())
        if max_queue_size > 100:
            print(f"{RED}⚠️  WARNING: Staging queue size exceeds 100 items{RESET}")
            return 1
        elif max_queue_size > 50:
            print(f"{YELLOW}⚠️  CAUTION: Staging queue size exceeds 50 items{RESET}")
            return 0
    
    print(f"{GREEN}✅ All metrics within normal range{RESET}")
    return 0


def main():
    """Main monitoring function."""
    print(f"{BLUE}Fetching metrics from {METRICS_URL}...{RESET}")
    metrics_text = fetch_metrics()
    
    if not metrics_text:
        print(f"{RED}No metrics retrieved{RESET}")
        return 1
    
    print(f"{GREEN}Parsing metrics...{RESET}")
    all_metrics = parse_metrics(metrics_text)
    
    print(f"{GREEN}Analyzing Intel metrics...{RESET}")
    result = analyze_intel_metrics(all_metrics)
    
    exit_code = print_report(result)
    
    # Save report to file
    report_file = Path(__file__).parent / "intel_metrics_report.json"
    with open(report_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "metrics_count": result["metrics_count"],
            "analysis": result["analysis"],
        }, f, indent=2)
    
    print(f"{BLUE}Report saved to: {report_file}{RESET}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
