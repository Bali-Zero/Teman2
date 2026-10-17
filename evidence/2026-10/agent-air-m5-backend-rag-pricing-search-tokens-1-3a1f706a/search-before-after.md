# PricingService.search_service: before / after (catalogue 2026, HEAD a08f78ca7f)

Source: scratch run of old code vs new code over 140 queries (search-after-v4.json, 2026-10-17 16:27 +08). Counts are rows returned. Every row lost by a query is listed by cause below; every gain is explained in section 3.

Totals: 35 queries differ, 28 lose rows (741 row-losses), 7 gain rows; 105 queries identical.

## 1. Table

| query                                                   | old hits | new hits | lost | gained |
| ------------------------------------------------------- | -------: | -------: | ---: | -----: |
| alcohol license                                         |        4 |        4 |    0 |      0 |
| izin minuman beralkohol                                 |        3 |        3 |    0 |      0 |
| harga izin minuman beralkohol                           |        3 |        3 |    0 |      0 |
| miras                                                   |        3 |        3 |    0 |      0 |
| minuman keras                                           |        3 |        3 |    0 |      0 |
| harga miras                                             |        3 |        3 |    0 |      0 |
| cost of alcohol licence golongan B                      |        3 |        3 |    0 |      0 |
| golongan A                                              |        3 |        3 |    0 |      0 |
| SLHS                                                    |        1 |        1 |    0 |      0 |
| SLHS as a restaurant                                    |       64 |        1 |   63 |      0 |
| laik higiene sanitasi                                   |        1 |        1 |    0 |      0 |
| halal certificate                                       |        4 |        4 |    0 |      0 |
| halal                                                   |        1 |        1 |    0 |      0 |
| quanto costa il certificato halal                       |        1 |        1 |    0 |      0 |
| PIRT                                                    |        1 |        1 |    0 |      0 |
| PIRT minuman                                            |        4 |        1 |    3 |      0 |
| kitas                                                   |       38 |       38 |    0 |      0 |
| how much is a working KITAS                             |       38 |       43 |    0 |      5 |
| quanto costa il KITAS lavoro                            |       38 |       38 |    0 |      0 |
| berapa harga KITAS investor                             |       41 |       41 |    0 |      0 |
| spouse kitas                                            |       38 |       38 |    0 |      0 |
| kitap                                                   |       13 |       13 |    0 |      0 |
| investor kitap                                          |       18 |       18 |    0 |      0 |
| e33                                                     |       10 |       10 |    0 |      0 |
| E33G                                                    |        3 |        3 |    0 |      0 |
| e33f                                                    |        4 |        4 |    0 |      0 |
| second home                                             |       10 |       10 |    0 |      0 |
| c1                                                      |        4 |        4 |    0 |      0 |
| B1 voa                                                  |        2 |        2 |    0 |      0 |
| visa on arrival extension                               |      116 |       41 |   75 |      0 |
| harga visa ke bali                                      |       50 |       32 |   18 |      0 |
| D2 business                                             |       12 |       12 |    0 |      0 |
| C22 internship                                          |        2 |        2 |    0 |      0 |
| PT PMA                                                  |       16 |        9 |    7 |      0 |
| ma quanto costa una PT PMA?                             |       42 |        9 |   33 |      0 |
| berapa biaya PT PMA di bali                             |       16 |        9 |    7 |      0 |
| berapa biaya NIB ke OSS                                 |       24 |        1 |   23 |      0 |
| virtual office                                          |        7 |        7 |    0 |      0 |
| biaya virtual office                                    |        7 |        7 |    0 |      0 |
| pensiun                                                 |        3 |        3 |    0 |      0 |
| pensiunan                                               |        3 |        3 |    0 |      0 |
| retirement                                              |        4 |        4 |    0 |      0 |
| driving license                                         |        4 |        4 |    0 |      0 |
| SIM                                                     |        1 |        1 |    0 |      0 |
| SKCK                                                    |        1 |        1 |    0 |      0 |
| SKTT                                                    |        1 |        1 |    0 |      0 |
| passport                                                |        5 |        5 |    0 |      0 |
| lapor lahir                                             |        3 |        3 |    0 |      0 |
| imta rptka                                              |        4 |        4 |    0 |      0 |
| ERP                                                     |        4 |        1 |    3 |      0 |
| EPO                                                     |       26 |        2 |   24 |      0 |
| urgent 1 hari                                           |        7 |        7 |    0 |      0 |
| efin                                                    |        1 |        1 |    0 |      0 |
| BPJS                                                    |        3 |        3 |    0 |      0 |
| npwp                                                    |        3 |        3 |    0 |      0 |
| akta perubahan                                          |        1 |        1 |    0 |      0 |
| close pma                                               |        9 |        9 |    0 |      0 |
| LKPM                                                    |        6 |        6 |    0 |      0 |
| pse registration                                        |       11 |       11 |    0 |      0 |
| vat assessment                                          |        5 |        3 |    2 |      0 |
| coretax                                                 |        3 |        3 |    0 |      0 |
| pajak tahunan pribadi                                   |        3 |        3 |    0 |      0 |
| compliance retainer                                     |        3 |        3 |    0 |      0 |
| freelance e23                                           |        2 |        2 |    0 |      0 |
| mutation address                                        |        6 |        6 |    0 |      0 |
| domicile letter                                         |        1 |        1 |    0 |      0 |
| bridging visa                                           |       32 |       32 |    0 |      0 |
| izin tinggal                                            |        1 |        1 |    0 |      0 |
| izin kerja                                              |        2 |        2 |    0 |      0 |
| izin usaha                                              |        0 |        0 |    0 |      0 |
| izin edar                                               |        0 |        0 |    0 |      0 |
| izin                                                    |        0 |        0 |    0 |      0 |
| berapa biaya izin usaha restoran?                       |        0 |        0 |    0 |      0 |
| izin usaha minuman ringan                               |        3 |        0 |    3 |      0 |
| mi serve un visto, quanto costa?                        |       53 |        0 |   53 |      0 |
| ke                                                      |       23 |        0 |   23 |      0 |
| mi                                                      |       53 |        0 |   53 |      0 |
| as                                                      |       64 |        6 |   58 |      0 |
| ber                                                     |       11 |        0 |   11 |      0 |
| man                                                     |       13 |        5 |    8 |      0 |
| tax report                                              |       26 |       26 |    0 |      0 |
| minuman ringan                                          |        3 |        0 |    3 |      0 |
| passport 10 years                                       |       12 |       11 |    1 |      0 |
| annual tax company                                      |       24 |       24 |    0 |      0 |
| hello                                                   |        0 |        0 |    0 |      0 |
| prezzo visto turistico                                  |        0 |        0 |    0 |      0 |
| berapa biaya izin alkohol                               |        3 |        3 |    0 |      0 |
| harga izin beralkohol                                   |        3 |        3 |    0 |      0 |
| alkohol                                                 |        3 |        3 |    0 |      0 |
| beralkohol                                              |        3 |        3 |    0 |      0 |
| minuman yang beralkohol                                 |        3 |        3 |    0 |      0 |
| izin minuman beralkoholnya berapa                       |        3 |        3 |    0 |      0 |
| polisi                                                  |        1 |        1 |    0 |      0 |
| catatan polisi                                          |        1 |        1 |    0 |      0 |
| sehat                                                   |        1 |        1 |    0 |      0 |
| certificato igiene                                      |        1 |        1 |    0 |      0 |
| voa ext                                                 |       15 |       15 |    0 |      0 |
| ext                                                     |       15 |       15 |    0 |      0 |
| kit                                                     |       40 |       40 |    0 |      0 |
| kitasnya                                                |        0 |       38 |    0 |     38 |
| berapa harga kitasnya?                                  |        0 |       38 |    0 |     38 |
| pensi                                                   |        4 |        4 |    0 |      0 |
| retir                                                   |        4 |        4 |    0 |      0 |
| visas                                                   |        0 |       32 |    0 |     32 |
| minuman                                                 |        3 |        0 |    3 |      0 |
| freelance                                               |        2 |        2 |    0 |      0 |
| internship                                              |        2 |        2 |    0 |      0 |
| pensionati                                              |        0 |        4 |    0 |      4 |
| ITAS                                                    |       39 |       38 |    1 |      0 |
| ITAP                                                    |       13 |       13 |    0 |      0 |
| TKA                                                     |        4 |        4 |    0 |      0 |
| pt-pma                                                  |        0 |        9 |    0 |      9 |
| non-alcoholic drinks                                    |        0 |        0 |    0 |      0 |
| minuman tanpa alkohol                                   |        3 |        0 |    3 |      0 |
| bevande senza alcol                                     |        0 |        0 |    0 |      0 |
| non alcoholic                                           |       14 |        0 |   14 |      0 |
| re-entry permit                                         |       20 |       20 |    0 |      0 |
| (empty string)                                          |      118 |        0 |  118 |      0 |
| (three spaces)                                          |      118 |        0 |  118 |      0 |
| how much is a work KITAS in Bali?                       |       45 |       45 |    0 |      0 |
| quanto costa il visto di 60 giorni?                     |        9 |        9 |    0 |      0 |
| berapa harga perpanjang VOA?                            |        1 |        1 |    0 |      0 |
| price for PT PMA setup                                  |       16 |        9 |    7 |      0 |
| quanto costa un permesso di soggiorno per pensionati?   |        0 |        4 |    0 |      4 |
| berapa biaya buat SKCK di Bali                          |        1 |        1 |    0 |      0 |
| I need a halal certificate for my restaurant, how much? |        7 |        7 |    0 |      0 |
| biaya sertifikat laik sehat restoran                    |        2 |        2 |    0 |      0 |
| harga virtual office di Canggu                          |        7 |        7 |    0 |      0 |
| can I get the price of a digital nomad visa E33G?       |       47 |       41 |    6 |      0 |
| quanto costa aprire una società a Bali?                 |        0 |        0 |    0 |      0 |
| berapa biaya kitas investor 2 tahun                     |       43 |       43 |    0 |      0 |
| extend my tourist visa C1 how much                      |       41 |       41 |    0 |      0 |
| harga izin usaha kafe dengan minuman keras              |        3 |        3 |    0 |      0 |
| costo licenza alcolici per bar                          |        0 |        0 |    0 |      0 |
| berapa biaya BPJS karyawan                              |        3 |        3 |    0 |      0 |
| annual tax report price                                 |       28 |       28 |    0 |      0 |
| biaya lapor SPT tahunan perusahaan                      |        5 |        5 |    0 |      0 |
| quanto costa il visto per mia moglie spouse?            |        6 |        6 |    0 |      0 |
| harga NPWP pribadi                                      |        4 |        4 |    0 |      0 |
| e-visa                                                  |        0 |        0 |    0 |      0 |

## 2. Rows lost, grouped by cause (spec rule 5: every loss is a substring-only match or an intended exclusion)

### A. Short token matched INSIDE an unrelated word (1-3 characters, now whole-word or prefix-with-3-chars only)

- visa on arrival extension: 75 lost ("on" in onshore / indonesian)
- SLHS as a restaurant: 63 lost ("as", "a" in many rows)
- as: 58 lost ("as")
- mi: 53 lost ("mi")
- mi serve un visto, quanto costa?: 53 lost ("mi", "un")
- ma quanto costa una PT PMA?: 33 lost ("ma", "una", "pt")
- ke: 23 lost ("ke" in worker / keras / kesehatan)
- berapa biaya NIB ke OSS: 23 lost ("ke")
- harga visa ke bali: 18 lost ("ke")
- ber: 11 lost ("ber" in members / number / beralkohol)
- man: 8 lost ("man" in permanent / dormant / minuman)
- can I get the price of a digital nomad visa E33G?: 6 lost ("of" in offshore (the E33G rows stay))

Why justified: Substring noise, the very bug class. Every lost row lacks the token as a word. The meaningful tokens of those sentences (visa, arrival, restaurant, SLHS, NIB, OSS, E33G) still find their own rows.

### B. Acronym or code that was only a fragment of another word

- PT PMA: 7 lost ("pt" in rptka / exemption / spt)
- berapa biaya PT PMA di bali: 7 lost (same)
- price for PT PMA setup: 7 lost (same)
- EPO: 24 lost ("epo" in deposit / report / reporting)
- ERP: 3 lost ("erp" in MERP (KITAP + MERP rows))
- vat assessment: 2 lost ("vat" in activation (Coretax Activation rows))
- passport 10 years: 1 lost ("10" in C10 (Speaker Visa))
- ITAS: 1 lost ("itas" in sanitasi (SLHS row); the 38 KITAS rows stay via the alias)

Why justified: None of these rows is about the acronym. ERP and EPO keep their own rows; PT PMA keeps New Company (PT PMA) and the PMA rows.

### C. Generic word shared with a curated MULTI-word alcohol keyword (cure of #8632 / #8633)

- minuman: 3 lost (alcohol rows)
- minuman ringan: 3 lost (alcohol rows)
- izin usaha minuman ringan: 3 lost (alcohol rows)
- PIRT minuman: 3 lost (alcohol rows; PIRT row stays)

Why justified: Zero 2026-10-17 alcohol ruling: a soft-drink or PIRT question must not price an alcohol licence. alkohol, beralkohol, miras, minuman keras, alcohol and minuman beralkohol still return the three Alcohol License rows (corpus).

### D. Negation (non / tanpa / senza / without drop the next word)

- non alcoholic: 14 lost (3 alcohol rows plus "non" substring rows)
- minuman tanpa alkohol: 3 lost (alcohol rows)

Why justified: Intended: a client asking for non-alcoholic drinks gets no alcohol licence.

### E. Empty query

- (empty string): 118 lost (all rows)
- (three spaces): 118 lost (all rows)

Why justified: Pinned by the spec: no words, no rows. All nine in-repo callers checked; /api/pricing/search has min_length=1.

## 3. Rows gained (7 queries, all recall gains from the light-suffix, alias and hyphen-phrase rules)

- how much is a working KITAS: +5 (old 38, new 43)
- kitasnya: +38 (old 0, new 38)
- berapa harga kitasnya?: +38 (old 0, new 38)
- visas: +32 (old 0, new 32)
- pensionati: +4 (old 0, new 4)
- pt-pma: +9 (old 0, new 9)
- quanto costa un permesso di soggiorno per pensionati?: +4 (old 0, new 4)

- kitasnya, berapa harga kitasnya?, visas: old code returned 0 rows for the inflected form; the stem is now found (light suffix nya / s).
- pensionati, quanto costa un permesso di soggiorno per pensionati?: reach the senior E33F rows through the curated keyword pension plus the light suffix, and BPJS Ketenagakerjaan, whose description mentions pension.
- pt-pma: hyphen compound matched as the phrase "pt pma" (0 rows before).
- how much is a working KITAS: +5 rows because "working" now matches the row word "work" with a light suffix; A1 Visa-Free, B1 VOA and C18 Work Trial carry "work" only in negative or secondary text ("no work, business, study"). Accepted as lexical recall noise, not a precision claim.

Known out-of-scope leftovers: Driving License still matches "license" queries (license family, spec); "toko minuman" no longer finds alcohol rows (kimi dissent, accepted).
