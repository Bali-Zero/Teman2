"""
Indonesian Legal Knowledge Graph Ontology
Based on LexID (Universitas Indonesia) and international best practices 2025

This ontology defines:
- Entity types for Indonesian legal domain
- Relation types between entities
- Extraction patterns and examples
"""

from dataclasses import dataclass, field
from enum import Enum


class EntityType(str, Enum):
    """Entity types for Indonesian Legal Knowledge Graph"""

    # Regulations (Peraturan)
    UNDANG_UNDANG = "undang_undang"           # Law (UU)
    PERATURAN_PEMERINTAH = "peraturan_pemerintah"  # Government Regulation (PP)
    PERPRES = "perpres"                        # Presidential Regulation
    PERMEN = "permen"                          # Ministerial Regulation
    PERDA = "perda"                            # Regional Regulation
    PERKA = "perka"                            # Agency Head Regulation
    KEPMEN = "kepmen"                          # Ministerial Decree
    INPRES = "inpres"                          # Presidential Instruction

    # Document Structure
    BAB = "bab"                                # Chapter
    BAGIAN = "bagian"                          # Section
    PASAL = "pasal"                            # Article
    AYAT = "ayat"                              # Paragraph/Clause
    HURUF = "huruf"                            # Letter point
    ANGKA = "angka"                            # Number point

    # Legal Entities
    BADAN_HUKUM = "badan_hukum"               # Legal Entity
    PT_PMA = "pt_pma"                          # Foreign Investment Company
    PT_PMDN = "pt_pmdn"                        # Domestic Investment Company
    PT_PERORANGAN = "pt_perorangan"            # Individual Company
    CV = "cv"                                  # Commanditaire Vennootschap
    FIRMA = "firma"                            # Partnership
    KOPERASI = "koperasi"                      # Cooperative
    YAYASAN = "yayasan"                        # Foundation
    PERSEKUTUAN_PERDATA = "persekutuan_perdata"  # Civil Partnership

    # Permits & Licenses
    NIB = "nib"                                # Business Registration Number
    SIUP = "siup"                              # Trade License
    TDP = "tdp"                                # Company Registration
    NPWP = "npwp"                              # Tax ID
    IZIN_USAHA = "izin_usaha"                  # Business License
    IZIN_PRINSIP = "izin_prinsip"              # Principle License
    IZIN_LOKASI = "izin_lokasi"                # Location Permit
    IZIN_LINGKUNGAN = "izin_lingkungan"        # Environmental Permit
    IMB = "imb"                                # Building Permit
    AMDAL = "amdal"                            # Environmental Impact Assessment

    # Immigration
    KITAS = "kitas"                            # Limited Stay Permit
    KITAP = "kitap"                            # Permanent Stay Permit
    IMTA = "imta"                              # Foreign Worker Permit
    RPTKA = "rptka"                            # Foreign Worker Plan
    VITAS = "vitas"                            # Limited Stay Visa
    VOA = "voa"                                # Visa On Arrival
    EVISA = "evisa"                            # Electronic Visa
    TELEX_VISA = "telex_visa"                  # Telex Visa

    # Tax Types
    PPH = "pph"                                # Income Tax
    PPH_21 = "pph_21"                          # Employee Income Tax
    PPH_23 = "pph_23"                          # Service Income Tax
    PPH_25 = "pph_25"                          # Installment Income Tax
    PPH_29 = "pph_29"                          # Annual Income Tax
    PPH_FINAL = "pph_final"                    # Final Income Tax
    PPN = "ppn"                                # Value Added Tax
    PBB = "pbb"                                # Property Tax
    BPHTB = "bphtb"                            # Land/Building Transfer Tax
    BEA_MATERAI = "bea_materai"                # Stamp Duty

    # Government Institutions
    KEMENTERIAN = "kementerian"                # Ministry
    LEMBAGA = "lembaga"                        # Agency
    DIREKTORAT = "direktorat"                  # Directorate
    BADAN = "badan"                            # Board/Body
    OSS = "oss"                                # Online Single Submission
    BKPM = "bkpm"                              # Investment Board
    DJP = "djp"                                # Tax Directorate
    KEMENKUMHAM = "kemenkumham"                # Law & HR Ministry
    KEMENAKER = "kemenaker"                    # Manpower Ministry
    IMIGRASI = "imigrasi"                      # Immigration
    KEMENKEU = "kemenkeu"                      # Finance Ministry
    KEMENDAG = "kemendag"                      # Trade Ministry

    # Procedures
    PENDAFTARAN = "pendaftaran"                # Registration
    PERMOHONAN = "permohonan"                  # Application
    PERPANJANGAN = "perpanjangan"              # Extension
    PERUBAHAN = "perubahan"                    # Amendment
    PENCABUTAN = "pencabutan"                  # Revocation
    PELAPORAN = "pelaporan"                    # Reporting

    # Requirements
    SYARAT = "syarat"                          # Requirement/Condition
    DOKUMEN = "dokumen"                        # Document
    FORMULIR = "formulir"                      # Form
    BIAYA = "biaya"                            # Fee/Cost
    JANGKA_WAKTU = "jangka_waktu"              # Duration/Timeframe

    # Sanctions
    DENDA = "denda"                            # Fine
    PIDANA = "pidana"                          # Criminal Penalty
    SANKSI_ADMINISTRATIF = "sanksi_administratif"  # Administrative Sanction
    PENCABUTAN_IZIN = "pencabutan_izin"        # License Revocation

    # Classification
    KBLI = "kbli"                              # Business Classification Code
    SEKTOR = "sektor"                          # Business Sector

    # Other
    PERSON = "person"                          # Named Person
    ORGANIZATION = "organization"              # Organization
    LOCATION = "location"                      # Location/Place
    DATE = "date"                              # Date
    AMOUNT = "amount"                          # Monetary Amount
    DURATION = "duration"                      # Time Duration


class RelationType(str, Enum):
    """Relation types for Indonesian Legal Knowledge Graph"""

    # Structural Relations
    PART_OF = "PART_OF"                        # X is part of Y (Ayat PART_OF Pasal)
    CONTAINS = "CONTAINS"                      # X contains Y
    AMENDS = "AMENDS"                          # X amends Y (regulation)
    REVOKES = "REVOKES"                        # X revokes Y
    IMPLEMENTS = "IMPLEMENTS"                  # PP IMPLEMENTS UU
    REFERENCES = "REFERENCES"                  # X references Y
    REPLACES = "REPLACES"                      # X replaces Y
    DERIVES_FROM = "DERIVES_FROM"              # X derives from Y

    # Requirement Relations
    REQUIRES = "REQUIRES"                      # X requires Y (KITAS REQUIRES IMTA)
    PREREQUISITE_FOR = "PREREQUISITE_FOR"      # X is prerequisite for Y
    DEPENDS_ON = "DEPENDS_ON"                  # X depends on Y
    ENABLES = "ENABLES"                        # X enables Y

    # Issuance Relations
    ISSUED_BY = "ISSUED_BY"                    # X issued by Y (NIB ISSUED_BY OSS)
    ISSUED_TO = "ISSUED_TO"                    # X issued to Y
    AUTHORIZED_BY = "AUTHORIZED_BY"            # X authorized by Y
    REGULATED_BY = "REGULATED_BY"              # X regulated by Y

    # Procedural Relations
    HAS_PROCEDURE = "HAS_PROCEDURE"            # X has procedure Y
    HAS_REQUIREMENT = "HAS_REQUIREMENT"        # X has requirement Y
    HAS_DOCUMENT = "HAS_DOCUMENT"              # X requires document Y
    HAS_FEE = "HAS_FEE"                        # X has fee Y
    HAS_DURATION = "HAS_DURATION"              # X has duration Y
    HAS_VALIDITY = "HAS_VALIDITY"              # X has validity period Y

    # Applicability Relations
    APPLIES_TO = "APPLIES_TO"                  # Regulation applies to entity
    EXEMPTS = "EXEMPTS"                        # X exempts Y from Z
    RESTRICTS = "RESTRICTS"                    # X restricts Y
    PERMITS = "PERMITS"                        # X permits Y to do Z
    PROHIBITS = "PROHIBITS"                    # X prohibits Y

    # Sanction Relations
    VIOLATES = "VIOLATES"                      # Action violates regulation
    PENALTY_FOR = "PENALTY_FOR"                # Penalty for violation
    RESULTS_IN = "RESULTS_IN"                  # X results in Y (sanction)

    # Tax Relations
    TAX_OBLIGATION = "TAX_OBLIGATION"          # Entity has tax obligation
    TAX_RATE = "TAX_RATE"                      # X has tax rate Y
    TAX_EXEMPT = "TAX_EXEMPT"                  # X is tax exempt

    # Classification Relations
    CLASSIFIED_AS = "CLASSIFIED_AS"            # X classified as Y (KBLI)
    BELONGS_TO = "BELONGS_TO"                  # X belongs to sector Y

    # Location Relations
    LOCATED_IN = "LOCATED_IN"                  # X located in Y
    JURISDICTION = "JURISDICTION"              # X has jurisdiction Y


@dataclass
class EntitySchema:
    """Schema for entity extraction"""
    type: EntityType
    patterns: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class RelationSchema:
    """Schema for relation extraction"""
    type: RelationType
    source_types: list[EntityType] = field(default_factory=list)
    target_types: list[EntityType] = field(default_factory=list)
    trigger_words: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    description: str = ""


# Entity extraction schemas with patterns and examples
ENTITY_SCHEMAS: dict[EntityType, EntitySchema] = {
    # Regulations
    EntityType.UNDANG_UNDANG: EntitySchema(
        type=EntityType.UNDANG_UNDANG,
        patterns=[
            r"UU\s+(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})",
            r"Undang-[Uu]ndang\s+(?:Nomor\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})",
        ],
        examples=[
            "UU No. 6 Tahun 2023 tentang Cipta Kerja",
            "Undang-Undang Nomor 25 Tahun 2007 tentang Penanaman Modal",
        ],
        attributes=["number", "year", "title", "about"],
        description="Indonesian Law (Undang-Undang)"
    ),
    EntityType.PERATURAN_PEMERINTAH: EntitySchema(
        type=EntityType.PERATURAN_PEMERINTAH,
        patterns=[
            r"PP\s+(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})",
            r"Peraturan\s+Pemerintah\s+(?:Nomor\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})",
        ],
        examples=[
            "PP No. 35 Tahun 2021 tentang PKWT",
            "Peraturan Pemerintah Nomor 5 Tahun 2021",
        ],
        attributes=["number", "year", "title", "about"],
        description="Government Regulation (Peraturan Pemerintah)"
    ),
    EntityType.PERPRES: EntitySchema(
        type=EntityType.PERPRES,
        patterns=[
            r"Perpres\s+(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})",
            r"Peraturan\s+Presiden\s+(?:Nomor\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})",
        ],
        examples=["Perpres No. 10 Tahun 2021"],
        attributes=["number", "year", "title"],
        description="Presidential Regulation"
    ),
    EntityType.PERMEN: EntitySchema(
        type=EntityType.PERMEN,
        patterns=[
            r"Permen(?:aker|keu|dag|kumham)?\s+(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})",
            r"Peraturan\s+Menteri\s+\w+\s+(?:Nomor\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})",
        ],
        examples=["Permenaker No. 8 Tahun 2021"],
        attributes=["number", "year", "ministry", "title"],
        description="Ministerial Regulation"
    ),

    # Document Structure
    EntityType.PASAL: EntitySchema(
        type=EntityType.PASAL,
        patterns=[
            r"Pasal\s+(\d+)",
            r"pasal\s+(\d+)",
        ],
        examples=["Pasal 42", "Pasal 5 ayat (1)"],
        attributes=["number", "parent_regulation"],
        description="Article in a regulation"
    ),
    EntityType.AYAT: EntitySchema(
        type=EntityType.AYAT,
        patterns=[
            r"[Aa]yat\s*\((\d+)\)",
            r"ayat\s+(\d+)",
        ],
        examples=["ayat (1)", "ayat (2) huruf a"],
        attributes=["number", "parent_pasal"],
        description="Paragraph/Clause within an article"
    ),

    # Legal Entities
    EntityType.PT_PMA: EntitySchema(
        type=EntityType.PT_PMA,
        patterns=[
            r"PT\s+PMA",
            r"Perseroan\s+(?:Terbatas\s+)?(?:dengan\s+)?[Pp]enanaman\s+[Mm]odal\s+[Aa]sing",
            r"perusahaan\s+(?:asing|PMA)",
        ],
        examples=["PT PMA", "perusahaan penanaman modal asing"],
        attributes=["name", "nationality", "sector"],
        description="Foreign Investment Company"
    ),
    EntityType.PT_PMDN: EntitySchema(
        type=EntityType.PT_PMDN,
        patterns=[
            r"PT\s+PMDN",
            r"Perseroan\s+(?:Terbatas\s+)?(?:dengan\s+)?[Pp]enanaman\s+[Mm]odal\s+[Dd]alam\s+[Nn]egeri",
        ],
        examples=["PT PMDN", "perusahaan PMDN"],
        attributes=["name", "sector"],
        description="Domestic Investment Company"
    ),

    # Permits
    EntityType.NIB: EntitySchema(
        type=EntityType.NIB,
        patterns=[
            r"\bNIB\b",
            r"Nomor\s+Induk\s+Berusaha",
        ],
        examples=["NIB", "Nomor Induk Berusaha"],
        attributes=["number", "issue_date", "validity"],
        description="Business Registration Number"
    ),
    EntityType.KITAS: EntitySchema(
        type=EntityType.KITAS,
        patterns=[
            r"\bKITAS\b",
            r"Kartu\s+Izin\s+Tinggal\s+Terbatas",
            r"[Ii]zin\s+[Tt]inggal\s+[Tt]erbatas",
        ],
        examples=["KITAS", "Kartu Izin Tinggal Terbatas"],
        attributes=["type", "duration", "sponsor"],
        description="Limited Stay Permit Card"
    ),
    EntityType.IMTA: EntitySchema(
        type=EntityType.IMTA,
        patterns=[
            r"\bIMTA\b",
            r"Izin\s+Mempekerjakan\s+Tenaga\s+(?:Kerja\s+)?Asing",
        ],
        examples=["IMTA", "Izin Mempekerjakan Tenaga Kerja Asing"],
        attributes=["number", "validity", "position"],
        description="Foreign Worker Employment Permit"
    ),
    EntityType.RPTKA: EntitySchema(
        type=EntityType.RPTKA,
        patterns=[
            r"\bRPTKA\b",
            r"Rencana\s+Penggunaan\s+Tenaga\s+Kerja\s+Asing",
        ],
        examples=["RPTKA"],
        attributes=["number", "positions", "duration"],
        description="Foreign Worker Utilization Plan"
    ),

    # Government Institutions
    EntityType.OSS: EntitySchema(
        type=EntityType.OSS,
        patterns=[
            r"\bOSS\b",
            r"Online\s+Single\s+Submission",
        ],
        examples=["OSS", "sistem OSS"],
        attributes=[],
        description="Online Single Submission System"
    ),
    EntityType.BKPM: EntitySchema(
        type=EntityType.BKPM,
        patterns=[
            r"\bBKPM\b",
            r"Badan\s+Koordinasi\s+Penanaman\s+Modal",
        ],
        examples=["BKPM"],
        attributes=[],
        description="Investment Coordinating Board"
    ),

    # Tax Types
    EntityType.PPH_21: EntitySchema(
        type=EntityType.PPH_21,
        patterns=[
            r"PPh\s*(?:Pasal\s*)?21",
            r"Pajak\s+Penghasilan\s+(?:Pasal\s*)?21",
        ],
        examples=["PPh 21", "PPh Pasal 21"],
        attributes=["rate", "threshold"],
        description="Employee Income Tax"
    ),
    EntityType.PPN: EntitySchema(
        type=EntityType.PPN,
        patterns=[
            r"\bPPN\b",
            r"Pajak\s+Pertambahan\s+Nilai",
        ],
        examples=["PPN", "PPN 11%"],
        attributes=["rate"],
        description="Value Added Tax"
    ),

    # KBLI
    EntityType.KBLI: EntitySchema(
        type=EntityType.KBLI,
        patterns=[
            r"KBLI\s*(\d{5})",
            r"kode\s+KBLI\s*(\d{5})",
        ],
        examples=["KBLI 62010", "KBLI 47111"],
        attributes=["code", "description", "risk_level"],
        description="Indonesian Business Classification Code"
    ),

    # Amounts and Durations
    EntityType.BIAYA: EntitySchema(
        type=EntityType.BIAYA,
        patterns=[
            r"Rp\.?\s*([\d\.,]+)",
            r"biaya\s+(?:sebesar\s+)?Rp\.?\s*([\d\.,]+)",
            r"\$\s*([\d\.,]+)",
            r"USD\s*([\d\.,]+)",
        ],
        examples=["Rp 1.200.000", "USD 100"],
        attributes=["amount", "currency"],
        description="Fee or Cost Amount"
    ),
    EntityType.JANGKA_WAKTU: EntitySchema(
        type=EntityType.JANGKA_WAKTU,
        patterns=[
            r"(\d+)\s*(?:hari|bulan|tahun)",
            r"(?:selama|dalam\s+waktu)\s+(\d+)\s*(?:hari|bulan|tahun)",
            r"(?:paling\s+lama|maksimal)\s+(\d+)\s*(?:hari|bulan|tahun)",
        ],
        examples=["30 hari", "1 tahun", "6 bulan"],
        attributes=["value", "unit"],
        description="Time Duration"
    ),
}


# Relation extraction schemas
RELATION_SCHEMAS: dict[RelationType, RelationSchema] = {
    RelationType.REQUIRES: RelationSchema(
        type=RelationType.REQUIRES,
        source_types=[
            EntityType.PT_PMA, EntityType.PT_PMDN, EntityType.KITAS,
            EntityType.IMTA, EntityType.IZIN_USAHA
        ],
        target_types=[
            EntityType.NIB, EntityType.NPWP, EntityType.IMTA,
            EntityType.RPTKA, EntityType.DOKUMEN
        ],
        trigger_words=[
            "wajib memiliki", "harus memiliki", "memerlukan", "dibutuhkan",
            "persyaratan", "syarat", "diperlukan", "harus dilengkapi",
            "wajib melampirkan", "harus menyertakan"
        ],
        examples=[
            "PT PMA wajib memiliki NIB",
            "KITAS memerlukan IMTA yang masih berlaku",
        ],
        description="Entity requires another entity"
    ),
    RelationType.ISSUED_BY: RelationSchema(
        type=RelationType.ISSUED_BY,
        source_types=[EntityType.NIB, EntityType.KITAS, EntityType.IMTA],
        target_types=[EntityType.OSS, EntityType.IMIGRASI, EntityType.KEMENAKER],
        trigger_words=[
            "diterbitkan oleh", "dikeluarkan oleh", "diterbitkan melalui",
            "issued by", "melalui sistem", "dari"
        ],
        examples=[
            "NIB diterbitkan melalui sistem OSS",
            "KITAS diterbitkan oleh Dirjen Imigrasi",
        ],
        description="Permit issued by government agency"
    ),
    RelationType.IMPLEMENTS: RelationSchema(
        type=RelationType.IMPLEMENTS,
        source_types=[EntityType.PERATURAN_PEMERINTAH, EntityType.PERMEN],
        target_types=[EntityType.UNDANG_UNDANG],
        trigger_words=[
            "sebagai pelaksanaan", "untuk melaksanakan",
            "sebagaimana dimaksud dalam", "berdasarkan"
        ],
        examples=[
            "PP No. 35 Tahun 2021 sebagai pelaksanaan UU No. 6 Tahun 2023",
        ],
        description="Regulation implements a law"
    ),
    RelationType.AMENDS: RelationSchema(
        type=RelationType.AMENDS,
        source_types=[EntityType.UNDANG_UNDANG, EntityType.PERATURAN_PEMERINTAH],
        target_types=[EntityType.UNDANG_UNDANG, EntityType.PERATURAN_PEMERINTAH],
        trigger_words=[
            "mengubah", "perubahan atas", "amandemen",
            "diubah dengan", "sebagaimana telah diubah"
        ],
        examples=[
            "UU No. 6 Tahun 2023 mengubah UU No. 13 Tahun 2003",
        ],
        description="Regulation amends another regulation"
    ),
    RelationType.HAS_FEE: RelationSchema(
        type=RelationType.HAS_FEE,
        source_types=[EntityType.KITAS, EntityType.NIB, EntityType.IMTA],
        target_types=[EntityType.BIAYA],
        trigger_words=[
            "biaya", "tarif", "PNBP", "sebesar", "dikenakan"
        ],
        examples=[
            "KITAS dikenakan biaya sebesar Rp 1.200.000",
        ],
        description="Permit has associated fee"
    ),
    RelationType.HAS_DURATION: RelationSchema(
        type=RelationType.HAS_DURATION,
        source_types=[EntityType.KITAS, EntityType.NIB, EntityType.IMTA],
        target_types=[EntityType.JANGKA_WAKTU],
        trigger_words=[
            "berlaku selama", "masa berlaku", "jangka waktu",
            "valid for", "selama", "maksimal"
        ],
        examples=[
            "KITAS berlaku selama 1 tahun",
            "NIB berlaku selama perusahaan masih beroperasi",
        ],
        description="Permit has validity duration"
    ),
    RelationType.APPLIES_TO: RelationSchema(
        type=RelationType.APPLIES_TO,
        source_types=[EntityType.UNDANG_UNDANG, EntityType.PERATURAN_PEMERINTAH, EntityType.PASAL],
        target_types=[EntityType.PT_PMA, EntityType.PT_PMDN, EntityType.BADAN_HUKUM],
        trigger_words=[
            "berlaku bagi", "ditujukan kepada", "mengatur tentang",
            "untuk", "bagi", "terhadap"
        ],
        examples=[
            "Pasal 42 berlaku bagi PT PMA",
        ],
        description="Regulation applies to entity type"
    ),
    RelationType.PENALTY_FOR: RelationSchema(
        type=RelationType.PENALTY_FOR,
        source_types=[EntityType.DENDA, EntityType.SANKSI_ADMINISTRATIF, EntityType.PIDANA],
        target_types=[EntityType.PASAL],
        trigger_words=[
            "dikenakan sanksi", "dipidana", "denda sebesar",
            "sanksi administratif", "pelanggaran"
        ],
        examples=[
            "Pelanggaran Pasal 42 dikenakan denda sebesar Rp 100.000.000",
        ],
        description="Penalty for violating regulation"
    ),
    RelationType.PART_OF: RelationSchema(
        type=RelationType.PART_OF,
        source_types=[EntityType.AYAT, EntityType.HURUF, EntityType.PASAL],
        target_types=[EntityType.PASAL, EntityType.BAB, EntityType.UNDANG_UNDANG],
        trigger_words=[],  # Structural, inferred from context
        examples=[
            "Ayat (1) Pasal 5 UU No. 6 Tahun 2023",
        ],
        description="Document part hierarchy"
    ),
    RelationType.REFERENCES: RelationSchema(
        type=RelationType.REFERENCES,
        source_types=[EntityType.PASAL, EntityType.AYAT],
        target_types=[EntityType.PASAL, EntityType.UNDANG_UNDANG, EntityType.PERATURAN_PEMERINTAH],
        trigger_words=[
            "sebagaimana dimaksud dalam", "mengacu pada", "berdasarkan",
            "sesuai dengan", "merujuk pada"
        ],
        examples=[
            "sebagaimana dimaksud dalam Pasal 5 ayat (1)",
        ],
        description="Cross-reference between regulations"
    ),
    RelationType.TAX_OBLIGATION: RelationSchema(
        type=RelationType.TAX_OBLIGATION,
        source_types=[EntityType.PT_PMA, EntityType.PT_PMDN, EntityType.BADAN_HUKUM],
        target_types=[EntityType.PPH, EntityType.PPH_21, EntityType.PPN],
        trigger_words=[
            "wajib pajak", "kewajiban pajak", "dikenakan pajak",
            "membayar pajak", "objek pajak"
        ],
        examples=[
            "PT PMA wajib membayar PPh 21 untuk karyawan",
        ],
        description="Entity has tax obligation"
    ),
    RelationType.CLASSIFIED_AS: RelationSchema(
        type=RelationType.CLASSIFIED_AS,
        source_types=[EntityType.PT_PMA, EntityType.PT_PMDN, EntityType.IZIN_USAHA],
        target_types=[EntityType.KBLI, EntityType.SEKTOR],
        trigger_words=[
            "termasuk dalam", "diklasifikasikan sebagai", "dengan KBLI",
            "kode usaha", "sektor usaha"
        ],
        examples=[
            "Kegiatan usaha dengan KBLI 62010",
        ],
        description="Business classification"
    ),
}


def get_entity_type_description(entity_type: EntityType) -> str:
    """Get description for an entity type"""
    if entity_type in ENTITY_SCHEMAS:
        return ENTITY_SCHEMAS[entity_type].description
    return entity_type.value


def get_all_entity_types() -> list[str]:
    """Get all entity type values"""
    return [e.value for e in EntityType]


def get_all_relation_types() -> list[str]:
    """Get all relation type values"""
    return [r.value for r in RelationType]


def get_extraction_schema_prompt() -> str:
    """Generate schema description for LLM prompt"""
    entity_lines = []
    for et in EntityType:
        schema = ENTITY_SCHEMAS.get(et)
        if schema:
            entity_lines.append(f"- {et.value}: {schema.description}")
        else:
            entity_lines.append(f"- {et.value}")

    relation_lines = []
    for rt in RelationType:
        schema = RELATION_SCHEMAS.get(rt)
        if schema:
            relation_lines.append(f"- {rt.value}: {schema.description}")
        else:
            relation_lines.append(f"- {rt.value}")

    return f"""
## ENTITY TYPES
{chr(10).join(entity_lines)}

## RELATION TYPES
{chr(10).join(relation_lines)}
"""
