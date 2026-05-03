"""
Knowledge Graph Enhanced Retrieval Service

Enhances RAG retrieval by:
1. Extracting entities from user query
2. Finding related entities in KG (1-2 hops)
3. Retrieving source chunks linked to those entities
4. Augmenting context with structured graph knowledge
5. Matching golden routes for common business queries
"""

import logging
import re
from dataclasses import dataclass, field

import asyncpg

logger = logging.getLogger(__name__)


@dataclass
class GoldenRoute:
    """Pre-computed path for common business scenarios"""

    route_id: str
    name: str
    description: str
    path: list[str]
    key_conditions: list[str] = field(default_factory=list)
    estimated_timeline_months: float | None = None
    estimated_cost_range_usd: tuple[int, int] | None = None


@dataclass
class KGContext:
    """Context from Knowledge Graph for RAG augmentation"""

    entities_found: list[dict]
    relationships: list[dict]
    source_chunk_ids: list[str]
    graph_summary: str
    confidence: float
    golden_route: GoldenRoute | None = None


class KGEnhancedRetrieval:
    """
    Service for KG-enhanced RAG retrieval.

    Usage in orchestrator:
        kg_context = await kg_retrieval.get_context_for_query(query)
        # Add kg_context.graph_summary to system prompt
        # Use kg_context.source_chunk_ids for chunk retrieval
    """

    # Common Indonesian legal/business entity patterns
    # Expanded Dec 2025 for better KG coverage
    ENTITY_PATTERNS = [
        # === LAWS AND REGULATIONS ===
        (r"UU\s*(?:No\.?\s*)?\d+(?:\s*(?:Tahun|/)?\s*\d{4})?", "undang_undang"),
        (r"PP\s*(?:No\.?\s*)?\d+(?:\s*(?:Tahun|/)?\s*\d{4})?", "peraturan_pemerintah"),
        (r"Perpres\s*(?:No\.?\s*)?\d+", "perpres"),
        (r"Permen\s*(?:No\.?\s*)?\d+", "permen"),
        (r"Perda\s*(?:No\.?\s*)?\d+", "perda"),
        (r"Perka\s*(?:No\.?\s*)?\d+", "perka"),  # Peraturan Kepala
        (r"Keppres\s*(?:No\.?\s*)?\d+", "keppres"),  # Keputusan Presiden
        (r"Kepmen\s*(?:No\.?\s*)?\d+", "kepmen"),  # Keputusan Menteri
        (r"Pasal\s+\d+", "pasal"),  # Article references
        # === BUSINESS CODES ===
        (r"KBLI\s*\d{5}", "kbli"),
        (r"NIB(?:\s*\d+)?", "nib"),
        # === COMPANY TYPES ===
        (r"PT\s+PMA", "pt_pma"),
        (r"PT\s+PMDN", "pt_pmdn"),
        (r"PT\s+Perorangan", "pt_perorangan"),
        (r"(?:perusahaan|company)\s+(?:asing|foreign)", "pt_pma"),
        (r"(?:CV|Firma|Koperasi|Yayasan)", "badan_usaha"),
        (r"badan\s+hukum", "badan_hukum"),
        # === PERMITS AND LICENSES ===
        (r"OSS", "oss"),
        (r"SIUP", "siup"),
        (r"TDP", "tdp"),
        (r"NPWP", "npwp"),
        (r"IMB", "imb"),  # Izin Mendirikan Bangunan
        (r"AMDAL", "amdal"),  # Analisis Dampak Lingkungan
        (r"izin\s+(?:usaha|lokasi|lingkungan|prinsip)", "izin_usaha"),
        (r"izin\s+tinggal", "izin_tinggal"),
        (r"sertifikat\s+standar", "sertifikat"),
        # === VISAS AND IMMIGRATION ===
        (r"KITAS", "kitas"),
        (r"KITAP", "kitap"),
        (r"VITAS", "vitas"),
        (r"E-?VISA", "evisa"),
        (r"ITAS", "kitas"),  # Without K prefix
        (r"(?:visa\s+)?(?:kerja|work)", "kitas"),
        (r"RPTKA", "rptka"),
        (r"IMTA", "imta"),
        (r"TKA", "tka"),  # Tenaga Kerja Asing
        (r"tenaga\s+kerja\s+asing", "tka"),
        (r"imigrasi", "imigrasi"),
        (r"paspor", "paspor"),
        # === TAX TYPES ===
        (r"PPh\s*(?:Pasal\s*)?\d+", "pph"),
        (r"PPh\s*21", "pph_21"),
        (r"PPh\s*23", "pph_23"),
        (r"PPh\s*25", "pph_25"),
        (r"PPh\s*29", "pph_29"),
        (r"PPN", "ppn"),
        (r"PBB", "pbb"),
        (r"Bea\s+Materai", "bea_materai"),
        (r"pajak\s+(?:penghasilan|pertambahan)", "tax"),
        (r"faktur\s+pajak", "faktur_pajak"),
        (r"SPT", "spt"),
        # === PROCEDURES ===
        (r"pendaftaran", "pendaftaran"),
        (r"permohonan", "permohonan"),
        (r"perpanjangan", "perpanjangan"),
        (r"pencabutan", "pencabutan"),
        (r"perubahan", "perubahan"),
        # === SANCTIONS ===
        (r"sanksi\s+(?:administratif|pidana)", "sanksi"),
        (r"denda", "denda"),
        # === COSTS AND FEES ===
        (r"biaya", "biaya"),
        (r"tarif", "biaya"),
        (r"retribusi", "biaya"),
        (r"(?:Rp\.?\s*)?[\d.,]+(?:\s*(?:juta|ribu|miliar))?", "amount"),  # Money amounts
        # === TIME PERIODS ===
        (r"\d+\s*(?:hari|bulan|tahun)", "jangka_waktu"),
        (r"jangka\s+waktu", "jangka_waktu"),
    ]

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        """
        Initialize KG Enhanced Retrieval.

        Args:
            db_pool: Database connection pool
        """
        self.db_pool = db_pool
        logger.info("KGEnhancedRetrieval initialized")

    def extract_entities_from_query(self, query: str) -> list[tuple[str, str]]:
        """
        Extract potential entity mentions from user query.

        Returns:
            List of (mention, entity_type) tuples
        """
        entities = []
        query_upper = query.upper()

        for pattern, entity_type in self.ENTITY_PATTERNS:
            matches = re.finditer(pattern, query_upper, re.IGNORECASE)
            for match in matches:
                mention = match.group(0).strip()
                entities.append((mention, entity_type))

        # Deduplicate while preserving order
        seen = set()
        unique_entities = []
        for e in entities:
            if e[0] not in seen:
                seen.add(e[0])
                unique_entities.append(e)

        return unique_entities

    async def find_kg_entities(
        self, mentions: list[tuple[str, str]], limit_per_mention: int = 3,
    ) -> list[dict]:
        """
        Find KG entities matching the extracted mentions.

        Uses fuzzy matching on entity name.
        """
        if not mentions:
            return []

        found_entities = []

        async with self.db_pool.acquire() as conn:
            for mention, entity_type in mentions:
                # Normalize mention for search
                # SECURITY: Sanitize SQL wildcards to prevent injection/unexpected behavior
                search_term = self._sanitize_search_term(mention)

                # Search by name similarity and optionally by type
                rows = await conn.fetch(
                    """
                    SELECT entity_id, entity_type, name, confidence,
                           source_chunk_ids
                    FROM kg_nodes
                    WHERE LOWER(name) LIKE $1
                       OR entity_type = $2
                    ORDER BY confidence DESC
                    LIMIT $3
                """,
                    f"%{search_term}%",
                    entity_type,
                    limit_per_mention,
                )

                for row in rows:
                    entity = dict(row)
                    entity["matched_mention"] = mention
                    found_entities.append(entity)

        return found_entities

    async def get_related_entities(
        self, entity_ids: list[str], max_depth: int = 2, limit: int = 20,
    ) -> tuple[list[dict], list[dict]]:
        """
        Get entities related to the given entities via KG edges.

        Uses a recursive CTE for efficient multi-hop traversal in a single SQL query.
        Tested on production (114k nodes): 2-hop ~100-250ms, 3-hop safe on moderate nodes.
        Auto-downgrades to 2-hop for highly-connected seeds (>500 edges).

        Returns:
            Tuple of (related_entities, relationships)
        """
        if not entity_ids:
            return [], []

        # Cap depth to prevent runaway queries
        max_depth = min(max_depth, 3)

        async with self.db_pool.acquire() as conn:
            # Guard: check seed connectivity, downgrade depth for super-hubs
            if max_depth > 2:
                edge_count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM kg_edges
                    WHERE source_entity_id = ANY($1) OR target_entity_id = ANY($1)
                    """,
                    entity_ids,
                )
                if edge_count > 500:
                    max_depth = 2
                    logger.info(
                        f"KG traversal: seed has {edge_count} edges, downgrading to 2-hop"
                    )

            # Single recursive CTE with directional join
            edges = await conn.fetch(
                """
                WITH RECURSIVE traversal AS (
                    SELECT e.relationship_id, e.source_entity_id, e.target_entity_id,
                           e.relationship_type, e.confidence, e.source_chunk_ids,
                           1 AS depth
                    FROM kg_edges e
                    WHERE e.source_entity_id = ANY($1) OR e.target_entity_id = ANY($1)

                    UNION ALL

                    SELECT e.relationship_id, e.source_entity_id, e.target_entity_id,
                           e.relationship_type, e.confidence, e.source_chunk_ids,
                           t.depth + 1
                    FROM kg_edges e
                    JOIN traversal t ON (
                        e.source_entity_id = t.target_entity_id
                        OR e.target_entity_id = t.source_entity_id
                    )
                    WHERE t.depth < $2
                )
                SELECT DISTINCT ON (tr.relationship_id)
                       tr.relationship_id, tr.source_entity_id, tr.target_entity_id,
                       tr.relationship_type, tr.confidence, tr.source_chunk_ids,
                       s.name as source_name, s.entity_type as source_type,
                       t.name as target_name, t.entity_type as target_type
                FROM traversal tr
                JOIN kg_nodes s ON tr.source_entity_id = s.entity_id
                JOIN kg_nodes t ON tr.target_entity_id = t.entity_id
                ORDER BY tr.relationship_id, tr.confidence DESC
                LIMIT $3
                """,
                entity_ids,
                max_depth,
                limit,
            )

            relationships = [dict(edge) for edge in edges]

            # Collect all discovered entity IDs
            visited_entity_ids = set(entity_ids)
            for edge_dict in relationships:
                visited_entity_ids.add(edge_dict["source_entity_id"])
                visited_entity_ids.add(edge_dict["target_entity_id"])

            # Fetch details of related entities (excluding seeds)
            new_ids = list(visited_entity_ids - set(entity_ids))
            related_entities = []
            if new_ids:
                rows = await conn.fetch(
                    """
                    SELECT entity_id, entity_type, name, confidence, source_chunk_ids
                    FROM kg_nodes
                    WHERE entity_id = ANY($1)
                    """,
                    new_ids,
                )
                related_entities = [dict(r) for r in rows]

        return related_entities, relationships

    def _sanitize_search_term(self, mention: str) -> str:
        r"""
        Sanitize mention for SQL LIKE query.

        Removes SQL wildcard characters (%, _, \) that could cause:
        - SQL injection risks
        - Unexpected wildcard matching behavior

        Args:
            mention: Raw entity mention from query

        Returns:
            Sanitized search term safe for SQL LIKE
        """
        import re

        # Remove SQL wildcard chars and normalize
        cleaned = re.sub(r"[%_\\]", "", mention)
        return cleaned.replace(".", "").replace(" ", "%").lower()

    async def get_source_chunks(self, entity_ids: list[str]) -> list[str]:
        """
        Get all source chunk IDs linked to the given entities.
        """
        if not entity_ids:
            return []

        chunk_ids = set()

        async with self.db_pool.acquire() as conn:
            # Get chunks from entities
            rows = await conn.fetch(
                """
                SELECT source_chunk_ids
                FROM kg_nodes
                WHERE entity_id = ANY($1) AND source_chunk_ids IS NOT NULL
            """,
                entity_ids,
            )

            for row in rows:
                if row["source_chunk_ids"]:
                    chunk_ids.update(row["source_chunk_ids"])

            # Get chunks from relationships
            rows = await conn.fetch(
                """
                SELECT source_chunk_ids
                FROM kg_edges
                WHERE (source_entity_id = ANY($1) OR target_entity_id = ANY($1))
                  AND source_chunk_ids IS NOT NULL
            """,
                entity_ids,
            )

            for row in rows:
                if row["source_chunk_ids"]:
                    chunk_ids.update(row["source_chunk_ids"])

        return list(chunk_ids)

    # Golden route patterns for common business scenarios
    GOLDEN_ROUTES = {
        "pt_pma_setup": GoldenRoute(
            route_id="pt_pma_setup",
            name="PT PMA Company Setup",
            description="Complete process to establish a foreign-owned company in Indonesia",
            path=[
                "Choose business sector (check DNI/Positive List)",
                "Prepare documents (passport, domicile letter)",
                "Reserve company name via AHU Online",
                "Obtain NIB via OSS (Online Single Submission)",
                "Apply for business licenses (SIUP, etc.)",
                "Open bank account",
                "Register for taxes (NPWP)",
            ],
            key_conditions=[
                "Minimum capital: IDR 10 billion",
                "Paid-up capital: minimum 25%",
                "Foreign ownership limits apply per sector",
            ],
            estimated_timeline_months=0.5,  # Starting from 2 weeks
            estimated_cost_range_usd=None,  # Usare PricingTool per prezzi reali
        ),
        "kitas_work": GoldenRoute(
            route_id="kitas_work",
            name="Work KITAS Application",
            description="Process to obtain work permit and stay permit for foreign workers",
            path=[
                "Apply for TKA allocation quota and IMTA via SPKP system (Kementerian Ketenagakerjaan)",
                "Apply for E-Visa online via imigrasi.go.id",
                "Enter Indonesia with approved visa",
                "Convert to KITAS at immigration office within 60 days",
                "Complete biometrics and obtain KITAS card",
            ],
            key_conditions=[
                "Sponsor company must be registered",
                "Position must be on approved list",
                "Valid passport with 18+ months validity",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "nib_oss": GoldenRoute(
            route_id="nib_oss",
            name="NIB Registration via OSS",
            description="Obtain business identification number through OSS system",
            path=[
                "Register account on OSS (Online Single Submission) portal",
                "Complete company profile",
                "Select KBLI business codes",
                "Submit NIB application",
                "Receive NIB (usually instant)",
                "Apply for relevant sector licenses",
            ],
            key_conditions=[
                "Company must be legally registered",
                "Valid NPWP required",
                "Correct KBLI codes selection",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        # === Business scenario routes ===
        "restaurant_foreigner": GoldenRoute(
            route_id="restaurant_foreigner",
            name="Open Restaurant as Foreigner in Indonesia",
            description="Complete process to open a restaurant (F&B) as a foreign investor in Bali/Indonesia",
            path=[
                "Establish PT PMA (foreign-owned company) - minimum IDR 10 billion capital",
                "Select KBLI 56101 (Restoran/Rumah Makan) as primary business code",
                "Obtain NIB via OSS (Online Single Submission)",
                "Apply for business licenses: Sertifikat Standar (medium risk) or Izin (high risk)",
                "Obtain food safety certificate (Sertifikat Laik Higiene Sanitasi)",
                "Apply for liquor license (SIUP-MB) if serving alcohol",
                "Apply for TKA allocation and IMTA via SPKP for investor/director position",
                "Apply for E-Visa online, then convert to KITAS E28G (Investor)",
                "Register for NPWP (tax number) and PKP if turnover > IDR 4.8 billion/year",
                "Obtain location permit and building permit (IMB/PBG) if needed",
            ],
            key_conditions=[
                "KBLI 56101 is open for foreign investment (PMA) with conditions",
                "F&B sector requires Sertifikat Standar or Izin based on risk level",
                "Foreign ownership up to 100% allowed for restaurants via PMA",
                "Must hire Indonesian staff (minimum ratio applies)",
                "Halal certification recommended but not mandatory for non-halal restaurants",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "import_export_business": GoldenRoute(
            route_id="import_export_business",
            name="Import/Export Business Setup",
            description="Establish an import/export trading company as a foreigner in Indonesia",
            path=[
                "Establish PT PMA with trading KBLI codes",
                "Select KBLI: 46100 (wholesale), 47 series (retail), or specific commodity codes",
                "Obtain NIB via OSS (Online Single Submission)",
                "Apply for API-U (General Importer ID) or API-P (Producer Importer ID)",
                "Register as Eksportir Terdaftar if exporting regulated goods",
                "Obtain customs registration (NIK Kepabeanan) from DJBC",
                "Apply for specific sector licenses (e.g., BPOM for food/cosmetics, Kementan for agriculture)",
                "Sponsor yourself for KITAS E28G (Investor) or hire with KITAS E28A (Worker)",
                "Register for NPWP and PKP (mandatory for import/export)",
                "Set up bonded warehouse or free trade zone access if applicable",
            ],
            key_conditions=[
                "Negative Investment List restricts certain commodities for foreigners",
                "API-U required for general trading, API-P for own production materials",
                "Some commodities require Surveyor Report (LS/LPS) for import",
                "Export of natural resources may require downstream processing",
                "Minimum capital IDR 10 billion for PT PMA",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "tech_company_digital": GoldenRoute(
            route_id="tech_company_digital",
            name="Tech/Digital Company Setup",
            description="Establish a technology or digital services company as a foreigner",
            path=[
                "Establish PT PMA with tech KBLI codes",
                "Select KBLI: 62011 (software), 62019 (IT services), 63111 (data processing)",
                "Obtain NIB via OSS (Online Single Submission)",
                "Register as Penyelenggara Sistem Elektronik (PSE) with Kominfo",
                "Apply for Tanda Daftar PSE (electronic system registration)",
                "Comply with PP 71/2019 data localization requirements if applicable",
                "Sponsor yourself for KITAS E28G (Investor) or E28A (Worker/Director)",
                "Apply for IMTA for foreign tech workers",
                "Register for NPWP and digital tax obligations",
                "Consider Sertifikasi ISO 27001 for data security compliance",
            ],
            key_conditions=[
                "Tech/IT sector generally 100% foreign ownership allowed",
                "PSE registration mandatory for all electronic systems serving Indonesian users",
                "Data localization rules apply for strategic/public data",
                "Digital tax (PPN PMSE) applies to digital services",
                "KBLI 62011-62019 are low-to-medium risk (faster licensing)",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "investor_kitas_retirement": GoldenRoute(
            route_id="investor_kitas_retirement",
            name="Investor KITAS or Retirement KITAS",
            description="Obtain long-term stay permit for investors or retirees in Indonesia",
            path=[
                "Choose KITAS type: E28G (Investor) or E31E (Retirement/Lansia)",
                "For Investor: Establish PT PMA or invest in Indonesian company",
                "For Retirement: Prove pension/passive income min USD 2,500/month",
                "Prepare documents: passport (18+ months validity), health certificate",
                "Apply for E-Visa online via imigrasi.go.id",
                "Enter Indonesia and convert to KITAS at immigration office",
                "Complete biometrics and obtain KITAS card (valid 1-2 years)",
                "Apply for KITAP (permanent stay) after 3 consecutive years on KITAS",
                "Renew KITAS annually or apply for Second Home Visa (5-10 years)",
            ],
            key_conditions=[
                "Investor KITAS requires active PT PMA with IMTA approval",
                "Retirement KITAS: minimum age 55, proof of income/pension",
                "Second Home Visa: show USD 130,000 in bank account",
                "KITAP available after 3 years continuous KITAS (good behavior)",
                "Must report to immigration every 90 days (STM)",
                "Cannot work on Retirement KITAS - investment only",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "hire_foreign_worker": GoldenRoute(
            route_id="hire_foreign_worker",
            name="Hire Foreign Worker (TKA Process)",
            description="Complete process to legally employ a foreign worker in Indonesia",
            path=[
                "Apply for TKA allocation quota to Kementerian Ketenagakerjaan",
                "Apply for IMTA (Izin Mempekerjakan TKA) via SPKP system",
                "Receive IMTA approval with approved positions and duration",
                "Pay DKP-TKA compensation fund (USD 100/month per foreign worker)",
                "Worker applies for E-Visa online via imigrasi.go.id",
                "Worker enters Indonesia, converts to KITAS E28A at immigration office",
                "Register worker with BPJS Kesehatan and BPJS Ketenagakerjaan",
                "Appoint Indonesian understudy (pendamping TKA) for knowledge transfer",
                "Renew IMTA and KITAS annually (max 5 years per position)",
            ],
            key_conditions=[
                "Position must be on approved list (not in Jabatan Tertutup for TKA)",
                "Company must have minimum 10 Indonesian employees per 1 TKA",
                "DKP-TKA: USD 100/month mandatory compensation fund",
                "Indonesian understudy (pendamping) is legally required",
                "IMTA valid for max 5 years, renewable",
                "Foreign worker must have relevant qualifications/experience",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        # === Real Estate / Property routes ===
        "villa_rental_business": GoldenRoute(
            route_id="villa_rental_business",
            name="Villa Rental Business (Sewa Villa)",
            description="Set up a villa rental or property rental business as a foreigner in Bali/Indonesia",
            path=[
                "Establish PT PMA with accommodation KBLI codes",
                "Select KBLI 55130 (Penyediaan Akomodasi Jangka Pendek - Villa) as primary code",
                "Optionally add KBLI 55120 (Pondok Wisata/Homestay) or 55191 (Akomodasi Lainnya)",
                "Obtain NIB via OSS (Online Single Submission)",
                "Apply for Sertifikat Standar (accommodation is medium-high risk)",
                "Obtain Tanda Daftar Usaha Pariwisata (TDUP) from local tourism office",
                "Secure property rights: Hak Pakai or Hak Sewa (foreigners cannot hold Hak Milik)",
                "Obtain PBG (Persetujuan Bangunan Gedung) if building/renovating",
                "Apply for SLF (Sertifikat Laik Fungsi) - building worthiness certificate",
                "Register with local tax office (Pajak Hotel for accommodation tax)",
                "Sponsor yourself for KITAS E28G (Investor KITAS)",
                "Register on OTA platforms (Airbnb, Booking.com) with NIB/TDUP",
            ],
            key_conditions=[
                "KBLI 55130 covers short-term villa rental (daily/weekly stays)",
                "Foreigners CANNOT own land (Hak Milik) - use Hak Pakai (25+20+20 years) or lease",
                "PT PMA required for foreign-owned villa business (not personal name)",
                "Pajak Hotel (accommodation tax) typically 10% applies to villa rentals",
                "TDUP mandatory for all tourism accommodation businesses",
                "Building must comply with local zoning (tata ruang) - check green/yellow zone",
                "Bali specific: Perda Desa Adat may apply (village customary rules)",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "hotel_business": GoldenRoute(
            route_id="hotel_business",
            name="Hotel Business Setup",
            description="Establish a hotel or boutique hotel business as a foreigner in Indonesia",
            path=[
                "Establish PT PMA with hotel KBLI codes",
                "Select primary KBLI: 55101-55106 (Bintang 1-5) or 55111 (Hotel Non-Bintang)",
                "Obtain NIB via OSS (Online Single Submission)",
                "Apply for Izin (hotels are high-risk classification in OSS)",
                "Obtain Tanda Daftar Usaha Pariwisata (TDUP) for hotel category",
                "Apply for hotel star classification from Kemenparekraf (optional but recommended)",
                "Secure land rights: Hak Pakai or HGB (Hak Guna Bangunan) for PT PMA",
                "Obtain PBG (Persetujuan Bangunan Gedung) for hotel construction/renovation",
                "Obtain SLF (Sertifikat Laik Fungsi) after construction",
                "Apply for Sertifikat Laik Higiene Sanitasi for F&B areas",
                "Obtain AMDAL/UKL-UPL (environmental impact assessment) based on scale",
                "Register for NPWP, PKP, and Pajak Hotel",
                "Apply for KITAS E28G (Investor) and IMTA for foreign hotel staff",
                "Register with PHRI (Perhimpunan Hotel dan Restoran Indonesia) - recommended",
            ],
            key_conditions=[
                "Hotels classified as high-risk in OSS (requires Izin, not just Sertifikat Standar)",
                "Star classification (1-5 bintang) requires meeting Kemenparekraf standards",
                "AMDAL required for hotels > certain room threshold (varies by region)",
                "Foreign ownership up to 100% allowed for hotels via PT PMA",
                "HGB (Hak Guna Bangunan) allows building on land for 30+20+20 years",
                "Pajak Hotel 10% + PPh final on rental income",
                "Fire safety certificate (Sertifikat Keselamatan Kebakaran) required",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "real_estate_developer": GoldenRoute(
            route_id="real_estate_developer",
            name="Real Estate Development Business",
            description="Set up a property development company as a foreigner in Indonesia",
            path=[
                "Establish PT PMA with real estate KBLI codes",
                "Select KBLI: 68110 (Real Estate Milik Sendiri/Sewa), 68111-68112 (specific types)",
                "Optionally add KBLI 41011-41020 (Construction) if building yourself",
                "Obtain NIB via OSS (Online Single Submission)",
                "Apply for Izin Mendirikan Bangunan/PBG for each project",
                "Obtain Izin Lokasi from local government (land acquisition permit)",
                "Conduct AMDAL (environmental impact assessment) for large developments",
                "Secure land via HGB (Hak Guna Bangunan) for PT PMA",
                "Register with REI (Real Estate Indonesia) association - recommended",
                "Obtain SLF for completed buildings before handover to buyers",
                "Register for NPWP, PKP, and property-related taxes (BPHTB, PBB)",
                "Apply for KITAS E28G for yourself and IMTA for foreign construction staff",
            ],
            key_conditions=[
                "PT PMA minimum capital IDR 10 billion for real estate",
                "Foreigners cannot hold Hak Milik - use HGB (30+20+20 years) for development",
                "Izin Lokasi required before land acquisition",
                "AMDAL mandatory for developments above certain thresholds",
                "Strata title (SHMSRS) can be sold to foreign buyers as Hak Pakai",
                "PPh Final 2.5% on property sale, BPHTB 5% on acquisition",
                "Negative Investment List may restrict certain residential development for PMA",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "property_management": GoldenRoute(
            route_id="property_management",
            name="Property Management Company",
            description="Set up a property/villa management company managing properties for owners",
            path=[
                "Establish PT PMA with property management KBLI codes",
                "Select KBLI: 68200 (Real Estate Atas Dasar Balas Jasa/Fee) or 68210 (Property Management)",
                "Optionally add KBLI 55130 (Villa Accommodation) if also renting",
                "Obtain NIB via OSS (Online Single Submission)",
                "Apply for Sertifikat Standar (property management is medium risk)",
                "Draft management agreements with property owners (legal templates)",
                "Set up trust account for owner rental income separation",
                "Register for NPWP and withhold PPh 23 (2%) on management fees",
                "Apply for KITAS E28G (Investor KITAS)",
                "Register on booking platforms as property manager",
                "Obtain TDUP if managing tourist accommodation properties",
            ],
            key_conditions=[
                "Property management (fee-based) is lower risk than ownership/development",
                "KBLI 68200 covers real estate services on fee/commission basis",
                "Management company holds no land rights - manages for owners",
                "Must withhold and report taxes on behalf of property owners",
                "Foreign ownership up to 100% allowed for property management services",
                "Lower capital requirement than real estate development",
                "Consider partnership with local notaris for property agreements",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "buy_property_foreigner": GoldenRoute(
            route_id="buy_property_foreigner",
            name="Buy Property as Foreigner in Indonesia",
            description="Legal options for foreigners to acquire property/land rights in Indonesia",
            path=[
                "Understand land title types: Hak Milik (PROHIBITED for foreigners), Hak Pakai, HGB, Hak Sewa",
                "Option A - Hak Pakai (Right to Use): Available to foreigners with KITAS/KITAP, 25+20+20 years",
                "Option B - Through PT PMA: Company holds HGB (30+20+20 years), you own the company",
                "Option C - Hak Sewa (Lease): Long-term lease agreement (25-30 years, renewable)",
                "Option D - Strata Title (Apartemen/Kondominium): Buy apartment unit as Hak Pakai",
                "Conduct due diligence: verify land certificate (BPN), check zoning, check disputes",
                "Engage PPAT (Pejabat Pembuat Akta Tanah) for property transfer deed",
                "Pay taxes: BPHTB 5% (buyer), PPh Final 2.5% (seller)",
                "Register transfer at BPN (Badan Pertanahan Nasional)",
                "For Hak Pakai: must have valid KITAS/KITAP, property for personal residence only",
                "For PT PMA route: establish company first, then acquire under HGB",
            ],
            key_conditions=[
                "Foreigners CANNOT own Hak Milik (freehold) - this is Constitutional (UUPA 1960)",
                "Nominee arrangements (using Indonesian name) are ILLEGAL and unenforceable",
                "Hak Pakai for foreigners: max 25 years, extendable 20+20 = 65 years total",
                "HGB for PT PMA: max 30 years, extendable 20+20 = 70 years total",
                "Minimum property value for foreign Hak Pakai varies by region",
                "Bali minimum: IDR 5 billion for house, IDR 3 billion for apartment",
                "Only one residential property per foreigner (Hak Pakai personal)",
                "Must not be in abandoned state for > 3 years (risk of revocation)",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        # === Visa scenario routes ===
        "visa_tourism_c1_d1": GoldenRoute(
            route_id="visa_tourism_c1_d1",
            name="Tourism Visa (C1 Single Entry / D1 Multiple Entry)",
            description="Apply for a tourism visa to visit Indonesia",
            path=[
                "Choose visa type: C1 (single entry, 60 days) or D1 (multiple entry, 60 days per visit)",
                "Apply online via molina.imigrasi.go.id or e-Visa portal",
                "Upload required documents: passport (18+ months validity), photo, return ticket, hotel booking",
                "Pay visa fee (PNBP) online",
                "Receive e-Visa approval via email",
                "Enter Indonesia at designated immigration checkpoint",
                "C1: extendable 2x30 days at immigration office (total max 120 days)",
                "D1: valid for multiple entries within 1-2 years, max 60 days per visit",
            ],
            key_conditions=[
                "C1 is single entry, D1 is multiple entry",
                "C1 extendable at local immigration office (2x30 days)",
                "D1 cannot be extended per visit but allows re-entry",
                "Alternative: Visa on Arrival (B1) for 30 days, extendable 1x30 days",
                "E-VOA available for quick processing at airport",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "visa_business_c2_d2": GoldenRoute(
            route_id="visa_business_c2_d2",
            name="Business Visit Visa (C2 Single Entry / D2 Multiple Entry)",
            description="Apply for a business visit visa for meetings, conferences, or business exploration",
            path=[
                "Choose visa type: C2 (single entry, 60 days) or D2 (multiple entry, 60 days per visit)",
                "Obtain sponsor letter from Indonesian company or business partner",
                "Apply online via molina.imigrasi.go.id or e-Visa portal",
                "Upload documents: passport, sponsor letter, company letter, photo",
                "Pay visa fee (PNBP) online",
                "Receive e-Visa approval",
                "Enter Indonesia for business activities (meetings, negotiations, conferences)",
                "C2: extendable 2x60 days at immigration office",
                "D2: valid for multiple entries, max 60 days per stay",
            ],
            key_conditions=[
                "Business visit does NOT allow working or earning income in Indonesia",
                "Requires sponsor (Indonesian company, organization, or government entity)",
                "C2 extendable up to 180 days total",
                "D2 valid 1-2 years with multiple entries",
                "For actual work: need KITAS E23/E28 instead",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "visa_pre_investment_d12": GoldenRoute(
            route_id="visa_pre_investment_d12",
            name="Pre-Investment Visa (D12)",
            description="Visa for business investigation and pre-investment activities in Indonesia",
            path=[
                "Apply for D12 visa online via e-Visa portal (imigrasi.go.id)",
                "Provide documents: passport, business plan/proposal, financial proof",
                "Obtain sponsor letter (can be from BKPM/investment board or local partner)",
                "Pay visa fee (PNBP)",
                "Receive D12 visa (valid 60-90 days per entry, multiple entry)",
                "Enter Indonesia to explore business opportunities, visit locations, meet partners",
                "Use D12 period to set up PT PMA if proceeding with investment",
                "Convert to KITAS E28G (Investor) once company is established",
            ],
            key_conditions=[
                "D12 is specifically for pre-investment investigation",
                "Max stay 60-90 days per entry, extendable",
                "Multiple entry valid up to 1 year",
                "Does NOT allow working - only investigation/exploration",
                "Good stepping stone before PT PMA + Investor KITAS",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "visa_digital_nomad_e33g": GoldenRoute(
            route_id="visa_digital_nomad_e33g",
            name="Digital Nomad / Remote Worker Visa (E33G)",
            description="KITAS for digital nomads and remote workers working for foreign employers",
            path=[
                "Apply for E-Visa E33G online via imigrasi.go.id",
                "Provide documents: passport, proof of remote employment/freelance income",
                "Show proof of income (minimum threshold applies)",
                "Provide health insurance valid in Indonesia",
                "Pay visa fee (PNBP)",
                "Receive VITAS E33G approval",
                "Enter Indonesia and convert VITAS to KITAS E33G at immigration",
                "Complete biometrics at immigration office",
                "KITAS E33G valid for 1 year, renewable",
            ],
            key_conditions=[
                "Must work for foreign company or be freelancer with foreign clients",
                "Cannot work for Indonesian companies on this visa",
                "No Indonesian employer/sponsor needed",
                "Income earned must be from outside Indonesia",
                "Health insurance coverage in Indonesia required",
                "SKTT reporting required every 90 days",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "visa_spouse_family_e31": GoldenRoute(
            route_id="visa_spouse_family_e31",
            name="Spouse / Family Reunion KITAS (E31 Series)",
            description="KITAS for spouse or family members of Indonesian citizens or KITAS holders",
            path=[
                "Determine KITAS type: E31A (spouse of Indonesian), E31B (spouse of KITAS holder), E31J (child)",
                "Prepare marriage certificate (legalized/apostilled) or birth certificate",
                "Indonesian spouse or KITAS holder acts as sponsor",
                "Apply for E-Visa online via imigrasi.go.id",
                "Upload documents: passport, marriage/birth certificate, sponsor KTP/KITAS, photo",
                "Pay visa fee (PNBP)",
                "Enter Indonesia and convert VITAS to KITAS at immigration",
                "Complete biometrics at immigration office",
                "KITAS valid 1-2 years, renewable",
                "After 3 consecutive years: eligible for KITAP (permanent stay)",
            ],
            key_conditions=[
                "E31A: spouse of Indonesian citizen (WNI)",
                "E31B: spouse of KITAS/KITAP holder",
                "E31J: child joining parent with KITAS",
                "E31E: elderly parent joining child in Indonesia",
                "Marriage must be legally recognized (registered at Catatan Sipil)",
                "Spouse KITAS allows working with separate IMTA",
                "Mixed marriage: special property rules apply (prenuptial agreement recommended)",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "visa_retirement_e33e": GoldenRoute(
            route_id="visa_retirement_e33e",
            name="Retirement Visa (E33E / Silver Hair)",
            description="KITAS for retirees wanting to live in Indonesia",
            path=[
                "Confirm eligibility: minimum age 55 years",
                "Prepare proof of pension or passive income (min USD 2,500/month)",
                "Arrange accommodation in Indonesia (rental agreement or property proof)",
                "Obtain health insurance valid in Indonesia",
                "Apply for E-Visa E33E online via imigrasi.go.id",
                "Upload documents: passport, pension proof, insurance, accommodation proof, photo",
                "Pay visa fee (PNBP)",
                "Enter Indonesia and convert VITAS to KITAS E33E",
                "Complete biometrics at immigration office",
                "KITAS valid 1 year, renewable annually",
                "Must employ Indonesian helper/caretaker (recommended, not always enforced)",
            ],
            key_conditions=[
                "Minimum age: 55 years",
                "Cannot work or earn income in Indonesia",
                "Must show proof of pension/passive income",
                "Health insurance mandatory",
                "SKTT reporting every 90 days",
                "After 3 years: eligible for KITAP",
                "Alternative: Second Home Visa (E33) for younger retirees with savings",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "visa_second_home": GoldenRoute(
            route_id="visa_second_home",
            name="Second Home Visa",
            description="Long-term visa (5-10 years) for wealthy foreigners to live in Indonesia",
            path=[
                "Confirm eligibility: show bank balance of min USD 130,000",
                "Apply for Second Home Visa online via e-Visa portal (imigrasi.go.id)",
                "Upload documents: passport, bank statements (6 months), photo",
                "Pay visa fee (PNBP)",
                "Receive Second Home Visa approval",
                "Enter Indonesia - visa valid for 5 years, extendable to 10 years",
                "No need for annual renewal during validity period",
                "Register at local immigration office and obtain SKTT",
            ],
            key_conditions=[
                "Bank balance requirement: USD 130,000 (or equivalent)",
                "Valid for 5 years, extendable once for another 5 years (total 10)",
                "No age requirement (unlike retirement E33E)",
                "Cannot work in Indonesia on this visa",
                "Can invest/own PT PMA separately",
                "Family members can apply as dependents",
                "No need for annual extension - valid full duration",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "visa_golden": GoldenRoute(
            route_id="visa_golden",
            name="Golden Visa Indonesia",
            description="Premium visa for high-value investors and global talent",
            path=[
                "Choose Golden Visa category: Investor or Talent",
                "Investor: invest minimum USD 2.5 million in Indonesia (business, property, government bonds)",
                "Talent: demonstrate exceptional skills/achievements in relevant field",
                "Apply through Directorate General of Immigration",
                "Submit investment proof or talent portfolio with supporting documents",
                "Pay applicable fees",
                "Receive Golden Visa (5 or 10 years validity)",
                "Benefit: no SKTT reporting, fast-track immigration services",
            ],
            key_conditions=[
                "Investor category: minimum USD 2.5 million investment",
                "Property investment: minimum USD 350,000 in designated areas",
                "Government bonds: minimum investment threshold applies",
                "Talent category: proven track record in technology, arts, sports, etc.",
                "5-year or 10-year validity depending on investment level",
                "Includes spouse and children as dependents",
                "Premium immigration service and no regular reporting",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
        "visa_performing_event_c7_c10_c11": GoldenRoute(
            route_id="visa_performing_event_c7_c10_c11",
            name="Performing Arts / Event Visa (C7, C10, C11)",
            description="Visa for performers, event participants, and exhibitors",
            path=[
                "Determine visa type: C7 (performing arts), C10 (event participant), C11 (exhibitor)",
                "Obtain sponsor letter from event organizer or Indonesian promoter",
                "C7: provide performance contract, event details, itinerary",
                "C10: provide event invitation, participation confirmation",
                "C11: provide exhibition details, booth registration",
                "Apply online via e-Visa portal (imigrasi.go.id)",
                "Pay visa fee (PNBP)",
                "Enter Indonesia for the specific event/performance",
                "Visa valid for event duration (typically 30-60 days)",
            ],
            key_conditions=[
                "C7: music concerts, theater, cultural performances",
                "C7A/B/C: sub-categories for different performing arts types",
                "C10: conferences, seminars, sports events",
                "C11: trade fairs, exhibitions",
                "All require Indonesian sponsor/organizer",
                "Limited to specific event - not for general work",
                "Extension possible if event schedule changes",
            ],
            estimated_timeline_months=None,
            estimated_cost_range_usd=None,
        ),
    }

    # Keywords to match golden routes
    ROUTE_KEYWORDS = {
        "pt_pma_setup": [
            "pt pma",
            "perusahaan asing",
            "foreign company",
            "setup company",
            "establish company",
            "buat pt",
            "dirikan perusahaan",
        ],
        "kitas_work": [
            "kitas",
            "work permit",
            "izin kerja",
            "working visa",
            "imta",
            "rptka",
            "stay permit",
        ],
        "nib_oss": ["nib", "oss", "nomor induk berusaha", "business number", "izin usaha"],
        "restaurant_foreigner": [
            "restaurant",
            "restoran",
            "rumah makan",
            "cafe",
            "bar",
            "food and beverage",
            "f&b",
            "open restaurant",
            "buka restoran",
            "56101",
        ],
        "import_export_business": [
            "import",
            "export",
            "ekspor",
            "impor",
            "trading",
            "perdagangan",
            "api-u",
            "api-p",
            "customs",
            "kepabeanan",
        ],
        "tech_company_digital": [
            "tech company",
            "startup",
            "software",
            "digital",
            "it company",
            "saas",
            "app development",
            "perusahaan teknologi",
            "62011",
            "62019",
        ],
        "investor_kitas_retirement": [
            "investor kitas",
            "retirement",
            "pensiun",
            "retire in bali",
            "second home",
            "lansia",
            "passive income",
            "kitap",
            "permanent stay",
        ],
        "hire_foreign_worker": [
            "hire foreigner",
            "foreign worker",
            "tka",
            "tenaga kerja asing",
            "rptka",
            "dkp-tka",
            "employ foreigner",
            "sponsor worker",
            "mempekerjakan asing",
        ],
        "villa_rental_business": [
            "villa",
            "sewa villa",
            "rent villa",
            "villa rental",
            "airbnb",
            "holiday rental",
            "vacation rental",
            "akomodasi",
            "55130",
            "homestay",
            "pondok wisata",
        ],
        "hotel_business": [
            "hotel",
            "boutique hotel",
            "resort",
            "penginapan",
            "akomodasi hotel",
            "bintang",
            "star hotel",
            "55101",
            "55111",
            "hospitality",
        ],
        "real_estate_developer": [
            "real estate",
            "property development",
            "developer",
            "pengembang",
            "build property",
            "konstruksi",
            "68110",
            "bangun rumah",
            "perumahan",
            "apartemen",
        ],
        "property_management": [
            "property management",
            "manage villa",
            "kelola properti",
            "villa management",
            "68200",
            "68210",
            "manage property",
            "pengelolaan",
        ],
        "buy_property_foreigner": [
            "buy property",
            "buy land",
            "beli tanah",
            "beli rumah",
            "hak pakai",
            "hak milik",
            "land ownership",
            "property purchase",
            "beli properti",
            "nominee",
            "hgb",
            "sertifikat",
        ],
        "visa_tourism_c1_d1": [
            "tourist visa",
            "visa wisata",
            "visa turis",
            "visa c1",
            "visa d1",
            "holiday visa",
            "visit indonesia",
            "visa kunjungan",
            "tourism visa",
        ],
        "visa_business_c2_d2": [
            "business visa",
            "visa bisnis",
            "visa c2",
            "visa d2",
            "business visit",
            "meeting visa",
            "conference visa",
            "visa kunjungan bisnis",
        ],
        "visa_pre_investment_d12": [
            "d12",
            "pre-investment",
            "pra investasi",
            "business investigation",
            "explore business",
            "investment visa",
            "visa investasi",
        ],
        "visa_digital_nomad_e33g": [
            "digital nomad",
            "remote worker",
            "e33g",
            "freelance visa",
            "work remotely",
            "pekerja jarak jauh",
            "nomad digital",
            "remote work bali",
        ],
        "visa_spouse_family_e31": [
            "spouse visa",
            "visa pasangan",
            "e31a",
            "e31b",
            "family visa",
            "marriage visa",
            "mixed marriage",
            "penyatuan keluarga",
            "visa keluarga",
            "visa nikah",
        ],
        "visa_retirement_e33e": [
            "retirement visa",
            "visa pensiun",
            "e33e",
            "silver hair",
            "retire indonesia",
            "visa lansia",
            "pension visa",
            "retire bali",
        ],
        "visa_second_home": [
            "second home",
            "rumah kedua",
            "visa 5 tahun",
            "visa 10 tahun",
            "long term visa",
            "long stay",
        ],
        "visa_golden": [
            "golden visa",
            "visa emas",
            "investor visa premium",
            "high value investor",
        ],
        "visa_performing_event_c7_c10_c11": [
            "performing visa",
            "concert visa",
            "event visa",
            "visa c7",
            "visa c10",
            "visa c11",
            "exhibition visa",
            "performer visa",
            "visa pertunjukan",
        ],
    }

    def match_golden_route(self, query: str) -> GoldenRoute | None:
        """
        Match user query to a predefined golden route.

        Returns the best matching route or None.
        """
        query_lower = query.lower()
        best_match: tuple[str, int] | None = None

        for route_id, keywords in self.ROUTE_KEYWORDS.items():
            match_count = sum(1 for kw in keywords if kw in query_lower)
            if match_count > 0 and (best_match is None or match_count > best_match[1]):
                best_match = (route_id, match_count)

        if best_match and best_match[0] in self.GOLDEN_ROUTES:
            route = self.GOLDEN_ROUTES[best_match[0]]
            logger.info(f"Matched golden route: {route.route_id} (score: {best_match[1]})")
            return route

        return None

    def format_golden_route(self, route: GoldenRoute) -> str:
        """Format golden route for LLM context."""
        lines = [
            f"\n[GOLDEN ROUTE: {route.name}]",
            f"Description: {route.description}",
            "\nRecommended Path:",
        ]

        for i, step in enumerate(route.path, 1):
            lines.append(f"  {i}. {step}")

        if route.key_conditions:
            lines.append("\nKey Conditions:")
            for cond in route.key_conditions:
                lines.append(f"  ⚠️ {cond}")

        if route.estimated_timeline_months:
            weeks = route.estimated_timeline_months * 4
            if weeks <= 4:
                lines.append(f"\nEstimated Timeline: from {weeks:.0f} week(s)")
            else:
                lines.append(
                    f"\nEstimated Timeline: from {route.estimated_timeline_months:.1f} months",
                )

        if route.estimated_cost_range_usd:
            low, high = route.estimated_cost_range_usd
            lines.append(f"Estimated Cost: ${low:,} - ${high:,} USD")

        lines.append("")
        return "\n".join(lines)

    def build_graph_summary(
        self,
        entities: list[dict],
        relationships: list[dict],
        query_mentions: list[tuple[str, str]],
        golden_route: GoldenRoute | None = None,
    ) -> str:
        """
        Build a human-readable summary of the KG context for the LLM.
        Includes golden route if matched.
        """
        if not entities and not relationships and not golden_route:
            return ""

        lines = ["[KNOWLEDGE GRAPH CONTEXT]"]

        # Include golden route if matched
        if golden_route:
            lines.append(self.format_golden_route(golden_route))

        # Group entities by type
        entity_by_type = {}
        for e in entities:
            etype = e.get("entity_type", "unknown")
            if etype not in entity_by_type:
                entity_by_type[etype] = []
            entity_by_type[etype].append(e["name"])

        if entity_by_type:
            lines.append("\nEntities found:")
            for etype, names in entity_by_type.items():
                names_str = ", ".join(names[:5])
                if len(names) > 5:
                    names_str += f" (+{len(names) - 5} more)"
                lines.append(f"  - {etype}: {names_str}")

        # Key relationships
        if relationships:
            lines.append("\nKey relationships:")
            seen_rels = set()
            for rel in relationships[:15]:  # Limit to avoid context bloat
                rel_str = (
                    f"{rel['source_name']} --[{rel['relationship_type']}]--> {rel['target_name']}"
                )
                if rel_str not in seen_rels:
                    seen_rels.add(rel_str)
                    lines.append(f"  - {rel_str}")

        lines.append("")
        return "\n".join(lines)

    async def get_context_for_query(
        self, query: str, max_depth: int = 2, max_entities: int = 10,
    ) -> KGContext:
        """
        Main entry point: Get KG context for a user query.

        Args:
            query: User's question
            max_depth: How many hops to traverse (1-2)
            max_entities: Max entities to include

        Returns:
            KGContext with entities, relationships, chunk IDs, summary, and golden_route
        """
        # Step 0: Check for golden route match first
        golden_route = self.match_golden_route(query)

        # Step 1: Extract entity mentions from query
        mentions = self.extract_entities_from_query(query)

        if not mentions and not golden_route:
            logger.debug(f"No entity mentions found in query: {query[:100]}")
            return KGContext(
                entities_found=[],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.0,
                golden_route=None,
            )

        logger.info(f"Extracted {len(mentions)} entity mentions from query")

        # Step 2: Find matching KG entities
        kg_entities = await self.find_kg_entities(mentions) if mentions else []

        # Step 3: Get related entities (graph traversal)
        if kg_entities:
            entity_ids = [e["entity_id"] for e in kg_entities]
            related_entities, relationships = await self.get_related_entities(
                entity_ids, max_depth=max_depth, limit=max_entities * 2,
            )
        else:
            related_entities, relationships = [], []

        all_entities = kg_entities + related_entities

        # Step 4: Get source chunk IDs
        all_entity_ids = [e["entity_id"] for e in all_entities]
        chunk_ids = await self.get_source_chunks(all_entity_ids)

        # Step 5: Build summary for LLM (include golden route if found)
        graph_summary = self.build_graph_summary(
            all_entities, relationships, mentions, golden_route,
        )

        # Calculate confidence based on match quality
        if kg_entities:
            avg_confidence = sum(e.get("confidence", 0.5) for e in kg_entities) / len(kg_entities)
        elif golden_route:
            avg_confidence = 0.8  # High confidence for golden route match
        else:
            avg_confidence = 0.0

        logger.info(
            f"KG context: {len(all_entities)} entities, "
            f"{len(relationships)} relationships, {len(chunk_ids)} chunks, "
            f"golden_route={'matched' if golden_route else 'none'}",
        )

        return KGContext(
            entities_found=all_entities[:max_entities],
            relationships=relationships,
            source_chunk_ids=chunk_ids[:50],  # Limit chunk IDs
            graph_summary=graph_summary,
            confidence=avg_confidence,
            golden_route=golden_route,
        )
