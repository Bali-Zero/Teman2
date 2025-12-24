# ANALISI KBLI: Nostro JSON vs Numero Ufficiale

## RIEPILOGO

| Metrica | Valore |
|---------|--------|
| **Totale 5-digit nel JSON** | 1,948 |
| **Numero ufficiale (da verificare)** | ~1,430 |
| **Differenza** | ~518 |

## RISULTATI VERIFICA

| Check | Risultato |
|-------|-----------|
| Duplicati | ✅ Nessuno |
| Sotto-KBLI (suffissi a/b/c) | ✅ Nessuno |
| Codici >5 cifre | ✅ Nessuno |
| KBLI con dati parziali | ⚠️ 65 |

## BREAKDOWN DATI

```
┌─────────────────────────────────────────────────────────┐
│  KBLI con dati COMPLETI:           1,883               │
│  KBLI con dati PARZIALI:              65               │
│  ───────────────────────────────────────────────────── │
│  TOTALE:                           1,948               │
└─────────────────────────────────────────────────────────┘
```

## 65 KBLI CON DATI INCOMPLETI

Questi KBLI potrebbero non essere nel conteggio ufficiale PP 28/2025:

| Kode | Judul | Sektor | Manca |
|------|-------|--------|-------|
| 03151 | Penangkapan/Pengambilan Ikan Bersir | Perikanan | SCALES |
| 03153 | Penangkapan/Pengambilan Mollusca ya | Perikanan | SCALES |
| 03154 | Penangkapan/Pengambilan Coelenterat | Perikanan | SCALES |
| 03155 | Penangkapan/Pengambilan Echinoderma | Perikanan | SCALES |
| 03156 | Penangkapan/Pengambilan Amphibia ya | Perikanan | SCALES |
| 03157 | Penangkapan/Pengambilan Reptilia ya | Perikanan | SCALES |
| 03159 | Penangkapan/Pengambilan Algae dan B | Perikanan | SCALES |
| 03272 | Pengembangbiakan Crustacea yang Dil | Perikanan | SCALES |
| 03273 | Pengembangbiakan Mollusca yang Dili | Perikanan | RISK, SCALES |
| 03274 | Pengembangbiakan Coelenterata yang  | Perikanan | SCALES |
| 03275 | Pengembangbiakan Echinodermata yang | Perikanan | RISK, SCALES |
| 03276 | Pengembangbiakan Amphibia yang Dili | Perikanan | RISK, SCALES |
| 03277 | Pengembangbiakan Reptilia yang Dili | Perikanan | SCALES |
| 03278 | Pengembangbiakan Mamalia yang Dilin | Perikanan | SCALES |
| 03279 | Pengembangbiakan Algae dan Biota Pe | Perikanan | SCALES |
| 07295 | Pertambangan Bijih Nikel | ESDM | RISK |
| 08106 | Penggalian Gips | ESDM | RISK |
| 08911 | Pertambangan Belerang | ESDM | RISK, SCALES |
| 08995 | Penggalian Kuarsa/Pasir Kuarsa | ESDM | RISK |
| 10791 | Industri Makanan Bayi | Industri | RISK |
| 11010 | Industri Minuman Beralkohol Hasil D | Industri | RISK, SCALES |
| 11244 | - | Industri | RISK, SCALES |
| 12253 | - | Industri | RISK, SCALES |
| 12965 | - | Industri | SCALES |
| 13724 | - | Industri | RISK, SCALES |
| 13734 | - | Industri | RISK, SCALES |
| 13743 | - | Industri | RISK, SCALES |
| 14701 | - | Industri | RISK, SCALES |
| 14834 | - | Industri | RISK, SCALES |
| 19709 | - | ESDM | SCALES |
| 19710 | - | ESDM | RISK, SCALES |
| 19849 | - | ESDM | RISK |
| 19850 | - | ESDM | RISK |
| 19873 | - | ESDM | RISK, SCALES |
| 19890 | - | ESDM | RISK, SCALES |
| 19903 | - | ESDM | RISK, SCALES |
| 19904 | - | ESDM | RISK, SCALES |
| 19916 | - | ESDM | RISK, SCALES |
| 19917 | - | ESDM | RISK |
| 19919 | - | ESDM | RISK |
| 19950 | - | ESDM | RISK |
| 19956 | - | ESDM | RISK |
| 19959 | - | ESDM | RISK |
| 19961 | - | ESDM | RISK |
| 19962 | - | ESDM | RISK |
| 19963 | - | ESDM | RISK |
| 19970 | - | ESDM | RISK |
| 20000 | - | Industri | RISK, SCALES |
| 20292 | Industri Bahan Peledak | Industri | RISK |
| 22230 | Industri Pipa Plastik Dan Perlengka | Industri | RISK |
| 24202 | Industri Pembuatan Logam Dasar Buka | Industri | RISK |
| 24203 | Industri Penggilingan Logam Bukan B | Industri | RISK |
| 25120 | Industri Tangki, Tandon Air Dan Wad | Industri | RISK |
| 28151 | Industri Oven, Perapian dan Tungku  | Industri | SCALES |
| 30112 | Industri Bangunan Lepas Pantai Dan  | Industri | RISK |
| 30300 | Industri Pesawat Terbang Dan Perlen | Industri | RISK |
| 30990 | Industri Alat Angkutan Lainnya YTDL | Industri | RISK |
| 32502 | Industri Peralatan Kedokteran Dan K | Industri | RISK |
| 33159 | Reparasi Alat Angkutan Lainnya, Buk | Industri | RISK |
| 35201 | Pengadaan Gas Alam Dan Buatan | ESDM | RISK |
| 46610 | Perdagangan Besar Bahan Bakar Padat | Perdagangan | RISK, SCALES |
| 64300 | Trust, Pendanaan dan Entitas Keuang | Keuangan | RISK, PMA, SCALES |
| 71206 | Jasa Commissioning Proses Industria | Jasa Profesional | RISK |
| 74100 | AKTIVITAS PERANCANGAN KHUSUS | Jasa Profesional | RISK, PMA, SCALES |
| 77301 | AKTIVITAS PENYEWAAN DAN SEWA GUNA U | Jasa Persewaan | RISK, PMA, SCALES |

## IPOTESI SULLA DIFFERENZA (518 KBLI)

Se il numero ufficiale è 1,430, le possibili spiegazioni sono:

1. **65 con dati parziali** - Confermati sopra
2. **~453 restanti** potrebbero essere:
   - KBLI esistenti in OSS ma non regolati da PP 28/2025
   - KBLI di settori esclusi (es. ESDM gestiti separatamente)
   - KBLI legacy mantenuti per compatibilità
   - Errore nel conteggio della fonte '1,430'

## RACCOMANDAZIONE

Verificare la fonte del numero 1,430:
- PDF originale PP 28/2025?
- Sito OSS?
- Altra fonte?

---
*Generato: 2025-12-23*