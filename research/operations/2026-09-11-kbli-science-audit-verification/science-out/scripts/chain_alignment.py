#!/usr/bin/env python3
"""Join Lane A/B/C outputs to answer: of 1559 OSS codes, how many have corpus, website and app
all aligned word-for-word with OSS judul_id / uraian_id?

Usage: python3 chain_alignment.py <snapshot_root>
Inputs : science-out/data/lane_a_per_code.json, lane_b_render_map.json, lane_c_render_map.json
Output : science-out/data/chain_alignment.json

Definitions
  corpus_aligned(code)  : Lane A judul_id EXACT and uraian_id EXACT and ruang_lingkup EXACT/BOTH_EMPTY
  STRICT surface align  : every rendered title/description text on the code page equals the corpus field
                          byte-for-byte: website = hero.h1_title, hero.subtitle_judul, lead.uraian;
                          app = titleEn (h1), titleId (subtitle), description (lead).
                          Metadata/JSON-LD truncations are excluded (not page body) and reported separately.
  ID-TEXT surface align : only the Indonesian text surfaces (subtitle judul + lead uraian) must be verbatim;
                          the English h1 is treated as ENRICHMENT with no OSS counterpart (OSS has no
                          translated judul: judul_en == judul_id for all 1559).
  Full chain            : corpus_aligned AND website aligned AND app aligned, under each definition.
"""
import json, sys
ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
D = f"{ROOT}/science-out/data"
A = json.load(open(f"{D}/lane_a_per_code.json"))
B = json.load(open(f"{D}/lane_b_render_map.json"))
C = json.load(open(f"{D}/lane_c_render_map.json"))
codes = sorted(A)
assert len(codes) == 1559

corpus_ok = {k for k in codes if A[k]["in_corpus"] and A[k]["judul_id"]["class"] == "EXACT"
             and A[k]["uraian_id"]["class"] == "EXACT" and A[k]["ruang_lingkup"]["class"] in ("EXACT", "BOTH_EMPTY")}

def aff(m, key):
    v = m[key]["affected_codes"]
    assert v is not None, key
    return set(v)

site_h1, site_sub, site_lead = aff(B, "hero.h1_title"), aff(B, "hero.subtitle_judul"), aff(B, "lead.uraian")
app_h1 = aff(C, "titleEn (h1, card h3, metadata title, JSON-LD name, chat title)")
app_sub = aff(C, "titleId (subtitle, card p)")
app_lead = aff(C, "description (detail page lead)")

site_strict = set(codes) - site_h1 - site_sub - site_lead
site_idtext = set(codes) - site_sub - site_lead
app_strict = set(codes) - app_h1 - app_sub - app_lead
app_idtext = set(codes) - app_sub - app_lead

out = {
    "definitions": __doc__,
    "corpus_aligned": len(corpus_ok),
    "website": {"h1_not_verbatim": len(site_h1), "subtitle_not_verbatim": len(site_sub), "lead_not_verbatim": len(site_lead),
                "strict_aligned": len(site_strict), "idtext_aligned": len(site_idtext),
                "jsonld_description_truncated": len(aff(B, "jsonld.description"))},
    "app": {"h1_not_verbatim": len(app_h1), "subtitle_not_verbatim": len(app_sub), "lead_not_verbatim": len(app_lead),
            "strict_aligned": len(app_strict), "idtext_aligned": len(app_idtext),
            "metadata_description_truncated": len(aff(C, "description (metadata)")),
            "jsonld_description_truncated": len(aff(C, "description (JSON-LD)")),
            "ruang_lingkup_not_rendered": len(aff(C, "ruang_lingkup"))},
    "cross_checks": {"titlecase_sets_identical_B_vs_C": site_sub == app_sub,
                     "lead_replaced_intersection": len(site_lead & app_lead),
                     "lead_replaced_site_only": sorted(site_lead - app_lead),
                     "lead_replaced_app_only": sorted(app_lead - site_lead)},
    "idtext_exclusion_decomposition": {"titlecase_altered": len(site_sub | app_sub), "lead_replaced_union": len(site_lead | app_lead),
                                       "in_both_sets": len((site_sub | app_sub) & (site_lead | app_lead)),
                                       "union": len(site_sub | app_sub | site_lead | app_lead)},
    "full_chain_strict": len(corpus_ok & site_strict & app_strict),
    "full_chain_idtext": len(corpus_ok & site_idtext & app_idtext),
    "full_chain_idtext_codes_excluded": sorted(set(codes) - (corpus_ok & site_idtext & app_idtext)),
}
json.dump(out, open(f"{D}/chain_alignment.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ("definitions", "full_chain_idtext_codes_excluded")}, indent=1))
print("excluded codes (idtext):", len(out["full_chain_idtext_codes_excluded"]))
