"""
📊 Test Metrics & Logging System

Comprehensive metrics collection and logging for Test Force agents.
Tracks coverage, performance, and agent effectiveness.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class TestGenerationMetrics:
    """Metrics for test generation operations"""
    tests_generated: int = 0
    tests_successful: int = 0
    tests_failed: int = 0
    tests_fixed: int = 0
    total_generation_time: float = 0.0
    avg_generation_time: float = 0.0
    coverage_improvement: float = 0.0
    
    @property
    def success_rate(self) -> float:
        return (self.tests_successful / self.tests_generated * 100) if self.tests_generated > 0 else 0.0


@dataclass
class CoverageMetrics:
    """Coverage tracking metrics"""
    files_analyzed: int = 0
    files_below_threshold: int = 0
    current_coverage: float = 0.0
    target_coverage: float = 99.0
    coverage_gaps: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def coverage_gap_count(self) -> int:
        return len(self.coverage_gaps)
    
    @property
    def coverage_percentage(self) -> float:
        return self.current_coverage


@dataclass
class SystemMetrics:
    """System resource metrics"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    active_agents: int = 0
    uptime: float = 0.0
    
    @classmethod
    def collect(cls) -> "SystemMetrics":
        """Collect current system metrics"""
        return cls(
            cpu_usage=psutil.cpu_percent(),
            memory_usage=psutil.virtual_memory().percent,
            disk_usage=psutil.disk_usage('/').percent,
            active_agents=0,  # To be set by orchestrator
            uptime=time.time()
        )


@dataclass
class AgentMetrics:
    """Individual agent performance metrics"""
    agent_name: str
    operations_completed: int = 0
    operations_failed: int = 0
    total_operation_time: float = 0.0
    avg_operation_time: float = 0.0
    last_operation: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        total_ops = self.operations_completed + self.operations_failed
        return (self.operations_completed / total_ops * 100) if total_ops > 0 else 0.0
    
    def record_operation(self, duration: float, success: bool = True, error: Optional[str] = None):
        """Record an operation"""
        self.total_operation_time += duration
        if success:
            self.operations_completed += 1
        else:
            self.operations_failed += 1
            if error:
                self.errors.append(error)
        
        self.last_operation = datetime.now()
        self.avg_operation_time = self.total_operation_time / (self.operations_completed + self.operations_failed)


class TestMetricsCollector:
    """
    Comprehensive metrics collector for Test Force.
    
    Features:
    - Real-time metrics collection
    - Historical data storage
    - Performance trending
    - Alert generation
    - Export capabilities
    """
    
    def __init__(self, metrics_dir: Path = Path("metrics")):
        self.metrics_dir = metrics_dir
        self.metrics_dir.mkdir(exist_ok=True)
        
        # Metrics storage
        self.test_generation = TestGenerationMetrics()
        self.coverage = CoverageMetrics()
        self.system = SystemMetrics.collect()
        
        # Agent metrics
        self.agents: Dict[str, AgentMetrics] = {}
        
        # Historical data
        self.history: List[Dict[str, Any]] = []
        self.start_time = time.time()
        
        # Configuration
        self.target_coverage = 99.0
        self.alert_thresholds = {
            "success_rate": 80.0,
            "avg_generation_time": 30.0,
            "memory_usage": 85.0,
            "cpu_usage": 90.0
        }
        
        logger.info("📊 Test Metrics Collector initialized")
    
    def register_agent(self, agent_name: str) -> AgentMetrics:
        """Register a new agent for metrics tracking"""
        if agent_name not in self.agents:
            self.agents[agent_name] = AgentMetrics(agent_name=agent_name)
            logger.info(f"📝 Registered agent: {agent_name}")
        return self.agents[agent_name]
    
    def record_test_generation(self, duration: float, success: bool = True, coverage_delta: float = 0.0):
        """Record test generation operation"""
        self.test_generation.tests_generated += 1
        self.test_generation.total_generation_time += duration
        
        if success:
            self.test_generation.tests_successful += 1
            self.test_generation.coverage_improvement += coverage_delta
        else:
            self.test_generation.tests_failed += 1
        
        self.test_generation.avg_generation_time = (
            self.test_generation.total_generation_time / self.test_generation.tests_generated
        )
        
        logger.debug(f"📈 Test generation recorded: {success}, {duration:.2f}s, +{coverage_delta:.1f}% coverage")
    
    def record_coverage_update(self, coverage_data: Dict[str, Any]):
        """Update coverage metrics"""
        self.coverage.current_coverage = coverage_data.get("coverage", 0.0)
        self.coverage.files_analyzed = coverage_data.get("files_analyzed", 0)
        self.coverage.coverage_gaps = coverage_data.get("gaps", [])
        self.coverage.files_below_threshold = len([g for g in self.coverage.coverage_gaps if g["percent"] < self.target_coverage])
        
        logger.info(f"📊 Coverage updated: {self.coverage.current_coverage:.1f}% ({self.coverage.coverage_gap_count} gaps)")
    
    def update_system_metrics(self):
        """Update system resource metrics"""
        self.system = SystemMetrics.collect()
        self.system.active_agents = len(self.agents)
        self.system.uptime = time.time() - self.start_time
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        self.update_system_metrics()
        
        # Calculate agent averages
        total_operations = sum(a.operations_completed + a.operations_failed for a in self.agents.values())
        avg_success_rate = sum(a.success_rate for a in self.agents.values()) / len(self.agents) if self.agents else 0.0
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "uptime": self.system.uptime,
            "test_generation": asdict(self.test_generation),
            "coverage": asdict(self.coverage),
            "system": asdict(self.system),
            "agents": {name: asdict(agent) for name, agent in self.agents.items()},
            "totals": {
                "total_operations": total_operations,
                "avg_agent_success_rate": avg_success_rate,
                "active_agents": len(self.agents)
            }
        }
        
        return summary
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check for alert conditions"""
        alerts = []
        
        # Test generation alerts
        if self.test_generation.success_rate < self.alert_thresholds["success_rate"]:
            alerts.append({
                "type": "warning",
                "category": "test_generation",
                "message": f"Low success rate: {self.test_generation.success_rate:.1f}%",
                "threshold": self.alert_thresholds["success_rate"],
                "current": self.test_generation.success_rate
            })
        
        if self.test_generation.avg_generation_time > self.alert_thresholds["avg_generation_time"]:
            alerts.append({
                "type": "warning",
                "category": "performance",
                "message": f"Slow test generation: {self.test_generation.avg_generation_time:.1f}s",
                "threshold": self.alert_thresholds["avg_generation_time"],
                "current": self.test_generation.avg_generation_time
            })
        
        # Coverage alerts
        if self.coverage.current_coverage < self.target_coverage:
            alerts.append({
                "type": "info",
                "category": "coverage",
                "message": f"Coverage below target: {self.coverage.current_coverage:.1f}% < {self.target_coverage}%",
                "threshold": self.target_coverage,
                "current": self.coverage.current_coverage
            })
        
        # System alerts
        if self.system.memory_usage > self.alert_thresholds["memory_usage"]:
            alerts.append({
                "type": "critical",
                "category": "system",
                "message": f"High memory usage: {self.system.memory_usage:.1f}%",
                "threshold": self.alert_thresholds["memory_usage"],
                "current": self.system.memory_usage
            })
        
        if self.system.cpu_usage > self.alert_thresholds["cpu_usage"]:
            alerts.append({
                "type": "warning",
                "category": "system",
                "message": f"High CPU usage: {self.system.cpu_usage:.1f}%",
                "threshold": self.alert_thresholds["cpu_usage"],
                "current": self.system.cpu_usage
            })
        
        # Agent-specific alerts
        for name, agent in self.agents.items():
            if agent.success_rate < self.alert_thresholds["success_rate"]:
                alerts.append({
                    "type": "warning",
                    "category": "agent",
                    "message": f"Agent {name} low success rate: {agent.success_rate:.1f}%",
                    "agent": name,
                    "current": agent.success_rate
                })
        
        return alerts
    
    def save_snapshot(self, filename: Optional[str] = None):
        """Save current metrics snapshot to file"""
        if filename is None:
            filename = f"metrics_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        snapshot = self.get_summary()
        snapshot["alerts"] = self.check_alerts()
        
        filepath = self.metrics_dir / filename
        with open(filepath, 'w') as f:
            json.dump(snapshot, f, indent=2, default=str)
        
        logger.info(f"💾 Metrics snapshot saved: {filepath}")
        return filepath
    
    def generate_report(self, format: str = "html") -> str:
        """Generate comprehensive metrics report"""
        summary = self.get_summary()
        alerts = self.check_alerts()
        
        if format == "html":
            return self._generate_html_report(summary, alerts)
        elif format == "markdown":
            return self._generate_markdown_report(summary, alerts)
        else:
            return json.dumps(summary, indent=2, default=str)
    
    def _generate_html_report(self, summary: Dict[str, Any], alerts: List[Dict[str, Any]]) -> str:
        """Generate HTML report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Force Metrics Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .metric {{ background: #f5f5f5; padding: 10px; margin: 5px; border-radius: 5px; }}
        .success {{ background: #d4edda; }}
        .warning {{ background: #fff3cd; }}
        .critical {{ background: #f8d7da; }}
        .progress-bar {{ width: 100%; height: 20px; background: #e0e0e0; border-radius: 10px; }}
        .progress-fill {{ height: 100%; background: #4CAF50; border-radius: 10px; }}
    </style>
</head>
<body>
    <h1>🤖 Test Force Metrics Report</h1>
    <p>Generated: {summary['timestamp']}</p>
    
    <h2>📊 Test Generation</h2>
    <div class="metric">
        <strong>Tests Generated:</strong> {summary['test_generation']['tests_generated']}<br>
        <strong>Success Rate:</strong> {summary['test_generation']['success_rate']:.1f}%<br>
        <strong>Avg Generation Time:</strong> {summary['test_generation']['avg_generation_time']:.2f}s<br>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {summary['test_generation']['success_rate']}%"></div>
        </div>
    </div>
    
    <h2>📈 Coverage</h2>
    <div class="metric">
        <strong>Current Coverage:</strong> {summary['coverage']['current_coverage']:.1f}%<br>
        <strong>Target:</strong> {summary['coverage']['target_coverage']}%<br>
        <strong>Files Below Threshold:</strong> {summary['coverage']['files_below_threshold']}<br>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {summary['coverage']['current_coverage']}%"></div>
        </div>
    </div>
    
    <h2>💻 System Resources</h2>
    <div class="metric">
        <strong>CPU Usage:</strong> {summary['system']['cpu_usage']:.1f}%<br>
        <strong>Memory Usage:</strong> {summary['system']['memory_usage']:.1f}%<br>
        <strong>Active Agents:</strong> {summary['system']['active_agents']}<br>
        <strong>Uptime:</strong> {summary['system']['uptime']:.0f}s
    </div>
    
    <h2>🤖 Agents</h2>
"""
        
        for name, agent in summary['agents'].items():
            agent_class = "success" if agent['success_rate'] > 80 else "warning" if agent['success_rate'] > 60 else "critical"
            html += f"""
    <div class="metric {agent_class}">
        <strong>{name}:</strong><br>
        Operations: {agent['operations_completed']}/{agent['operations_completed'] + agent['operations_failed']}<br>
        Success Rate: {agent['success_rate']:.1f}%<br>
        Avg Time: {agent['avg_operation_time']:.2f}s
    </div>
"""
        
        if alerts:
            html += "<h2>🚨 Alerts</h2>"
            for alert in alerts:
                alert_class = alert['type']
                html += f"""
    <div class="metric {alert_class}">
        <strong>{alert['category'].title()}:</strong> {alert['message']}
    </div>
"""
        
        html += """
</body>
</html>
"""
        return html
    
    def _generate_markdown_report(self, summary: Dict[str, Any], alerts: List[Dict[str, Any]]) -> str:
        """Generate Markdown report"""
        md = f"""# 🤖 Test Force Metrics Report

**Generated:** {summary['timestamp']}

## 📊 Test Generation
- **Tests Generated:** {summary['test_generation'].get('tests_generated', 0)}
- **Success Rate:** {summary['test_generation'].get('success_rate', 0):.1f}%
- **Avg Generation Time:** {summary['test_generation'].get('avg_generation_time', 0):.2f}s
- **Coverage Improvement:** {summary['test_generation'].get('coverage_improvement', 0):.1f}%

## 📈 Coverage
- **Current Coverage:** {summary['coverage'].get('current_coverage', 0):.1f}%
- **Target:** {summary['coverage'].get('target_coverage', 0)}%
- **Files Analyzed:** {summary['coverage'].get('files_analyzed', 0)}
- **Files Below Threshold:** {summary['coverage'].get('files_below_threshold', 0)}
- **Coverage Gaps:** {summary['coverage'].get('coverage_gap_count', 0)}

## 💻 System Resources
- **CPU Usage:** {summary['system'].get('cpu_usage', 0):.1f}%
- **Memory Usage:** {summary['system'].get('memory_usage', 0):.1f}%
- **Disk Usage:** {summary['system'].get('disk_usage', 0):.1f}%
- **Active Agents:** {summary['system'].get('active_agents', 0)}
- **Uptime:** {summary['system'].get('uptime', 0):.0f}s

## 🤖 Agents
"""
        
        for name, agent in summary.get('agents', {}).items():
            md += f"""### {name}
- **Operations:** {agent.get('operations_completed', 0)}/{agent.get('operations_completed', 0) + agent.get('operations_failed', 0)}
- **Success Rate:** {agent.get('success_rate', 0):.1f}%
- **Avg Operation Time:** {agent.get('avg_operation_time', 0):.2f}s
- **Last Operation:** {agent.get('last_operation', 'N/A')}
"""
        
        if alerts:
            md += "\n## 🚨 Alerts\n"
            for alert in alerts:
                md += f"- **{alert['category'].title()}:** {alert['message']}\n"
        
        return md
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.test_generation = TestGenerationMetrics()
        self.coverage = CoverageMetrics()
        self.agents.clear()
        self.history.clear()
        self.start_time = time.time()
        logger.info("📊 All metrics reset")


# Singleton instance
_metrics_collector: Optional[TestMetricsCollector] = None


def get_metrics_collector() -> TestMetricsCollector:
    """Get singleton metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = TestMetricsCollector()
    return _metrics_collector
