"""
RAG Evaluation Dataset Builder

Builds evaluation datasets from:
- Real user queries (anonymized)
- Synthetic generated questions
- Ground truth answers from experts

Target: 50-100 question-answer pairs
Format: JSON with query, expected_answer, relevant_context_ids
"""

import json
import logging
import random
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from backend.app.core.logging_config import get_performance_logger
from backend.llm.base import LLMMessage
from backend.llm.client import UnifiedLLMClient, create_default_client

logger = logging.getLogger(__name__)

# Domain-specific question templates for synthetic generation
VISA_QUESTION_TEMPLATES = [
    "Apa persyaratan untuk mengajukan {visa_type}?",
    "Berapa lama proses pengajuan {visa_type}?",
    "Dokumen apa saja yang diperlukan untuk {visa_type}?",
    "Berapa biaya pengajuan {visa_type}?",
    "Apa perbedaan {visa_type1} dan {visa_type2}?",
    "Bagaimana cara memperpanjang {visa_type}?",
    "Apa saja ketentuan {visa_type} untuk {nationality}?",
    "Berapa lama masa berlaku {visa_type}?",
    "Apa konsekuensi jika {visa_type} kedaluwarsa?",
    "Bisakah {visa_type} diubah menjadi {visa_type2}?",
]

BUSINESS_QUESTION_TEMPLATES = [
    "Apa persyaratan pendirian {company_type} di Indonesia?",
    "Berapa modal dasar minimum untuk {company_type}?",
    "Dokumen apa saja yang diperlukan untuk mendirikan {company_type}?",
    "Berapa lama proses pendirian {company_type}?",
    "Apa perbedaan {company_type1} dan {company_type2}?",
    "Bagaimana cara mengurus izin usaha untuk {business_type}?",
    "Apa saja kewajiban pajak untuk {company_type}?",
    "Bagaimana proses penutupan {company_type}?",
    "Apa yang dimaksud dengan {business_term}?",
    "Bagaimana cara mengubah {company_type1} menjadi {company_type2}?",
]

TAX_QUESTION_TEMPLATES = [
    "Apa itu {tax_type} dan siapa yang wajib membayar?",
    "Berapa tarif {tax_type} untuk {entity_type}?",
    "Kapan tenggat waktu pembayaran {tax_type}?",
    "Bagaimana cara melaporkan {tax_type}?",
    "Apa sanksi jika terlambat membayar {tax_type}?",
    "Apa perbedaan {tax_type1} dan {tax_type2}?",
    "Bagaimana cara mengajukan pengembalian {tax_type}?",
    "Apa saja kredit pajak yang dapat dikurangkan?",
    "Bagaimana perhitungan {tax_type} untuk {business_type}?",
    "Apa itu tax amnesty dan bagaimana caranya?",
]

LEGAL_QUESTION_TEMPLATES = [
    "Apa yang dimaksud dengan {legal_term}?",
    "Bagaimana prosedur {legal_procedure}?",
    "Apa konsekuensi hukum dari {legal_action}?",
    "Berapa biaya untuk {legal_service}?",
    "Dokumen apa saja yang diperlukan untuk {legal_procedure}?",
    "Berapa lama proses {legal_procedure}?",
    "Apa perbedaan {legal_term1} dan {legal_term2}?",
    "Bagaimana cara mengajukan {legal_application}?",
    "Apa hak dan kewajiban {legal_party}?",
    "Bagaimana mekanisme penyelesaian {legal_dispute}?",
]

# Domain values for template filling
VISA_TYPES = [
    "KITAS",
    "KITAP",
    "Visa Kunjungan",
    "Visa B211A",
    "Visa B211B",
    "Visa D",
    "Visa on Arrival",
    "E-Visa",
    "Multiple Entry Visa",
    "Single Entry Visa",
    "Work Permit (IMTA)",
    "MERP",
    "Re-entry Permit",
    "Telex Visa",
    "Calling Visa",
]

COMPANY_TYPES = [
    "PT",
    "PT PMA",
    "CV",
    "Firma",
    "Perseorangan",
    "Koperasi",
    "PT Perorangan",
    "PMA",
    "PMDN",
    "Representative Office",
    "Branch Office",
    "Yayasan",
]

BUSINESS_TYPES = [
    "restoran",
    "kafe",
    "hotel",
    "villa",
    "rental mobil",
    "toko retail",
    "e-commerce",
    "jasa konsultan",
    "kontraktor",
    "importir",
    "eksportir",
    "manufaktur",
    "farmasi",
]

TAX_TYPES = [
    "PPh 21",
    "PPh 23",
    "PPh 25",
    "PPh 26",
    "PPh 29",
    "PPN",
    "PPNBM",
    "PBB",
    "BPHTB",
    "PPh Final",
    "Tax Amnesty",
    "SPT Tahunan",
    "SPT Masa",
]

NATIONALITIES = [
    "WNA",
    "WNI",
    "Amerika",
    "Australia",
    "Inggris",
    "Jepang",
    "Korea",
    "Cina",
    "India",
    "Jerman",
    "Prancis",
    "Belanda",
    "Malaysia",
    "Singapura",
]

LEGAL_TERMS = [
    "hak milik",
    "hak guna bangunan",
    "hak pakai",
    "hak sewa",
    "akta notaris",
    "perjanjian",
    "sertifikat",
    "IMB",
    "SLF",
    "izin lingkungan",
    "AMDAL",
    "UKL-UPL",
    "NIB",
    "TDP",
]


@dataclass
class EvaluationSample:
    """Single evaluation sample."""

    id: str
    query: str
    expected_answer: str
    relevant_context_ids: list[str]
    category: str
    difficulty: str  # easy, medium, hard
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class DatasetBuilder:
    """
    Builder for creating RAG evaluation datasets.

    Supports three data sources:
    1. Real user queries (anonymized from production logs)
    2. Synthetic questions generated from templates
    3. Expert-curated question-answer pairs

    Example:
        >>> builder = DatasetBuilder()
        >>> dataset = await builder.build_dataset(target_size=50)
        >>> builder.save_dataset(dataset, "eval_dataset.json")
    """

    def __init__(
        self,
        llm_client: UnifiedLLMClient | None = None,
        seed: int | None = None,
    ) -> None:
        """
        Initialize DatasetBuilder.

        Args:
            llm_client: LLM client for synthetic generation
            seed: Random seed for reproducibility
        """
        self.llm_client = llm_client or create_default_client()
        self.seed = seed or 42
        random.seed(self.seed)

        # Question templates by category
        self.templates = {
            "visa": VISA_QUESTION_TEMPLATES,
            "business": BUSINESS_QUESTION_TEMPLATES,
            "tax": TAX_QUESTION_TEMPLATES,
            "legal": LEGAL_QUESTION_TEMPLATES,
        }

        # Domain values for template filling
        self.domain_values = {
            "visa_type": VISA_TYPES,
            "visa_type1": VISA_TYPES,
            "visa_type2": VISA_TYPES,
            "company_type": COMPANY_TYPES,
            "company_type1": COMPANY_TYPES,
            "company_type2": COMPANY_TYPES,
            "business_type": BUSINESS_TYPES,
            "tax_type": TAX_TYPES,
            "tax_type1": TAX_TYPES,
            "tax_type2": TAX_TYPES,
            "nationality": NATIONALITIES,
            "legal_term": LEGAL_TERMS,
            "legal_term1": LEGAL_TERMS,
            "legal_term2": LEGAL_TERMS,
            "entity_type": ["perorangan", "badan usaha", "WNA", "WNI"],
            "legal_procedure": [
                "pendirian PT",
                "perpanjangan KITAS",
                "pengurusan NPWP",
                "pengajuan izin",
                "sertifikasi",
                "perjanjian",
            ],
            "legal_action": [
                "overstay",
                "tidak lapor SPT",
                "melanggar izin",
                "bentrok kepentingan",
                "pelanggaran kontrak",
            ],
            "legal_service": [
                "pendirian PT",
                "pengurusan visa",
                "konsultasi hukum",
                "perjanjian",
                "sertifikasi",
            ],
            "legal_application": [
                "izin tinggal",
                "izin kerja",
                "NPWP",
                "NIB",
                "perpanjangan dokumen",
                "banding pajak",
            ],
            "legal_party": [
                "pemegang saham",
                "direksi",
                "komisaris",
                "karyawan",
                "pemilik properti",
                "WNA bekerja",
            ],
            "legal_dispute": [
                "sengketa tanah",
                "perselisihan kontrak",
                "banding pajak",
                "sengketa ketenagakerjaan",
            ],
        }

        logger.info(f"DatasetBuilder initialized (seed={self.seed})")

    def _fill_template(self, template: str, category: str) -> str:
        """Fill a question template with random domain values."""
        question = template

        # Find all placeholders in template
        import re

        placeholders = re.findall(r"\{(\w+)\}", template)

        for placeholder in placeholders:
            if placeholder in self.domain_values:
                value = random.choice(self.domain_values[placeholder])
                question = question.replace(f"{{{placeholder}}}", value)

        return question

    def generate_synthetic_questions(
        self,
        category: str,
        count: int = 10,
    ) -> list[str]:
        """
        Generate synthetic questions from templates.

        Args:
            category: Question category (visa, business, tax, legal)
            count: Number of questions to generate

        Returns:
            List of generated questions
        """
        templates = self.templates.get(category, [])
        if not templates:
            logger.warning(f"No templates for category: {category}")
            return []

        questions = []
        for _ in range(count):
            template = random.choice(templates)
            question = self._fill_template(template, category)
            questions.append(question)

        logger.info(f"Generated {len(questions)} synthetic questions for {category}")
        return questions

    async def generate_synthetic_answer(
        self,
        query: str,
        category: str,
    ) -> str:
        """
        Generate synthetic ground truth answer using LLM.

        Args:
            query: The question to answer
            category: Question category

        Returns:
            Generated ground truth answer
        """
        prompt = f"""Anda adalah ahli {category} Indonesia. Berikan jawaban singkat dan akurat.

Pertanyaan: {query}

Jawaban (maksimal 3 paragraf, dalam Bahasa Indonesia):"""

        messages = [
            LLMMessage(
                role="system",
                content="Anda adalah ahli hukum dan bisnis Indonesia yang memberikan jawaban akurat dan terpercaya.",
            ),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            response = await self.llm_client.generate(
                messages=messages,
                temperature=0.3,
                max_tokens=1024,
            )
            return response.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate synthetic answer: {e}")
            return f"[Failed to generate answer: {str(e)}]"

    def create_expert_samples(self) -> list[EvaluationSample]:
        """
        Create expert-curated evaluation samples.

        Returns:
            List of expert-curated samples
        """
        expert_samples = [
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Apa itu KITAS dan apa bedanya dengan KITAP?",
                expected_answer=(
                    "KITAS (Kartu Izin Tinggal Terbatas) adalah izin tinggal untuk WNA "
                    "dengan masa berlaku terbatas (biasanya 6-24 bulan) dan dapat diperpanjang. "
                    "KITAP (Kartu Izin Tinggal Tetap) adalah izin tinggal permanen dengan "
                    "masa berlaku 5 tahun yang dapat diperpanjang tanpa batas. "
                    "KITAP memberikan hak lebih banyak seperti memiliki properti dan "
                    "mengajukan pinjaman bank."
                ),
                relevant_context_ids=["visa_kitaskitap_001", "immigration_guide_042"],
                category="visa",
                difficulty="easy",
                metadata={"source": "expert", "curated_by": "legal_team"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Berapa modal minimum untuk mendirikan PT PMA?",
                expected_answer=(
                    "Modal minimum untuk PT PMA (Penanaman Modal Asing) adalah "
                    "Rp 10 miliar (sekitar USD 700,000) untuk setiap bidang usaha. "
                    "Modal ini harus disetor paling sedikit 25% atau minimal Rp 2,5 miliar. "
                    "Persyaratan modal dapat bervariasi tergantung sektor bisnis dan "
                    "peraturan BKPM terbaru."
                ),
                relevant_context_ids=["business_ptpma_001", "bkpm_regulation_015"],
                category="business",
                difficulty="medium",
                metadata={"source": "expert", "curated_by": "legal_team"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Apa perbedaan PPh 21 dan PPh 23?",
                expected_answer=(
                    "PPh 21 adalah pajak penghasilan atas penghasilan karyawan atau "
                    "individu yang dipotong oleh pemberi kerja. PPh 23 adalah pajak "
                    "penghasilan atas penghasilan dari modal atau penyerahan jasa "
                    "yang dipotong oleh pihak yang membayar. Tarif PPh 21 bersifat "
                    "progresif (5-35%), sedangkan PPh 23 umumnya 15% untuk dividen "
                    "dan bunga, 2% untuk royalti dan jasa."
                ),
                relevant_context_ids=["tax_pph21_001", "tax_pph23_002"],
                category="tax",
                difficulty="medium",
                metadata={"source": "expert", "curated_by": "tax_team"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Bagaimana proses balik nama sertifikat tanah?",
                expected_answer=(
                    "Proses balik nama sertifikat tanah meliputi: 1) Penandatanganan "
                    "akta jual beli di hadapan notaris/PPAT, 2) Pembayaran BPHTB oleh pembeli, "
                    "3) Pembayaran PPh final oleh penjual, 4) Pengajuan permohonan balik nama "
                    "ke BPN dengan dokumen: sertifikat asli, KTP, NPWP, SPPT PBB, dan bukti "
                    "pembayaran pajak. Proses memakan waktu 7-14 hari kerja setelah dokumen lengkap."
                ),
                relevant_context_ids=["land_certificate_045", "bpn_procedure_032"],
                category="legal",
                difficulty="hard",
                metadata={"source": "expert", "curated_by": "legal_team"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Apa konsekuensi overstay visa di Indonesia?",
                expected_answer=(
                    "Overstay visa di Indonesia dikenakan denda Rp 1 juta per hari "
                    "dengan maksimum Rp 25 juta. Overstay lebih dari 60 hari dapat "
                    "menyebabkan deportasi dan masuk daftar hitam (blacklist) yang "
                    "melarang masuk ke Indonesia untuk periode tertentu. Dalam kasus "
                    "serius, dapat dikenakan tindakan pidana sesuai UU Keimigrasian."
                ),
                relevant_context_ids=["visa_overstay_012", "immigration_penalty_089"],
                category="visa",
                difficulty="medium",
                metadata={"source": "expert", "curated_by": "immigration_team"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Bagaimana cara mengurus NIB untuk usaha kecil?",
                expected_answer=(
                    "NIB (Nomor Induk Berusaha) diurus melalui OSS (Online Single Submission) "
                    "dengan langkah: 1) Login ke oss.go.id, 2) Pilih jenis pelaku usaha "
                    "(perorangan/badan usaha), 3) Isi data profil pengusaha, 4) Isi detail "
                    "kegiatan usaha (KBLI), 5) Unggah dokumen pendukung, 6) Verifikasi dan "
                    "terbitkan NIB. NIB gratis dan biasanya terbit dalam 1 hari kerja jika "
                    "dokumen lengkap."
                ),
                relevant_context_ids=["business_nib_023", "oss_guide_067"],
                category="business",
                difficulty="easy",
                metadata={"source": "expert", "curated_by": "business_team"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Kapan tenggat lapor SPT Tahunan untuk orang pribadi?",
                expected_answer=(
                    "Tenggat waktu pelaporan SPT Tahunan PPh Orang Pribadi adalah "
                    "31 Maret untuk tahun pajak berjalan. Jika tanggal tersebut jatuh "
                    "pada hari libur, tenggat diundur ke hari kerja berikutnya. "
                    "Keterlambatan pelaporan dikenakan denda administrasi Rp 100 ribu "
                    "untuk SPT PPh Orang Pribadi."
                ),
                relevant_context_ids=["tax_spt_annual_034", "dgt_procedure_078"],
                category="tax",
                difficulty="easy",
                metadata={"source": "expert", "curated_by": "tax_team"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Apa yang dimaksud dengan HGB dan berapa masa berlakunya?",
                expected_answer=(
                    "HGB (Hak Guna Bangunan) adalah hak untuk membangun dan memiliki "
                    "bangunan di atas tanah yang dikuasai negara atau orang lain. "
                    "HGB dapat dimiliki oleh WNI dan PT PMA. Masa berlaku HGB maksimal "
                    "30 tahun pertama, dapat diperpanjang 20 tahun, dan diperbaharui "
                    "maksimal 30 tahun. Total masa berlaku dapat mencapai 80 tahun."
                ),
                relevant_context_ids=["land_hgb_056", "property_rights_091"],
                category="legal",
                difficulty="medium",
                metadata={"source": "expert", "curated_by": "legal_team"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Dokumen apa saja yang diperlukan untuk perpanjangan KITAS?",
                expected_answer=(
                    "Dokumen untuk perpanjangan KITAS: 1) Paspor dengan masa berlaku "
                    "min. 18 bulan, 2) KITAS lama, 3) SKTT (Surat Keterangan Tempat Tinggal), "
                    "4) STM (Surat Tanda Melapor) dari kepolisian, 5) NPWP (jika sudah punya), "
                    "6) Fotokopi akta perusahaan (untuk KITAS kerja), 7) RPTKA, 8) IMTA, "
                    "9) Bukti pembayaran DPKK (USD 1,200/tahun), 10) Surat rekomendasi dari "
                    "instansi terkait. Perpanjangan diajukan maksimal 30 hari sebelum habis masa berlaku."
                ),
                relevant_context_ids=["visa_extension_044", "immigration_requirements_023"],
                category="visa",
                difficulty="hard",
                metadata={"source": "expert", "curated_by": "immigration_team"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Apa itu Tax Amnesty dan bagaimana mekanismenya?",
                expected_answer=(
                    "Tax Amnesty (Pengampunan Pajak) adalah program pemerintah yang "
                    "memberikan kelonggaran berupa penghapusan sanksi administrasi "
                    "dan sanksi pidana di bidang perpajakan dengan membayar uang tebusan. "
                    "Mekanisme: 1) Lapor harta yang belum/ kurang diungkapkan, 2) Hitung "
                    "dan bayar uang tebusan (2-17% tergantung jenis harta dan periode), "
                    "3) Dapatkan Surat Keterangan Pengampunan Pajak. Tax Amnesty Jilid II "
                    "berlaku hingga Juni 2025 dengan tarif tebusan mulai dari 6%."
                ),
                relevant_context_ids=["tax_amnesty_067", "dgt_program_034"],
                category="tax",
                difficulty="hard",
                metadata={"source": "expert", "curated_by": "tax_team"},
            ),
        ]

        logger.info(f"Created {len(expert_samples)} expert-curated samples")
        return expert_samples

    def create_real_user_samples(self) -> list[EvaluationSample]:
        """
        Create anonymized samples from real user queries.

        Note: These are representative samples, not actual user data.
        In production, this would query from anonymized logs.

        Returns:
            List of anonymized user samples
        """
        real_samples = [
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Bisa bantu jelasin cara bikin PT untuk bisnis online?",
                expected_answer=(
                    "Untuk mendirikan PT untuk bisnis online, persyaratannya: "
                    "1) Minimal 2 pemegang saham, 2) Modal dasar min. Rp 50 juta "
                    "(disetor min. 25%), 3) Susunan direksi dan komisaris, "
                    "4) Akta pendirian di notaris, 5) Pengesahan dari Kemenkumham, "
                    "6) NPWP dan NIB. Proses sekitar 2-4 minggu dengan biaya "
                    "mulai dari Rp 5-10 juta."
                ),
                relevant_context_ids=["business_pt_online_001", "nib_procedure_045"],
                category="business",
                difficulty="easy",
                metadata={"source": "anonymized_user", "channel": "whatsapp"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Saya WNA mau beli rumah di Bali, bisa nggak?",
                expected_answer=(
                    "WNA tidak dapat memiliki hak milik (SHM) atas tanah di Indonesia "
                    "berdasarkan UUPA. Namun, WNA dapat: 1) Sewa tanah jangka panjang "
                    "(hak sewa), 2) Memiliki unit apartemen (hak pakai atas satuan "
                    "rumah susun), 3) Melalui PT PMA dengan HGB, 4) Melalui nominee "
                    "(tidak direkomendasikan karena berisiko hukum). Untuk properti "
                    "di Bali, opsi paling aman adalah sewa jangka panjang atau "
                    "beli apartemen."
                ),
                relevant_context_ids=["property_wna_078", "land_rights_034"],
                category="legal",
                difficulty="medium",
                metadata={"source": "anonymized_user", "channel": "chat"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Saya karyawan, kapan harus lapor SPT ya?",
                expected_answer=(
                    "Karyawan wajib lapor SPT Tahunan PPh Orang Pribadi paling lambat "
                    "31 Maret setiap tahun untuk pajak tahun sebelumnya. Walaupun "
                    "pajak sudah dipotong oleh perusahaan (PPh 21), pelaporan SPT "
                    "tetap wajib. Jika hanya punya satu penghasilan dari pekerjaan "
                    "dan sudah dipotong PPh 21 final, bisa lapor SPT 1770 SS (sederhana). "
                    "Keterlambatan lapor dikenakan denda Rp 100 ribu."
                ),
                relevant_context_ids=["tax_spt_employee_045", "dgt_guide_023"],
                category="tax",
                difficulty="easy",
                metadata={"source": "anonymized_user", "channel": "email"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Anak saya lahir di Indonesia, otomatis WNI kan?",
                expected_answer=(
                    "Anak yang lahir di Indonesia dari orang tua WNA tidak otomatis "
                    "menjadi WNI. Status kewarganegaraan mengikuti orang tua (ius sanguinis). "
                    "Namun, anak tersebut dapat: 1) Ajukan kewarganegaraan Indonesia jika "
                    "tinggal di Indonesia dan salah satu orang tua menjadi WNI, 2) Dapatkan "
                    "KITAS sebagai tanggungan orang tua, 3) Ajukan naturalisasi jika memenuhi "
                    "syarat. Jika orang tua stateless atau tidak dapat ditentukan kewarganegaraannya, "
                    "anak dapat menjadi WNI."
                ),
                relevant_context_ids=["citizenship_child_056", "immigration_family_089"],
                category="visa",
                difficulty="hard",
                metadata={"source": "anonymized_user", "channel": "consultation"},
            ),
            EvaluationSample(
                id=str(uuid.uuid4()),
                query="Saya punya PT PMA, kewajiban laporan keuangan tahunan apa saja?",
                expected_answer=(
                    "PT PMA wajib menyampaikan: 1) Laporan Keuangan Tahunan yang diaudit "
                    "oleh akuntan publik (dalam Bahasa Inggris dan Indonesia), 2) Laporan "
                    "Tahunan kepada Kemenkumham dalam jangka waktu 6 bulan setelah tahun "
                    "buku berakhir, 3) Laporan PKBL (Penanaman Modal Dalam Negeri) kepada "
                    "BKPM secara berkala, 4) Laporan perubahan kepemilikan saham dan "
                    "perubahan pengurus. Keterlambatan pelaporan dikenakan sanksi "
                    "administratif berupa denda."
                ),
                relevant_context_ids=["business_reporting_067", "bkpm_compliance_034"],
                category="business",
                difficulty="hard",
                metadata={"source": "anonymized_user", "channel": "portal"},
            ),
        ]

        logger.info(f"Created {len(real_samples)} anonymized user samples")
        return real_samples

    async def build_dataset(
        self,
        target_size: int = 50,
        expert_ratio: float = 0.3,
        user_ratio: float = 0.2,
        synthetic_ratio: float = 0.5,
        generate_answers: bool = False,
    ) -> list[EvaluationSample]:
        """
        Build evaluation dataset from multiple sources.

        Args:
            target_size: Target number of samples (default: 50)
            expert_ratio: Ratio of expert-curated samples
            user_ratio: Ratio of real user samples
            synthetic_ratio: Ratio of synthetic samples
            generate_answers: Whether to generate answers for synthetic questions

        Returns:
            Combined evaluation dataset
        """
        with get_performance_logger(__name__, "dataset_building"):
            assert abs(expert_ratio + user_ratio + synthetic_ratio - 1.0) < 0.01, (
                "Ratios must sum to 1.0"
            )

            dataset: list[EvaluationSample] = []

            # Add expert samples
            expert_count = int(target_size * expert_ratio)
            expert_samples = self.create_expert_samples()
            dataset.extend(expert_samples[:expert_count])

            # Add real user samples
            user_count = int(target_size * user_ratio)
            user_samples = self.create_real_user_samples()
            dataset.extend(user_samples[:user_count])

            # Generate synthetic samples
            synthetic_count = target_size - len(dataset)
            categories = ["visa", "business", "tax", "legal"]
            questions_per_category = synthetic_count // len(categories)

            for category in categories:
                questions = self.generate_synthetic_questions(
                    category=category,
                    count=questions_per_category,
                )

                for question in questions:
                    sample = EvaluationSample(
                        id=str(uuid.uuid4()),
                        query=question,
                        expected_answer="",  # Will be filled if generate_answers=True
                        relevant_context_ids=[],  # Will be filled by retrieval
                        category=category,
                        difficulty=random.choice(["easy", "medium", "hard"]),
                        metadata={"source": "synthetic", "template_generated": True},
                    )
                    dataset.append(sample)

            # Generate answers for synthetic samples if requested
            if generate_answers:
                logger.info("Generating answers for synthetic samples...")
                for sample in dataset:
                    if sample.metadata.get("source") == "synthetic":
                        sample.expected_answer = await self.generate_synthetic_answer(
                            sample.query,
                            sample.category,
                        )

            # Shuffle dataset
            random.shuffle(dataset)

            logger.info(
                f"Built evaluation dataset with {len(dataset)} samples: "
                f"expert={len([s for s in dataset if s.metadata.get('source') == 'expert'])}, "
                f"user={len([s for s in dataset if s.metadata.get('source') == 'anonymized_user'])}, "
                f"synthetic={len([s for s in dataset if s.metadata.get('source') == 'synthetic'])}",
            )

            return dataset

    def save_dataset(
        self,
        dataset: list[EvaluationSample],
        filepath: str,
    ) -> None:
        """
        Save dataset to JSON file.

        Args:
            dataset: Evaluation dataset to save
            filepath: Path to save JSON file
        """
        data = {
            "metadata": {
                "total_samples": len(dataset),
                "categories": list({s.category for s in dataset}),
                "difficulty_distribution": {
                    "easy": len([s for s in dataset if s.difficulty == "easy"]),
                    "medium": len([s for s in dataset if s.difficulty == "medium"]),
                    "hard": len([s for s in dataset if s.difficulty == "hard"]),
                },
                "source_distribution": {
                    "expert": len([s for s in dataset if s.metadata.get("source") == "expert"]),
                    "user": len(
                        [s for s in dataset if s.metadata.get("source") == "anonymized_user"],
                    ),
                    "synthetic": len(
                        [s for s in dataset if s.metadata.get("source") == "synthetic"],
                    ),
                },
            },
            "samples": [s.to_dict() for s in dataset],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved dataset to {filepath}")

    def load_dataset(self, filepath: str) -> list[EvaluationSample]:
        """
        Load dataset from JSON file.

        Args:
            filepath: Path to JSON file

        Returns:
            List of evaluation samples
        """
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        samples = [EvaluationSample(**s) for s in data["samples"]]
        logger.info(f"Loaded {len(samples)} samples from {filepath}")
        return samples
