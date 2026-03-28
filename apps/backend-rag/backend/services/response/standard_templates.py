"""
Standard Response Templates for ZANTARA
Defines structured markdown formats for key business domains (Visa, Tax, etc.)
to ensure consistency and readability.
"""

from backend.app.core.config import settings


def get_visa_template(language: str = "en") -> str:
    """
    Returns the markdown template for Visa/KITAS responses.
    """
    if language == "it":
        return f"""
### 📋 Scheda Visto: [NOME_VISTO] (Codice: [CODICE])

| Caratteristica | Dettaglio |
| :--- | :--- |
| **Scopo** | [Scopo principale: Lavoro, Investimento, Turismo, etc.] |
| **Durata** | [Validità del visto] |
| **Costo ({settings.COMPANY_NAME})** | [Prezzo ufficiale da get_pricing] |
| **Tempo di Processo** | [Giorni lavorativi stimati] |

#### ✅ Requisiti Principali
- [Requisito 1]
- [Requisito 2]
- [Requisito 3]

#### ⚠️ Note Importanti
[Eventuali restrizioni, divieti o consigli strategici]
"""
    if language == "id":
        return f"""
### 📋 Detail Visa: [NAMA_VISA] (Kode: [KODE])

| Fitur | Detail |
| :--- | :--- |
| **Tujuan** | [Tujuan utama: Kerja, Investasi, Wisata, dll.] |
| **Durasi** | [Masa berlaku] |
| **Biaya ({settings.COMPANY_NAME})** | [Harga resmi dari get_pricing] |
| **Waktu Proses** | [Estimasi hari kerja] |

#### ✅ Persyaratan Utama
- [Syarat 1]
- [Syarat 2]
- [Syarat 3]

#### ⚠️ Catatan Penting
[Batasan, larangan, atau saran strategis]
"""
    # Default English
    return f"""
### 📋 Visa Snapshot: [VISA_NAME] (Code: [CODE])

| Feature | Detail |
| :--- | :--- |
| **Purpose** | [Main purpose: Work, Investment, Tourism, etc.] |
| **Duration** | [Validity period] |
| **Cost ({settings.COMPANY_NAME})** | [Official price from get_pricing] |
| **Process Time** | [Estimated working days] |

#### ✅ Key Requirements
- [Requirement 1]
- [Requirement 2]
- [Requirement 3]

#### ⚠️ Important Notes
[Any restrictions, prohibitions, or strategic advice]
"""


def get_tax_template(language: str = "en") -> str:
    """
    Returns the markdown template for Tax responses.
    """
    if language == "it":
        return """
### 💰 Riepilogo Fiscale: [TIPO_IMPOSTA]

| Voce | Dettaglio |
| :--- | :--- |
| **Aliquota** | [Percentuale o importo fisso] |
| **Base Imponibile** | [Su cosa si calcola] |
| **Scadenza** | [Quando pagare/dichiarare] |
| **Soggetto** | [Chi deve pagare: PT PMA, Individuo, etc.] |

#### 🧮 Esempio di Calcolo
> Se l'importo è **[X]**, l'imposta è **[Y]**.
> *Formula: [X] * [Aliquota] = [Y]*

#### 💡 Consiglio Strategico
[Consiglio su deduzioni, conformità o pianificazione]
"""
    if language == "id":
        return """
### 💰 Ringkasan Pajak: [JENIS_PAJAK]

| Item | Detail |
| :--- | :--- |
| **Tarif** | [Persentase atau jumlah tetap] |
| **Dasar Pengenaan** | [Dihitung dari apa] |
| **Tenggat Waktu** | [Kapan bayar/lapor] |
| **Subjek** | [Siapa yang bayar: PT PMA, Perorangan, dll.] |

#### 🧮 Contoh Perhitungan
> Jika jumlahnya **[X]**, pajaknya adalah **[Y]**.
> *Rumus: [X] * [Tarif] = [Y]*

#### 💡 Saran Strategis
[Saran tentang pengurangan, kepatuhan, atau perencanaan]
"""
    # Default English
    return """
### 💰 Tax Summary: [TAX_TYPE]

| Item | Detail |
| :--- | :--- |
| **Rate** | [Percentage or fixed amount] |
| **Tax Base** | [What it's calculated on] |
| **Deadline** | [When to pay/file] |
| **Subject** | [Who pays: PT PMA, Individual, etc.] |

#### 🧮 Calculation Example
> If amount is **[X]**, tax is **[Y]**.
> *Formula: [X] * [Rate] = [Y]*

#### 💡 Strategic Tip
[Tip on deductions, compliance, or planning]
"""


def get_company_setup_template(language: str = "en") -> str:
    """
    Returns the markdown template for Company Setup (PT PMA) responses.
    """
    if language == "it":
        return """
### 🏢 Setup Aziendale: [TIPO_AZIENDA] (es. PT PMA)

| Parametro | Dettaglio |
| :--- | :--- |
| **Proprietà Straniera** | [Max % consentita per il settore] |
| **Capitale Minimo** | [Capitale versato richiesto] |
| **KBLI (Codici)** | [Codici attività suggeriti] |
| **Tempo Setup** | [Settimane stimate] |

#### 🚀 Roadmap di Attivazione
1. **Nome & Approvazione**: [Dettagli]
2. **Atto Notarile & SK**: [Dettagli]
3. **NIB & Licenze**: [Dettagli]
4. **Conto Bancario**: [Dettagli]

#### ⚠️ Punto Critico
[Il rischio o l'attenzione principale per questo tipo di azienda]
"""
    if language == "id":
        return """
### 🏢 Pendirian Perusahaan: [TIPE_PERUSAHAAN] (cth. PT PMA)

| Parameter | Detail |
| :--- | :--- |
| **Kepemilikan Asing** | [Maks % yang diizinkan] |
| **Modal Minimum** | [Modal disetor yang diperlukan] |
| **KBLI (Kode)** | [Kode aktivitas yang disarankan] |
| **Waktu Setup** | [Estimasi minggu] |

#### 🚀 Roadmap Aktivasi
1. **Nama & Persetujuan**: [Detail]
2. **Akta Notaris & SK**: [Detail]
3. **NIB & Izin**: [Detail]
4. **Rekening Bank**: [Detail]

#### ⚠️ Poin Kritis
[Risiko atau perhatian utama untuk jenis perusahaan ini]
"""
    # Default English
    return """
### 🏢 Company Setup: [COMPANY_TYPE] (e.g., PT PMA)

| Parameter | Detail |
| :--- | :--- |
| **Foreign Ownership** | [Max % allowed for sector] |
| **Min Capital** | [Paid-up capital required] |
| **KBLI (Codes)** | [Suggested activity codes] |
| **Setup Time** | [Estimated weeks] |

#### 🚀 Activation Roadmap
1. **Name & Approval**: [Detail]
2. **Deed & SK**: [Detail]
3. **NIB & Licenses**: [Detail]
4. **Bank Account**: [Detail]

#### ⚠️ Critical Point
[Main risk or focus area for this company type]
"""
