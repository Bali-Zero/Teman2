import asyncio
from sqlalchemy import text
from backend.core.database import SessionLocal

async def main():
    try:
        async with SessionLocal() as session:
            # Test query
            result = await session.execute(text("SELECT id, company_name FROM companies WHERE id = 3004"))
            company = result.fetchone()
            if company:
                print(f"Found company: {company.company_name} (ID: {company.id})")
            else:
                print("Company 3004 not found")
    except Exception as e:
        print(f"DB Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
