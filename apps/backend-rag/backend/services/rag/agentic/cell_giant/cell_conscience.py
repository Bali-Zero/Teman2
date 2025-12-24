"""
Cell Conscience - Fase 2 dell'architettura Cellula-Gigante.

Il Consigliere (nostra KB) calibra il ragionamento del Sovrano.

Tre livelli di intervento:
1. CALIBRAZIONI: Prezzi, team, tempi (sempre aggiunti)
2. CORREZIONI: Quando il Sovrano sbaglia (sovrascrivono)
3. ENHANCEMENTS: Esperienza pratica (arricchiscono)

"La Cellula non sostituisce il Gigante. Lo guida."
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# CORREZIONI NOTE
# La Cellula SA che il Gigante sbaglia su questi punti specifici
# Queste hanno PRIORITA MASSIMA e sovrascrivono il ragionamento
# ============================================================================

KNOWN_CORRECTIONS: dict[str, dict[str, Any]] = {
    # KBLI Errors
    "kbli 56102": {
        "trigger_patterns": [r"kbli\s*56102", r"56102.*pma", r"pma.*56102"],
        "correction": "KBLI 56102 e riservato ESCLUSIVAMENTE a UMKM locali (micro-imprese indonesiane). "
                      "Per una PMA straniera, usa SOLO KBLI 56101 (Restoran).",
        "source": "PP 28/2025, verificato su 12 casi PMA",
        "severity": "critical"
    },
    "kbli 56104": {
        "trigger_patterns": [r"kbli\s*56104.*pma", r"pma.*56104"],
        "correction": "KBLI 56104 (mobile food) puo essere problematico per PMA. "
                      "Preferisci KBLI 56101 come codice principale.",
        "source": "Esperienza pratica Bali Zero",
        "severity": "medium"
    },

    # Visa Errors
    "b211a": {
        "trigger_patterns": [r"b211a", r"b-?211-?a"],
        "correction": "B211A NON ESISTE PIU dal 2024! I nuovi codici sono: "
                      "E33G (Digital Nomad KITAS), E31A (Work KITAS), E28A (Investor KITAS).",
        "source": "Imigrasi update Marzo 2024",
        "severity": "critical"
    },
    "social visa 6 months": {
        "trigger_patterns": [r"social.*visa.*6\s*month", r"sosial.*6\s*bulan"],
        "correction": "Il Social/Cultural Visa (C316) ha durata massima 180 giorni (6 mesi), "
                      "ma richiede sponsor indonesiano e NON permette di lavorare.",
        "source": "Imigrasi regulations 2024",
        "severity": "medium"
    },

    # Capital Requirements
    "10 miliardi totale": {
        "trigger_patterns": [r"10\s*miliardi?.*total", r"investimento.*10.*miliardi?[^/]"],
        "correction": "ATTENZIONE: Per settore F&B (jasa makanan dan minuman), Art. 212 comma 3b "
                      "richiede 10 Miliardi IDR PER OGNI KBLI (campo di attività) a 5 cifre. "
                      "Tuttavia, l'OSS RBA spesso richiede di allocare l'investimento per ogni 'Progetto' (location) "
                      "per generare i permessi ambientali specifici. Pianifica con cautela.",
        "source": "PP 28/2025 Art. 212 comma 3b; Perka BKPM 4/2021",
        "severity": "critical"
    },
    "2.5 miliardi capitale": {
        "trigger_patterns": [r"2[,.]?5\s*miliardi?.*tutto", r"solo.*2[,.]?5"],
        "correction": "2.5 Miliardi IDR e il capitale VERSATO minimo, ma il piano investimento "
                      "deve essere almeno 10 Miliardi (esclusi terreni/edifici).",
        "source": "PP 28/2025",
        "severity": "high"
    },

    # Common Misconceptions
    "virtual office ovunque": {
        "trigger_patterns": [r"virtual\s*office.*qualsiasi", r"vo.*zona\s*residenziale"],
        "correction": "Virtual Office e permesso SOLO in zona commerciale (perdagangan/jasa). "
                      "Zona residenziale (kuning) = NIB rifiutato.",
        "source": "OSS requirements, 8 casi verificati",
        "severity": "high"
    },
    "pt local straniero": {
        "trigger_patterns": [r"straniero.*pt\s*local", r"wna.*pt\s*lokal", r"foreigner.*local\s*pt"],
        "correction": "Uno straniero (WNA) NON PUO possedere una PT Local. "
                      "Le opzioni legali sono: PT PMA oppure essere dipendente/consulente.",
        "source": "UU 40/2007 tentang PT",
        "severity": "critical"
    },
    "nominee arrangement": {
        "trigger_patterns": [r"nominee", r"prestanome", r"nome.*amico.*indonesiano"],
        "correction": "Nominee arrangements sono ILLEGALI in Indonesia e non proteggono l'investitore. "
                      "In caso di disputa, il nominee (indonesiano) vince sempre in tribunale.",
        "source": "Giurisprudenza indonesiana, UU 25/2007",
        "severity": "critical"
    },

    # ========================================================================
    # ROUND 1 - Nuove correzioni critiche (5)
    # ========================================================================

    # KITAS Sponsor Requirements
    "kitas_sponsor": {
        "trigger_patterns": [
            r"kitas.*senza.*sponsor",
            r"kitas.*no.*company",
            r"kitas.*freelance.*sponsor",
            r"sponsor.*non.*necessario.*kitas"
        ],
        "correction": "OGNI KITAS lavorativo (E31A, E33G, etc.) richiede OBBLIGATORIAMENTE uno sponsor. "
                      "Lo sponsor puo essere: una PT PMA (per dipendenti), un'agenzia accreditata (per digital nomad), "
                      "o un ente governativo. NON ESISTE KITAS lavorativo senza sponsor.",
        "source": "Permen 22/2023 tentang Visa dan Izin Tinggal, Art. 45-48",
        "severity": "critical"
    },

    # DNI Restrictions (Daftar Negatif Investasi)
    "dni_restrictions": {
        "trigger_patterns": [
            r"pma.*100%.*qualsiasi",
            r"straniero.*qualsiasi.*settore",
            r"no.*restrizioni.*pma",
            r"tutti.*settori.*aperti"
        ],
        "correction": "NON tutti i settori sono aperti al 100% straniero! La DNI (Daftar Negatif Investasi) "
                      "in PP 10/2021 limita molti settori: alcuni riservati a UMKM (es. KBLI 56102), "
                      "altri con cap ownership (es. real estate 49%), altri chiusi (es. gambling, armi). "
                      "SEMPRE verificare su OSS prima di procedere.",
        "source": "PP 10/2021 (Perpres Daftar Bidang Usaha), aggiornato 2024",
        "severity": "critical"
    },

    # OSS Not Automatic
    "oss_not_automatic": {
        "trigger_patterns": [
            r"oss.*automatic",
            r"nib.*instant",
            r"oss.*subito.*approvato",
            r"nib.*immediato"
        ],
        "correction": "OSS NON e automatico per tutti! Il sistema ha 3 livelli di rischio: "
                      "Basso (NIB immediato), Medio (verifica 1-2 settimane), Alto (ispezione fisica obbligatoria). "
                      "F&B e spesso rischio MEDIO/ALTO. Inoltre, NIB e solo il PRIMO step - "
                      "servono ancora SLHS, Halal, SIUP/SIUJK secondo settore.",
        "source": "PP 5/2021 tentang OSS-RBA, Art. 13-15",
        "severity": "high"
    },

    # Freelance Illegal
    "freelance_illegal": {
        "trigger_patterns": [
            r"freelance.*legale.*indonesia",
            r"lavorare.*freelance.*bali",
            r"remote.*work.*tourist",
            r"digital\s*nomad.*tourist\s*visa"
        ],
        "correction": "Lavorare come freelance con visto turistico (B1/VOA) e ILLEGALE! "
                      "Anche il remote work per clienti esteri richiede un visto appropriato: "
                      "E33G (Digital Nomad KITAS) o almeno Second Home Visa (E33A). "
                      "Violazione = deportazione + ban 1-5 anni.",
        "source": "UU 6/2011 tentang Keimigrasian, Art. 122; Permen 22/2023",
        "severity": "critical"
    },

    # Tourist Visa Work
    "tourist_visa_work": {
        "trigger_patterns": [
            r"voa.*lavorare",
            r"tourist.*visa.*work",
            r"b1.*attivita.*business",
            r"visa.*turista.*meeting"
        ],
        "correction": "Con VOA/B1 puoi fare SOLO: turismo, visite familiari, meeting esplorativi (senza contratti). "
                      "NON puoi: firmare contratti, ricevere pagamenti, gestire staff, operare business. "
                      "Per attivita business serve minimo B211B (Business Visa) o KITAS appropriato.",
        "source": "Permen 22/2023, Art. 28; UU 6/2011 Art. 52",
        "severity": "critical"
    },

    # ========================================================================
    # ROUND 2 - Nuove correzioni critiche (5)
    # ========================================================================

    # IMTA Mandatory
    "imta_mandatory": {
        "trigger_patterns": [
            r"kitas.*senza.*imta",
            r"lavorare.*no.*imta",
            r"imta.*non.*serve",
            r"direttore.*no.*work\s*permit"
        ],
        "correction": "Per LAVORARE con KITAS serve SEMPRE il permesso di lavoro (IMTA/Notifikasi)! "
                      "Anche i direttori PT PMA necessitano RPTKA approvato + Notifikasi. "
                      "Eccezione: KITAS Investor puro (E28A) senza ruolo operativo. "
                      "Lavorare senza IMTA = reato penale (UU 13/2003 Art. 185).",
        "source": "UU 13/2003 tentang Ketenagakerjaan, PP 34/2021",
        "severity": "critical"
    },

    # Tax Residency 183 Days
    "tax_resident_183": {
        "trigger_patterns": [
            r"meno.*183.*giorni.*no.*tax",
            r"sotto.*6.*mesi.*esente",
            r"non.*residente.*no.*tasse",
            r"183.*giorni.*rule"
        ],
        "correction": "La regola 183 giorni NON e cosi semplice! Diventi tax resident indonesiano se: "
                      "(1) Presente 183+ giorni in 12 mesi, OPPURE (2) Hai 'niat untuk tinggal' (intenzione di restare) "
                      "dimostrata da KITAS, casa, famiglia. Con KITAS sei AUTOMATICAMENTE tax resident "
                      "dal giorno 1, indipendentemente dai 183 giorni.",
        "source": "UU 36/2008 (PPh) Art. 2; PER-43/PJ/2011",
        "severity": "high"
    },

    # Property Ownership Foreigner
    "property_foreigner": {
        "trigger_patterns": [
            r"straniero.*compra.*terreno",
            r"foreigner.*buy.*land",
            r"wna.*hak\s*milik",
            r"freehold.*foreigner"
        ],
        "correction": "Stranieri NON possono avere Hak Milik (freehold) su terreni/edifici! "
                      "Opzioni legali: (1) Hak Pakai max 80 anni (uso personale), "
                      "(2) PT PMA con HGB (Hak Guna Bangunan) max 80 anni, "
                      "(3) Leasehold tramite notaio. Mai usare nominee per terreni!",
        "source": "UU 5/1960 (UUPA) Art. 21; PP 18/2021",
        "severity": "critical"
    },

    # CV vs PT for Foreigners
    "cv_vs_pt": {
        "trigger_patterns": [
            r"straniero.*cv",
            r"foreigner.*cv.*indonesia",
            r"wna.*commanditaire",
            r"cv.*piu.*semplice.*pma"
        ],
        "correction": "Stranieri NON possono essere soci di una CV (Commanditaire Vennootschap)! "
                      "La CV e riservata esclusivamente a WNI (cittadini indonesiani). "
                      "Per stranieri l'unica opzione e PT PMA. Usare CV con nominee = illegale.",
        "source": "KUHD Art. 19-35; UU 40/2007; OSS requirements",
        "severity": "critical"
    },

    # KITAP 5 Years Requirement
    "kitap_5_years": {
        "trigger_patterns": [
            r"kitap.*subito",
            r"permanent.*resident.*immediato",
            r"kitap.*senza.*kitas",
            r"direct.*kitap"
        ],
        "correction": "KITAP (Permanent Stay Permit) richiede MINIMO 5 anni consecutivi di KITAS valido! "
                      "Non puoi ottenere KITAP direttamente. Processo: KITAS → rinnova 5 anni → KITAP. "
                      "Eccezioni limitate: coniuge di WNI (dopo 2 anni matrimonio), figli nati in Indonesia.",
        "source": "UU 6/2011 Art. 54; Permen 22/2023 Art. 89",
        "severity": "high"
    },

    # ========================================================================
    # ROUND 3 - Nuove correzioni critiche (5)
    # ========================================================================

    # Investment Plan Must Be Proven
    "investment_plan_proof": {
        "trigger_patterns": [
            r"piano.*investimento.*carta",
            r"investment.*plan.*paper",
            r"10.*miliardi.*non.*serve.*realmente",
            r"capitale.*solo.*dichiarazione"
        ],
        "correction": "Il piano investimento 10 Miliardi IDR NON e solo su carta! "
                      "OSS traccia l'implementazione. Se dopo 2 anni non hai raggiunto almeno 50% "
                      "del piano dichiarato, rischi: revoca NIB, blacklist BKPM, problemi rinnovo KITAS. "
                      "Dichiara un piano REALISTICO, non gonfiato.",
        "source": "PP 5/2021 Art. 51; Peraturan BKPM 4/2021",
        "severity": "high"
    },

    # Personal Bank Account Business
    "bank_account_personal": {
        "trigger_patterns": [
            r"conto.*personale.*business",
            r"personal.*account.*pt",
            r"usare.*mio.*conto",
            r"rekening.*pribadi.*usaha"
        ],
        "correction": "NON usare conti personali per transazioni PT! E illegale e crea problemi: "
                      "(1) Violazione fiscale (mixing funds), (2) Problemi audit, "
                      "(3) Rischio piercing corporate veil, (4) Blocco conto da BI. "
                      "Apri SEMPRE un conto a nome della PT, richiede ~2 settimane post-NIB.",
        "source": "UU 40/2007 Art. 3; Best practices fiscali",
        "severity": "high"
    },

    # Visa Extension Timing
    "extension_overstay": {
        "trigger_patterns": [
            r"estendere.*ultimo.*giorno",
            r"extend.*last.*day",
            r"overstay.*pochi.*giorni.*ok",
            r"multa.*overstay.*bassa"
        ],
        "correction": "INIZIA l'estensione visto ALMENO 14 giorni prima della scadenza! "
                      "Overstay = 1 milione IDR/giorno di multa + deportazione + ban 1-5 anni. "
                      "Anche 1 giorno di overstay va sul record. Il processo estensione richiede "
                      "5-10 giorni lavorativi, non aspettare l'ultimo momento.",
        "source": "UU 6/2011 Art. 124; Permen 22/2023 Art. 133",
        "severity": "critical"
    },

    # Unlicensed Agents
    "agent_notaris": {
        "trigger_patterns": [
            r"agente.*economico",
            r"cheap.*agent",
            r"fixer.*500.*dollar",
            r"amico.*conosce.*sistema"
        ],
        "correction": "ATTENZIONE agli agenti non autorizzati! Solo notai registrati (PPAT) possono "
                      "costituire PT. Gli 'agenti' economici spesso: (1) Fanno documenti falsi, "
                      "(2) Non completano il processo, (3) Spariscono col deposito. "
                      "Verifica SEMPRE la licenza notarile su sito Kemenkumham.",
        "source": "UU 30/2004 tentang Jabatan Notaris; esperienza pratica",
        "severity": "critical"
    },

    # NPWP Mandatory for Directors
    "npwp_director": {
        "trigger_patterns": [
            r"direttore.*no.*npwp",
            r"npwp.*non.*obbligatorio",
            r"director.*skip.*npwp",
            r"pt.*senza.*npwp.*direttore"
        ],
        "correction": "Direttori stranieri PT PMA DEVONO avere NPWP entro 30 giorni dal KITAS! "
                      "Senza NPWP: (1) Non puoi firmare SPT annuale, (2) Problemi renewal NIB, "
                      "(3) Blocco conto bancario PT, (4) Sanzioni fiscali. "
                      "NPWP richiede: KITAS + domicilio + contratto lavoro/SK Direksi.",
        "source": "UU 28/2007 Art. 2; PER-04/PJ/2020",
        "severity": "high"
    }
}


# ============================================================================
# ENHANCEMENTS - Insights da esperienza pratica
# Arricchiscono il ragionamento con know-how reale
# ============================================================================

PRACTICAL_INSIGHTS: dict[str, list[str]] = {
    "ghost_kitchen": [
        "GoFood/GrabFood richiedono SLHS (certificato igiene) PRIMA di attivare l'account merchant",
        "Halal certification obbligatoria dal Oct 2024 per imprese medie/grandi",
        "Timeline reale setup: 8-10 settimane, non 6 come spesso quotato",
        "Zona Badung: approvazioni piu veloci di Denpasar (2-3 settimane differenza)",
        "Central Kitchen strategy: 1 location grande = 1x requisito capitale, poi distribuzione"
    ],
    "pt_pma": [
        "Capitale 2.5B IDR da versare subito su conto PT, resto secondo piano investimento",
        "Virtual Office OK ma SOLO zona commerciale - verifica PRIMA di firmare contratto",
        "Notaio: scegliere uno con esperienza PMA, non notaio generico",
        "Timeline reale costituzione: 4-6 settimane (non 2 come promesso da alcuni)",
        "RUPS annuale obbligatoria anche se socio unico"
    ],
    "kitas": [
        "E33G (Digital Nomad): richiede proof of income $2000/mese o savings $24000",
        "Processo KITAS: RPTKA → Notifikasi → Telex → VITAS → Arrival → KITAS",
        "SKTT e STM: obbligatori dopo KITAS, molti dimenticano",
        "Sponsor company: deve avere ratio 1 TKA : 10 TKI (eccezioni per startup)"
    ],
    "tax": [
        "NPW obbligatorio per direttori stranieri PMA",
        "Tax treaty Italia-Indonesia: evita doppia imposizione ma richiede documentazione",
        "PPh 21: ritenuta mensile obbligatoria per stipendi",
        "Transfer pricing: documentazione obbligatoria se transazioni con related parties"
    ],
    "f&b": [
        "SLHS: ispezione cucina da Dinas Kesehatan, budget ~2-3 juta per ispezione",
        "Halal certification: processo 3-6 mesi con BPJPH",
        "Liquor license (SKPL-A): richiede location in zona turistica + sponsor distributor",
        "Food testing: obbligatorio per prodotti confezionati, lab accreditato"
    ],

    # ========================================================================
    # ROUND 4 - Nuovi PRACTICAL_INSIGHTS (5 topic)
    # ========================================================================

    "banking": [
        "Apertura conto PT richiede: Akte, NIB, NPWP PT, KTP direttore/KITAS, SK Direksi",
        "BCA e Mandiri preferiti per business - BCA piu veloce apertura (5-7 gg)",
        "Internet banking richiede visita branch per attivazione token/mobile",
        "Conto USD: non tutte le banche lo offrono per PT - BCA/Mandiri/CIMB si",
        "Minimum balance PT: varia 1-5 juta, alcune banche richiedono saldo medio",
        "Transfer internazionale: documenti underlying (invoice/kontrak) obbligatori sopra $10k"
    ],
    "real_estate": [
        "Hak Pakai per WNA: max 30 anni + rinnovo 20 + rinnovo 30 = 80 anni totali",
        "Due diligence terreno: verifica SHM/SHGB + PBB + IMB + zonasi di persona al BPN",
        "Notaio terreni (PPAT): DIVERSO da notaio societario - verifica specializzazione",
        "Akta Jual Beli (AJB): mai firmare senza verifica completa certificato al BPN",
        "Zona hijau (verde): no costruzioni, molti terreni venduti illegalmente in zona protetta",
        "Villa rental business: richiede izi usaha pariwisata + TDUP da Dinas Pariwisata"
    ],
    "employment": [
        "Contratto TKA (straniero): WAJIB in Bahasa Indonesia, versione inglese e solo traduzione",
        "Salary minimum TKA: nessun minimo legale MA deve essere 'reasonable' per RPTKA",
        "BPJS Kesehatan: obbligatoria anche per TKA dopo 6 mesi di KITAS",
        "BPJS Ketenagakerjaan: obbligatoria dal giorno 1 per tutti i dipendenti",
        "Termination TKA: notifica a Disnaker entro 7 giorni + cancellazione IMTA",
        "Probation period: max 3 mesi, deve essere scritto nel contratto",
        "THR (bonus): obbligatorio, 1 mese stipendio, pagato 7 giorni prima Lebaran"
    ],
    "permits": [
        "NIB e solo l'inizio - molti settori richiedono izin operasional aggiuntive",
        "Izin Lingkungan: obbligatorio per attivita con impatto ambientale (incluso F&B grande)",
        "SIUP vs NIB: SIUP e stato abolito 2021, ora tutto tramite NIB/OSS",
        "Pertek (Persetujuan Teknis): alcuni settori richiedono approvazione tecnica ministeriale",
        "UKL-UPL: documento ambientale per rischio medio, timeline 2-4 settimane",
        "AMDAL: per progetti grandi/alto impatto, timeline 6+ mesi"
    ],
    "digital_nomad": [
        "E33G Second Home Visa: 5 anni, richiede proof $130k assets o $2k/mese income",
        "E33G NON permette di possedere/dirigere PT PMA - solo lavoro remoto per estero",
        "Co-working space: molti accettano E33G holder, alcuni richiedono izin usaha",
        "Crypto/trading: attivita grigia, meglio non menzionare in application",
        "Bank account con E33G: possibile ma limitato, non tutti i servizi business",
        "Exit requirement: deve uscire 1x ogni 180 giorni per mantenere status"
    ],

    # ========================================================================
    # ROUND 5 - Nuovi PRACTICAL_INSIGHTS (5 topic)
    # ========================================================================

    "import_export": [
        "NIB dengan Angka Pengenal Importir (API): necessario per importare",
        "API-U (Umum) per trading company, API-P (Produsen) per manifattura",
        "Lartas: lista prodotti con restrizioni, verifica PRIMA di importare",
        "Bea Cukai: documenti PIB obbligatori, broker doganale raccomandato per primi import",
        "HS Code: classificazione critica, errore = multa + ritardo + sequestro merce",
        "SNI: molti prodotti richiedono certificazione standard nazionale"
    ],
    "tech_startup": [
        "PT PMA tech: minimo 10B IDR piano investimento, ma disbursement graduale OK",
        "PSE (Penyelenggara Sistem Elektronik): registrazione obbligatoria per app/platform",
        "Data localization: dati utente indonesiano DEVONO essere stored in Indonesia",
        "Fintech: licenza OJK obbligatoria, processo 6-12 mesi, sandbox disponibile",
        "E-commerce: PMSE registration richiesta se transazioni sopra threshold",
        "Incubator/accelerator: possono sponsorizzare KITAS per founder stranieri"
    ],
    "hospitality": [
        "TDUP (Tanda Daftar Usaha Pariwisata): obbligatorio per hotel/villa/tour",
        "Sertifikat Laik Fungsi (SLF): obbligatorio per edifici ospitalita",
        "Star rating: non obbligatorio ma fortemente raccomandato per marketing",
        "OTA registration: Booking/Agoda richiedono TDUP + foto verifica",
        "Retribusi Daerah: tassa locale ~10% per accommodation, varia per kabupaten",
        "Foreign manager: possibile ma richiede KITAS + competency certification"
    ],
    "manufacturing": [
        "KBLI manufacturing: verifica cap ownership straniero nel settore specifico",
        "Izin Lokasi: necessario prima di costruire factory, processo BPN",
        "ANDAL/UKL-UPL: obbligatorio per manufacturing, categoria dipende da scala",
        "K3 (Keselamatan Kerja): ispezioni periodiche obbligatorie, sanzioni severe",
        "TKA ratio: manufacturing standard 1:10, alcune zone industri hanno eccezioni",
        "Kawasan Industri: setup in zona industriale semplifica molte approvazioni"
    ],
    "retail": [
        "KBLI retail: 47xx series, verifica restrizioni specifiche per categoria",
        "Location permit: mall/standalone hanno requisiti diversi",
        "Franchise: registrazione STPW obbligatoria per franchisor straniero",
        "Mini market (<400m2): in teoria riservato UMKM, ma enforcement varia",
        "Modern retail (>400m2): foreign ownership possibile ma con limitazioni",
        "POS/kasir: registrazione fiscale per ogni punto vendita"
    ],

    # ========================================================================
    # ROUND 6 - Ultimi PRACTICAL_INSIGHTS (5 topic)
    # ========================================================================

    "education": [
        "Sekolah/kursus: izin dari Dinas Pendidikan, processo lungo 6-12 mesi",
        "Online education platform: PSE registration + content moderation obbligatoria",
        "Foreign teacher: KITAS pendidikan specifico + sertifikat kompetensi",
        "Franchise education: STPW + curriculum approval dal Kemendikbud",
        "Language school: KBLI 85499, relativamente meno restrizioni",
        "Student visa sponsor: istituzione deve essere terakreditasi"
    ],
    "healthcare": [
        "Klinik: izin dari Dinas Kesehatan, requisiti molto stringenti",
        "Dokter asing: riconoscimento titolo + STR + SIP, processo 1+ anno",
        "Farmasi: licenza BPOM per prodotti, distribusi richiede CDOB",
        "Telemedicine: regolamentazione in evoluzione, verifica requisiti attuali",
        "Medical tourism: PT PMA possibile ma partnership con RS lokal raccomandata",
        "Supplement/wellness: BPOM registration per ogni prodotto, 3-6 mesi"
    ],
    "construction": [
        "Kontraktor asing: wajib joint venture con lokal, max 67% foreign share",
        "SBUJK (Sertifikat Badan Usaha Jasa Konstruksi): obbligatorio per project",
        "SKA/SKT: sertifikasi individuale per tenaga ahli konstruksi",
        "IUJK: izin usaha jasa konstruksi, categoria dipende da scala progetto",
        "Proyek pemerintah: requisiti procurement specifici, track record lokal importante",
        "Subcontract: possibile per stranieri senza JV su progetti specifici"
    ],
    "media_creative": [
        "Production house: KBLI 59xx, izin usaha perfilman da Kemendikbud",
        "Foreign crew: KITAS event-based per shooting, max 60 giorni",
        "Content creation: PSE per platform, moderasi contenuto obbligatoria",
        "Advertising: izin dari Dewan Pers per media tradizionali",
        "Music/entertainment: royalty collection tramite WAMI/KCI/YKCI",
        "IP registration: HKI per trademark/copyright, processo 6-18 mesi"
    ],
    "logistics": [
        "Freight forwarding: SIUP-JKT obbligatorio, foreign ownership limitata",
        "Warehouse: izin lokasi + IMB gudang, zona industri/pergudangan",
        "Last-mile delivery: in espansione, relativamente meno restrizioni",
        "Cold chain: requisiti aggiuntivi BPOM per food/pharma logistics",
        "Cross-border: AEO certification per velocizzare customs",
        "Fleet: izin operasional per setiap kendaraan, compliance ketat"
    ]
}


# ============================================================================
# CALIBRAZIONI - Dati specifici Bali Zero
# ============================================================================

BALI_ZERO_SERVICES: dict[str, dict[str, str]] = {
    # --- CORE SERVICES ---
    "pt_pma_setup": {
        "price": "20.000.000 IDR",
        "timeline": "30-45 giorni",
        "includes": "Akte, Minister approval, NIB, NPWP, Domicilio",
        "consultant": "Team Legal",
        "category": "company"
    },
    "virtual_office": {
        "price": "5.000.000 IDR",
        "timeline": "3-5 giorni",
        "includes": "Domicilio legale 1 anno",
        "consultant": "Team Admin",
        "category": "company"
    },
    
    # --- VISAS & KITAS (New 2025 Pricing) ---
    "visa_c1_tourism": {
        "price": "2.300.000 IDR",
        "extension": "1.700.000 IDR",
        "duration": "60 giorni",
        "notes": "Ex B211A. Estendibile 2x60gg",
        "consultant": "Team Visa",
        "category": "visa"
    },
    "visa_c2_business": {
        "price": "3.600.000 IDR",
        "extension": "1.700.000 IDR",
        "duration": "60 giorni",
        "notes": "Business meetings only",
        "consultant": "Team Visa",
        "category": "visa"
    },
    "visa_d12_1year": {
        "price": "7.500.000 IDR",
        "validity": "1 anno",
        "notes": "Business Investigation Multiple Entry",
        "category": "visa"
    },
    "visa_d12_2years": {
        "price": "10.000.000 IDR",
        "validity": "2 anni",
        "category": "visa"
    },
    
    # --- KITAS REMOTE WORKER (E33G) ---
    "kitas_e33g_offshore": {
        "price": "13.000.000 IDR",
        "timeline": "30-45 giorni",
        "includes": "Remote Worker KITAS 1 anno (Offshore) + Urgent Service included",
        "consultant": "Team Visa",
        "category": "visa"
    },
    "kitas_e33g_altus": {
        "price": "14.000.000 IDR",
        "timeline": "45-60 giorni",
        "includes": "Remote Worker KITAS 1 anno (Onshore/Conversion)",
        "consultant": "Team Visa",
        "category": "visa"
    },
    "kitas_e33g_extend": {
        "price": "10.000.000 IDR",
        "timeline": "30 giorni",
        "includes": "Estensione KITAS E33G",
        "category": "visa"
    },

    # --- KITAS INVESTOR (E28A) ---
    "kitas_e28a_investor_offshore": {
        "price": "17.000.000 IDR",
        "timeline": "30-45 giorni",
        "includes": "Investor KITAS 2 anni (Offshore)",
        "consultant": "Team Visa",
        "category": "visa"
    },
    "kitas_e28a_investor_altus": {
        "price": "19.000.000 IDR",
        "timeline": "45-60 giorni",
        "includes": "Investor KITAS 2 anni (Onshore/Conversion)",
        "category": "visa"
    },
    "kitas_e28a_investor_extend": {
        "price": "18.000.000 IDR",
        "timeline": "30 giorni",
        "includes": "Estensione Investor KITAS",
        "category": "visa"
    },

    # --- KITAS WORKING (E23) ---
    "kitas_working_offshore": {
        "price": "34.500.000 IDR",
        "timeline": "45-60 giorni",
        "includes": "Working KITAS 1 anno + IMTA + RPTKA (Offshore)",
        "consultant": "Team Visa",
        "category": "visa"
    },
    "kitas_working_altus": {
        "price": "36.000.000 IDR",
        "timeline": "60 giorni",
        "includes": "Working KITAS 1 anno (Onshore/Conversion)",
        "category": "visa"
    },
    
    # --- KITAS FREELANCE (E23 Special) ---
    "kitas_freelance_offshore": {
        "price": "25.800.000 IDR",
        "validity": "6 mesi",
        "includes": "Freelance KITAS 6 mesi (Offshore)",
        "category": "visa"
    },
    
    # --- OTHER PROCESSES ---
    "epo_exit_permit": {
        "price": "700.000 IDR",
        "notes": "+300k per urgent",
        "category": "admin"
    },
    "erp_exit_reentry": {
        "price": "800.000 IDR",
        "notes": "+500k per urgent",
        "category": "admin"
    },
    "sktt": {
        "price": "1.500.000 IDR",
        "includes": "Surat Keterangan Tempat Tinggal",
        "category": "admin"
    },
    "skck": {
        "price": "2.000.000 IDR",
        "includes": "Police Clearance Certificate",
        "category": "admin"
    },
    
    # --- URGENT SERVICES ---
    "urgent_1_day": {
        "price": "3.000.000 IDR",
        "category": "urgent"
    },
    "urgent_3_days": {
        "price": "1.000.000 IDR",
        "category": "urgent"
    }
}


async def cell_calibrate(
    query: str,
    giant_reasoning: dict[str, Any],
    user_id: str | None = None,
    user_facts: list[str] | None = None
) -> dict[str, Any]:
    """
    Fase 2: La Cellula calibra il ragionamento del Gigante.

    Tre livelli di intervento:
    1. CORREZIONI: Errori del Gigante da sovrascrivere
    2. ENHANCEMENTS: Insights pratici da aggiungere
    3. CALIBRAZIONI: Dati specifici Bali Zero

    Args:
        query: La domanda originale
        giant_reasoning: Output di giant_reason()
        user_id: ID utente per memory lookup
        user_facts: Fatti gia noti dell'utente

    Returns:
        {
            "corrections": list,    # Errori da correggere (priorita massima)
            "enhancements": list,   # Insights pratici
            "calibrations": dict,   # Prezzi, team, tempi
            "user_memory": list,    # Fatti specifici utente
            "legal_sources": list   # Fonti legali dalla KB
        }
    """
    result: dict[str, Any] = {
        "corrections": [],
        "enhancements": [],
        "calibrations": {},
        "user_memory": user_facts or [],
        "legal_sources": []
    }

    reasoning_text = giant_reasoning.get("reasoning", "").lower()
    query_lower = query.lower()

    # ========================================================================
    # 1. CORREZIONI - Cerca errori noti nel ragionamento del Gigante
    # ========================================================================
    for error_key, correction_data in KNOWN_CORRECTIONS.items():
        for pattern in correction_data["trigger_patterns"]:
            if re.search(pattern, reasoning_text, re.IGNORECASE):
                result["corrections"].append({
                    "error_key": error_key,
                    "correction": correction_data["correction"],
                    "source": correction_data["source"],
                    "severity": correction_data["severity"]
                })
                logger.warning(f"Cell correction triggered: {error_key} (severity: {correction_data['severity']})")
                break  # Una correzione per errore

    # ========================================================================
    # 2. ENHANCEMENTS - Aggiungi insights pratici basati sul topic
    # ========================================================================
    detected_topics = _detect_topics(query_lower, reasoning_text)

    for topic in detected_topics:
        if topic in PRACTICAL_INSIGHTS:
            result["enhancements"].extend(PRACTICAL_INSIGHTS[topic])
            logger.info(f"Cell enhancement added for topic: {topic}")

    # Deduplica enhancements
    result["enhancements"] = list(dict.fromkeys(result["enhancements"]))

    # ========================================================================
    # 3. CALIBRAZIONI - Dati specifici Bali Zero
    # ========================================================================
    result["calibrations"] = _get_calibrations(query_lower, detected_topics)

    # ========================================================================
    # 4. LEGAL SOURCES - Future enhancement: Query KB directly from Cell
    # ========================================================================
    # result["legal_sources"] = await search_kb(query)

    # Log summary
    logger.info(
        f"Cell calibration complete: "
        f"{len(result['corrections'])} corrections, "
        f"{len(result['enhancements'])} enhancements, "
        f"{len(result['calibrations'])} calibrations"
    )

    return result


def _detect_topics(query: str, reasoning: str) -> list[str]:
    """Rileva i topic rilevanti dalla query e dal ragionamento."""
    combined = f"{query} {reasoning}"
    topics: list[str] = []

    topic_patterns: dict[str, list[str]] = {
        # Core business topics
        "ghost_kitchen": [r"ghost\s*kitchen", r"cloud\s*kitchen", r"dark\s*kitchen", r"cucina.*delivery"],
        "pt_pma": [r"pt\s*pma", r"pma", r"penanaman\s*modal", r"foreign.*company", r"societa.*straniera"],
        "kitas": [r"kitas", r"visa.*kerja", r"work.*permit", r"e31a", r"izin\s*tinggal"],
        "tax": [r"pajak", r"tax", r"pph", r"ppn", r"npwp", r"fiscal", r"spt"],
        "f&b": [r"f&b", r"food.*beverage", r"ristorante", r"restaurant", r"cafe", r"bar", r"makanan"],

        # Round 4 topics
        "banking": [r"bank", r"conto", r"rekening", r"transfer", r"account.*business"],
        "real_estate": [r"terreno", r"property", r"villa", r"land", r"tanah", r"hak\s*pakai", r"hgb"],
        "employment": [r"dipendente", r"employee", r"karyawan", r"tka", r"kontrak\s*kerja", r"bpjs"],
        "permits": [r"izin", r"permit", r"license", r"licenza", r"perizinan", r"siup"],
        "digital_nomad": [r"digital\s*nomad", r"remote\s*work", r"e33g", r"second\s*home", r"freelance"],

        # Round 5 topics
        "import_export": [r"import", r"export", r"bea\s*cukai", r"customs", r"api-[up]", r"lartas"],
        "tech_startup": [r"startup", r"fintech", r"app", r"platform", r"pse", r"tech"],
        "hospitality": [r"hotel", r"hostel", r"tdup", r"pariwisata", r"tourism", r"akomodasi"],
        "manufacturing": [r"factory", r"pabrik", r"manufacturing", r"produksi", r"kawasan\s*industri"],
        "retail": [r"retail", r"toko", r"shop", r"franchise", r"minimarket", r"mall"],

        # Round 6 topics
        "education": [r"sekolah", r"school", r"kursus", r"training", r"education", r"pendidikan"],
        "healthcare": [r"klinik", r"clinic", r"dokter", r"doctor", r"farmasi", r"pharmacy", r"kesehatan"],
        "construction": [r"konstruksi", r"construction", r"kontraktor", r"building", r"proyek"],
        "media_creative": [r"film", r"production", r"content", r"media", r"creative", r"advertising"],
        "logistics": [r"logistics", r"warehouse", r"gudang", r"shipping", r"freight", r"delivery"]
    }

    for topic, patterns in topic_patterns.items():
        for pattern in patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                topics.append(topic)
                break

    return list(set(topics))


def _get_calibrations(query: str, topics: list[str]) -> dict[str, Any]:
    """Recupera calibrazioni specifiche Bali Zero per i topic rilevati."""
    calibrations: dict[str, Any] = {}
    query_lower = query.lower()

    # Map topics to primary services
    topic_to_services: dict[str, list[str]] = {
        "pt_pma": ["pt_pma_setup", "pt_pma_premium"],
        "kitas": ["kitas_e31a_worker", "kitas_e33g_offshore", "kitas_e28a_investor_offshore"],
        "digital_nomad": ["kitas_e33g_offshore"],
        "f&b": ["liquor_license"],
        "tax": ["npwp_personal", "monthly_tax"],
    }

    # Detect specific service needs from query
    # NOTE: Only include services that exist in BALI_ZERO_SERVICES
    specific_patterns: dict[str, str] = {
        r"investor.*kitas|kitas.*investor|e28a": "kitas_e28a_investor_offshore",  # Default to offshore
        r"e33g|digital.*nomad|remote.*worker": "kitas_e33g_offshore",  # Default to offshore
        r"liquor|alcohol|alkohol|bir|wine": "liquor_license",
        r"npwp|registrasi.*pajak|tax.*reg": "npwp_personal",
        r"monthly.*tax|pajak.*bulanan|pph.*monthly": "monthly_tax",
        r"visa.*c1|tourist.*visa|b211": "visa_c1_tourism",
    }

    matched_services: set[str] = set()

    # Check specific patterns first
    for pattern, service_key in specific_patterns.items():
        if re.search(pattern, query_lower, re.IGNORECASE):
            if service_key in BALI_ZERO_SERVICES:
                matched_services.add(service_key)

    # Then add topic-based services
    for topic in topics:
        if topic in topic_to_services:
            for service_key in topic_to_services[topic][:2]:  # Max 2 services per topic
                if service_key in BALI_ZERO_SERVICES:
                    matched_services.add(service_key)

    # Build calibrations from matched services
    # Double-check that service exists (defensive programming)
    for service_key in matched_services:
        if service_key not in BALI_ZERO_SERVICES:
            logger.warning(f"⚠️ Service key '{service_key}' not found in BALI_ZERO_SERVICES, skipping")
            continue
        
        service_info = BALI_ZERO_SERVICES[service_key]
        calibrations[service_key] = {
            "service": service_key,
            "price": service_info.get("price", "Su richiesta"),
            "timeline": service_info.get("timeline", "Variabile"),
            "includes": service_info.get("includes", "Servizio completo"),
            "consultant": service_info.get("consultant", "Team Bali Zero"),
            "category": service_info.get("category", "general")
        }

    return calibrations
