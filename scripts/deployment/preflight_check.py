import os
import sys


def check_file_exists(path, description):
    if not os.path.exists(path):
        print(f"❌ Missing {description}: {path}")
        return False
    print(f"✅ Found {description}: {path}")
    return True


def main():
    print("✈️  PRE-FLIGHT CHECKS")
    print("---------------------")

    root_dir = os.getcwd()
    backend_dir = os.path.join(root_dir, "apps", "backend-rag")
    mouth_dir = os.path.join(root_dir, "apps", "mouth")

    # 1. Critical Files Verification
    checks = [
        (os.path.join(backend_dir, "fly.toml"), "Backend fly.toml"),
        (os.path.join(mouth_dir, "fly.toml"), "Frontend fly.toml"),
        (
            os.path.join(backend_dir, "requirements-prod.txt"),
            "Backend requirements-prod.txt",
        ),
    ]

    all_passed = True
    for path, desc in checks:
        if not check_file_exists(path, desc):
            all_passed = False

    # 2. Secret Verification (Mock logic - in real deployment we might check fly secrets list)
    # For now, we just remind the user.
    print("\n🔐 SECRETS REMINDER:")
    print("   Ensure the following secrets are set in Fly.io:")
    print("   - DATABASE_URL")
    print("   - REDIS_URL")
    print("   - QDRANT_URL")
    print("   - GOOGLE_API_KEY")
    print("   - OPENAI_API_KEY")

    if not all_passed:
        print("\n❌ One or more pre-flight checks failed.")
        sys.exit(1)

    print("\n✅ All local pre-flight checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
