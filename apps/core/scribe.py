#!/usr/bin/env python3
"""
THE SCRIBE: Automated Documentation Generator
Scans codebase, extracts docstrings and API routes, generates LIVING_ARCHITECTURE.md
"""

import ast
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from collections import defaultdict


class Colors:
    """Terminal colors"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


class RouteExtractor(ast.NodeVisitor):
    """Extract FastAPI routes from AST"""

    def __init__(self):
        self.routes: List[Dict] = []
        self.router_info: Dict[str, Dict] = {}  # router_name -> {prefix, tags}
        self.functions: List[ast.FunctionDef] = []

    def visit_Assign(self, node):
        """Find router = APIRouter(...) assignments"""
        if isinstance(node.value, ast.Call):
            # Check if it's APIRouter(...)
            if (
                isinstance(node.value.func, ast.Name)
                and node.value.func.id == "APIRouter"
            ):
                # Get the variable name (could be router, api_router, etc.)
                if isinstance(node.targets[0], ast.Name):
                    router_name = node.targets[0].id

                    # Extract prefix and tags from APIRouter call
                    prefix = ""
                    tags = []
                    for keyword in node.value.keywords:
                        if keyword.arg == "prefix":
                            if isinstance(keyword.value, ast.Constant):
                                prefix = keyword.value.value
                        elif keyword.arg == "tags":
                            if isinstance(keyword.value, ast.List):
                                tags = [
                                    elt.value
                                    for elt in keyword.value.elts
                                    if isinstance(elt, ast.Constant)
                                ]

                    self.router_info[router_name] = {
                        "prefix": prefix,
                        "tags": tags,
                    }
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Find route decorators - routers should already be found"""
        for decorator in node.decorator_list:
            route_info = self._extract_route_info(decorator, node)
            if route_info:
                route_info["function_name"] = node.name
                route_info["docstring"] = ast.get_docstring(node) or ""
                self.routes.append(route_info)
        self.generic_visit(node)

    def _extract_route_info(
        self, decorator: ast.AST, func_node: ast.FunctionDef
    ) -> Dict | None:
        """Extract route method and path from decorator"""
        if isinstance(decorator, ast.Call):
            # Check for @router.get(), @router.post(), etc.
            if isinstance(decorator.func, ast.Attribute):
                # Check if it's router.get, router.post, etc.
                if isinstance(decorator.func.value, ast.Name):
                    router_name = decorator.func.value.id
                    # Check if this router is known
                    if router_name in self.router_info:
                        method = decorator.func.attr.upper()  # get -> GET, post -> POST
                        if method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                            path = ""
                            if decorator.args:
                                if isinstance(decorator.args[0], ast.Constant):
                                    path = decorator.args[0].value

                            # Extract response_model if present
                            response_model = None
                            for keyword in decorator.keywords:
                                if keyword.arg == "response_model":
                                    if isinstance(keyword.value, ast.Name):
                                        response_model = keyword.value.id

                            router_data = self.router_info[router_name]
                            return {
                                "method": method,
                                "path": path,
                                "response_model": response_model,
                                "prefix": router_data["prefix"],
                                "tags": router_data["tags"],
                            }
        return None


class DocstringExtractor(ast.NodeVisitor):
    """Extract docstrings from modules, classes, and functions"""

    def __init__(self):
        self.modules: Dict[str, str] = {}
        self.classes: Dict[str, Dict] = {}
        self.functions: Dict[str, Dict] = {}
        self.current_module = ""

    def visit_Module(self, node):
        """Extract module docstring"""
        docstring = ast.get_docstring(node)
        if docstring:
            self.modules[self.current_module] = docstring.strip()
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Extract class docstring"""
        docstring = ast.get_docstring(node)
        if docstring:
            self.classes[node.name] = {
                "docstring": docstring.strip(),
                "module": self.current_module,
            }
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Extract function docstring"""
        docstring = ast.get_docstring(node)
        if docstring:
            full_name = f"{self.current_module}.{node.name}"
            self.functions[full_name] = {
                "docstring": docstring.strip(),
                "module": self.current_module,
            }
        self.generic_visit(node)


class Scribe:
    """The Scribe - Documentation Generator"""

    def __init__(self, backend_dir: Path, docs_dir: Path):
        self.backend_dir = backend_dir
        self.docs_dir = docs_dir
        self.output_file = docs_dir / "LIVING_ARCHITECTURE.md"
        self.system_overview_file = docs_dir / "SYSTEM_OVERVIEW.md"

    def scan_codebase(self) -> Tuple[List[Dict], Dict, Dict, Dict]:
        """Scan all Python files and extract information"""
        routes = []
        modules = {}
        classes = {}
        functions = {}

        # Find all Python files
        python_files = list(self.backend_dir.rglob("*.py"))
        python_files = [f for f in python_files if "__pycache__" not in str(f)]

        print(
            f"{Colors.OKCYAN}📚 Scanning {len(python_files)} Python files...{Colors.ENDC}"
        )

        for file_path in python_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Skip empty files
                if not content.strip():
                    continue

                try:
                    tree = ast.parse(content, filename=str(file_path))
                except SyntaxError:
                    print(
                        f"{Colors.WARNING}⚠ Skipping {file_path.name} (syntax error){Colors.ENDC}"
                    )
                    continue

                # Extract routes - create new extractor for each file
                route_extractor = RouteExtractor()
                # First pass: find all router definitions using walk
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        route_extractor.visit_Assign(node)
                # Second pass: find all route decorators using walk
                # Note: FastAPI routes can be async (AsyncFunctionDef) or sync (FunctionDef)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Process decorators directly
                        for decorator in node.decorator_list:
                            route_info = route_extractor._extract_route_info(
                                decorator, node
                            )
                            if route_info:
                                route_info["function_name"] = node.name
                                route_info["docstring"] = ast.get_docstring(node) or ""
                                route_extractor.routes.append(route_info)
                for route in route_extractor.routes:
                    route["file"] = str(file_path.relative_to(self.backend_dir))
                    routes.append(route)

                # Extract docstrings
                rel_path = str(file_path.relative_to(self.backend_dir))
                doc_extractor = DocstringExtractor()
                doc_extractor.current_module = rel_path.replace("/", ".").replace(
                    ".py", ""
                )
                doc_extractor.visit(tree)

                modules.update(doc_extractor.modules)
                classes.update(doc_extractor.classes)
                functions.update(doc_extractor.functions)

            except Exception as e:
                print(
                    f"{Colors.WARNING}⚠ Error processing {file_path}: {e}{Colors.ENDC}"
                )
                continue

        return routes, modules, classes, functions

    def categorize_routes(self, routes: List[Dict]) -> Dict[str, List[Dict]]:
        """Group routes by tag/prefix"""
        categorized = defaultdict(list)

        for route in routes:
            # Use tag if available, otherwise use prefix
            category = route.get("tags", [])
            if category:
                cat_name = category[0]  # Use first tag
            else:
                cat_name = (
                    route.get("prefix", "uncategorized")
                    .replace("/", "")
                    .replace("api", "")
                    .title()
                )

            categorized[cat_name].append(route)

        return dict(categorized)

    def generate_markdown(
        self, routes: List[Dict], modules: Dict, classes: Dict, functions: Dict
    ) -> str:
        """Generate LIVING_ARCHITECTURE.md content"""
        lines = []

        # Header
        lines.append("# LIVING ARCHITECTURE")
        lines.append("")
        lines.append(
            f"*Auto-generated by The Scribe on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )
        lines.append("")
        lines.append(
            "> **Note:** This document is automatically updated. Do not edit manually."
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Table of Contents
        lines.append("## Table of Contents")
        lines.append("")
        lines.append("- [API Endpoints](#api-endpoints)")
        lines.append("- [Modules](#modules)")
        lines.append("- [Services](#services)")
        lines.append("- [Agents](#agents)")
        lines.append("")
        lines.append("---")
        lines.append("")

        # API Endpoints Section
        lines.append("## API Endpoints")
        lines.append("")

        categorized_routes = self.categorize_routes(routes)

        for category in sorted(categorized_routes.keys()):
            lines.append(f"### {category}")
            lines.append("")

            for route in sorted(
                categorized_routes[category], key=lambda x: (x["method"], x["path"])
            ):
                method = route["method"]
                path = route["path"]
                prefix = route.get("prefix", "")
                full_path = f"{prefix}{path}" if prefix else path

                lines.append(f"#### `{method} {full_path}`")
                if route.get("docstring"):
                    lines.append("")
                    lines.append(route["docstring"])
                    lines.append("")

                if route.get("response_model"):
                    lines.append(f"**Response Model:** `{route['response_model']}`")
                    lines.append("")

                lines.append(f"**File:** `{route['file']}`")
                lines.append("")
                lines.append("---")
                lines.append("")

        # Modules Section
        lines.append("## Modules")
        lines.append("")

        # Group modules by directory
        module_groups = defaultdict(list)
        for module_path, docstring in modules.items():
            parts = module_path.split(".")
            if len(parts) > 1:
                group = parts[0]
            else:
                group = "root"
            module_groups[group].append((module_path, docstring))

        for group in sorted(module_groups.keys()):
            lines.append(f"### {group.title()}")
            lines.append("")
            for module_path, docstring in sorted(module_groups[group]):
                lines.append(f"#### `{module_path}`")
                lines.append("")
                lines.append(docstring)
                lines.append("")

        # Services Section
        lines.append("## Services")
        lines.append("")

        service_classes = {k: v for k, v in classes.items() if "service" in k.lower()}
        for class_name, info in sorted(service_classes.items()):
            lines.append(f"### `{class_name}`")
            lines.append("")
            lines.append(f"**Module:** `{info['module']}`")
            lines.append("")
            lines.append(info["docstring"])
            lines.append("")

        # Agents Section
        lines.append("## Agents")
        lines.append("")

        agent_files = [f for f in self.backend_dir.rglob("*agent*.py")]
        agent_files = [f for f in agent_files if "__pycache__" not in str(f)]

        for agent_file in agent_files:
            rel_path = str(agent_file.relative_to(self.backend_dir))
            lines.append(f"### `{rel_path}`")
            lines.append("")
            # Try to get module docstring
            module_name = rel_path.replace("/", ".").replace(".py", "")
            if module_name in modules:
                lines.append(modules[module_name])
                lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)

    def generate_system_overview(
        self, routes: List[Dict], modules: Dict, classes: Dict, functions: Dict
    ) -> str:
        """Generate SYSTEM_OVERVIEW.md - concise summary"""
        lines = []

        # Header
        lines.append("# SYSTEM OVERVIEW")
        lines.append("")
        lines.append(
            f"*Auto-generated by The Scribe on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )
        lines.append("")
        lines.append(
            "> **Note:** This document is automatically updated. Do not edit manually."
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Quick Stats
        lines.append("## Quick Statistics")
        lines.append("")
        lines.append(f"- **Total API Routes:** {len(routes)}")
        lines.append(f"- **Modules:** {len(modules)}")
        lines.append(
            f"- **Services:** {len([k for k in classes.keys() if 'service' in k.lower()])}"
        )
        agent_count = len(
            [
                f
                for f in self.backend_dir.rglob("*agent*.py")
                if "__pycache__" not in str(f)
            ]
        )
        lines.append(f"- **Agents:** {agent_count}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # API Endpoints Summary
        lines.append("## API Endpoints Summary")
        lines.append("")

        categorized_routes = self.categorize_routes(routes)

        for category in sorted(categorized_routes.keys()):
            category_routes = categorized_routes[category]
            lines.append(f"### {category} ({len(category_routes)} endpoints)")
            lines.append("")

            # Group by method
            by_method = defaultdict(list)
            for route in category_routes:
                by_method[route["method"]].append(route)

            for method in sorted(by_method.keys()):
                method_routes = by_method[method]
                lines.append(f"**{method}:**")
                for route in sorted(method_routes, key=lambda x: x["path"]):
                    path = route["path"]
                    prefix = route.get("prefix", "")
                    full_path = f"{prefix}{path}" if prefix else path
                    lines.append(f"- `{full_path}`")
                lines.append("")

        lines.append("---")
        lines.append("")

        # Key Modules
        lines.append("## Key Modules")
        lines.append("")

        # Show only modules with meaningful docstrings
        important_modules = {
            k: v
            for k, v in modules.items()
            if v and len(v) > 50 and not k.endswith("__init__")
        }

        for module_path, docstring in sorted(list(important_modules.items())[:20]):
            lines.append(f"### `{module_path}`")
            lines.append("")
            # Truncate long docstrings
            if len(docstring) > 200:
                docstring = docstring[:200] + "..."
            lines.append(docstring)
            lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append("")
        lines.append(
            "For detailed documentation, see [LIVING_ARCHITECTURE.md](./LIVING_ARCHITECTURE.md)"
        )

        return "\n".join(lines)

    def run(self):
        """Execute The Scribe"""
        print(f"{Colors.HEADER}{Colors.BOLD}")
        print("╔════════════════════════════════════════╗")
        print("║      THE SCRIBE: DOCUMENTATION         ║")
        print("╚════════════════════════════════════════╝")
        print(f"{Colors.ENDC}")

        if not self.backend_dir.exists():
            print(
                f"{Colors.FAIL}✘ Backend directory not found: {self.backend_dir}{Colors.ENDC}"
            )
            return False

        # Ensure docs directory exists
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        # Scan codebase
        routes, modules, classes, functions = self.scan_codebase()

        print(f"{Colors.OKGREEN}✔ Found {len(routes)} API routes{Colors.ENDC}")
        print(f"{Colors.OKGREEN}✔ Found {len(modules)} modules{Colors.ENDC}")
        print(f"{Colors.OKGREEN}✔ Found {len(classes)} classes{Colors.ENDC}")
        print(f"{Colors.OKGREEN}✔ Found {len(functions)} functions{Colors.ENDC}")

        # Generate markdown
        markdown_content = self.generate_markdown(routes, modules, classes, functions)
        system_overview_content = self.generate_system_overview(
            routes, modules, classes, functions
        )

        # Write to files
        self.output_file.write_text(markdown_content, encoding="utf-8")
        self.system_overview_file.write_text(system_overview_content, encoding="utf-8")

        print(
            f"{Colors.OKGREEN}✔ Documentation written to {self.output_file}{Colors.ENDC}"
        )
        print(
            f"{Colors.OKGREEN}✔ System overview written to {self.system_overview_file}{Colors.ENDC}"
        )

        return True


def main():
    """Main entry point"""
    import sys
    from pathlib import Path

    # Determine paths
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent.parent
    backend_dir = root_dir / "apps" / "backend-rag" / "backend"
    docs_dir = root_dir / "docs"

    scribe = Scribe(backend_dir, docs_dir)
    success = scribe.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
