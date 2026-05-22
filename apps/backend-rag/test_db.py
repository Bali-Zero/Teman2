import asyncio
from backend.core.database import SessionLocal
from backend.app.models import Client, Company, ClientCompanyLink
from sqlalchemy import select

async def check():
    async with SessionLocal() as db:
        # Check Ariana Campolmi
        res = await db.execute(select(Client).filter(Client.full_name.ilike('%Ariana Campolmi%')))
        ariana = res.scalars().first()
        if ariana:
            print(f"Ariana Client ID: {ariana.id}, Folder: {ariana.google_drive_folder_id}")
            # Links
            res = await db.execute(select(ClientCompanyLink).filter(ClientCompanyLink.client_id == ariana.id))
            links = res.scalars().all()
            for link in links:
                comp_res = await db.execute(select(Company).filter(Company.id == link.company_id))
                comp = comp_res.scalars().first()
                print(f"  -> Linked to Company: {comp.company_name}, Folder: {comp.google_drive_folder_id}")

        # Check Alberto Menico as Company?
        res = await db.execute(select(Company).filter(Company.company_name.ilike('%Alberto Menico%')))
        alberto_c = res.scalars().first()
        if alberto_c:
            print(f"Alberto found as COMPANY: {alberto_c.id}, Folder: {alberto_c.google_drive_folder_id}")

        res = await db.execute(select(Client).filter(Client.full_name.ilike('%Alberto Menico%')))
        alberto = res.scalars().first()
        if alberto:
            print(f"Alberto found as CLIENT: {alberto.id}, Folder: {alberto.google_drive_folder_id}")
            
asyncio.run(check())
