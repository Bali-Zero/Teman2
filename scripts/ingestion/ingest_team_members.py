#!/usr/bin/env python3
"""
Ingest Team Members Bio into Qdrant collection bali_zero_team
"""

import os
import sys

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not QDRANT_API_KEY:
    raise OSError("QDRANT_API_KEY environment variable is required")
COLLECTION_NAME = "bali_zero_team"
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536

# Team members with expanded bios
TEAM_MEMBERS = [
    {
        "id": "zainal",
        "name": "Zainal Abidin",
        "email": "zainal@balizero.com",
        "role": "CEO",
        "department": "management",
        "team": "management",
        "location": "Jakarta",
        "languages": ["id", "jv"],
        "bio": """Email: zainal@balizero.com
Ruolo: CEO e leader dell'organizzazione Bali Zero
Location: Jakarta | Lingue: Indonesiano, Giavanese

Zainal Abidin è il CEO di Bali Zero, guida l'intera organizzazione con uno stile di leadership esperto e autorevole. Di origine giavanese e fede musulmana, porta con sé valori di rispetto e disciplina. È il punto di riferimento per le decisioni strategiche aziendali e la direzione generale del gruppo. Per questioni di alto livello o decisioni executive, Zainal è l'interlocutore finale.""",
    },
    {
        "id": "zero",
        "name": "Zero",
        "email": "zero@balizero.com",
        "role": "Founder",
        "department": "technology",
        "team": "technology",
        "location": "Bali",
        "languages": ["it", "en", "id"],
        "bio": """Email: zero@balizero.com
Ruolo: Founder e Tech Lead
Location: Bali | Lingue: Italiano, Inglese, Indonesiano

Zero è il fondatore di Bali Zero e la mente visionaria dietro tutta la tecnologia dell'azienda. Italiano, cattolico, con uno stile diretto ed efficiente. Guida lo sviluppo tecnologico, le scelte architetturali e l'innovazione. Preferisce comunicazioni rapide e senza fronzoli. È il riferimento per tutto ciò che riguarda tech, AI, automazioni e direzione strategica del prodotto.""",
    },
    {
        "id": "ruslana",
        "name": "Ruslana",
        "email": "ruslana@balizero.com",
        "role": "Board Member",
        "department": "management",
        "team": "management",
        "location": "Ukraine",
        "languages": ["uk", "en"],
        "bio": """Email: ruslana@balizero.com
Ruolo: Board Member
Location: Ucraina | Lingue: Ucraino, Inglese

Ruslana è membro del consiglio di amministrazione di Bali Zero. Ucraina, cristiana, con una visione strategica e ispiratrice. Porta una prospettiva internazionale al board e contribuisce alle decisioni strategiche di alto livello. Sognatrice e orientata al futuro, bilancia pragmatismo e visione.""",
    },
    {
        "id": "anton",
        "name": "Anton",
        "email": "anton@balizero.com",
        "role": "Executive Consultant",
        "department": "setup",
        "team": "setup",
        "location": "Jakarta",
        "languages": ["id", "jv"],
        "bio": """Email: anton@balizero.com
Ruolo: Executive Consultant nel team Setup
Location: Jakarta | Lingue: Indonesiano, Giavanese

Anton è un consulente executive nel team Setup, specializzato nell'assistenza clienti per la costituzione di società in Indonesia. Di origine giavanese/Jakarta, conosce bene le dinamiche burocratiche locali. Ha bisogno di stimoli per essere proattivo, ma quando ingaggiato porta esperienza solida. Per pratiche di setup societario standard, Anton è un riferimento competente.""",
    },
    {
        "id": "vino",
        "name": "Vino",
        "email": "info@balizero.com",
        "role": "Junior Consultant",
        "department": "setup",
        "team": "setup",
        "location": "Jakarta",
        "languages": ["id", "jv"],
        "bio": """Email: info@balizero.com
Ruolo: Junior Consultant nel team Setup
Location: Jakarta | Lingue: Indonesiano, Giavanese (poco inglese)

Vino è un consulente junior nel team Setup. Giavanese, giovane (22 anni), parla poco inglese ed è generalmente riservato. Sta imparando il mestiere della consulenza per setup societari. Per task semplici e supporto operativo nel team Setup, Vino può essere coinvolto sotto supervisione.""",
    },
    {
        "id": "krishna",
        "name": "Krishna",
        "email": "krishna@balizero.com",
        "role": "Executive Consultant",
        "department": "setup",
        "team": "setup",
        "location": "Jakarta",
        "languages": ["id", "ban"],
        "bio": """Email: krishna@balizero.com
Ruolo: Executive Consultant nel team Setup
Location: Jakarta | Lingue: Indonesiano, Balinese

Krishna è un consulente executive nel team Setup, di origine balinese ma basato a Jakarta. Molto curioso e socievole, è sempre pronto ad imparare e a interagire con i clienti. Specializzato in procedure di setup PMA, KITAS e coordinamento con notai. Per domande su costituzione società, permessi di lavoro e pratiche burocratiche, Krishna è un ottimo punto di contatto.""",
    },
    {
        "id": "adit",
        "name": "Adit",
        "email": "consulting@balizero.com",
        "role": "Supervisor",
        "department": "setup",
        "team": "setup",
        "location": "Jakarta",
        "languages": ["id", "jv", "ban"],
        "bio": """Email: consulting@balizero.com
Ruolo: Supervisor nel team Setup
Location: Jakarta | Lingue: Indonesiano, Giavanese, Balinese

Adit è supervisor nel team Setup, con background giavanese e balinese. Estremamente leale e affettuoso con il team, a volte può essere indisciplinato ma il suo cuore è sempre al posto giusto. Insieme ad Ari forma il nucleo solido del team. Supervisiona le pratiche di setup e coordina i consultant junior.""",
    },
    {
        "id": "ari",
        "name": "Ari",
        "email": "ari.firda@balizero.com",
        "role": "Team Leader",
        "department": "setup",
        "team": "setup",
        "location": "Bandung",
        "languages": ["id", "su"],
        "bio": """Email: ari.firda@balizero.com
Ruolo: Team Leader nel team Setup
Location: Bandung | Lingue: Indonesiano, Sundanese

Ari è il Team Leader del team Setup, una storia di resilienza incredibile: da operaio in fabbrica a consulente legale. Si è sposato con Lilis a Bandung nell'ottobre 2025. Insieme ad Adit è una roccia per il team. Ha grande forza di volontà e determinazione. Per la gestione operativa del team Setup e coordinamento pratiche complesse, Ari è il riferimento.""",
    },
    {
        "id": "dea",
        "name": "Dea",
        "email": "dea@balizero.com",
        "role": "Executive Consultant",
        "department": "setup",
        "team": "setup",
        "location": "Jakarta",
        "languages": ["id", "jv"],
        "bio": """Email: dea@balizero.com
Ruolo: Executive Consultant cross-funzionale
Location: Jakarta | Lingue: Indonesiano, Giavanese

Dea è una vera "jolly" dell'azienda: lavora trasversalmente tra Setup, Marketing e Tax. Curiosa e multitasking, riesce a gestire progetti su più fronti. Per questioni che toccano più dipartimenti o per supporto flessibile, Dea è la persona giusta. Porta energia e versatilità al team.""",
    },
    {
        "id": "surya",
        "name": "Surya",
        "email": "surya@balizero.com",
        "role": "Team Leader",
        "department": "setup",
        "team": "setup",
        "location": "Jakarta",
        "languages": ["id", "jv"],
        "bio": """Email: surya@balizero.com
Ruolo: Team Leader nel team Setup
Location: Jakarta | Lingue: Indonesiano, Giavanese

Surya, soprannominato "il Professore", è Team Leader nel Setup. Perfezionista con grande attenzione all'estetica e ai dettagli. Sta lavorando per approfondire le sue competenze tecniche. Per pratiche che richiedono precisione e cura nella presentazione, Surya è meticoloso e affidabile.""",
    },
    {
        "id": "damar",
        "name": "Damar",
        "email": "damar@balizero.com",
        "role": "Junior Consultant",
        "department": "setup",
        "team": "setup",
        "location": "Jakarta",
        "languages": ["id", "jv"],
        "bio": """Email: damar@balizero.com
Ruolo: Junior Consultant nel team Setup
Location: Jakarta | Lingue: Indonesiano, Giavanese

Damar è l'ultima aggiunta al team Setup. Giovane, educato e con buone maniere. Sta imparando le basi della consulenza per setup societari. Per supporto operativo e task di apprendimento, Damar è disponibile e rispettoso.""",
    },
    {
        "id": "veronika",
        "name": "Veronika",
        "email": "tax@balizero.com",
        "role": "Tax Manager",
        "department": "tax",
        "team": "tax",
        "location": "Jakarta",
        "languages": ["id"],
        "bio": """Email: tax@balizero.com
Ruolo: Tax Manager - responsabile dipartimento fiscale
Location: Jakarta | Lingue: Indonesiano

Veronika è la Tax Manager di Bali Zero, responsabile dell'intero dipartimento fiscale. Esperta con anni di esperienza, cattolica, grande amante degli animali. Mantiene un'atmosfera rispettosa e professionale nel team. Per questioni fiscali complesse, tax compliance, audit e strategie fiscali, Veronika è il riferimento senior.""",
    },
    {
        "id": "olena",
        "name": "Olena",
        "email": "olena@balizero.com",
        "role": "Advisory",
        "department": "advisory",
        "team": "tax",
        "location": "Ukraine",
        "languages": ["uk", "en"],
        "bio": """Email: olena@balizero.com
Ruolo: Advisory per il Tax Board
Location: Ucraina | Lingue: Ucraino, Inglese

Olena è advisor ucraina per il board fiscale di Bali Zero. Porta analisi sharp e dirette, con un approccio molto professionale. Per consulenze strategiche fiscali ad alto livello e prospettive internazionali sul tax planning, Olena contribuisce con insight analitici preziosi.""",
    },
    {
        "id": "marta",
        "name": "Marta",
        "email": "marta@balizero.com",
        "role": "Advisory",
        "department": "advisory",
        "team": "advisory",
        "location": "Ukraine",
        "languages": ["uk", "en"],
        "bio": """Email: marta@balizero.com
Ruolo: Advisory generale
Location: Ucraina | Lingue: Ucraino, Inglese

Marta è advisor ucraina che porta struttura ed empatia a Bali Zero. Contribuisce con un approccio organizzato ma umano alle questioni aziendali. Per consulenze che richiedono sia metodo che sensibilità, Marta bilancia entrambi gli aspetti.""",
    },
    {
        "id": "angel",
        "name": "Angel",
        "email": "angel.tax@balizero.com",
        "role": "Tax Lead",
        "department": "tax",
        "team": "tax",
        "location": "Jakarta",
        "languages": ["id", "jv"],
        "bio": """Email: angel.tax@balizero.com
Ruolo: Tax Lead nel team fiscale
Location: Jakarta | Lingue: Indonesiano, Giavanese

Angel è Tax Lead nonostante la giovane età (21 anni). Estremamente dedicata e professionale, gestisce pratiche fiscali con serietà. Per dichiarazioni fiscali, SPT, compliance mensile e supporto tax ai clienti, Angel è un riferimento affidabile e preparato.""",
    },
    {
        "id": "kadek",
        "name": "Kadek",
        "email": "kadek.tax@balizero.com",
        "role": "Tax Lead",
        "department": "tax",
        "team": "tax",
        "location": "Bali",
        "languages": ["id", "ban"],
        "bio": """Email: kadek.tax@balizero.com
Ruolo: Tax Lead nel team fiscale
Location: Bali | Lingue: Indonesiano, Balinese

Kadek è Tax Lead basato a Bali, brillante e in crescita continua. Sta migliorando il suo inglese mentre bilancia le tradizioni balinesi con il lavoro. Per pratiche fiscali gestite da Bali e clienti nella zona, Kadek è il punto di contatto ideale. Competente e metodico.""",
    },
    {
        "id": "dewaayu",
        "name": "Dewa Ayu",
        "email": "dewa.ayu.tax@balizero.com",
        "role": "Tax Lead",
        "department": "tax",
        "team": "tax",
        "location": "Bali",
        "languages": ["id", "ban"],
        "bio": """Email: dewa.ayu.tax@balizero.com
Ruolo: Tax Lead nel team fiscale
Location: Bali | Lingue: Indonesiano, Balinese

Dewa Ayu è Tax Lead balinese, dolce e socievole. Ama TikTok e porta leggerezza al team pur mantenendo professionalità. Per pratiche fiscali da Bali con un tocco friendly, Dewa Ayu rende l'esperienza cliente piacevole e umana.""",
    },
    {
        "id": "faisha",
        "name": "Faisha",
        "email": "faisha.tax@balizero.com",
        "role": "Tax Care",
        "department": "tax",
        "team": "tax",
        "location": "Jakarta",
        "languages": ["id", "su"],
        "bio": """Email: faisha.tax@balizero.com
Ruolo: Tax Care nel team fiscale
Location: Jakarta | Lingue: Indonesiano, Sundanese

Faisha è la più giovane del team tax (19 anni), nel ruolo di Tax Care. Chiacchierona e un po' fifona, ma estremamente premurosa con i clienti. Per supporto caring ai clienti su questioni fiscali base e follow-up, Faisha porta attenzione e cura.""",
    },
    {
        "id": "rina",
        "name": "Rina",
        "email": "rina@balizero.com",
        "role": "Reception",
        "department": "operations",
        "team": "reception",
        "location": "Jakarta",
        "languages": ["id", "jv"],
        "bio": """Email: rina@balizero.com
Ruolo: Receptionist
Location: Jakarta | Lingue: Indonesiano, Giavanese

Rina è la receptionist di Bali Zero a Jakarta. Introversa ma molto gentile, accoglie clienti e visitatori con garbo. Ha bisogno di un tono delicato. Per informazioni generali, accoglienza e primo contatto in ufficio Jakarta, Rina è il volto amichevole dell'azienda.""",
    },
    {
        "id": "nina",
        "name": "Nina",
        "email": "nina@balizero.com",
        "role": "Marketing Advisory",
        "department": "marketing",
        "team": "marketing",
        "location": "Jakarta / Italy",
        "languages": ["it", "id"],
        "bio": """Email: nina@balizero.com
Ruolo: Marketing Advisory
Location: Jakarta / Italia | Lingue: Italiano, Indonesiano

Nina è advisor marketing, preferisce comunicare in italiano con Zero. Focalizzata su branding, storytelling e strategia di comunicazione. Creativa e con stile italiano. Per consulenze marketing, brand strategy e contenuti creativi, Nina porta visione e gusto estetico.""",
    },
    {
        "id": "sahira",
        "name": "Sahira",
        "email": "sahira@balizero.com",
        "role": "Marketing & Accounting",
        "department": "marketing",
        "team": "marketing",
        "location": "Jakarta",
        "languages": ["id", "jv"],
        "bio": """Email: sahira@balizero.com
Ruolo: Marketing & Accounting Specialist
Location: Jakarta | Lingue: Indonesiano, Giavanese

Sahira è specialist junior che copre sia marketing che accounting. Stilosa e ambiziosa, vuole proiettare un'immagine professionale. Per supporto marketing operativo e task di accounting base, Sahira sta crescendo e costruendo le sue competenze.""",
    },
]


def main():
    # Initialize clients
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("ERROR: OPENAI_API_KEY not set")
        sys.exit(1)

    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
    openai_client = OpenAI(api_key=openai_api_key)

    # Check/create collection
    collections = [c.name for c in qdrant.get_collections().collections]

    if COLLECTION_NAME in collections:
        # Delete existing to start fresh
        print(f"Deleting existing collection {COLLECTION_NAME}...")
        qdrant.delete_collection(COLLECTION_NAME)

    print(f"Creating collection {COLLECTION_NAME}...")
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    # Generate embeddings and insert
    points = []
    for i, member in enumerate(TEAM_MEMBERS):
        print(f"Processing {i + 1}/{len(TEAM_MEMBERS)}: {member['name']}...")

        # Generate embedding for the bio
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL, input=member["bio"]
        )
        embedding = response.data[0].embedding

        # Create point
        point = PointStruct(
            id=i + 1,
            vector=embedding,
            payload={
                "member_id": member["id"],
                "name": member["name"],
                "email": member["email"],
                "role": member["role"],
                "department": member["department"],
                "team": member["team"],
                "location": member["location"],
                "languages": member["languages"],
                "content": member["bio"],
                "source": "team_members",
                "type": "team_member_bio",
            },
        )
        points.append(point)

    # Upsert all points
    print(f"\nUpserting {len(points)} points to {COLLECTION_NAME}...")
    qdrant.upsert(collection_name=COLLECTION_NAME, points=points)

    # Verify
    info = qdrant.get_collection(COLLECTION_NAME)
    print(f"\n✅ Done! Collection {COLLECTION_NAME} now has {info.points_count} points")

    # Test search
    print("\n--- Test Search: 'chi si occupa di tax?' ---")
    test_response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL, input="chi si occupa di tax?"
    )
    test_embedding = test_response.data[0].embedding

    results = qdrant.search(
        collection_name=COLLECTION_NAME, query_vector=test_embedding, limit=3
    )

    for r in results:
        print(f"  - {r.payload['name']} ({r.payload['role']}) - score: {r.score:.3f}")


if __name__ == "__main__":
    main()
