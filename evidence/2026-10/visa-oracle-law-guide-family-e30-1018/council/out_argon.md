VERDICT: SHIP

### Findings

1. **`apps/backend-rag/backend/services/visa_engine/families/guide.py:75` — Medium (Null-safety & `DAY` option handling in `resolve`)**
   `if "stay_options" in visa:` checks key presence instead of `if visa.get("stay_options") is not None:`. In `family_e30.json` (`lines 46, 116, 125`), visas without discrete options include `"stay_options": null`. E30/E30E/E30F happen to be unreachable in the E30 decision tree, but any reachable visa following this schema convention with `"stay_options": null` will raise `TypeError: 'NoneType' object is not iterable` at `guide.py:80` instead of falling through to `stay_days`. Additionally, when `DAY`-unit `stay_options` are added (planned for C12/C22 per `research/visa/2026-10-17-visa-oracle-law-and-guide.md:67`), entering this branch asks `stay_months`, filters out `DAY` options (`guide.py:80`), and unconditionally returns `STAY_TOO_LONG`.

2. **`apps/backend-rag/backend/services/visa_engine/families/law/E30/ITAP.json:64-98` — Low (Mismatched source URLs in ITAP evidence)**
   `sources_reviewed` maps `"key": "itap-direct"` (`line 64`) to `.../perpanjangan-izin-tinggal-kunjungan-2` (Visit Stay Permit / ITK extension) and `"key": "itap-extension"` (`line 82`) to `.../perpanjangan-izin-tinggal-terbatas-2` (Limited Stay Permit / ITAS extension), contradicting `notes[1]` (`line 139`, *"Direct ITAP issuance, ITAP extension and ITAS-to-ITAP conversion are separate source contexts"*).

3. **`apps/backend-rag/backend/services/visa_engine/families/importer.py:92` & `333_visa_types_law_family_e30.sql:27,180,234` — Low (Unverified `permit_class` projected on `NOT_FOUND` cards)**
   For `E30`, `E30E`, and `E30F`, the source pages returned `"Data Belum Tersedia"` and `jenis_visa_verbatim` is `null` and listed in `to_verify`. Unlike `entry_type` (which stays `NULL` on those three rows), `importer.py:92` unconditionally copies `data["permit_class"]` (`'ITAS'`) into all five rows rather than leaving `permit_class` `NULL` when `card["status"] == "NOT_FOUND"`.

4. **`apps/backend-rag/backend/services/visa_engine/families/law/E30/E30A.json:65-69` & `E30B.json:64-68` — Low (Allowed activities duplicated into `prohibited_or_conditions_verbatim`)**
   The first element of `prohibited_or_conditions_verbatim` in both cards is a verbatim copy of `allowed_activities` because the parser matched the word `"ketentuan"` in `"sepanjang memenuhi ketentuan peraturan perundang·undangan"`.

### Design Dissent

- **Returning `STAY_TOO_LONG` above initial stay options when `extendable = true` (`guide.py:81-86`, `GUIDE.md:20`):** Because `total_max_verbatim` is `null` on the E30A/E30B source pages, the Guide treats the max initial stay option (24 months for E30A, 48 months for E30B) as a hard ceiling and returns `STAY_TOO_LONG` even though both cards explicitly state *"Izin Tinggal ini dapat diperpanjang"*. Returning a distinct status or caveat when ` months > max(stay_options)` and `extendable is True` with unknown `max_total_*` would avoid telling a 3-year high-school student (E30A) they are ineligible when extensions are explicitly permitted by law.
