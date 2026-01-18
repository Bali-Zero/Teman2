#!/usr/bin/env python3
"""
Test isolato per verificare la configurazione test senza dipendenze complesse
"""

import sys
import os
from pathlib import Path

# Aggiungi il path del backend
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_basic_import():
    """Test di import base senza dipendenze esterne"""
    try:
        # Test solo il modulo CORS senza dipendenze complesse
        from backend.app.setup.cors_config import get_allowed_origins
        print("✅ CORS config import successful")
        
        # Test funzione base
        origins = get_allowed_origins()
        print(f"✅ get_allowed_origins() returned: {type(origins)}")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_cors_functionality():
    """Test funzionalità CORS base"""
    try:
        from backend.app.setup.cors_config import get_allowed_origins
        
        # Test con environment variables
        os.environ['ENVIRONMENT'] = 'development'
        origins = get_allowed_origins()
        assert isinstance(origins, list)
        assert len(origins) > 0
        print("✅ CORS functionality test passed")
        
        return True
    except Exception as e:
        print(f"❌ CORS functionality test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Running isolated test configuration check...")
    
    success1 = test_basic_import()
    success2 = test_cors_functionality()
    
    if success1 and success2:
        print("\n✅ All tests passed! Configuration is working.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)
