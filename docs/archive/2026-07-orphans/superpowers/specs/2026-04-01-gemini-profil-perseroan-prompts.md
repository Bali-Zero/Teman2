# 8 Prompt Gemini 3 Flash — Estrazione Profil Perseroan

Per ogni batch: apri ogni PDF, estrai i dati, e inseriscili nel DB della company indicata.

**Endpoint per inserire i dati:**

```
POST https://nuzantara-rag.fly.dev/api/crm/companies/{company_id}
Header: X-API-Key: zantara-secret-2024
Body: { "custom_fields": { ... } }
```

**Oppure direttamente in DB:**

```sql
UPDATE companies SET
  custom_fields = jsonb_set(COALESCE(custom_fields::jsonb,'{}'), '{key}', '"value"'),
  registered_address = '...',
  akta_pendirian_no = '...',
  sk_menhumkam_no = '...',
  updated_at = NOW()
WHERE id = {company_id};
```

**Campi da estrarre da ogni Profil Perseroan:**

- `company_name` — nome PT
- `authorized_capital` — Modal Dasar (numero in Rp)
- `paid_up_capital` — Modal Ditempatkan/Disetor (numero in Rp)
- `share_price` — Harga Per Lembar Saham
- `total_shares` — Jumlah Lembar Saham totali
- `shareholders` — array [{name, passport, nationality, role, shares, value, address}]
- `akta_no` — Nomor Akta
- `akta_date` — Tanggal Akta (YYYY-MM-DD)
- `sk_no` — Nomor SK (AHU-...)
- `sk_date` — Tanggal SK (YYYY-MM-DD)
- `notaris` — Nome completo notaio con titolo
- `notaris_kedudukan` — Citta notaio
- `registered_address` — Alamat completo
- `company_status` — TERTUTUP / TERBUKA
- `jangka_waktu` — TIDAK TERBATAS / data specifica
- `kbli_codes` — array codici KBLI se presenti
- `risk_status` — status risiko usaha se presente

---

## BATCH 1 (docs 1-11)

| #   | Doc ID | Client            | Company (ID)                        | PDF Link                                                               |
| --- | ------ | ----------------- | ----------------------------------- | ---------------------------------------------------------------------- |
| 1   | 350    | Dylon Dimech      | PT Indo Investments Bali (1904)     | https://drive.google.com/file/d/16aWU3Nv27qdm8vBJZR4JobhR85bk-15X/view |
| 2   | 371    | Laurane Binard    | PT Flavor Emotion Experience (1749) | https://drive.google.com/file/d/1XDAVb0Nms2G8ofS8TG_l-iiMps-WTvH1/view |
| 3   | 383    | Armando Puddu     | PT Shardana West Sumbawa (996)      | https://drive.google.com/file/d/1peojMpSqIBbHGi7XuhDX_396NAPpNo56/view |
| 4   | 439    | Andrea Francolini | PT The Italian Guy (2628)           | https://drive.google.com/file/d/1ZzJChYWMV_CDefGIPo2hstUOG2qORB6Z/view |
| 5   | 453    | Federico Barnabe  | NO COMPANY                          | https://drive.google.com/file/d/1qpGRDHwOjvQZv7m3FtGJdB6P__nktvJI/view |
| 6   | 462    | Sara Garzillo     | PT Creativity Art Love (1591)       | https://drive.google.com/file/d/16yBR16uhwmw69xxSwOExW8G-vUpWbZUP/view |
| 7   | 522    | Jacques Teisseire | PT The Bara Jade (2638)             | https://drive.google.com/file/d/1PoN4RiQFhx4fsHwelBjgAW7jiQRXVFJZ/view |
| 8   | 558    | Anna Garratini    | NO COMPANY                          | https://drive.google.com/file/d/1ksnoxYXrLOrtoCnxue76GCNOcoXASqZx/view |
| 9   | 598    | Cesare Negro      | PT DGJ Bali Hospitality (1599)      | https://drive.google.com/file/d/1Pbr33_cH-BPy84DDWF4ziNxtUWHpgmyQ/view |
| 10  | 611    | Rosy Marchese     | NO COMPANY                          | https://drive.google.com/file/d/1MMdjv5f9Ur90YINQTfdHGFM8RGRW8hYx/view |
| 11  | 622    | Pablo Dutto       | PT The Melting Pot (2623)           | https://drive.google.com/file/d/1hreVD2c3QP1sMcTLMxPFamZDGBFbh_oi/view |

**Prompt:** Apri ognuno di questi 11 PDF di Profil Perseroan. Per ciascuno estrai TUTTI i campi elencati sopra. Per le company con ID, aggiorna il DB. Per quelle senza company (NO COMPANY), crea la company dal nome estratto dal PDF e linka al client. Output JSON per ogni documento.

---

## BATCH 2 (docs 12-22)

| #   | Doc ID | Client           | Company (ID)                     | PDF Link                                                               |
| --- | ------ | ---------------- | -------------------------------- | ---------------------------------------------------------------------- |
| 12  | 628    | Byron Bourne     | NO COMPANY                       | https://drive.google.com/file/d/1uOYV8XnqqjYOI85LA5P2-5oSBnBmZjjc/view |
| 13  | 665    | Patrizia Albano  | NO COMPANY                       | https://drive.google.com/file/d/1loEvXh1eKux4dDKmp6Lm0OLB6A8wQ3ip/view |
| 14  | 671    | Tobias Rein      | NO COMPANY                       | https://drive.google.com/file/d/1USDFZV4k-VgKphLKTfgrnyEofabCb3_M/view |
| 15  | 692    | Greta Gheser     | PT TLG Future Group (2586)       | https://drive.google.com/file/d/1OOhhD3GCjmLH1mWuLQLN2-yCH6D3riBQ/view |
| 16  | 713    | Brandi Burdine   | PT Burdine Wellness Bali (3233)  | https://drive.google.com/file/d/1D_Q4LvGk-_k2--67n1KZXgC84ruE3TdY/view |
| 17  | 729    | Clint Dorman     | PT Ophidian Lounge Canggu (2991) | https://drive.google.com/file/d/1hY8ZPQ3X9q4i9fzHh9Ap1Oorx7TiARGn/view |
| 18  | 750    | Ayoub Bouhamidi  | NO COMPANY                       | https://drive.google.com/file/d/1xK9f_aBEGZna4P-cpy2xyNIAcy4eqJq0/view |
| 19  | 758    | Andrea Lo Coco   | PT Bale Glory Home (15)          | https://drive.google.com/file/d/1ElBIS5GP0CDg9USCnj-iV1_d9RpNlk2h/view |
| 20  | 768    | Alessandro Bocci | PT Makan Tiga Sembilan (2139)    | https://drive.google.com/file/d/1NrPypRGtD55ontrNHbVM8xiPINvQabxR/view |
| 21  | 780    | Marco Stefanoni  | NO COMPANY                       | https://drive.google.com/file/d/1laH2mME7Tn7F5HB71L_IdkadH7EeaEHp/view |
| 22  | 788    | Roberto Vacca    | NO COMPANY                       | https://drive.google.com/file/d/1q9Aw5ddoGptpIBeZe-yytSyMN5E3CJFJ/view |

---

## BATCH 3 (docs 23-33)

| #   | Doc ID | Client                 | Company (ID)                     | PDF Link                                                               |
| --- | ------ | ---------------------- | -------------------------------- | ---------------------------------------------------------------------- |
| 23  | 793    | Cristina Vertemati     | NO COMPANY                       | https://drive.google.com/file/d/1V5No6zT3BUaPJhSDGNq1y3IwsJH3L8n3/view |
| 24  | 805    | Tonino Montesanti      | PT Padel Tennis Indonesia (2978) | https://drive.google.com/file/d/1Nm2l57GSLxm01kRvQAWfNTLEg_yymJhZ/view |
| 25  | 806    | Tonino Montesanti      | PT Padel Tennis Indonesia (2978) | https://drive.google.com/file/d/1Vnx3xzqayRD4R_8kLGWTuV8xPH9JW6Ne/view |
| 26  | 807    | Tonino Montesanti      | PT Padel Tennis Indonesia (2978) | https://drive.google.com/file/d/17vxexXHV6pWv-CqebKxo6J_pbPOPjcqw/view |
| 27  | 817    | Anne Kristin Eilertsen | NO COMPANY                       | https://drive.google.com/file/d/1xXOpaVZ1Mghkw34i2XDXrD81mq9AZ-PY/view |
| 28  | 831    | Pasquale Piccolo       | PT Boost Energy Ventures (3243)  | https://drive.google.com/file/d/1YYJbG4i3eL-ADNkd7ZY9p2bAx19QEdYf/view |
| 29  | 886    | Andreas Sandstroem     | NO COMPANY                       | https://drive.google.com/file/d/1SpHQDCOhSfMR58OAZNW-aFSkjPJ8QIYP/view |
| 30  | 890    | Angela Xuan Wilson     | NO COMPANY                       | https://drive.google.com/file/d/1zXwAj9DURj528pQsGr5Y1gHhb6xQS50r/view |
| 31  | 914    | Faris El Hafid         | PT BOO International Hotel (9)   | https://drive.google.com/file/d/10HVHUZm1q2cAtyF2qZ5KjG1qrn54wZDL/view |
| 32  | 915    | Faris El Hafid         | PT BOO International Hotel (9)   | https://drive.google.com/file/d/1gQPPIr-EmbUvuYmIyI2HcFqj6ysv5uRj/view |
| 33  | 921    | Francisco Javier       | NO COMPANY                       | https://drive.google.com/file/d/13kyHSio807x7JGS2xo6i_GTv87jFJbqW/view |

---

## BATCH 4 (docs 34-44)

| #   | Doc ID | Client            | Company (ID)                    | PDF Link                                                               |
| --- | ------ | ----------------- | ------------------------------- | ---------------------------------------------------------------------- |
| 34  | 922    | Francisco Javier  | NO COMPANY                      | https://drive.google.com/file/d/1biCklqozpTwt00k_Qjjo-Hq4P-z6hHjJ/view |
| 35  | 923    | Francisco Javier  | NO COMPANY                      | https://drive.google.com/file/d/1UcHxjSOLWzqGr3yJc3i7PaYjg7RjibAs/view |
| 36  | 930    | Giancarlo Mozzini | NO COMPANY                      | https://drive.google.com/file/d/1IZqJlGrMHya4uKjGnZFvzi1cOpaPD4Tj/view |
| 37  | 944    | Giuseppe Alcini   | NO COMPANY                      | https://drive.google.com/file/d/1wKgbRoZL5c0BYSp6cGwpIr4WlxGDmreq/view |
| 38  | 965    | Iuliia Ukho       | NO COMPANY                      | https://drive.google.com/file/d/1UNbgm9mvFR07sZFMeTniF8IQUAsFpqK6/view |
| 39  | 981    | Ksenia Filatova   | PT Novi Media Consulting (3016) | https://drive.google.com/file/d/1fIOhezDuTX5pprgrMqEu2uu5x4W_D-aJ/view |
| 40  | 988    | Manuela Benvegnu  | NO COMPANY                      | https://drive.google.com/file/d/1ttkWbpdIp0QFXiPoxpfTVxcYA2F2EFnf/view |
| 41  | 991    | Marine Hebert     | PT Maison Properties (2135)     | https://drive.google.com/file/d/1UXGA5dfbMuRs8G_McYCKoAOsPC-zbAt2/view |
| 42  | 1006   | Mauro Spataro     | NO COMPANY                      | https://drive.google.com/file/d/1Nd54_aDlCdmn5Mu0IG4oJIor5o7rNG56/view |
| 43  | 1028   | Nikita Iakushin   | NO COMPANY                      | https://drive.google.com/file/d/1Nd8aPL5dGq3Y6oosMS0hhvgfq45hQ200/view |
| 44  | 1043   | Rafael Villalon   | PT Valencia Bali Kuliner (2513) | https://drive.google.com/file/d/1gGnGNvP7GV0ETtD3QfeConYSFSNOfyvr/view |

---

## BATCH 5 (docs 45-55)

| #   | Doc ID | Client               | Company (ID)                        | PDF Link                                                               |
| --- | ------ | -------------------- | ----------------------------------- | ---------------------------------------------------------------------- |
| 45  | 1062   | Reka Szendi          | PT Kelapa Digital Consulting (2012) | https://drive.google.com/file/d/14wGFFoeClQ0hJKZ8LwuTBxOzxksPqw29/view |
| 46  | 1073   | Roosje Ewals         | NO COMPANY                          | https://drive.google.com/file/d/1f2v-N2JiBoPjuomUMbuk4x9jW5OxVey8/view |
| 47  | 1089   | Trent Di Pietro      | PT Bali Akusara Jaya (18)           | https://drive.google.com/file/d/1z2fE6TXT53tpHWjvEz1fb72xsUgo48YM/view |
| 48  | 1101   | Vlad Rojisteanu      | PT Nebulo Eko Disinfeksi (3035)     | https://drive.google.com/file/d/1A9G319KBZ0beAgZEKnSoOYr9ktZqCa0c/view |
| 49  | 1111   | Zulmira Murtazina    | PT Orange Rock Investment (2987)    | https://drive.google.com/file/d/1EssV7BbW2K0-ZdQE6oa4mHS8o0Nhfx_I/view |
| 50  | 1116   | Christian Fjellstrom | NO COMPANY                          | https://drive.google.com/file/d/1cIRYWXZjmZ3xrMGtWuHeumS6sHeFolNK/view |
| 51  | 1125   | Larissa Galvanone    | PT Health And Leisure Agency (3117) | https://drive.google.com/file/d/1BrLE-pG-LEoX87F0PRhGie3DbWA8ATgZ/view |
| 52  | 1143   | Samuel Mcloughlin    | PT Ciao Bali Pizza (3209)           | https://drive.google.com/file/d/1P62Rl315QoioVrCgLMP1XdsxKqUTQyju/view |
| 53  | 1152   | Balthasar Biedermann | PT Melba Partners Bali (2172)       | https://drive.google.com/file/d/16WjISAmMbgAMI2IreZFIkTLSUjnkDHcM/view |
| 54  | 1168   | Daisy Roehrig        | PT Joyful Principles Bali (1975)    | https://drive.google.com/file/d/1k-2_p2Jl79iAZ1v6Tz7hVxlyMq1ssgYO/view |
| 55  | 1192   | Erin Hayes           | PT Erin Hayes Investment (1705)     | https://drive.google.com/file/d/1ygbMVblMWgjasxnEA_o6kVlF3S8jpOgw/view |

---

## BATCH 6 (docs 56-66)

| #   | Doc ID | Client            | Company (ID)                      | PDF Link                                                               |
| --- | ------ | ----------------- | --------------------------------- | ---------------------------------------------------------------------- |
| 56  | 1222   | Christian Audino  | PT Paradise Beach Brothers (2962) | https://drive.google.com/file/d/1wrB26FkfZHkFs90mgBpY3-6evdFku4tH/view |
| 57  | 1226   | Simone Gentile    | NO COMPANY                        | https://drive.google.com/file/d/17jklWzFKhYsyep51odXkx00OZ1tcTAs7/view |
| 58  | 1251   | Marco Mino        | PT Minori Alam Bali (3083)        | https://drive.google.com/file/d/1l1rO519Z7Gn-ihiI979ZJC2IzeiVfEHE/view |
| 59  | 1272   | Andrey Yusupov    | NO COMPANY                        | https://drive.google.com/file/d/1RY2dQAurh9nKukok5AZuGp3-UXxlnmsX/view |
| 60  | 1285   | Giulio Prudente   | NO COMPANY                        | https://drive.google.com/file/d/1kzEJM6spKdoLrWufTOUQrdJEb90NZEV9/view |
| 61  | 1315   | Massimo Benedetti | NO COMPANY                        | https://drive.google.com/file/d/1Gk3AfHBkMwVpGv5eHUFmHOaLSrOTimwj/view |
| 62  | 1336   | Paolo Gigli       | NO COMPANY                        | https://drive.google.com/file/d/1p69GVd-UK9ESHCW7ID0bs13O7y4lqbsy/view |
| 63  | 1357   | Ivan Simonov      | PT Bright Horizon Ventures (3239) | https://drive.google.com/file/d/1FYNLZDG4G9dMlPHYSa_tppOg_V7PmHZP/view |
| 64  | 1361   | Erika Bernini     | NO COMPANY                        | https://drive.google.com/file/d/1vMsN2uP_uUem1kXmAts6AJY9PoJcu2kn/view |
| 65  | 1374   | Daniele Campus    | NO COMPANY                        | https://drive.google.com/file/d/1wi-o1XZTGT-r-J30Pw_5lZE5Xa4XysCT/view |
| 66  | 1385   | Edoardo Domolo    | NO COMPANY                        | https://drive.google.com/file/d/186m1h0ET_mL0R_RXFDo7Cw_zA9zbpBUm/view |

---

## BATCH 7 (docs 67-76)

| #   | Doc ID | Client               | Company (ID)                 | PDF Link                                                               |
| --- | ------ | -------------------- | ---------------------------- | ---------------------------------------------------------------------- |
| 67  | 1394   | Viktoriia Korpan     | PT Craft Home Estate (1584)  | https://drive.google.com/file/d/1lIH8qRPwbl2oFNOpTcdyeiwe6aG_YEwn/view |
| 68  | 1409   | Benjamin Woolliss    | NO COMPANY                   | https://drive.google.com/file/d/1Arm2z0LAaq8GVfQrr5KBMHf_96OopElk/view |
| 69  | 1419   | Giovanni Solinas     | NO COMPANY                   | https://drive.google.com/file/d/1Lehixg-63qxGpVw2sFOTWF-1cHsE8i2D/view |
| 70  | 1424   | Jade India Morrison  | PT Ohana Project Bali (3007) | https://drive.google.com/file/d/1o6ZCIRPy2jJkeLeQYcS0vQ4ifb4zSR7U/view |
| 71  | 1431   | Andrea Maria Mirable | PT Khali Bali Ubud (2020)    | https://drive.google.com/file/d/1prR--YBPt5SBaMzyFPnALThwgKZzUfkp/view |
| 72  | 1475   | Jose Luis Contreras  | PT Bali Nean Dolo (1383)     | https://drive.google.com/file/d/1GYIiKbcJb2Q_eCXGL7B3ZEqs-f7Dlpdb/view |
| 73  | 1488   | Juliana Meneguetti   | NO COMPANY                   | https://drive.google.com/file/d/1nZ9xXEu2Aut_quadRBqcYvCWRhRGb4ns/view |
| 74  | 1500   | ULAN NAZARALIEV      | PT The Nazar Ali (2620)      | https://drive.google.com/file/d/1SgtuW6rC5RcVZ2O5RfTbdTu1TeOMmtQw/view |
| 75  | 1514   | Karima Talhi         | NO COMPANY                   | https://drive.google.com/file/d/1V9SEgnTtluPK6DAHq25u1q98SUMuHHv-/view |
| 76  | 1522   | Roman Nurutdinov     | PT Mus Mus Indonesia (3058)  | https://drive.google.com/file/d/1Yrhxl2F3RksN6IJwT61nv0Z4Q-eg26t-/view |

---

## BATCH 8 (docs 77-83)

| #   | Doc ID | Client             | Company (ID)                         | PDF Link                                                                            |
| --- | ------ | ------------------ | ------------------------------------ | ----------------------------------------------------------------------------------- |
| 77  | 1523   | Roman Nurutdinov   | PT Mus Mus Indonesia (3058)          | https://drive.google.com/file/d/19m2YUGgdjH69SPbfAGCigP3w6jAI6TEw/view              |
| 78  | 1566   | Francesca Samarani | NO COMPANY                           | https://drive.google.com/file/d/175lgPNMinRViCU56KxmIkynlur9NRb68/view              |
| 79  | 1567   | Carlo Percuoco     | PT Seminyak Hospitality Group (2784) | https://drive.google.com/file/d/1uBvOzwLf5xXZ5xYbg_II0AghcDQxkg4l/view              |
| 80  | 1568   | Carlo Percuoco     | PT Seminyak Hospitality Group (2784) | https://drive.google.com/file/d/1LM0b7qr3v1U5SNjbZvsx5x0ZjnviuWvu/view              |
| 81  | 1647   | Michele Porinelli  | PT FRA Real Estate Consulting (1762) | https://drive.google.com/file/d/1ZSNYrnnPu48PeRRyxub2ajXO5pFKTQGU/view?usp=drivesdk |
| 82  | 3091   | Eaton De Ridder    | PT Deridder Investments Bali (1624)  | https://drive.google.com/file/d/16_7pJxw1p11jr8HlzbvbGKiu7K2blGfa/view?usp=drivesdk |
| 83  | 5024   | Mars Marquez       | PT Enkay Dream Investments (1701)    | https://drive.google.com/file/d/1aGh_NJV_9citOhf1A8ez9cdOOStHXcN_/view?usp=drivesdk |

---

## Note per Gemini

1. **Per "NO COMPANY"**: estrai il nome company dal PDF, poi `INSERT INTO companies` e crea il link `INSERT INTO client_company_links`
2. **Per company duplicati (stesso client, multipli docs)**: usa il PDF piu recente, ignora i vecchi
3. **Shareholders**: estrai TUTTI — nome completo, passaporto, nazionalita, ruolo (DIREKTUR/KOMISARIS/PEMEGANG SAHAM), numero shares, valore shares, indirizzo
4. **Date**: formato YYYY-MM-DD
5. **Capital**: solo numero in Rp (es. 41385000000, non "Rp 41.385.000.000")
6. **Se il PDF non e leggibile**: scrivi "UNREADABLE" e passa al prossimo
7. **Output**: JSON per ogni documento, pronto per INSERT nel DB
