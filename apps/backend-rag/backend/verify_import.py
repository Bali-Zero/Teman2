import os
import sys
import time

print("Starting import test...")
sys.path.append(os.getcwd())
start = time.time()

try:
    print("Importing app.routers.oracle_universal...")
    from app.routers.oracle_universal import router

    print(f"✅ Import successful! Time: {time.time() - start:.2f}s")
except ImportError as e:
    print(f"❌ ImportError: {e}")
except Exception as e:
    print(f"❌ Exception: {e}")

print("Done.")
