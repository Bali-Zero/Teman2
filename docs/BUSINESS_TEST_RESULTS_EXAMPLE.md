# Business Test Results - Report Struttura

Questo documento mostra la struttura attesa dei risultati del test e le risposte di esempio per ogni categoria.

## ⚠️ NOTA IMPORTANTE

Per eseguire i test reali, è necessario:

1. **Autenticazione**: Fornire `AUTH_TOKEN` o `NUZANTARA_API_KEY` come variabile d'ambiente
2. **Rate Limiting**: Il backend ha un limite di 30 richieste per minuto
3. **Tempo**: Il test completo richiede ~15-20 minuti

## Struttura Risultati Attesi

### Per Ogni Domanda

```json
{
  "question_id": "Q1",
  "question": "Ciao! Che tipo di visto serve per aprire un'attività a Bali?",
  "language": "it",
  "complexity": "semplice",
  "success": true,
  "response_time": 3.45,
  "response": "[Risposta completa con tone Jaksel]",
  "model_used": "gemma-9b-jaksel",
  "error": null
}
```

### Metriche da Valutare

- **Success Rate**: % di domande con risposta valida
- **Response Time**: Tempo medio di risposta (target: <5s)
- **Model Usage**: % di risposte da Jaksel vs Gemini fallback
- **Tone Jaksel**: Presenza di caratteristiche Jaksel nella risposta
- **Language Detection**: Corrispondenza lingua domanda/risposta

---

## RISPOSTE ATTESE PER CATEGORIA

### CATEGORIA 1: IMMIGRAZIONE & VISA

#### Q1 - Italiano, Semplice
**Domanda**: "Ciao! Che tipo di visto serve per aprire un'attività a Bali?"

**Risposta Attesa (Tone Jaksel)**:
```
Halo! Untuk buka usaha di Bali, lo perlu KITAS Investor.
Ini visa yang khusus buat orang asing yang mau invest atau buka bisnis di Indonesia.

Prosesnya:
- Minimal investasi: 1 miliar rupiah (atau setara)
- Lo perlu buat PT PMA dulu
- Dokumen: paspor, foto, surat keterangan kesehatan, dll
- Waktu proses: sekitar 2-3 bulan

Kalau lo mau kerja remote dari Bali (tapi gak invest), bisa pakai B211A atau visa turis yang diperpanjang.

Ada yang mau lo tanya lebih detail?
```

**Metriche Attese**:
- Tone Jaksel: ✅ (slang Jakarta, "lo", "gak")
- Lingua: ID (adattato da IT)
- Model: gemma-9b-jaksel
- Tempo: 2-4s

---

#### Q4 - Inglese, Semplice
**Domanda**: "Hey! What visa do I need to work remotely from Bali?"

**Risposta Attesa (Tone Jaksel in English)**:
```
Hey! So, untuk kerja remote dari Bali, lo punya beberapa opsi:

1. **B211A Visa** - Business visa, bisa extend sampai 6 bulan
2. **Tourist Visa** - Bisa extend beberapa kali, tapi ada limit
3. **KITAS** - Kalau lo mau stay lebih lama dan invest

Tapi hati-hati ya, kalau lo kerja remote untuk perusahaan luar negeri, technically lo gak boleh kerja di Indonesia tanpa visa kerja yang proper.

Best option? B211A kalau lo mau stay 3-6 bulan, atau KITAS kalau lo serius mau settle di sini.

Need more details?
```

**Metriche Attese**:
- Tone Jaksel: ✅ (mix ID/EN, "lo", "gak")
- Lingua: EN (con influenze ID)
- Model: gemma-9b-jaksel
- Tempo: 2-4s

---

### CATEGORIA 2: TASSE & PERPAJAKAN

#### Q9 - Italiano, Semplice
**Domanda**: "Come funziona il sistema fiscale in Indonesia? Devo pagare le tasse se sono straniero?"

**Risposta Attesa (Tone Jaksel)**:
```
Oke, jadi sistem pajak di Indonesia itu kayak gini:

**Kalau lo WNA (Warga Negara Asing)**:
- Lo wajib bayar pajak kalau lo tinggal di Indonesia lebih dari 183 hari dalam setahun
- Atau kalau lo punya penghasilan dari Indonesia
- Lo perlu daftar NPWP (Nomor Pokok Wajib Pajak)

**Tarif Pajak**:
- Penghasilan sampai 60 juta: 5%
- 60-250 juta: 15%
- 250-500 juta: 25%
- Di atas 500 juta: 30%

**Kalau lo punya PT PMA**:
- Corporate tax: 22% (turun dari 25% di 2022)
- Ada tax holiday untuk beberapa sektor (tech, manufacturing, etc.)

Intinya: kalau lo kerja atau punya bisnis di sini, ya harus bayar pajak. Gak bisa avoid, kecuali lo cuma turis yang stay kurang dari 183 hari.

Ada yang mau lo tanya lebih detail soal pajak?
```

**Metriche Attese**:
- Tone Jaksel: ✅
- Lingua: ID (adattato da IT)
- Model: gemma-9b-jaksel
- Tempo: 3-5s

---

#### Q11 - Italiano, Complessa
**Domanda**: "La mia azienda ha fatturato 4.5 miliardi di rupie quest'anno. Qual è la struttura fiscale ottimale per ridurre il carico fiscale? Ci sono incentivi fiscali disponibili?"

**Risposta Attesa (Tone Jaksel)**:
```
Wah, 4.5 miliar itu lumayan besar! Oke, lo perlu strategi pajak yang smart.

**Struktur Fiskal Ottimale**:

1. **Tax Holiday** - Kalau lo di sektor prioritas (tech, manufacturing, agribisnis), bisa dapat tax holiday sampai 20 tahun
   - Tahun 1-5: 100% tax exemption
   - Tahun 6-10: 50% tax exemption
   - Tahun 11-20: 25% tax exemption

2. **Tax Allowance** - Pengurangan pajak 30-100% untuk investasi di daerah tertentu
   - Cocok kalau lo mau expand ke luar Jakarta/Bali

3. **PPN (VAT) Strategy**:
   - Pastikan lo register sebagai PKP (Pengusaha Kena Pajak)
   - Lo bisa claim kembali PPN yang lo bayar untuk operasional

4. **Dividend Strategy**:
   - Kalau lo ambil dividen, ada tax 10% (atau 0% kalau reinvest)

**Action Items**:
- Cek apakah sektor lo eligible untuk tax holiday
- Konsultasi dengan konsultan pajak yang certified
- Pastikan semua dokumen compliance (SPT, laporan keuangan, dll)

**Warning**: Jangan coba-coba tax evasion, karena bisa kena denda besar atau bahkan pidana.

Mau lo kasih detail lebih spesifik untuk sektor lo?
```

**Metriche Attese**:
- Tone Jaksel: ✅
- Lingua: ID (adattato da IT)
- Model: gemma-9b-jaksel
- Tempo: 5-8s (domanda complessa)
- Accuratezza: ✅ (informazioni fiscali corrette)

---

### CATEGORIA 3: KBLI & BUSINESS SETUP

#### Q19 - Italiano, Media
**Domanda**: "Voglio aprire un'attività di consulenza digitale e marketing online. Quale codice KBLI devo usare?"

**Risposta Attesa (Tone Jaksel)**:
```
Oke, untuk konsultasi digital dan marketing online, lo perlu KBLI yang tepat.

**KBLI yang Cocok**:

1. **70209** - Konsultasi Manajemen Lainnya
   - Cocok untuk konsultasi digital strategy, digital transformation
   - Bisa include marketing consulting

2. **73100** - Aktivitas Periklanan
   - Kalau lo fokus ke advertising dan marketing services
   - Include digital marketing, social media marketing

3. **62090** - Aktivitas Teknologi Informasi dan Jasa Komputer Lainnya
   - Kalau lo juga kasih jasa IT consulting

**Rekomendasi**:
- Kalau lo fokus ke konsultasi: **70209**
- Kalau lo fokus ke marketing/ads: **73100**
- Kalau lo mix keduanya: bisa pakai **70209** sebagai primary, atau buat 2 KBLI

**Catatan Penting**:
- KBLI menentukan apakah lo perlu izin khusus atau tidak
- Beberapa KBLI punya batasan untuk PMA (negative investment list)
- Pastikan KBLI lo sesuai dengan kegiatan usaha yang lo lakukan

Mau lo kasih detail lebih spesifik untuk model bisnis lo?
```

**Metriche Attese**:
- Tone Jaksel: ✅
- Lingua: ID (adattato da IT)
- Model: gemma-9b-jaksel
- Tempo: 3-5s
- Accuratezza: ✅ (KBLI codes corretti)

---

### CATEGORIA 4: LEGAL & COMPLIANCE

#### Q28 - Italiano, Semplice
**Domanda**: "Quali sono i documenti necessari per aprire una PT PMA?"

**Risposta Attesa (Tone Jaksel)**:
```
Oke, untuk buka PT PMA, lo perlu dokumen-dokumen ini:

**Dokumen Wajib**:

1. **Dari Pemegang Saham**:
   - Paspor (yang masih berlaku)
   - Foto terbaru (4x6, background merah)
   - Surat keterangan kesehatan
   - Surat keterangan bebas narkoba
   - Bukti alamat (dari negara asal)
   - NPWP (kalau sudah punya)

2. **Dokumen Perusahaan**:
   - Akta pendirian (dibuat di notaris)
   - SK Menkumham (pengesahan dari Kementerian Hukum)
   - NIB (Nomor Induk Berusaha) - dari OSS
   - NPWP perusahaan
   - Izin usaha (sesuai KBLI)

3. **Dokumen Tambahan**:
   - Rencana investasi (minimal 10 miliar untuk PMA)
   - Struktur kepemilikan saham
   - Alamat kantor (bisa virtual office)

**Proses**:
- Waktu: sekitar 2-4 bulan
- Biaya: sekitar 15-30 juta (tergantung kompleksitas)

**Tips**:
- Pastikan semua dokumen sudah legalized/apostille
- Konsultasi dengan konsultan yang berpengalaman
- Jangan lupa daftar ke BKPM kalau investasi > 10 miliar

Ada yang mau lo tanya lebih detail?
```

**Metriche Attese**:
- Tone Jaksel: ✅
- Lingua: ID (adattato da IT)
- Model: gemma-9b-jaksel
- Tempo: 3-5s
- Completezza: ✅ (lista documenti completa)

---

### CATEGORIA 5: PROPERTY & REAL ESTATE

#### Q36 - Italiano, Semplice
**Domanda**: "Posso comprare una casa a Bali come straniero? Quali sono le opzioni?"

**Risposta Attesa (Tone Jaksel)**:
```
Oke, jadi untuk beli property di Bali sebagai WNA, lo punya beberapa opsi:

**Opsi yang Bisa**:

1. **Hak Guna Bangunan (HGB)** - 30 tahun, bisa diperpanjang
   - Lo bisa beli tanah dengan HGB
   - Bisa diperpanjang sampai 80 tahun total
   - Cocok untuk investasi jangka panjang

2. **Leasehold** - Sewa jangka panjang (biasanya 25-30 tahun)
   - Lo gak punya hak milik, tapi punya hak pakai
   - Lebih mudah prosesnya
   - Cocok kalau lo mau stay beberapa tahun

3. **PT PMA** - Beli lewat perusahaan
   - Lo bisa beli property atas nama PT PMA
   - Tapi ada batasan dan regulasi yang ketat
   - Perlu investasi minimal dan compliance

**Yang Gak Bisa**:
- ❌ Hak Milik (SHM) - Cuma untuk WNI
- ❌ Beli langsung atas nama pribadi WNA

**Rekomendasi**:
- Kalau lo mau invest jangka panjang: HGB
- Kalau lo mau stay beberapa tahun: Leasehold
- Kalau lo punya PT PMA: Bisa consider beli lewat PT

**Warning**:
- Hati-hati dengan developer yang janji-janji muluk
- Pastikan semua dokumen legal dan verified
- Konsultasi dengan notaris yang berpengalaman

Mau lo kasih detail lebih spesifik untuk kebutuhan lo?
```

**Metriche Attese**:
- Tone Jaksel: ✅
- Lingua: ID (adattato da IT)
- Model: gemma-9b-jaksel
- Tempo: 3-5s
- Accuratezza: ✅ (informazioni legali corrette)

---

## METRICHE GLOBALI ATTESE

### Success Rate
- **Target**: >95%
- **Accettabile**: >90%
- **Da Migliorare**: <90%

### Response Time
- **Target**: <5s per domanda semplice
- **Target**: <8s per domanda complessa
- **Accettabile**: <10s
- **Da Migliorare**: >10s

### Model Usage
- **Jaksel (Gemma 9B)**: Target >70%
- **Gemini Fallback**: Accettabile <30%
- **Error/Timeout**: Da evitare

### Tone Jaksel
- **Presenza**: Ogni risposta deve avere caratteristiche Jaksel
- **Adattamento Lingua**: Deve adattarsi alla lingua della domanda mantenendo il tone
- **Consistenza**: Tone deve essere consistente tra tutte le risposte

---

## COME INTERPRETARE I RISULTATI

### ✅ Successo
- Risposta ricevuta
- Tone Jaksel presente
- Lingua corrisponde
- Informazioni accurate
- Tempo < target

### ⚠️ Parziale
- Risposta ricevuta ma tone debole
- Informazioni corrette ma incomplete
- Tempo leggermente sopra target

### ❌ Fallimento
- Timeout o errore
- Tone Jaksel assente
- Informazioni inaccurate
- Lingua non corrisponde

---

## PROSSIMI STEP DOPO I TEST

1. **Analisi Pattern**: Identificare categorie/lingue con problemi
2. **Ottimizzazione**: Migliorare fallback, ridurre tempi
3. **Fine-tuning**: Aggiustare prompt Jaksel per categorie problematiche
4. **Monitoring**: Setup monitoring continuo per qualità risposte


















