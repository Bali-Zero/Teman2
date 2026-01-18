#!/usr/bin/env python3
"""
Python wrapper per Test Force Orchestrator
Evita problemi di import con PIL e altri moduli
"""

import sys
import os
from pathlib import Path

# Setup paths
project_root = Path(__file__).parent.parent
backend_dir = project_root / "apps" / "backend-rag"
backend_path = backend_dir / "backend"

# Add to path
sys.path.insert(0, str(backend_path))
sys.path.insert(0, str(backend_dir))

# Set environment
os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:latest")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

# Change to backend-rag directory
os.chdir(backend_dir)

# Import and run orchestrator
if __name__ == "__main__":
    import asyncio
    import logging
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] 🎭 TestForce: %(message)s",
    )
    
    try:
        # Try to import orchestrator
        from backend.agents.agents.test_force_orchestrator import main
        
        # Run
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
        
    except ImportError as e:
        # If import fails due to PIL or other issues, try direct execution
        logging.warning(f"⚠️ Import error: {e}")
        logging.info("🔄 Trying alternative import method...")
        
        # Try importing only what we need
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "test_force_orchestrator",
                backend_path / "agents" / "agents" / "test_force_orchestrator.py"
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules["test_force_orchestrator"] = module
            
            # Mock problematic imports
            import types
            mock_pil = types.ModuleType("PIL")
            sys.modules["PIL"] = mock_pil
            sys.modules["PIL.Image"] = mock_pil
            
            spec.loader.exec_module(module)
            
            if hasattr(module, "main"):
                exit_code = asyncio.run(module.main())
                sys.exit(exit_code)
            else:
                logging.error("❌ Could not find main() function")
                sys.exit(1)
                
        except Exception as e2:
            logging.error(f"❌ Alternative import also failed: {e2}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
