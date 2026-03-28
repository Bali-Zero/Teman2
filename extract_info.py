import re
import json

text_content = """
PROFIL PERUSAHAAN
PT ZORRIN VIDEO PRODUCTION
DIMOHONKAN OLEH

: Dea Nanda Putri Natasya

Email

: deanandaputrinatasya@gmail.com

Nomor HP

: 081235369255

Tanggal Permohonan

: 25 Juni 2025 pukul 13:58:11

Tanggal Pembayaran

: 25 Juni 2025 pukul 14:01:41

Tujuan Permohonan

: Permohonan Profil Terakhir PT

: 25 Juni 2025 pukul 14:06:34

Telah diunduh

: 1 kali

JE
N

Waktu Unduh PDF

AH

INFORMASI BERKAS PDF

U

Nama

I

D

AR

I

D

IT

VERIFIKASI BERKAS PDF

ES

M

1. Persetujuan Perubahan Anggaran Dasar And Pemberitahuan
Perubahan Anggaran Dasar
JENIS PERUBAHAN

R

Jenis Perubahan

: 1. Persetujuan Perubahan Anggaran Dasar
- Peningkatan modal dasar
2. Pemberitahuan Perubahan Anggaran Dasar
- Peningkatan Modal Ditempatkan/Disetor

DATA PERSEROAN

Nama Perseroan

: ZORRIN VIDEO PRODUCTION

Nama Singkatan

:

Nomor SK Pengesahan

: AHU-0019212.AH.01.02.Tahun 2025

Tanggal SK

: 17 Maret 2025

Nomor SP Anggaran
Dasar

: AHU-AH.01.03-0081316

Tanggal SP Anggaran
Dasar

: 17 Maret 2025

Jenis Perseroan

: PMA

Jangka Waktu Perseroan : TIDAK TERBATAS
Status Perseroan

: TERTUTUP

Nomor Telepon

: 0361736342

Jenis Transaksi

: PERUBAHAN

DATA NOTARIS

: ESI SUSANTI S.H., M.Kn.

Kedudukan Notaris

: JAKARTA PUSAT

Nomor Akta

: 21

Tanggal Akta

: 14 Maret 2025

KEDUDUKAN PERSEROAN

: JL. RAYA ANYAR GANG III No. 2

RT

: 000

RW

: 000

Kode Pos

: 80361

Kelurahan

: KEROBOKAN KLOD

Kecamatan

: KUTA UTARA

Kabupaten

: KABUPATEN BADUNG

Provinsi

: BALI

IT

D

AR

I

MAKSUD DAN TUJUAN

JE
N

Alamat

AH

U

Nama Notaris

Judul KBLI

70209 Aktivitas
Konsultasi
Manajemen
Lainnya

R

ES

M

1

Kode
KBLI

I

No

D

Daftar Kegiatan Usaha
Data KBLI Tahun : 2020

Uraian KBLI

Kelompok ini mencakup ketentuan bantuan nasihat,
bimbingan dan operasional usaha dan permasalahan
organisasi dan manajemen lainnya, seperti
perencanaan strategi dan organisasi; keputusan
berkaitan dengan keuangan; tujuan dan kebijakan
pemasaran; perencanaan, praktik dan kebijakan
sumber daya manusia; perencanaan penjadwaluan dan
pengontrolan produksi. Penyediaan jasa usaha ini
dapat mencakup bantuan nasihat, bimbingan dan
operasional berbagai fungsi manajemen, konsultasi
manajemen olah agronomist dan agricultural economis
pada bidang pertanian dan sejenisnya, rancangan dari
metode dan prosedur akuntansi, program akuntansi
biaya, prosedur pengawasan anggaran belanja,
pemberian nasihat dan bantuan untuk usaha dan
pelayanan masyarakat dalam perencanaan,
pengorganisasian, efisiensi dan pengawasan, informasi
manajemen dan lain-lain. Termasuk jasa pelayanan
studi investasi infrastruktur.

74141 Aktivitas
Desain
Khusus Film,
Video,
Program TV,
Animasi dan
Komik

Kelompok ini mencakup kegiatan perencanaan konten
kreatif khusus film, video, program tv, animasi dan
komik antara lain: desain cerita; desain ketokohan dan
pemilihan peran; desain artistik dan visual; desain
teknis produksi; dan kebutuhan penunjang lainya.
Kegiatan pembuatan komik masuk dalam kelompok
90023.

3

74201 Aktivitas
Fotografi

Kelompok ini mencakup kegiatan fotografi atau
pemotretan, baik untuk perorangan atau kepentingan
bisnis, seperti fotografi untuk paspor, sekolah,
pernikahan dan lain-lain; fotografi untuk tujuan
komersil, publikasi, mode, real estat atau pariwacana;
fotografi dari udara (pemotretan dari udara atau aerial
photography) dan perekaman video untuk acara
seperti pernikahan, rapat dan lain-lain. Kegiatan lain
adalah pemrosesan dan pencetakan hasil pemotretan
tersebut, meliputi pencucian, pencetakan dan
perbesaran dari negatif film atau cine-film yang
diambil klien; laboratorium pencucian film dan
pencetakan foto; photo shop (tempat cuci foto) satu
jam (bukan bagian dari toko kamera); mounting slide
dan penggandaan dan restoring atau pengubahan
sedikit tranparasi dalam hubungannya dengan
fotografi. Termasuk juga kegiatan jurnalis foto dan
pembuatan mikrofilm dari dokumen. Produksi film
untuk bioskop dan video dan distribusinya dimasukkan
dalam golongan 591.

4

74902 Aktivitas
Konsultasi
Bisnis Dan
Broker Bisnis

Kelompok ini mencakup usaha pemberian saran dan
bantuan operasional pada dunia bisnis, seperti
kegiatan broker bisnis yang mengatur pembelian dan
penjualan bisnis berskala kecil dan menengah,
termasuk praktik profesional, kegiatan broker hak
paten (pengaturan pembelian dan penjualan hak
paten), kegiatan penilaian selain real estat dan
asuransi (untuk barang antik, perhiasan dan lain-lain),
audit rekening dan informasi tarif barang atau
muatan, kegiatan pengukuran kuantitas dan kegiatan
peramalan cuaca. Tidak termasuk makelar real estat.

ES

M

I

D

AR

I

D
IT

JE
N

AH

U

2

MODAL DASAR

R

Klasifikasi
Saham

Harga Per Lembar

-

Rp. 1000000.

Jumlah Lembar
Saham

Total

20.000 Rp. 20.000.000.000

MODAL DITEMPATKAN

Klasifikasi
Saham

Harga Per Lembar

MODAL DISETOR
Rp 20.000.000.000
Dalam bentuk uang.

Rp. 1000000.

Jumlah Lembar
Saham

Total

20.000 Rp. 20.000.000.000

PENGURUS DAN PEMEGANG SAHAM

Nama

Jabatan

Alamat

Klasifikasi
Saham

Jumlah
Lembar
Saham

Total

KOMISARIS

-

10.000 Rp. 10.000.000.000

VOLODYMYR
ZORIN

DIREKTUR

-

10.000 Rp. 10.000.000.000

ALINA
ZORINA
"""

def parse_indonesian_number(s):
    if s is None:
        return None
    # Remove 'Rp.', '.', and ',' then convert to int
    s = s.replace('Rp.', '').replace('.', '').replace(',', '').strip()
    try:
        return int(s)
    except ValueError:
        return None

# Initialize output dictionary
output = {
    "total_authorized_capital": None,
    "share_nominal_value": None,
    "kbli_codes": None,
    "shareholders": []
}

# Extract Total Authorized Capital
total_authorized_capital_match = re.search(r"MODAL DASAR.*?Total\s+\d+\.?\d*\s+(Rp\.\s[\d\.]+)", text_content, re.DOTALL)
if total_authorized_capital_match:
    output["total_authorized_capital"] = parse_indonesian_number(total_authorized_capital_match.group(1))

# Extract Share Nominal Value
share_nominal_value_match = re.search(r"MODAL DASAR.*?Harga Per Lembar\s+-\s+(Rp\.\s[\d\.]+)", text_content, re.DOTALL)
if share_nominal_value_match:
    output["share_nominal_value"] = parse_indonesian_number(share_nominal_value_match.group(1))

# Extract KBLI Codes
# Debugging: Print text_content to inspect newlines
print("--- text_content ---")
print(text_content)
print("--- end text_content ---")

# Look for lines that start with a number, then "Kode KBLI", then the 5-digit code.
kbli_codes_matches = re.findall(r"^\s*\d+\s+Kode\s+KBLI\s+(\d{5})", text_content, re.MULTILINE)
# Debugging: Print kbli_codes_matches
print("KBLI Matches (strict):", kbli_codes_matches)
if kbli_codes_matches:
    output["kbli_codes"] = ",".join(kbli_codes_matches)
else:
    # Simpler regex if the above is too strict
    kbli_codes_matches = re.findall(r"Kode\s+KBLI\s+(\d{5})", text_content)
    print("KBLI Matches (simple):", kbli_codes_matches)
    if kbli_codes_matches:
        output["kbli_codes"] = ",".join(kbli_codes_matches)


# Extract Shareholders
shareholders_section_match = re.search(r"PENGURUS DAN PEMEGANG SAHAM\s+(.*?)(?=\s{2,}|\Z)", text_content, re.DOTALL)
if shareholders_section_match:
    shareholders_section = shareholders_section_match.group(1)
    # Debugging: Print shareholders_section
    print("Shareholders Section:", shareholders_section)
    
    # Get total shares for percentage calculation
    total_shares_match = re.search(r"MODAL DASAR.*?Jumlah Lembar\s+Saham\s+(\d+\.?\d*)", text_content, re.DOTALL)
    total_shares = parse_indonesian_number(total_shares_match.group(1)) if total_shares_match else 1 # Default to 1 to avoid division by zero

    # Pattern to capture multiline names, role, and shares count
    # Use (.+?) to capture the name non-greedily, including newlines due to re.DOTALL
    shareholder_pattern = re.compile(
        r"(.+?)\s*(KOMISARIS|DIREKTUR)\s*-\s*(\d+\.?\d*)\s*Rp\.\s[\d\.]+",
        re.DOTALL | re.IGNORECASE
    )
    
    # Process the entire section to find all shareholders
    shareholder_data = shareholder_pattern.findall(shareholders_section)
    # Debugging: Print shareholder_data
    print("Shareholder Data:", shareholder_data)

    for name, role, shares_count_str in shareholder_data:
        # Clean up name: remove excess whitespace and newlines, then strip
        name = re.sub(r'\s+', ' ', name).strip()
        shares_count = parse_indonesian_number(shares_count_str)
        
        mapped_role = None
        if "KOMISARIS" in role.upper():
            mapped_role = "komisaris"
        elif "DIREKTUR" in role.upper():
            mapped_role = "direktur"
        
        ownership_percentage = None
        if total_shares and shares_count is not None:
            ownership_percentage = (shares_count / total_shares) * 100
            
        output["shareholders"].append({
            "name": name,
            "role": mapped_role,
            "shares_count": shares_count,
            "ownership_percentage": ownership_percentage
        })

print(json.dumps(output, indent=2))
