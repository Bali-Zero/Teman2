"""Read-only tax company pilot maps for the CRM workspace."""

from typing import Literal

from pydantic import BaseModel, Field

DriveConfidence = Literal["confirmed", "high", "medium", "low", "unconfirmed"]


class TaxCompanyPilotEntity(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)


class TaxCompanyPilotTaxMember(BaseModel):
    name: str
    workspace_branch: str
    source_folder_url: str


class TaxCompanyPilotPerson(BaseModel):
    name: str
    folder_url: str | None = None
    evidence: list[str] = Field(default_factory=list)
    role: str | None = None
    role_confidence: DriveConfidence = "unconfirmed"
    relationship_confidence: DriveConfidence = "unconfirmed"


class TaxCompanyPilotDocument(BaseModel):
    name: str
    group: Literal["company", "tax", "lkpm", "finance", "person", "coretax"]
    evidence_url: str | None = None
    sensitivity: Literal["internal", "company", "person", "financial", "credential"] = "internal"
    confidence: DriveConfidence = "confirmed"


class TaxCompanyPilotGap(BaseModel):
    code: str
    label: str
    severity: Literal["high", "medium", "low"]


class TaxCompanyPilotDuplicateCandidate(BaseModel):
    label: str
    urls: list[str]
    confidence: DriveConfidence


class TaxCompanyPilotEvidenceLink(BaseModel):
    label: str
    url: str
    kind: Literal["folder", "file", "spreadsheet", "document"]


class TaxCompanyPilotMap(BaseModel):
    key: Literal["ocean", "bimala"]
    company: TaxCompanyPilotEntity
    tax_member: TaxCompanyPilotTaxMember
    drive_folders: dict[str, str]
    persons: list[TaxCompanyPilotPerson]
    documents: list[TaxCompanyPilotDocument]
    duplicate_candidates: list[TaxCompanyPilotDuplicateCandidate]
    gaps: list[TaxCompanyPilotGap]
    evidence_links: list[TaxCompanyPilotEvidenceLink]
    ai_recap: list[str]
    read_only: bool = True
    confidence: DriveConfidence = "medium"


def _drive_folder(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}"


def _drive_file(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"


def _ocean_map() -> TaxCompanyPilotMap:
    operational = _drive_folder("1qJwTPkKFbm5Re1mKMeEEBFTfw0bYAYnQ")
    canonical = _drive_folder("1WRzDqNb_5M9DS7bqokaSgDxGkUlpj-TT")
    tax = _drive_folder("1Mfwo4txaLarfoDucQzB4_QFgt1YKragA")
    return TaxCompanyPilotMap(
        key="ocean",
        company=TaxCompanyPilotEntity(
            name="OCEAN CLOTHES AND SHOES PT",
            aliases=["PT Ocean Clothes and Shoes", "PT Ocean Clothes"],
        ),
        tax_member=TaxCompanyPilotTaxMember(
            name="DEA",
            workspace_branch="TAX DEPARTMENT/Members/Dea",
            source_folder_url=_drive_folder("1sFBLD2VxPBRdq-fpAtuHS0vRTr2fXxtc"),
        ),
        drive_folders={
            "operational": operational,
            "canonical_candidate": canonical,
            "tax": tax,
        },
        persons=[
            TaxCompanyPilotPerson(
                name="Natan Kleimonov",
                folder_url=_drive_folder("1cEVr2XasfdL8x80vD3kqDxXWrN2XgRk3"),
                evidence=["Passport"],
                relationship_confidence="medium",
            ),
            TaxCompanyPilotPerson(
                name="Ihor Osmanov",
                folder_url=_drive_folder("1TEReUTgln8MPtTCMIBJjaZq988rMxPn8"),
                evidence=[
                    "TIN card",
                    "Certificate of registration",
                    "Digital certificate issuance letter",
                    "Taxpayer account issuance letter",
                    "Passport",
                    "ITK",
                    "evisa",
                    "Bank statement",
                ],
                relationship_confidence="medium",
            ),
            TaxCompanyPilotPerson(
                name="Yaroslav Voitenko",
                folder_url=_drive_folder("1Caa_oMOSpl44KSX3fKZ8KCWlWRQTY-uB"),
                evidence=["Passport"],
                relationship_confidence="medium",
            ),
        ],
        documents=[
            TaxCompanyPilotDocument(name="AKTA", group="company", evidence_url=operational),
            TaxCompanyPilotDocument(name="DOKUMEN", group="company", evidence_url=operational),
            TaxCompanyPilotDocument(
                name="Profil Perseroan.pdf",
                group="company",
                evidence_url=_drive_file("1GvYpn2MD_JWaSFVvqxh6WJCBQ7bHUdzu"),
            ),
            TaxCompanyPilotDocument(
                name="Rincian PT.pdf",
                group="company",
                evidence_url=_drive_file("1i6HcJuwlFwM_rNMjSDjp6-Zh49I9rvyy"),
            ),
            TaxCompanyPilotDocument(name="SPT 2025", group="tax", evidence_url=tax),
            TaxCompanyPilotDocument(
                name="Laporan Keuangan PT Ocean Clothes and Shoes 2025",
                group="finance",
                evidence_url="https://docs.google.com/spreadsheets/d/1HI5OawsDsDQpl326lyDrT8IYr1VQ101nRQUYr4oltQ0",
                sensitivity="financial",
            ),
            TaxCompanyPilotDocument(
                name="Laporan Keuangan PT Ocean Clothes and Shoes 2026",
                group="finance",
                evidence_url="https://docs.google.com/spreadsheets/d/1hcHE48Pv8jPNWBJV1HBxGeDtijq-zfVFr_yI80_Vwfs",
                sensitivity="financial",
            ),
            TaxCompanyPilotDocument(name="INCOME", group="finance", evidence_url=tax),
            TaxCompanyPilotDocument(name="BILLING & PROOF", group="tax", evidence_url=tax),
            TaxCompanyPilotDocument(name="Employee", group="tax", evidence_url=tax),
        ],
        duplicate_candidates=[
            TaxCompanyPilotDuplicateCandidate(
                label="Operational tax folder vs canonical-like company folder",
                urls=[operational, canonical],
                confidence="medium",
            ),
        ],
        gaps=[
            TaxCompanyPilotGap(
                code="confirm_company_roles",
                label="Confirm director/shareholder/commissioner roles from company PDFs.",
                severity="high",
            ),
            TaxCompanyPilotGap(
                code="confirm_individual_crm_folders",
                label="Check whether Individual_CRM folders already exist for Natan, Ihor, and Yaroslav.",
                severity="medium",
            ),
            TaxCompanyPilotGap(
                code="separate_company_finance_rbac",
                label="Expose financial files only to internal users or confirmed company roles.",
                severity="high",
            ),
        ],
        evidence_links=[
            TaxCompanyPilotEvidenceLink(label="Operational folder", url=operational, kind="folder"),
            TaxCompanyPilotEvidenceLink(label="Canonical candidate", url=canonical, kind="folder"),
            TaxCompanyPilotEvidenceLink(label="Tax folder", url=tax, kind="folder"),
        ],
        ai_recap=[
            "Ocean is currently best represented by a DEA tax working folder plus a separate canonical-like company folder.",
            "The visible tax trail includes SPT 2025, finance sheets for 2025 and 2026, income, billing/proof, and employee folders.",
            "Person links are visible but roles must be confirmed from company PDFs before exposing company financial files on person pages.",
        ],
    )


def _bimala_map() -> TaxCompanyPilotMap:
    dewa_ayu = _drive_folder("12A9-sgVqC-pTg_vN3LydCRIcyPLBUwfR")
    operational = _drive_folder("192muakUUFdYZVq67w10dy_75R63nor_L")
    nested_company = _drive_folder("1XtwojMeO0ladAvjswmEdMclns7efdCaq")
    tax = _drive_folder("1j3ru9wKOEC1vP3AUPrteO95I4lm7UuAI")
    return TaxCompanyPilotMap(
        key="bimala",
        company=TaxCompanyPilotEntity(
            name="BIMALA / Bimala Investments Bali PT",
            aliases=["Bimala Investments Bali PT", "PT Bimala", "PT Bimala Investments Bali"],
        ),
        tax_member=TaxCompanyPilotTaxMember(
            name="Dewa Ayu",
            workspace_branch="TAX DEPARTMENT/Members/Dewa Ayu",
            source_folder_url=dewa_ayu,
        ),
        drive_folders={
            "dewa_ayu_target": dewa_ayu,
            "operational": operational,
            "nested_company": nested_company,
            "tax": tax,
        },
        persons=[
            TaxCompanyPilotPerson(
                name="Giulia Del Giudice",
                folder_url=_drive_folder("1Xy60Q9k5detu8oZhFWVWexDYh07Yx4LO"),
                evidence=["ITAS E28A Investor", "Passport", "CV", "Bank statement", "Address", "Travel", "Photo"],
                role_confidence="unconfirmed",
                relationship_confidence="confirmed",
            ),
            TaxCompanyPilotPerson(
                name="Gianluca Morelli",
                folder_url=_drive_folder("1a1LhqSttRqLwUgDXmOdV38QYTaYdMU6X"),
                evidence=["ITAS E28A Investor", "Passport", "CV", "Bank statement", "Address", "Travel", "Photo"],
                role_confidence="unconfirmed",
                relationship_confidence="confirmed",
            ),
            TaxCompanyPilotPerson(name="Giorgia Emidio", evidence=["Child evisa file"], relationship_confidence="unconfirmed"),
            TaxCompanyPilotPerson(name="Iuma Morelli", evidence=["Child evisa file"], relationship_confidence="unconfirmed"),
            TaxCompanyPilotPerson(name="Mailen Morelli", evidence=["Child evisa file"], relationship_confidence="unconfirmed"),
        ],
        documents=[
            TaxCompanyPilotDocument(name="Proof of receipt letter", group="tax", evidence_url=operational),
            TaxCompanyPilotDocument(name="TIN card", group="tax", evidence_url=operational),
            TaxCompanyPilotDocument(name="Certificate of registration", group="tax", evidence_url=operational),
            TaxCompanyPilotDocument(name="Taxpayer account issuance letter", group="tax", evidence_url=operational),
            TaxCompanyPilotDocument(name="EMAIL DJP & CORTAX ACSES", group="coretax", evidence_url=nested_company, sensitivity="credential"),
            TaxCompanyPilotDocument(name="Tax/2026", group="tax", evidence_url=tax),
            TaxCompanyPilotDocument(name="Bukti Lapor SPT zero 2024.pdf", group="tax", evidence_url=nested_company),
            TaxCompanyPilotDocument(name="FORM SPT 7117 2024.pdf", group="tax", evidence_url=nested_company),
            TaxCompanyPilotDocument(name="Dokument Pelengkap SPT PT Bimala Investment.pdf", group="tax", evidence_url=nested_company),
            TaxCompanyPilotDocument(name="LKPM Periode 4 PDFs", group="lkpm", evidence_url=nested_company),
            TaxCompanyPilotDocument(name="AKTA", group="company", evidence_url=nested_company),
            TaxCompanyPilotDocument(name="DOKUMEN", group="company", evidence_url=nested_company),
            TaxCompanyPilotDocument(name="Profil Perseroan.pdf", group="company", evidence_url=nested_company),
            TaxCompanyPilotDocument(name="Rincian PT.pdf", group="company", evidence_url=nested_company),
            TaxCompanyPilotDocument(name="Company bank statement", group="finance", evidence_url=nested_company, sensitivity="financial"),
        ],
        duplicate_candidates=[
            TaxCompanyPilotDuplicateCandidate(
                label="Bimala / PT Bimala / Bimala Investments Bali naming variants",
                urls=[operational, nested_company],
                confidence="medium",
            ),
        ],
        gaps=[
            TaxCompanyPilotGap(
                code="confirm_family_relationships",
                label="Confirm child/person relationships before nesting child files under a parent profile.",
                severity="high",
            ),
            TaxCompanyPilotGap(
                code="confirm_company_roles",
                label="Confirm company roles from Profil Perseroan and Rincian PT.",
                severity="high",
            ),
            TaxCompanyPilotGap(
                code="confirm_individual_crm_folders",
                label="Check whether Individual_CRM folders already exist for Giulia and Gianluca.",
                severity="medium",
            ),
        ],
        evidence_links=[
            TaxCompanyPilotEvidenceLink(label="Dewa Ayu target", url=dewa_ayu, kind="folder"),
            TaxCompanyPilotEvidenceLink(label="Operational BIMALA", url=operational, kind="folder"),
            TaxCompanyPilotEvidenceLink(label="Nested company", url=nested_company, kind="folder"),
            TaxCompanyPilotEvidenceLink(label="Tax folder", url=tax, kind="folder"),
        ],
        ai_recap=[
            "Bimala is currently represented through Dewa Ayu's legacy working folder plus nested company and tax folders.",
            "The visible evidence covers Coretax access, tax registration documents, SPT proof/form, LKPM, bank PDFs, and company documents.",
            "Giulia and Gianluca are visible person nodes; child-related evisa files should remain unconfirmed family edges until reviewed.",
        ],
    )


PILOT_MAPS: dict[str, TaxCompanyPilotMap] = {
    "ocean": _ocean_map(),
    "bimala": _bimala_map(),
}


def get_tax_company_pilot_map(company_key: str) -> TaxCompanyPilotMap | None:
    """Return the read-only pilot map for a normalized company key."""
    normalized = company_key.strip().lower()
    return PILOT_MAPS.get(normalized)
