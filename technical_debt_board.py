#!/usr/bin/env python3
"""
Technical Debt Board for Nuzantara
Tracks and manages TODO/FIXME/HACK/BUG items across the codebase
"""

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess
import os


class TechnicalDebtItem:
    """Represents a single technical debt item"""
    
    def __init__(self, file_path: str, line_number: int, content: str, type: str):
        self.file_path = file_path
        self.line_number = line_number
        self.content = content.strip()
        self.type = type  # TODO, FIXME, HACK, BUG
        self.created_at = datetime.now()
        self.priority = self._extract_priority()
        self.assignee = self._extract_assignee()
        self.issue_url = self._extract_issue_url()
        self.component = self._extract_component()
        
    def _extract_priority(self) -> str:
        """Extract priority from content"""
        priority_patterns = [
            (r'!\s*(P0|CRITICAL)', 'P0'),
            (r'!\s*(P1|HIGH)', 'P1'),
            (r'!\s*(P2|MEDIUM)', 'P2'),
            (r'!\s*(P3|LOW)', 'P3'),
        ]
        
        for pattern, priority in priority_patterns:
            if re.search(pattern, self.content, re.IGNORECASE):
                return priority
        
        # Default priority based on type
        type_priorities = {
            'BUG': 'P1',
            'FIXME': 'P2',
            'HACK': 'P2',
            'TODO': 'P3',
        }
        return type_priorities.get(self.type, 'P3')
    
    def _extract_assignee(self) -> Optional[str]:
        """Extract assignee from content"""
        match = re.search(r'@(\w+)', self.content)
        return match.group(1) if match else None
    
    def _extract_issue_url(self) -> Optional[str]:
        """Extract GitHub issue URL from content"""
        # Match GitHub URLs
        match = re.search(r'https://github\.com/[^/]+/[^/]+/issues/\d+', self.content)
        if match:
            return match.group(0)
        
        # Match issue numbers (convert to URL later)
        match = re.search(r'#(\d+)', self.content)
        if match:
            return f"#{match.group(1)}"
        
        return None
    
    def _extract_component(self) -> str:
        """Extract component from file path"""
        if 'apps/backend-rag' in self.file_path:
            return 'backend'
        elif 'apps/mouth' in self.file_path:
            return 'frontend'
        elif 'apps/bali-intel-scraper' in self.file_path:
            return 'scraper'
        else:
            return 'shared'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'file_path': self.file_path,
            'line_number': self.line_number,
            'content': self.content,
            'type': self.type,
            'priority': self.priority,
            'assignee': self.assignee,
            'issue_url': self.issue_url,
            'component': self.component,
            'created_at': self.created_at.isoformat(),
            'age_days': (datetime.now() - self.created_at).days
        }


class TechnicalDebtBoard:
    """Manages technical debt across the codebase"""
    
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.items: List[TechnicalDebtItem] = []
        self.exclude_patterns = [
            r'\.git/',
            r'node_modules/',
            r'\.venv/',
            r'__pycache__/',
            r'\.next/',
            r'coverage/',
            r'\.pytest_cache/',
            r'test-results/',
            r'\.DS_Store',
        ]
        
    def scan_codebase(self) -> None:
        """Scan the entire codebase for technical debt items"""
        print("🔍 Scanning codebase for technical debt...")
        
        # Patterns to search for
        patterns = [
            (r'//\s*(TODO|FIXME|HACK|BUG)(.*)', lambda m: m.group(1), ['.ts', '.tsx', '.js', '.jsx']),
            (r'#\s*(TODO|FIXME|HACK|BUG)(.*)', lambda m: m.group(1), ['.py']),
            (r'/\*\*\s*(TODO|FIXME|HACK|BUG)(.*?)\*/', lambda m: m.group(1), ['.ts', '.tsx', '.js', '.jsx']),
            (r'<!--\s*(TODO|FIXME|HACK|BUG)(.*?)-->', lambda m: m.group(1), ['.html', '.md']),
        ]
        
        for pattern, type_extractor, extensions in patterns:
            self._search_pattern(pattern, type_extractor, extensions)
        
        print(f"📊 Found {len(self.items)} technical debt items")
    
    def _search_pattern(self, pattern: str, type_extractor, extensions: List[str]) -> None:
        """Search for a specific pattern in files with given extensions"""
        regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        for ext in extensions:
            for file_path in self.repo_root.rglob(f'*{ext}'):
                # Skip excluded paths
                if any(re.search(exclude, str(file_path)) for exclude in self.exclude_patterns):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    for match in regex.finditer(content):
                        line_number = content[:match.start()].count('\n') + 1
                        debt_type = type_extractor(match).upper()
                        debt_content = match.group(0)
                        
                        item = TechnicalDebtItem(
                            str(file_path.relative_to(self.repo_root)),
                            line_number,
                            debt_content,
                            debt_type
                        )
                        self.items.append(item)
                        
                except (UnicodeDecodeError, PermissionError):
                    # Skip binary files or files we can't read
                    continue
    
    def generate_report(self, output_format: str = 'markdown') -> str:
        """Generate a technical debt report"""
        if output_format == 'json':
            return self._generate_json_report()
        else:
            return self._generate_markdown_report()
    
    def _generate_markdown_report(self) -> str:
        """Generate markdown report"""
        # Group items by priority and type
        by_priority = {}
        by_type = {}
        by_component = {}
        
        for item in self.items:
            # Group by priority
            if item.priority not in by_priority:
                by_priority[item.priority] = []
            by_priority[item.priority].append(item)
            
            # Group by type
            if item.type not in by_type:
                by_type[item.type] = []
            by_type[item.type].append(item)
            
            # Group by component
            if item.component not in by_component:
                by_component[item.component] = []
            by_component[item.component].append(item)
        
        # Sort priorities
        priority_order = ['P0', 'P1', 'P2', 'P3']
        
        report = f"""# 🚧 Technical Debt Board - {datetime.now().strftime('%Y-%m-%d')}

## 📊 Summary

| Metric | Count |
|--------|-------|
| Total Items | {len(self.items)} |
| P0 (Critical) | {len(by_priority.get('P0', []))} |
| P1 (High) | {len(by_priority.get('P1', []))} |
| P2 (Medium) | {len(by_priority.get('P2', []))} |
| P3 (Low) | {len(by_priority.get('P3', []))} |

### By Type
"""
        
        for debt_type in ['TODO', 'FIXME', 'HACK', 'BUG']:
            count = len(by_type.get(debt_type, []))
            report += f"- {debt_type}: {count}\n"
        
        report += "\n### By Component\n"
        for component in ['backend', 'frontend', 'scraper', 'shared']:
            count = len(by_component.get(component, []))
            report += f"- {component}: {count}\n"
        
        # Critical items first
        report += "\n---\n\n## 🚨 P0 - Critical Issues\n\n"
        p0_items = by_priority.get('P0', [])
        if p0_items:
            for item in sorted(p0_items, key=lambda x: x.file_path):
                report += self._format_item(item)
        else:
            report += "✅ No critical issues found!\n"
        
        # High priority
        report += "\n---\n\n## ⚠️ P1 - High Priority\n\n"
        p1_items = by_priority.get('P1', [])
        if p1_items:
            for item in sorted(p1_items, key=lambda x: x.file_path):
                report += self._format_item(item)
        else:
            report += "✅ No high priority issues!\n"
        
        # Medium priority
        report += "\n---\n\n## 📝 P2 - Medium Priority\n\n"
        p2_items = by_priority.get('P2', [])
        if p2_items:
            for item in sorted(p2_items, key=lambda x: x.file_path)[:20]:  # Limit to 20
                report += self._format_item(item)
            if len(p2_items) > 20:
                report += f"... and {len(p2_items) - 20} more items\n"
        else:
            report += "✅ No medium priority issues!\n"
        
        # Low priority (sample)
        report += "\n---\n\n## 📋 P3 - Low Priority (Sample)\n\n"
        p3_items = by_priority.get('P3', [])
        if p3_items:
            for item in sorted(p3_items, key=lambda x: x.file_path)[:10]:  # Limit to 10
                report += self._format_item(item)
            if len(p3_items) > 10:
                report += f"... and {len(p3_items) - 10} more items\n"
        else:
            report += "✅ No low priority issues!\n"
        
        # Recommendations
        report += "\n---\n\n## 💡 Recommendations\n\n"
        report += self._generate_recommendations(by_priority, by_type, by_component)
        
        return report
    
    def _format_item(self, item: TechnicalDebtItem) -> str:
        """Format a single item for markdown"""
        formatted = f"### {item.type} - {item.priority}\n\n"
        formatted += f"**File:** `{item.file_path}:{item.line_number}`\n\n"
        formatted += f"**Component:** {item.component}\n\n"
        
        if item.assignee:
            formatted += f"**Assignee:** @{item.assignee}\n\n"
        
        if item.issue_url:
            formatted += f"**Issue:** {item.issue_url}\n\n"
        
        formatted += f"**Content:**\n```\n{item.content}\n```\n\n"
        formatted += "---\n\n"
        
        return formatted
    
    def _generate_recommendations(self, by_priority, by_type, by_component) -> str:
        """Generate recommendations based on the analysis"""
        recommendations = []
        
        # Critical issues
        p0_count = len(by_priority.get('P0', []))
        if p0_count > 0:
            recommendations.append(f"🚨 **Address {p0_count} critical issues immediately** - These block production readiness")
        
        # Bug count
        bug_count = len(by_type.get('BUG', []))
        if bug_count > 5:
            recommendations.append(f"🐛 **High bug concentration ({bug_count} items)** - Consider a bug-fix sprint")
        
        # Component-specific recommendations
        backend_count = len(by_component.get('backend', []))
        frontend_count = len(by_component.get('frontend', []))
        
        if backend_count > frontend_count * 2:
            recommendations.append("🔧 **Backend technical debt is high** - Focus on backend refactoring")
        elif frontend_count > backend_count * 2:
            recommendations.append("🎨 **Frontend technical debt is high** - Focus on frontend cleanup")
        
        # Unassigned items
        unassigned = [item for item in self.items if not item.assignee]
        if len(unassigned) > len(self.items) * 0.5:
            recommendations.append(f"👥 **{len(unassigned)} items are unassigned** - Consider assigning ownership")
        
        # Items without GitHub issues
        no_issue = [item for item in self.items if not item.issue_url]
        if len(no_issue) > len(self.items) * 0.7:
            recommendations.append(f"🔗 **{len(no_issue)} items lack GitHub issues** - Create issues for better tracking")
        
        if not recommendations:
            recommendations.append("✅ **Technical debt is well managed** - Keep up the good work!")
        
        return "\n".join(recommendations)
    
    def _generate_json_report(self) -> str:
        """Generate JSON report"""
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_items': len(self.items),
                'by_priority': {},
                'by_type': {},
                'by_component': {},
            },
            'items': [item.to_dict() for item in self.items]
        }
        
        # Calculate summary statistics
        for item in self.items:
            # By priority
            if item.priority not in report_data['summary']['by_priority']:
                report_data['summary']['by_priority'][item.priority] = 0
            report_data['summary']['by_priority'][item.priority] += 1
            
            # By type
            if item.type not in report_data['summary']['by_type']:
                report_data['summary']['by_type'][item.type] = 0
            report_data['summary']['by_type'][item.type] += 1
            
            # By component
            if item.component not in report_data['summary']['by_component']:
                report_data['summary']['by_component'][item.component] = 0
            report_data['summary']['by_component'][item.component] += 1
        
        return json.dumps(report_data, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Technical Debt Board for Nuzantara')
    parser.add_argument('--repo-root', default='.', help='Repository root directory')
    parser.add_argument('--format', choices=['markdown', 'json'], default='markdown', 
                       help='Output format')
    parser.add_argument('--output', help='Output file (default: stdout)')
    
    args = parser.parse_args()
    
    # Create board and scan
    board = TechnicalDebtBoard(args.repo_root)
    board.scan_codebase()
    
    # Generate report
    report = board.generate_report(args.format)
    
    # Output report
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"📄 Report saved to {args.output}")
    else:
        print(report)


if __name__ == '__main__':
    main()
