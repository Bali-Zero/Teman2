import asyncio
import os
import sys

# Imposta PYTHONPATH se necessario, altrimenti assumiamo che il file venga eseguito dalla root
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.app.core.config import settings
from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService

def move_folders():
    try:
        print("Inizializzando Google Drive Service...")
        drive_service = ServiceAccountDriveService()
        drive = drive_service.service
        
        company_parent = getattr(settings, "gdrive_companies_folder_id", None)
        client_parent = getattr(settings, "gdrive_individuals_folder_id", None)
        
        if not company_parent or not client_parent:
            print("ERRORE: ID cartelle parent mancanti nelle configurazioni!")
            return
            
        print(f"Company Parent ID: {company_parent}")
        print(f"Client Parent ID: {client_parent}")
        
        folders_to_move = [
            {'name': 'ALBERTO MENICO', 'id': '14RlEujjd3o45DlOcOofitl4vSIGeCwD7'},
            {'name': 'Alberto Menico', 'id': '1h6zMGX-KnwHUEvQYVpexbQNvuOlenKlW'},
            {'name': 'LEONARDO FONTANA', 'id': '1MiIXzfLbBZa65CBLOfNiVhc21JL0KWbh'},
            {'name': 'Leonardo Fontana', 'id': '1WiEShiQNcOJoc8a1Tdg73nKA8D_c8egG'},
            {'name': 'Arianna Campolmi', 'id': '1b323yfGvo0wpPCwiOb1JeMpkLcgiHrRB'}
        ]
        
        for folder in folders_to_move:
            print(f"\nSpostando cartella {folder['name']} ({folder['id']})...")
            
            # Controlliamo prima se esiste e dove si trova
            try:
                f = drive.files().get(fileId=folder['id'], fields='parents').execute()
                current_parents = f.get('parents', [])
                
                if client_parent in current_parents:
                    print(f"La cartella è già in Client_CRM. Ignoro.")
                    continue
                    
                if company_parent not in current_parents:
                    print(f"ATTENZIONE: La cartella non è in Company_CRM. I suoi parents attuali sono: {current_parents}")
                    # Comunque aggiungiamo al nuovo parent e rimuoviamo dai vecchi
                    previous_parents = ",".join(current_parents)
                else:
                    previous_parents = company_parent
                    
                # Eseguiamo lo spostamento
                f = drive.files().update(
                    fileId=folder['id'],
                    addParents=client_parent,
                    removeParents=previous_parents,
                    fields='id, parents'
                ).execute()
                
                print(f"SUCCESSO! Cartella {folder['name']} spostata correttamente.")
                
            except Exception as inner_e:
                print(f"Errore durante lo spostamento di {folder['name']}: {inner_e}")
                
    except Exception as e:
        print(f"Errore critico: {e}")

if __name__ == "__main__":
    move_folders()
