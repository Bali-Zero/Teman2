import type { Language } from "../_lib/flow";
import { translate, type I18nKey } from "../_lib/i18n";
import { roadCopy } from "./road-copy";

/**
 * Plain wording over the frozen dictionary. `_lib/i18n.ts` is frozen for this
 * surface (BRIEF-v2 R-6), yet some of its customer-facing strings still speak
 * the engine's language — "interview branches", "closed", "the engine",
 * "facts" — which Zero rejected on this surface (2026-09-22, MV:2167) and the
 * council flagged again (CRITIQUE-v2 Oracle #1). Components render through
 * `plainTranslate`, which reads an override here first and falls back to the
 * frozen string, with the SAME `{{var}}` / `{{plural:a|b}}` grammar, so the
 * placeholders a call site passes keep working. Parity, placeholder
 * agreement and the vocabulary guard live in plain-copy.test.ts.
 *
 * Deliberately NOT overridden: the `why.*` explanations behind "Why we ask"
 * (a collapsed disclosure, 100+ strings of regulatory wording — a seam for
 * its own PR), internal-preview strings, and "branch" where it names a
 * company's branch office.
 */
export const PLAIN_COPY = {
  en: {
    "paths.counter.label":
      "{{count}} {{plural:purpose — the one you chose|purposes still possible}}",
    "paths.counter.aria":
      "{{count}} {{plural:purpose — the one you chose|purposes still possible}}",
    "confirmation.paths_remaining":
      "{{count}} {{plural:purpose — the one you chose|purposes still possible}}",
    "confirmation.group.identity": "About you",
    "confirmation.group.details": "Details of your purpose",
    "tree.breadcrumb_label": "Your latest answers",
    "tree.sr_status.pruned": "not asked for this purpose",
    "process.phase.outcome": "Your result",
    "process.phase_status.pruned": "not needed for this purpose",
    "process.categories_title": "Purposes",
    "process.category_status.pruned": "set aside for now",
    "process.pruned_because":
      "{{count}} other {{plural:purpose was|purposes were}} set aside when you chose “{{category}}”. To change purpose, go back to the purpose question.",
    "process.pruned_none":
      "Every purpose is still possible. Choosing one sets the others aside for now.",
    "process.branch_reopen_aria":
      "Switch to {{category}} — asks the questions for that purpose",
    "process.candidates_pending":
      "No visa path is named yet. Your answers are checked only after you confirm them — this page never decides on its own.",
    "process.candidates_none":
      "No visa path fits these answers. The result below says why.",
    "process.candidates_undecided":
      "No visa path was named for these answers. The result below says why.",
    "process.candidates_follow_up":
      "One more answer is needed before a path can be suggested. This question asks for it.",
    "process.outcome_node":
      "This is where the road ends: the result below belongs to it, not to a separate page.",
    "process.announce_prune":
      "You chose {{category}}. {{count}} other {{plural:purpose is|purposes are}} set aside for now.",
    "verdict.state_description.SUPPORTED_CANDIDATES":
      "For the answers you gave and the dated rules checked, these paths can be considered. None of them is an approval: each has conditions, listed below.",
    "verdict.provenance_description.CLIENT_GUARD":
      "No result was produced. Review the highlighted answer or continue with a person.",
    "outcome.needs_input_body":
      "No path can be suggested yet, because these answers are still missing:",
    "outcome.provenance.CLIENT_GUARD.body":
      "This is an operational hold, not a result. No visa path was selected.",
    "outcome.provenance.NETWORK_FAILURE.body":
      "The check did not answer. Nothing was filled in to replace it.",
    "outcome.disclaimer.based_on_facts":
      "The result reflects only the answers you gave and the dated sources shown above.",
    "assumption.work_payer":
      "You weren’t sure who pays you, so we recorded that as unresolved; everything else was still checked, and a Bali Zero advisor confirms this point with you.",
    "assumption.remote_clients":
      "You weren’t sure where your clients sit, so we recorded that as unresolved; everything else was still checked, and a Bali Zero advisor confirms this point with you.",
    "q.birth_date.hint":
      "We send your date of birth as you give it; your age is worked out from it the same way every time.",
    "q.investment_vehicle.hint":
      "This only decides the next questions; it is not sent for the check.",
    "q.diaspora_connection.hint":
      "This is context for a person to read; your nationality is asked separately.",
    "q.other_purpose.hint":
      "This is kept as you wrote it; it is not turned into a visa purpose or a service.",
    "q.other_paid_activity.hint":
      "This is context for a person to read; it is not turned into an answer about employment.",
  },
  id: {
    "paths.counter.label":
      "{{count}} {{plural:tujuan — yang Anda pilih|tujuan masih mungkin}}",
    "paths.counter.aria":
      "{{count}} {{plural:tujuan — yang Anda pilih|tujuan masih mungkin}}",
    "confirmation.paths_remaining":
      "{{count}} {{plural:tujuan — yang Anda pilih|tujuan masih mungkin}}",
    "confirmation.group.identity": "Tentang Anda",
    "confirmation.group.details": "Rincian tujuan Anda",
    "tree.breadcrumb_label": "Jawaban terakhir Anda",
    "tree.sr_status.pruned": "tidak ditanyakan untuk tujuan ini",
    "process.phase.outcome": "Hasil Anda",
    "process.phase_status.pruned": "tidak diperlukan untuk tujuan ini",
    "process.categories_title": "Tujuan",
    "process.category_status.pruned": "dikesampingkan untuk saat ini",
    "process.pruned_because":
      "{{count}} tujuan lain dikesampingkan saat Anda memilih “{{category}}”. Untuk mengganti tujuan, kembali ke pertanyaan tujuan.",
    "process.pruned_none":
      "Semua tujuan masih mungkin. Memilih satu akan mengesampingkan yang lain untuk saat ini.",
    "process.branch_reopen_aria":
      "Beralih ke {{category}} — menanyakan pertanyaan untuk tujuan itu",
    "process.candidates_pending":
      "Belum ada jalur visa yang disebut. Jawaban Anda baru diperiksa setelah Anda mengonfirmasinya — halaman ini tidak pernah memutuskan sendiri.",
    "process.candidates_none":
      "Tidak ada jalur visa yang sesuai dengan jawaban ini. Hasil di bawah menjelaskan alasannya.",
    "process.candidates_undecided":
      "Tidak ada jalur visa yang disebut untuk jawaban ini. Hasil di bawah menjelaskan alasannya.",
    "process.candidates_follow_up":
      "Masih perlu satu jawaban lagi sebelum jalur dapat disarankan. Pertanyaan ini menanyakannya.",
    "process.outcome_node":
      "Di sinilah jalan berakhir: hasil di bawah adalah bagiannya, bukan halaman terpisah.",
    "process.announce_prune":
      "Anda memilih {{category}}. {{count}} tujuan lain dikesampingkan untuk saat ini.",
    "verdict.state_description.SUPPORTED_CANDIDATES":
      "Untuk jawaban Anda dan aturan bertanggal yang diperiksa, jalur berikut layak dipertimbangkan. Tidak satu pun merupakan persetujuan: masing-masing memiliki syarat, tercantum di bawah.",
    "verdict.provenance_description.CLIENT_GUARD":
      "Belum ada hasil. Tinjau jawaban yang ditandai atau lanjutkan dengan konsultan.",
    "outcome.needs_input_body":
      "Belum ada jalur yang dapat disarankan karena jawaban berikut masih kurang:",
    "outcome.provenance.CLIENT_GUARD.body":
      "Ini penahanan operasional, bukan hasil. Tidak ada jalur visa yang dipilih.",
    "outcome.provenance.NETWORK_FAILURE.body":
      "Pemeriksaan tidak memberikan jawaban. Tidak ada hasil pengganti yang dibuat.",
    "outcome.disclaimer.based_on_facts":
      "Hasil ini hanya mencerminkan jawaban yang Anda berikan dan sumber bertanggal yang ditampilkan di atas.",
    "assumption.work_payer":
      "Anda tidak yakin siapa yang menggaji Anda, jadi kami mencatatnya sebagai hal yang belum dipastikan; hal lainnya tetap diperiksa, dan konsultan Bali Zero akan memastikan poin ini bersama Anda.",
    "assumption.remote_clients":
      "Anda tidak yakin di mana klien Anda berada, jadi kami mencatatnya sebagai hal yang belum dipastikan; hal lainnya tetap diperiksa, dan konsultan Bali Zero akan memastikannya bersama Anda.",
    "q.birth_date.hint":
      "Tanggal lahir dikirim sesuai yang Anda berikan; usia Anda dihitung darinya dengan cara yang sama setiap kali.",
    "q.investment_vehicle.hint":
      "Ini hanya menentukan pertanyaan berikutnya; tidak dikirim untuk pemeriksaan.",
    "q.diaspora_connection.hint":
      "Ini konteks untuk dibaca seseorang; kewarganegaraan Anda ditanyakan terpisah.",
    "q.other_purpose.hint":
      "Ini disimpan sesuai tulisan Anda; tidak diubah menjadi tujuan visa atau layanan.",
    "q.other_paid_activity.hint":
      "Ini konteks untuk dibaca seseorang; tidak diubah menjadi jawaban tentang pekerjaan.",
  },
} as const satisfies Record<Language, Partial<Record<I18nKey, string>>>;

const PLURAL_MARKER_RE = /\{\{plural:([^|{}]*)\|([^{}]*)\}\}/g;

/** `translate()` with the plain override read first. Same grammar. */
export function plainTranslate(
  language: Language,
  key: I18nKey,
  vars?: Record<string, string | number>,
): string {
  const override = (PLAIN_COPY[language] as Partial<Record<I18nKey, string>>)[
    key
  ];
  if (override === undefined) return translate(language, key, vars);
  let value: string = override;
  if (vars) {
    for (const [name, v] of Object.entries(vars)) {
      value = value.replaceAll(`{{${name}}}`, String(v));
    }
    if (typeof vars.count === "number") {
      const count = vars.count;
      value = value.replace(
        PLURAL_MARKER_RE,
        (_m, one: string, many: string) => (count === 1 ? one : many),
      );
    }
  }
  return value;
}

/**
 * "3 of 7 answered" read as a fixed count while the 7 grew as the walk went
 * on (council CRITIQUE-v2 Oracle #4: "0 of 6" at the trailhead, "3 of 7"
 * mid-walk). The total is the length of the road as the answers so far
 * project it, so until the last answer it is an estimate and says so.
 */
export function answeredOf(
  language: Language,
  current: number,
  total: number,
): string {
  return current >= total
    ? translate(language, "process.step_of", { current, total })
    : roadCopy(language, "answeredAbout", { current, total });
}

/** Frozen keys the override layer is allowed to leave alone although they
 * match the vocabulary guard — each with its reason. */
export const PLAIN_COPY_EXEMPT: Record<string, string> = {
  "q.investment_foreign_branch": "a company's branch office, not a tree branch",
  "tree.investment_foreign_branch":
    "a company's branch office, not a tree branch",
  "q.stay_permit_code.opt.E28D": "official permit name",
  "prototype.badge.detail": "internal preview only (PIN-unlocked testers)",
  "outcome.provenance.SHADOW.body": "internal shadow mode only",
  "lane.bridging.notice": "not rendered by any component on this surface",
};
