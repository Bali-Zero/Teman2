#!/usr/bin/env python3
"""
NUZANTARA PRIME - Automated Test Generator
Generates unit tests for Python functions and API endpoints following project standards.
"""

import ast
import inspect
import sys
from pathlib import Path
from typing import Any

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class TestGenerator:
    """Generates pytest-compatible test files"""

    def __init__(self, source_file: Path, output_dir: Path | None = None):
        self.source_file = Path(source_file)
        self.source_content = self.source_file.read_text()
        self.source_tree = ast.parse(self.source_content)
        
        # Determine output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            # Mirror structure: apps/backend-rag/backend/app/modules/X/service.py -> tests/modules/X/test_service.py
            relative_path = self.source_file.relative_to(backend_path)
            if "modules" in str(relative_path):
                # Extract module name and file name
                parts = relative_path.parts
                module_idx = parts.index("modules")
                module_name = parts[module_idx + 1]
                file_name = parts[-1].replace(".py", "")
                self.output_dir = backend_path.parent / "tests" / "modules" / module_name
            else:
                # Fallback: tests/unit/
                self.output_dir = backend_path.parent / "tests" / "unit"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_functions(self) -> list[ast.FunctionDef]:
        """Extract all function definitions from source"""
        functions = []
        for node in ast.walk(self.source_tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                functions.append(node)
        return functions

    def extract_classes(self) -> list[ast.ClassDef]:
        """Extract all class definitions from source"""
        classes = []
        for node in ast.walk(self.source_tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                classes.append(node)
        return classes

    def is_async_function(self, func_node: ast.FunctionDef) -> bool:
        """Check if function is async"""
        return any(isinstance(decorator, ast.Name) and decorator.id == "async" 
                  for decorator in func_node.decorator_list) or \
               isinstance(func_node, ast.AsyncFunctionDef)

    def is_api_endpoint(self, func_node: ast.FunctionDef) -> bool:
        """Check if function is a FastAPI endpoint"""
        decorators = func_node.decorator_list
        for decorator in decorators:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    # router.get(), router.post(), etc.
                    if decorator.func.attr in ["get", "post", "put", "delete", "patch"]:
                        return True
                elif isinstance(decorator.func, ast.Name):
                    # @app.get(), etc.
                    if decorator.func.id in ["get", "post", "put", "delete", "patch"]:
                        return True
        return False

    def get_function_signature(self, func_node: ast.FunctionDef) -> str:
        """Generate function signature string"""
        params = []
        for arg in func_node.args.args:
            param_name = arg.arg
            # Try to infer type from annotation
            if arg.annotation:
                params.append(f"{param_name}: {ast.unparse(arg.annotation)}")
            else:
                params.append(param_name)
        
        return_type = ""
        if func_node.returns:
            return_type = f" -> {ast.unparse(func_node.returns)}"
        
        return f"def {func_node.name}({', '.join(params)}){return_type}"

    def generate_function_test(self, func_node: ast.FunctionDef, module_path: str) -> str:
        """Generate test code for a function"""
        is_async = self.is_async_function(func_node)
        is_endpoint = self.is_api_endpoint(func_node)
        
        test_name = f"test_{func_node.name}"
        docstring = ast.get_docstring(func_node) or f"Test {func_node.name}"
        
        # Determine import path
        relative_path = self.source_file.relative_to(backend_path)
        import_parts = relative_path.with_suffix("").parts
        import_path = ".".join(import_parts)
        
        test_code = f'''    def {test_name}_success(self):
        """Test {func_node.name} success case"""
'''
        
        if is_async:
            test_code = test_code.replace("def ", "@pytest.mark.asyncio\n    async def ")
        
        if is_endpoint:
            # API endpoint test
            test_code += f'''        # TODO: Implement API endpoint test
        # Example:
        # response = client.{self._get_http_method(func_node)}("/api/endpoint")
        # assert response.status_code == 200
'''
        else:
            # Regular function test
            test_code += f'''        # TODO: Implement test for {func_node.name}
        # Example:
        # result = {func_node.name}(...)
        # assert result is not None
'''
        
        test_code += f'''
    def {test_name}_error(self):
        """Test {func_node.name} error case"""
'''
        
        if is_async:
            test_code = test_code.replace("def ", "@pytest.mark.asyncio\n    async def ", 1)
        
        test_code += f'''        # TODO: Implement error case test
        # Example:
        # with pytest.raises(ValueError):
        #     {func_node.name}(...)
'''
        
        return test_code

    def _get_http_method(self, func_node: ast.FunctionDef) -> str:
        """Extract HTTP method from decorator"""
        for decorator in func_node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    return decorator.func.attr
                elif isinstance(decorator.func, ast.Name):
                    return decorator.func.id
        return "get"

    def generate_test_file(self) -> Path:
        """Generate complete test file"""
        test_file_name = f"test_{self.source_file.stem}.py"
        test_file_path = self.output_dir / test_file_name
        
        # Extract module path for imports
        relative_path = self.source_file.relative_to(backend_path)
        import_parts = relative_path.with_suffix("").parts
        import_path = ".".join(import_parts)
        
        # Generate imports
        imports = '''"""
Auto-generated test file for {source_file}
Generated by test_generator.py - Review and complete TODO sections
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from {import_path} import *
'''.format(source_file=self.source_file.name, import_path=import_path)
        
        # Generate test classes
        test_classes = []
        functions = self.extract_functions()
        classes = self.extract_classes()
        
        # Generate tests for functions
        if functions:
            test_class = f'''
class Test{self.source_file.stem.title()}:
    """Tests for {self.source_file.stem} module"""
'''
            for func in functions:
                test_class += self.generate_function_test(func, import_path)
            test_classes.append(test_class)
        
        # Generate tests for classes
        for cls in classes:
            test_class = f'''
class Test{cls.name}:
    """Tests for {cls.name} class"""
    
    def test_{cls.name.lower()}_initialization(self):
        """Test {cls.name} initialization"""
        # TODO: Implement initialization test
        # instance = {cls.name}(...)
        # assert instance is not None
'''
            test_classes.append(test_class)
        
        # Combine all parts
        test_content = imports + "\n".join(test_classes)
        
        # Write file
        test_file_path.write_text(test_content)
        logger.info(f"✅ Generated test file: {test_file_path}")
        
        return test_file_path

    def generate(self) -> Path:
        """Main generation method"""
        return self.generate_test_file()


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate tests for Python files")
    parser.add_argument("source", type=str, help="Source Python file path")
    parser.add_argument("--output", "-o", type=str, help="Output directory (optional)")
    
    args = parser.parse_args()
    
    source_path = Path(args.source)
    if not source_path.exists():
        logger.error(f"❌ Source file not found: {source_path}")
        sys.exit(1)
    
    output_dir = Path(args.output) if args.output else None
    
    generator = TestGenerator(source_path, output_dir)
    test_file = generator.generate()
    
    print(f"\n✅ Test file generated: {test_file}")
    print(f"📝 Review and complete TODO sections in the generated file")
    print(f"🧪 Run tests with: pytest {test_file}")


if __name__ == "__main__":
    main()

