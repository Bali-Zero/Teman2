import {
  requireEngineResponse,
  VisaOracleResponseError,
} from "./engine-response";
import { QUESTIONS, type OracleFacts } from "./tree";
import { followUpPrerequisitesMet } from "./flow";
import { translate, type I18nKey } from "./i18n";
import { trustedPrimarySourceUrl } from "./trusted-source-url";
import type {
  InterviewAssumption,
  LocalizedText,
  OperationalAvailabilityStatus,
  OutcomeCandidate,
  OutcomeDocument,
  OutcomeNextSteps,
  OutcomePrice,
  OutcomeReason,
  OutcomeSource,
  OutcomeTimeline,
  OutcomeViewModel,
  ServiceAvailabilityStatus,
} from "./outcome-view-model";
import type {
  VisaOracleCandidateDisplay,
  VisaOracleEvaluateResponse,
  VisaOracleSourceRecord,
} from "./visa-oracle-contract";

const text = (en: string, id: string): LocalizedText => ({ en, id });

const SPOUSAL_WORK_ARTICLE_61_COPY = text(
  "Article 61 of UU 6/2011 allows qualifying mixed-marriage stay-permit holders to work and/or conduct business to support themselves or their family. This assessment does not verify the separate requirements, if any, for employment or self-employment/business.",
  "Pasal 61 UU 6/2011 memperbolehkan pemegang izin tinggal yang memenuhi kategori perkawinan campur untuk melakukan pekerjaan dan/atau usaha guna memenuhi kebutuhan hidupnya dan/atau keluarganya. Penilaian ini tidak memverifikasi persyaratan terpisah, jika ada, untuk hubungan kerja atau usaha mandiri.",
);

const KITAP_TWO_YEAR_MARRIAGE_AND_INTEGRATION_COPY = text(
  "Article 60(2) of UU 6/2011 requires two years of marriage and a signed Pernyataan Integrasi for a mixed-marriage KITAP. These prerequisites are not verified by this assessment.",
  "Pasal 60 ayat (2) UU 6/2011 mensyaratkan usia perkawinan mencapai dua tahun dan Pernyataan Integrasi yang ditandatangani untuk KITAP perkawinan campur. Penilaian ini belum memverifikasi kedua prasyarat tersebut.",
);

/**
 * Exported so the gold-oracle SHADOW baseline (`preview-adapter.ts`'s
 * `buildGoldOraclePreviewOutcome`) reproduces the SAME public next-steps
 * copy a real `NEEDS_INPUT` engine outcome carries — `shadow-parity.ts`'s
 * `semanticProjection` compares `nextSteps` verbatim (id/title/body), so an
 * independently-worded preview copy would read as a permanent mismatch on
 * this axis alone, even when state and missing facts agree exactly.
 */
export const NEXT_STEPS: OutcomeNextSteps = [
  {
    id: "review-decision",
    title: text(
      "Review the verified decision and its assumptions",
      "Tinjau keputusan terverifikasi dan asumsinya",
    ),
  },
  {
    id: "prepare-verified-items",
    title: text(
      "Prepare only documents marked as verified",
      "Siapkan hanya dokumen yang ditandai terverifikasi",
    ),
  },
  {
    id: "consented-advice",
    title: text(
      "Choose whether to contact a Bali Zero advisor",
      "Pilih apakah akan menghubungi konsultan Bali Zero",
    ),
  },
];

const PUBLIC_ID = /^[a-z0-9]{16,20}$/;

/**
 * Human-readable copy for the pack's SUPPORT reason codes — the "why this
 * path is supported" line. Without it the UI printed the bare machine code
 * (`Verified reason: B1_VOA_ELIGIBLE`) on every candidate of every product.
 *
 * Each sentence is derived from the rule's own `when` clause and may claim
 * NOTHING the rule did not test. `PURPOSE_PRODUCT_MATCH` is deliberately
 * generic: 16 rules share that one code — employment, six family relations,
 * D1/D2/D12 multi-entry and study — so any specific sentence would be false
 * for fifteen of them.
 *
 * Unknown codes keep the existing `Verified reason: <code>` form rather than
 * degrading to a generic sentence: a code we have not written copy for is
 * still information, and silently blanking it would hide a new rule instead
 * of surfacing it. (The REVIEW map above chooses the opposite fallback on
 * purpose — there, a wrong-sounding specific is worse than a safe generic.)
 */
export const SUPPORT_REASON_COPY: Record<string, LocalizedText> = {
  A1_BVK_ELIGIBLE: text(
    "Your nationality is on the visa-free (BVK) list for tourism or transit, and your stay is 30 days or less.",
    "Kewarganegaraan Anda ada dalam daftar bebas visa (BVK) untuk wisata atau transit, dan masa tinggal Anda 30 hari atau kurang.",
  ),
  B1_VOA_ELIGIBLE: text(
    "Your nationality is on the Visa on Arrival list for tourism, and your stay is 30 days or less.",
    "Kewarganegaraan Anda ada dalam daftar Visa on Arrival untuk wisata, dan masa tinggal Anda 30 hari atau kurang.",
  ),
  C1_VISIT_ELIGIBLE: text(
    "A tourism or family visit with a stay of 60 days or less.",
    "Kunjungan wisata atau keluarga dengan masa tinggal 60 hari atau kurang.",
  ),
  C2_BUSINESS_ELIGIBLE: text(
    "Business meetings or investment, with a confirmed sponsor and a stay of 60 days or less.",
    "Pertemuan bisnis atau investasi, dengan penjamin terkonfirmasi dan masa tinggal 60 hari atau kurang.",
  ),
  C6_SOCIAL_ELIGIBLE: text(
    "A social or other stated purpose, with a confirmed sponsor and a stay of 60 days or less.",
    "Tujuan sosial atau lainnya, dengan penjamin terkonfirmasi dan masa tinggal 60 hari atau kurang.",
  ),
  E28A_INVESTMENT_ELIGIBLE: text(
    "You committed to a PT PMA as shareholder-director or shareholder-commissioner, with paid-up capital of IDR 2.5 billion or more.",
    "Anda berkomitmen pada PT PMA sebagai pemegang saham-direktur atau pemegang saham-komisaris, dengan modal disetor minimal Rp 2,5 miliar.",
  ),
  E33E_RETIREMENT_ELIGIBLE: text(
    "Retirement, age 55 or over, with a deposit of USD 50,000 or more held in your own name at a state bank.",
    "Pensiun, usia 55 tahun ke atas, dengan deposito minimal USD 50.000 atas nama sendiri di bank BUMN.",
  ),
  E33F_RETIREMENT_ELIGIBLE: text(
    "Retirement with passive income of USD 3,000 per month or more and a confirmed sponsor.",
    "Pensiun dengan penghasilan pasif minimal USD 3.000 per bulan dan penjamin terkonfirmasi.",
  ),
  E33_DEPOSIT_BASIS_ELIGIBLE: text(
    "Second Home on the deposit basis: USD 130,000 or more held in your own name at a state bank.",
    "Rumah Kedua berbasis deposito: minimal USD 130.000 atas nama sendiri di bank BUMN.",
  ),
  E33_PROPERTY_BASIS_ELIGIBLE: text(
    "Second Home on the property basis: qualifying property valued at USD 1,000,000 or more.",
    "Rumah Kedua berbasis properti: properti memenuhi syarat senilai minimal USD 1.000.000.",
  ),
  REMOTE_WORK_ELIGIBLE: text(
    "You work remotely for a non-Indonesian employer, serve no Indonesian clients, and take no Indonesian-source compensation.",
    "Anda bekerja jarak jauh untuk pemberi kerja non-Indonesia, tidak melayani klien Indonesia, dan tidak menerima kompensasi dari sumber Indonesia.",
  ),
  BRIDGING_DESTINATION_STATED: text(
    "You named a destination status other than the bridging permit itself, so a bridging route can be assessed.",
    "Anda menyebut status tujuan selain izin peralihan itu sendiri, sehingga jalur peralihan dapat dinilai.",
  ),
  PURPOSE_PRODUCT_MATCH: text(
    "Your stated purpose and the circumstances you confirmed match what this visa covers.",
    "Tujuan yang Anda nyatakan dan keadaan yang Anda konfirmasi sesuai dengan cakupan visa ini.",
  ),

  // --- Requirements ------------------------------------------------------
  // Until rule pack seq-6 these were HUMAN_REVIEW rules, so an applicant who
  // matched one was shown nothing at all. They never detected a defect: most
  // test only the purpose (`hr.d2-funds-usd-2000` is literally
  // `intent.purposes intersects [BUSINESS_MEETINGS]` and reads no funds
  // fact). They are conditions attached to an offer, and the sentence must
  // read as one -- it may still claim NOTHING the rule did not test, so none
  // of these says the applicant HAS met the requirement.
  CV_REQUIRED: text(
    "You will need to provide a CV with your application.",
    "Anda perlu melampirkan CV pada permohonan Anda.",
  ),
  ITINERARY_REQUIRED: text(
    "You will need to provide a travel itinerary with your application.",
    "Anda perlu melampirkan rencana perjalanan pada permohonan Anda.",
  ),
  SUPPORT_LETTER_REQUIRED: text(
    "You will need a support letter with your application.",
    "Anda memerlukan surat dukungan pada permohonan Anda.",
  ),
  PASSPORT_VALIDITY_6_MONTHS_REQUIRED: text(
    "Your passport must be valid for at least 6 months on the date you enter.",
    "Paspor Anda harus berlaku minimal 6 bulan pada tanggal Anda masuk.",
  ),
  PROOF_OF_FUNDS_D1: text(
    "You will need to show proof of funds of USD 2,000 or more.",
    "Anda perlu menunjukkan bukti dana minimal USD 2.000.",
  ),
  PROOF_OF_FUNDS_D2: text(
    "You will need to show proof of funds of USD 2,000 or more.",
    "Anda perlu menunjukkan bukti dana minimal USD 2.000.",
  ),
  PROOF_OF_FUNDS_D12: text(
    "You will need to show proof of funds of USD 5,000 or more.",
    "Anda perlu menunjukkan bukti dana minimal USD 5.000.",
  ),
  REQ_FUNDS_2000: text(
    "You will need to show proof of funds of USD 2,000 or more.",
    "Anda perlu menunjukkan bukti dana minimal USD 2.000.",
  ),
  LIVING_COST_USD2000: text(
    "You will need to show living costs of USD 2,000 or more for your studies.",
    "Anda perlu menunjukkan biaya hidup minimal USD 2.000 untuk masa studi Anda.",
  ),
  REQ_SPONSOR_ITAS_ITAP: text(
    "Your sponsor must hold a valid ITAS or ITAP.",
    "Penjamin Anda harus memiliki ITAS atau ITAP yang berlaku.",
  ),
  REQ_SPONSOR_MIXED_MARRIAGE: text(
    "This route runs through a mixed-marriage sponsor, whose status we verify.",
    "Jalur ini melalui penjamin perkawinan campur, yang statusnya kami verifikasi.",
  ),
  REQ_MIXED_MARRIAGE_PARENTS: text(
    "This route requires a mixed-marriage parent relationship, which we verify from your documents.",
    "Jalur ini memerlukan hubungan orang tua perkawinan campur, yang kami verifikasi dari dokumen Anda.",
  ),
  REQ_STEP_PARENT_RELATION: text(
    "This route requires a step-parent relationship, which we verify from your documents.",
    "Jalur ini memerlukan hubungan orang tua tiri, yang kami verifikasi dari dokumen Anda.",
  ),
  MINOR_CONSENT_GUARDIAN: text(
    "As the applicant is a minor, guardian consent is required.",
    "Karena pemohon masih di bawah umur, diperlukan persetujuan wali.",
  ),
  // Keep the old key safe for persisted seq-5 decisions while seq-6 emits
  // the Article 61-specific key below.
  SPOUSAL_WORK_KEMENAKER_CAVEAT: SPOUSAL_WORK_ARTICLE_61_COPY,
  SPOUSAL_WORK_ARTICLE_61_CONTEXT: SPOUSAL_WORK_ARTICLE_61_COPY,
  // The second sentence is the compliance caveat the adversarial review of
  // 2026-09-06 (finding 2) required alongside the removal of `work_role`.
  // That question's five options could not identify a restricted position
  // and no rule in the pack read the fact, so it was a blanket hold rather
  // than a check — position eligibility is decided at the employer's RPTKA
  // step, and the result copy now says so instead of implying the
  // interview settled it.
  REQUIRED_RPTKA_APPROVAL: text(
    "Your employer must obtain RPTKA approval before this permit can be issued. Some positions are closed to foreign nationals; your employer's RPTKA determines which roles qualify.",
    "Pemberi kerja Anda harus memperoleh persetujuan RPTKA sebelum izin ini dapat diterbitkan. Beberapa jabatan tertutup bagi warga negara asing; RPTKA pemberi kerja Anda menentukan jabatan yang memenuhi syarat.",
  ),
  REQUIRED_DIPLOMAT_SPONSOR: text(
    "This permit requires a diplomatic mission as sponsor.",
    "Izin ini memerlukan perwakilan diplomatik sebagai penjamin.",
  ),
  REQUIRED_KDEI_SPONSOR: text(
    "This permit requires KDEI as sponsor.",
    "Izin ini memerlukan KDEI sebagai penjamin.",
  ),
  JABATAN_MUST_MATCH_KBLI: text(
    "Your job title must match the company's KBLI business activity.",
    "Jabatan Anda harus sesuai dengan bidang usaha KBLI perusahaan.",
  ),
  PROHIBITED_HR_ROLES_KEPMENAKER_349_2019: text(
    "Some human-resources roles are closed to foreign nationals under Kepmenaker 349/2019 — we check your specific job title against that list.",
    "Sebagian jabatan sumber daya manusia tertutup bagi warga negara asing menurut Kepmenaker 349/2019 — kami memeriksa jabatan Anda terhadap daftar tersebut.",
  ),
  E23_REQUIRED_FOR_OPERATIONAL_WORK_EVEN_IF_DIRECTOR: text(
    "Operational work needs this work permit even when you are a shareholder-director or shareholder-commissioner.",
    "Pekerjaan operasional memerlukan izin kerja ini meskipun Anda pemegang saham-direktur atau pemegang saham-komisaris.",
  ),
  RESTRICTED_TO_DOMESTIC_HELPER: text(
    "This permit covers domestic-helper roles only.",
    "Izin ini hanya mencakup pekerjaan asisten rumah tangga.",
  ),
  KEK_INSTITUTION_ONLY: text(
    "This permit covers study at a KEK-based institution only.",
    "Izin ini hanya mencakup studi di lembaga berbasis KEK.",
  ),
  EXCHANGE_PROGRAM_ONLY: text(
    "This permit covers exchange programmes only.",
    "Izin ini hanya mencakup program pertukaran.",
  ),
  STUDY_PERMIT_KEMDIKBUD: text(
    "You will need a Kemdikbud study permit (izin belajar).",
    "Anda memerlukan izin belajar dari Kemdikbud.",
  ),
  C2_CORPORATE_SPONSOR_TYPE_VERIFICATION: text(
    "We verify that your sponsor is the right type of company for this visa.",
    "Kami memverifikasi bahwa penjamin Anda adalah jenis perusahaan yang tepat untuk visa ini.",
  ),
  GOVT_INVITATION_REQUIRED: text(
    "This route requires an invitation from a central government body.",
    "Jalur ini memerlukan undangan dari instansi pemerintah pusat.",
  ),
  GUARANTEE_VALUE_MUST_BE_MAINTAINED: text(
    "The deposit or property value behind this permit must be maintained for as long as you hold it.",
    "Nilai deposito atau properti yang mendasari izin ini harus dipertahankan selama izin berlaku.",
  ),
  // The alias prevents historical seq-5 decisions from rendering the old,
  // incorrect "two years on this status" statement.
  KITAP_CONVERSION_TWO_YEAR_DOOR: KITAP_TWO_YEAR_MARRIAGE_AND_INTEGRATION_COPY,
  KITAP_TWO_YEAR_MARRIAGE_AND_INTEGRATION_NOT_VERIFIED:
    KITAP_TWO_YEAR_MARRIAGE_AND_INTEGRATION_COPY,
  BRIDGING_SOURCE_STATUS_VERIFY: text(
    "We verify your current immigration status before a bridging route can be filed.",
    "Kami memverifikasi status keimigrasian Anda saat ini sebelum jalur peralihan dapat diajukan.",
  ),
  BRIDGING_OVERSTAY_SHIELD_PAYMENT_CHECK: text(
    "We check whether an overstay payment is due before the bridging permit shields your stay.",
    "Kami memeriksa apakah ada pembayaran overstay yang terutang sebelum izin peralihan melindungi masa tinggal Anda.",
  ),

  // --- Advisor checks ----------------------------------------------------
  // Each names a threshold the engine has NO fact to test -- there is no
  // income field anywhere in `work.*`, and none for the Golden Visa USD
  // bands. Before seq-6 these rules walled the applicant instead of saying
  // so. Zero's ruling (2026-08-09): offer the route and name the check.
  // Where the figure is not in the rule itself it is deliberately NOT stated
  // here rather than guessed.
  E33G_INCOME_60K_ADVISOR_CHECK: text(
    "This route asks for annual income of USD 60,000 or more. We confirm the figure and the evidence with one of our advisors.",
    "Jalur ini mensyaratkan penghasilan tahunan minimal USD 60.000. Kami memastikan angka dan buktinya bersama konsultan kami.",
  ),
  E28B_USD_THRESHOLD_ADVISOR_CHECK: text(
    "This Golden Visa route has a minimum investment threshold in USD. We confirm the current figure and your evidence with one of our advisors.",
    "Jalur Golden Visa ini memiliki ambang investasi minimum dalam USD. Kami memastikan angka terkini dan bukti Anda bersama konsultan kami.",
  ),
  E28C_USD_THRESHOLD_ADVISOR_CHECK: text(
    "This Golden Visa route has a minimum investment threshold in USD. We confirm the current figure, the instrument, and your evidence with one of our advisors.",
    "Jalur Golden Visa ini memiliki ambang investasi minimum dalam USD. Kami memastikan angka terkini, instrumennya, dan bukti Anda bersama konsultan kami.",
  ),
  E28D_USD_THRESHOLD_TURNOVER_ADVISOR_CHECK: text(
    "This Golden Visa route has a minimum investment and turnover threshold. We confirm the current figures and your evidence with one of our advisors.",
    "Jalur Golden Visa ini memiliki ambang investasi dan omzet minimum. Kami memastikan angka terkini dan bukti Anda bersama konsultan kami.",
  ),
  E28F_IKN_THRESHOLD_ADVISOR_CHECK: text(
    "This IKN route has its own investment threshold. We confirm the current figure and your evidence with one of our advisors.",
    "Jalur IKN ini memiliki ambang investasi tersendiri. Kami memastikan angka terkini dan bukti Anda bersama konsultan kami.",
  ),
  E33B_EXPERTISE_QUALIFICATION_ADVISOR_CHECK: text(
    "This route is judged on your professional qualifications. We review them with one of our advisors before filing.",
    "Jalur ini dinilai berdasarkan kualifikasi profesional Anda. Kami meninjaunya bersama konsultan kami sebelum pengajuan.",
  ),
  E33E_DEPOSIT_INCOME_BASIS_ADVISOR_CHECK: text(
    "This route can be met on a deposit basis or a passive-income basis. We work out which one fits you with one of our advisors.",
    "Jalur ini dapat dipenuhi berbasis deposito atau penghasilan pasif. Kami menentukan mana yang sesuai untuk Anda bersama konsultan kami.",
  ),
  E33E_AGE_55_59_ADVISOR_CHECK: text(
    "Between 55 and 59 the age requirement for this route is read differently by different offices. We check how it currently applies to you.",
    "Antara usia 55 dan 59, persyaratan usia jalur ini ditafsirkan berbeda oleh kantor yang berbeda. Kami memeriksa penerapannya untuk Anda saat ini.",
  ),
  E33F_AGE_UNDER_55_ADVISOR_CHECK: text(
    "Under 55 this route is discretionary. We check whether it is open to you before filing.",
    "Di bawah usia 55, jalur ini bersifat diskresioner. Kami memeriksa apakah jalur ini terbuka untuk Anda sebelum pengajuan.",
  ),
  E33_PROPERTY_QUALIFICATION_ADVISOR_CHECK: text(
    "Whether your property qualifies for this route depends on how it is held and valued. We check it with one of our advisors.",
    "Apakah properti Anda memenuhi syarat untuk jalur ini bergantung pada bentuk kepemilikan dan penilaiannya. Kami memeriksanya bersama konsultan kami.",
  ),
  E31F_ADULT_AGE_ADVISOR_CHECK: text(
    "For an adult dependant, eligibility depends on age and relationship together. We check how it applies to you.",
    "Untuk tanggungan dewasa, kelayakan bergantung pada usia dan hubungan keluarga bersama-sama. Kami memeriksa penerapannya untuk Anda.",
  ),
  E31J_DEPENDENCY_AGE_ADVISOR_CHECK: text(
    "Dependency at this age is assessed case by case. We check how it applies to you.",
    "Status ketergantungan pada usia ini dinilai per kasus. Kami memeriksa penerapannya untuk Anda.",
  ),
  // EXCLUDE code (hf.e31c-marriage-not-registered, seq-10). Exclusion
  // reasons flow through the same reasonMessage fallback as candidate
  // reasons, so without this entry the raw code would render at a real
  // reader (Codex refuter finding 3 / Kimi finding 7, 2026-08-19).
  REQ_PARENTS_MARRIAGE_REGISTERED: text(
    "This route requires official proof of the parents' legally registered marriage. Without a registered marriage, this visa is not available.",
    "Jalur ini memerlukan bukti resmi perkawinan orang tua yang tercatat secara sah. Tanpa perkawinan tercatat, visa ini tidak tersedia.",
  ),
  // EXCLUDE code (hf.d2.indonesia-source-compensation, seq-20). The seq-20
  // fold compiles CL-D2-01's local-compensation prohibition for the first
  // time, so this code reaches the NO_SUPPORTED_PATH sheet through the same
  // `reasonMessage` fallback as every other reason — without this entry the
  // raw code would render at a real reader.
  BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED: text(
    "A business visit visa does not allow payment from an Indonesian source. Paid activity in Indonesia needs a work route.",
    "Visa kunjungan bisnis tidak mengizinkan pembayaran dari sumber di Indonesia. Aktivitas berbayar di Indonesia memerlukan jalur kerja.",
  ),
  D12_CUMULATIVE_STAY_ADVISOR_CHECK: text(
    "Long or repeated stays are counted cumulatively. We check your total against the limit with one of our advisors.",
    "Masa tinggal panjang atau berulang dihitung secara kumulatif. Kami memeriksa total Anda terhadap batasnya bersama konsultan kami.",
  ),
  BRIDGING_T3_WINDOW_ADVISOR_CHECK: text(
    "The filing window for this bridging route is tight. We check your dates with one of our advisors.",
    "Jendela pengajuan jalur peralihan ini sempit. Kami memeriksa tanggal Anda bersama konsultan kami.",
  ),
  // The engine's own OPERATIONAL fallback, emitted when NO_SUPPORTED_PATH is
  // reached with no named exclusion reason that belongs to this applicant
  // (evaluator.py `_fallback_no_path_reason`). It used to be unreachable in
  // practice — before the 2026-09-06 decisiveness reorder no interview walk
  // ended in NO_SUPPORTED_PATH at all — and would have rendered as the raw
  // `Verified reason: OPERATIONAL_...` code dump. It is now reachable, so it
  // gets a sentence. Deliberately NOT phrased as a legal conclusion: it says
  // no product COVERS the declared purposes, which is what the engine
  // actually established.
  OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES: text(
    "No visa in our verified catalogue covers the purpose you described. Bali Zero can review your case and suggest what to do next.",
    "Tidak ada visa dalam katalog terverifikasi kami yang mencakup tujuan yang Anda sebutkan. Bali Zero dapat meninjau kasus Anda dan menyarankan langkah selanjutnya.",
  ),
};

function reasonMessage(code: string): LocalizedText {
  return (
    SUPPORT_REASON_COPY[code] ??
    text(`Verified reason: ${code}`, `Alasan terverifikasi: ${code}`)
  );
}

function reason(
  code: string,
  sourceIds: readonly string[],
  trustedIds: ReadonlySet<string>,
): OutcomeReason {
  return {
    code,
    message: reasonMessage(code),
    sourceIds: sourceIds.filter((id) => trustedIds.has(id)),
  };
}

// Curated, human-readable copy for HUMAN_REVIEW reason codes: the rule
// pack's own `effect.reason_code` on REQUIRE_REVIEW rules (source:
// services/visa_engine/contracts/packs/rulepack-prod-*.json), plus a
// pack-independent set the backend emits itself (disclosed-review flags +
// the minor-guardian privacy hold — see evaluate_path.py
// `_DISCLOSED_REVIEW_REASON_CODES` and `_apply_minor_privacy_hold`). A code
// missing from this map falls back to an honest generic sentence — never a
// raw code dump — so a new rule can ship without breaking this UI, and this
// map can grow independently of a rule pack release.
//
// engine-adapter.test.ts's exhaustiveness test enforces two things: every
// key here must name a code that still exists (no stale renames — see
// KNOWN_UNMAPPED_REVIEW_REASON_CODES there for the ones this map doesn't
// cover yet), and every code the current pack can emit is accounted for,
// either here or in that known-gap list.
export const REVIEW_REASON_COPY: Record<string, LocalizedText> = {
  // D2-bis (owner ruling, 2026-09-12 20:50 WITA): every HUMAN_REVIEW string
  // must (1) name the specific fact/answer, in the applicant's own terms,
  // that the signed rules cannot decide, (2) state authoritatively that the
  // case is held deliberately for that named reason, and (3) name what
  // resolves it. Applies to these 9 pre-existing entries too, revised below.
  // review.calling-visa carries on_unknown: "HUMAN_REVIEW" (verified in
  // rulepack-prod-020.signed.json), so the identical code fires when
  // nationality itself is UNKNOWN, not only when it is confirmed on the
  // list — the round-2 refuter gate caught the first draft asserting the
  // list membership outright, false on that path. Worded to be true on
  // both without losing the list's own specificity.
  CALLING_VISA_REVIEW: text(
    "This case is held because your nationality is on Indonesia's Calling Visa list, or because your nationality has not been established. Confirming your nationality, and the calling-visa clearance that list requires if it applies, is what resolves it before any visa can be confirmed.",
    "Kasus ini ditahan karena kewarganegaraan Anda termasuk dalam daftar Calling Visa Indonesia, atau karena kewarganegaraan Anda belum dapat dipastikan. Konfirmasi kewarganegaraan Anda, beserta proses persetujuan calling visa yang disyaratkan oleh daftar tersebut apabila berlaku, adalah yang akan menyelesaikannya sebelum visa apa pun dapat dikonfirmasi.",
  ),
  ACTIVE_OVERSTAY: text(
    "You reported active overstay days on your immigration record, so a person needs to review it — clearing the overstay is what resolves it.",
    "Anda melaporkan adanya hari overstay yang masih berjalan pada catatan keimigrasian Anda, sehingga memerlukan peninjauan oleh seseorang — menyelesaikan overstay tersebut adalah yang akan menyelesaikannya.",
  ),
  // Renamed from CITIZENSHIP_EVIDENCE_CONFLICT (QW-4a, 2026-08-17): that key
  // named no code in any pack from seq-6 onward. CITIZENSHIP_LIST_DIVERGENCE
  // is its current name (services/visa_engine/contracts/packs/
  // rulepack-prod-007.source.json). review.citizenship-conflict ALSO carries
  // on_unknown: "HUMAN_REVIEW" (verified in rulepack-prod-020.signed.json),
  // so the identical code fires when nationality is entirely UNKNOWN, not
  // only when multiple declared nationalities are known to diverge — the
  // round-2 refuter gate caught the first draft asserting "you declared
  // more than one nationality" outright, false on the unknown path. Worded
  // to be true on both without losing the known-path specificity.
  CITIZENSHIP_LIST_DIVERGENCE: text(
    "This case is held because you declared more than one nationality that falls into different eligibility categories, or because your nationality has not been established. Confirming which passport you will use to apply is what resolves it.",
    "Kasus ini ditahan karena Anda mencantumkan lebih dari satu kewarganegaraan yang termasuk dalam kategori kelayakan yang berbeda, atau karena kewarganegaraan Anda belum dapat dipastikan. Konfirmasi paspor mana yang akan Anda gunakan untuk mengajukan permohonan adalah yang akan menyelesaikannya.",
  ),
  // review.minor-without-guardian: derived.is_minor == true AND
  // family.sponsor_confirmed == false — confirming the sponsor is the fact
  // that resolves it (the same fact the rule tests).
  MINOR_WITHOUT_CONFIRMED_GUARDIAN: text(
    "This case involves a minor whose sponsor has not yet been confirmed, and a person needs to review it — confirming the sponsor is what resolves it.",
    "Kasus ini melibatkan anak di bawah umur yang sponsornya belum dikonfirmasi, dan memerlukan peninjauan oleh seseorang — konfirmasi sponsor adalah yang akan menyelesaikannya.",
  ),
  // Wording follows the pack's own product names verbatim — "Working Visa —
  // Foreign Diplomat House Assistant (E23U)" / "Visa Kerja Asisten Rumah
  // Tangga Diplomat Asing" and "Working Visa — Trade and Economic Office
  // (E23V)" / "Visa Kerja Kantor Dagang dan Ekonomi". An adversarial review
  // of the first draft caught it narrowing E23V to "trade representative
  // office", dropping "and Economic": the applicant would then be told about
  // a category that is not the one the rule actually names. Both rules fire
  // unconditionally for their product code (no distinguishing fact beyond
  // the product itself), so naming the product IS the specific cause.
  E23U_DIPLOMATIC_HOUSEHOLD_STAFF_REVIEW: text(
    "Every application for the Working Visa — Foreign Diplomat House Assistant (E23U) is reviewed manually to confirm the household-employment relationship with the diplomat before it can be confirmed.",
    "Setiap permohonan Visa Kerja Asisten Rumah Tangga Diplomat Asing (E23U) ditinjau secara manual untuk memastikan hubungan kerja rumah tangga dengan diplomat tersebut sebelum dapat dikonfirmasi.",
  ),
  E23V_TRADE_OFFICE_STAFF_REVIEW: text(
    "Every application for the Working Visa — Trade and Economic Office (E23V) is reviewed manually to confirm the staff relationship with that trade and economic office before it can be confirmed.",
    "Setiap permohonan Visa Kerja Kantor Dagang dan Ekonomi (E23V) ditinjau secara manual untuk memastikan hubungan kerja dengan kantor dagang dan ekonomi tersebut sebelum dapat dikonfirmasi.",
  ),
  // Renamed from STATUS_BRIDGING_REVIEW (QW-4a, 2026-08-17): same stale
  // situation — BRIDGING_ADVERSE_HISTORY is the current name for this rule
  // in rulepack-prod-007+. review.bridging.adverse-history fires on ANY of 4
  // distinct violation_history values (OVERSTAY / DEPORTATION / BLACKLIST /
  // IMMIGRATION_INVESTIGATION) OR on that fact being unknown (on_unknown:
  // "HUMAN_REVIEW") — one code, several distinct causes with different
  // real-world resolutions. Named all 4 rather than guessing one; flagged as
  // a split candidate in the PR-O2 report. Round-1 refuter fix (Gemini 3.1
  // Pro + Kimi K3, converged independently): the first draft asserted the
  // record "shows" one of the four even on the UNKNOWN-fact trigger path —
  // false the moment the hold is raised because the record hasn't been
  // established at all, not because a specific violation was found. Rewritten
  // to cover both paths without asserting any of the four exists, matching
  // the "not yet established" pattern already used for the 4 HARD_FILTER
  // codes above.
  BRIDGING_ADVERSE_HISTORY: text(
    "This case is held to check your immigration record while in Indonesia for an overstay, deportation, blacklist entry, or open investigation, or because that record has not been established. Confirming your record is what resolves it before the Bridging Visa — Transitional Stay Permit can be confirmed.",
    "Kasus ini ditahan untuk memeriksa catatan keimigrasian Anda selama berada di Indonesia terkait overstay, deportasi, entri daftar hitam (blacklist), atau investigasi yang masih berjalan, atau karena catatan tersebut belum dapat dipastikan. Konfirmasi catatan Anda adalah yang akan menyelesaikannya sebelum Izin Tinggal Peralihan dapat dipastikan.",
  ),
  LOCAL_MARKET_ACTIVITY_REVIEW: text(
    "You said your remote work serves Indonesian clients, and the Second Home Visa — Remote Worker (E33G) is for income from outside Indonesia only — a person needs to confirm your work does not cross into locally reserved business.",
    "Anda menyatakan bahwa pekerjaan jarak jauh Anda melayani klien di Indonesia, sedangkan Visa Rumah Kedua Pekerja Jarak Jauh (E33G) hanya untuk penghasilan dari luar Indonesia — diperlukan konfirmasi oleh seseorang bahwa pekerjaan Anda tidak melanggar bidang usaha yang dicadangkan untuk lokal.",
  ),
  // fact-mapper.ts::hasUndecidableActivityAnswer raises this ONE code from 7
  // distinct question ids (business_activity, investment_vehicle,
  // retirement_basis, diaspora_connection, diaspora_documents,
  // other_purpose, other_paid_activity) whenever any of them holds an
  // answer value the signed pack cannot decide — the OutcomeReason carries
  // no field to say which. Old copy ("sits close to a legal boundary") was
  // ruled no longer acceptable (D2-bis) for being generic; named the
  // question DIMENSIONS below as the most specific honest statement
  // available, and flagged as a split candidate in the PR-O2 report.
  DISCLOSED_ACTIVITY_BOUNDARY_REVIEW: text(
    "One of your answers about your planned activity, investment vehicle, retirement basis, or diaspora connection is not one the signed rules can decide on their own, so a person needs to confirm it before a path can be confirmed.",
    "Salah satu jawaban Anda mengenai aktivitas yang direncanakan, kendaraan investasi, dasar pensiun, atau hubungan diaspora bukan jawaban yang dapat diputuskan sendiri oleh aturan yang telah disahkan, sehingga memerlukan konfirmasi oleh seseorang sebelum jalur dapat dipastikan.",
  ),

  // --- QW-4b (PR-O2, D1): the 29 codes that previously fell back to
  // GENERIC_REVIEW_REASON. Product names are copied verbatim from each
  // rule's `product_version_ids` entry in rulepack-prod-020.source.json
  // (`names.en` / `names.id`) — never shortened or re-described. Every
  // string below is written to D2-bis's three rules too: name the specific
  // fact, state the hold authoritatively, name what resolves it.

  // 8 codes from rulepack-prod-020 (rulepack-prod-007+ lineage), stage
  // HUMAN_REVIEW — each rule fires unconditionally for its product/purpose
  // combination (no numeric threshold is modeled as a fact, hence "manual"),
  // so naming the requested product IS the specific cause; the resolution is
  // the manual check the code name itself describes.
  E28B_USD_THRESHOLD_MANUAL_CHECK: text(
    "You requested the Investor Golden Visa — Company Establishment (E28B), which always has its required USD investment amount checked manually — confirming that amount against your documents is what resolves it.",
    "Anda mengajukan Visa Investor Pendirian Perusahaan (E28B), yang jumlah investasi USD yang disyaratkan selalu diperiksa secara manual — konfirmasi jumlah tersebut terhadap dokumen Anda adalah yang akan menyelesaikannya.",
  ),
  E28C_USD_THRESHOLD_AND_INSTRUMENT_CHECK: text(
    "You requested the Investor Golden Visa — Capital Market (E28C), which always has its USD investment amount and financial instrument checked manually — confirming both against your documents is what resolves it.",
    "Anda mengajukan Visa Investor Tanpa Mendirikan Perusahaan (E28C), yang jumlah investasi USD dan instrumen keuangannya selalu diperiksa secara manual — konfirmasi keduanya terhadap dokumen Anda adalah yang akan menyelesaikannya.",
  ),
  E28D_USD_THRESHOLD_AND_TURNOVER_CHECK: text(
    "You requested the Investor Golden Visa — Branch or Subsidiary (E28D), which always has its USD investment amount and company turnover checked manually — confirming both against your documents is what resolves it.",
    "Anda mengajukan Visa Investor Pendirian Kantor Cabang atau Anak Perusahaan (E28D), yang jumlah investasi USD dan omzet perusahaannya selalu diperiksa secara manual — konfirmasi keduanya terhadap dokumen Anda adalah yang akan menyelesaikannya.",
  ),
  E28F_IKN_THRESHOLD_MANUAL_CHECK: text(
    "You requested the Investor Golden Visa — New Capital (IKN) Subsidiary (E28F), which always has its IKN investment threshold checked manually — confirming that amount against your documents is what resolves it.",
    "Anda mengajukan Visa Investor Anak Perusahaan Ibukota Nusantara (E28F), yang ambang batas investasi IKN-nya selalu diperiksa secara manual — konfirmasi jumlah tersebut terhadap dokumen Anda adalah yang akan menyelesaikannya.",
  ),
  E33B_EXPERTISE_QUALIFICATION_CHECK: text(
    "You requested the Second Home Golden Visa — Special-Expertise Collaboration (E33B), which always has the applicant's expertise checked manually — confirming your qualification against your documents is what resolves it.",
    "Anda mengajukan Visa Rumah Kedua Kolaborasi Keahlian Khusus (E33B), yang keahlian pemohonnya selalu diperiksa secara manual — konfirmasi kualifikasi Anda terhadap dokumen Anda adalah yang akan menyelesaikannya.",
  ),
  E33G_EXCLUDES_LOCAL_COMPANY_OWNERSHIP: text(
    "You said you have committed to PT PMA company ownership, and the Second Home Visa — Remote Worker (E33G) excludes local company ownership — a person needs to confirm your PT PMA commitment before this can be resolved.",
    "Anda menyatakan telah berkomitmen pada kepemilikan perusahaan PT PMA, sedangkan Visa Rumah Kedua Pekerja Jarak Jauh (E33G) mengecualikan kepemilikan perusahaan lokal — diperlukan konfirmasi oleh seseorang atas komitmen PT PMA Anda sebelum hal ini dapat diselesaikan.",
  ),
  E33_WORK_RANGKAP_KEGIATAN_GATED: text(
    "You selected both a Second Home Visa (E33) purpose and an employment purpose, and a person needs to confirm how the two combine before this case can be resolved.",
    "Anda memilih tujuan Visa Rumah Kedua (E33) sekaligus tujuan bekerja, dan diperlukan konfirmasi oleh seseorang mengenai bagaimana keduanya digabungkan sebelum kasus ini dapat diselesaikan.",
  ),
  // Fires identically for two products (E33A, E33C) that share this reason
  // code — both name their own product verbatim rather than picking one.
  GOVT_INVITATION_REQUIRED: text(
    "You requested the Second Home Visa — Special-Expertise Government Invitation (E33A) or the Second Home Golden Visa — World-Figure Government Invitation (E33C), both issued only on a central government invitation — confirming that invitation is what resolves it.",
    "Anda mengajukan Visa Rumah Kedua Tenaga Ahli Undangan Pemerintah (E33A) atau Visa Rumah Kedua Tokoh Dunia Undangan Pemerintah (E33C), yang keduanya hanya diterbitkan berdasarkan undangan pemerintah pusat — konfirmasi undangan tersebut adalah yang akan menyelesaikannya.",
  ),

  // 4 codes from rulepack-prod-020, stage HARD_FILTER with
  // `on_unknown: "HUMAN_REVIEW"` (hf.bridging.offshore / .from-visit-itk /
  // .to-bridging / hf.b1.not-voa-nationality). When the underlying fact is
  // KNOWN these rules EXCLUDE the product outright; when it is UNKNOWN,
  // `evaluator.py::_partition_unknowns_by_policy` + `_reason_from_rule`
  // escalate to REVIEW and reuse the SAME reason_code (see
  // evaluator.py:355-410, 741-751) — so this copy must never read as an
  // exclusion, only as a fact still to be established; naming that missing
  // fact doubles as naming what resolves it (confirming the fact).
  BRIDGING_ONSHORE_ONLY: text(
    "This case is held because whether you are currently in Indonesia has not been established, which the Bridging Visa — Transitional Stay Permit requires — confirming your current location is what resolves it.",
    "Kasus ini ditahan karena belum dapat dipastikan apakah Anda saat ini berada di Indonesia, padahal Izin Tinggal Peralihan mensyaratkan hal itu — konfirmasi lokasi Anda saat ini adalah yang akan menyelesaikannya.",
  ),
  BRIDGING_FROM_VISIT_ITK_PROHIBITED: text(
    "This case is held because your current immigration status code has not been established, and the Bridging Visa — Transitional Stay Permit cannot be issued from certain visit-based statuses — confirming your current status code is what resolves it.",
    "Kasus ini ditahan karena kode status keimigrasian Anda saat ini belum dapat dipastikan, sedangkan Izin Tinggal Peralihan tidak dapat diterbitkan dari status berbasis kunjungan tertentu — konfirmasi kode status Anda saat ini adalah yang akan menyelesaikannya.",
  ),
  BRIDGING_TO_BRIDGING_PROHIBITED: text(
    "This case is held because your current immigration status code has not been established, and a Bridging Visa — Transitional Stay Permit cannot follow one already active — confirming your current status code is what resolves it.",
    "Kasus ini ditahan karena kode status keimigrasian Anda saat ini belum dapat dipastikan, sedangkan Izin Tinggal Peralihan tidak dapat mengikuti izin peralihan yang masih aktif — konfirmasi kode status Anda saat ini adalah yang akan menyelesaikannya.",
  ),
  VOA_NATIONALITY_ONLY: text(
    "This case is held because your nationality has not been established, and the Visa on Arrival — Tourism (B1) is issued only for listed nationalities — confirming your nationality is what resolves it.",
    "Kasus ini ditahan karena kewarganegaraan Anda belum dapat dipastikan, sedangkan Visa Saat Kedatangan Wisata (B1) hanya diterbitkan untuk kewarganegaraan yang terdaftar — konfirmasi kewarganegaraan Anda adalah yang akan menyelesaikannya.",
  ),

  // 17 pack-independent codes emitted by evaluate_path.py directly.
  //
  // CONFLICTING_IMMIGRATION_STATUS_REVIEW is a DisclosedReviewFlag
  // (api_models.py) with no current trigger in fact-mapper.ts — unlike
  // CITIZENSHIP_LIST_DIVERGENCE's precise nationality-list logic, there is
  // no `when` clause to read for which two status answers conflict. Named
  // as specifically as the code allows; flagged in the PR-O2 report as
  // meaning not fully pinned to a specific fact pair (not a split
  // candidate — there is no enumerable second cause to split out).
  CONFLICTING_IMMIGRATION_STATUS_REVIEW: text(
    "Your answers about your current immigration status conflict with each other — a person needs to confirm which status is correct before a path can be confirmed.",
    "Jawaban Anda tentang status keimigrasian Anda saat ini saling bertentangan — diperlukan konfirmasi oleh seseorang mengenai status mana yang benar sebelum jalur dapat dipastikan.",
  ),
  // `_apply_decisive_source_authority_hold` (evaluate_path.py:1097-1198):
  // abstains an otherwise-conclusive result when a citation the decision
  // itself relies on isn't authoritative/applicable, or its freshness is
  // unknown/stale. About the SOURCE behind the result, not an applicant
  // answer — D2-bis rule 1's "applicant's own terms" framing does not fit
  // this category, since nothing the applicant said caused this; named the
  // source mechanism as specifically as the code allows instead.
  DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE: text(
    "This result relies on a regulatory source that could not be confirmed as valid and currently applicable — verifying that source is what a person must do before this result can stand.",
    "Hasil ini bergantung pada sumber regulasi yang tidak dapat dikonfirmasi valid dan berlaku saat ini — memverifikasi sumber tersebut adalah yang harus dilakukan oleh seseorang sebelum hasil ini dapat dipastikan.",
  ),
  DECISIVE_SOURCE_FRESHNESS_UNKNOWN: text(
    "This result relies on a regulatory source whose currency could not be established automatically — confirming whether that source is still current is what a person must do before this result can stand.",
    "Hasil ini bergantung pada sumber regulasi yang keberlakuannya belum dapat dipastikan secara otomatis — memastikan apakah sumber tersebut masih berlaku adalah yang harus dilakukan oleh seseorang sebelum hasil ini dapat dipastikan.",
  ),
  DECISIVE_SOURCE_STALE: text(
    "This result relies on a regulatory source confirmed out of date — replacing it with a current source is what a person must do before this result can stand.",
    "Hasil ini bergantung pada sumber regulasi yang telah dipastikan usang — menggantinya dengan sumber yang berlaku saat ini adalah yang harus dilakukan oleh seseorang sebelum hasil ini dapat dipastikan.",
  ),
  // `_DISCLOSED_REVIEW_REASON_CODES` (evaluate_path.py:1014-1027) +
  // `_apply_disclosed_review_flags` (1304-1354): applicant self-disclosures,
  // never a legal eligibility claim — carry no source_refs by design.
  //
  // Owner-directed wording, revised twice (both rounds deliberately against
  // an example offered — do NOT assert the sponsor's nationality as the
  // cause; a parallel PR, D2, is narrowing this code's trigger from "any
  // sponsor-status answer" to "answered unsure about the sponsor, or the
  // product itself is sponsor-dependent", so anything naming nationality
  // would go FALSE the day that merges). Round 2 (owner's ruling on a
  // refuter objection to round 1, ACCEPTED — not dissent, adopted): round
  // 1's "the sponsor's own stay permit could not be established from the
  // answers given" implied a permit is needed at all, which is false when
  // the sponsor is an Indonesian citizen who holds no stay permit and needs
  // none. "Whether your sponsor holds a stay permit of their own has not
  // been established HERE" (owner's exact approved phrase) stays true under
  // the current trigger, the narrowed D2 trigger, AND the Indonesian-sponsor
  // case — it says the question wasn't settled by this tool, never that a
  // permit exists or is required.
  DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW: text(
    "This case is held because whether your sponsor holds a stay permit of their own has not been established here — confirming the sponsor's own stay permit is what resolves it.",
    "Kasus ini ditahan karena belum dapat dipastikan di sini apakah sponsor Anda memiliki izin tinggal sendiri — konfirmasi izin tinggal sponsor tersebut adalah yang akan menyelesaikannya.",
  ),
  DISCLOSED_CRIMINAL_RECORD_REVIEW: text(
    "You flagged a criminal record concern in your disclosures, and a person needs to review the details before any path can be confirmed.",
    "Anda menandai adanya masalah catatan kriminal dalam pengungkapan Anda, dan memerlukan peninjauan detail oleh seseorang sebelum jalur apa pun dapat dikonfirmasi.",
  ),
  DISCLOSED_DIPLOMATIC_PASSPORT_REVIEW: text(
    "You flagged holding a diplomatic passport in your disclosures, and a person needs to review the details before any path can be confirmed.",
    "Anda menandai kepemilikan paspor diplomatik dalam pengungkapan Anda, dan memerlukan peninjauan detail oleh seseorang sebelum jalur apa pun dapat dikonfirmasi.",
  ),
  DISCLOSED_HEALTH_CONCERN_REVIEW: text(
    "You flagged a health concern in your disclosures, and a person needs to review the details before any path can be confirmed.",
    "Anda menandai adanya masalah kesehatan dalam pengungkapan Anda, dan memerlukan peninjauan detail oleh seseorang sebelum jalur apa pun dapat dikonfirmasi.",
  ),
  // fact-mapper.ts: raised when trip_scope === "multiple".
  DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW: text(
    "You said your trip serves more than one purpose, and a person needs to review how those purposes combine before a path can be confirmed.",
    "Anda menyatakan bahwa perjalanan Anda memiliki lebih dari satu tujuan, dan memerlukan peninjauan oleh seseorang mengenai bagaimana tujuan-tujuan tersebut digabungkan sebelum jalur dapat dipastikan.",
  ),
  DISCLOSED_PEP_OR_SANCTIONS_REVIEW: text(
    "You flagged a politically-exposed-person or sanctions-list concern in your disclosures, and a person needs to review the details before any path can be confirmed.",
    "Anda menandai adanya masalah terkait status politically exposed person atau daftar sanksi dalam pengungkapan Anda, dan memerlukan peninjauan detail oleh seseorang sebelum jalur apa pun dapat dikonfirmasi.",
  ),
  DISCLOSED_PRIOR_VISA_REFUSAL_REVIEW: text(
    "You flagged a prior visa refusal in your disclosures, and a person needs to review the details before any path can be confirmed.",
    "Anda menandai adanya penolakan visa sebelumnya dalam pengungkapan Anda, dan memerlukan peninjauan detail oleh seseorang sebelum jalur apa pun dapat dikonfirmasi.",
  ),
  DISCLOSED_SOURCE_OF_FUNDS_REVIEW: text(
    "You flagged an unclear source of funds in your disclosures, and a person needs to review the details before any path can be confirmed.",
    "Anda menandai sumber dana yang tidak jelas dalam pengungkapan Anda, dan memerlukan peninjauan detail oleh seseorang sebelum jalur apa pun dapat dikonfirmasi.",
  ),
  // fact-mapper.ts: raised when ANY answer across the interview equals
  // "unsure" — the OutcomeReason carries no field for which question. One
  // code, as many potential causes as there are questions; flagged as a
  // split candidate in the PR-O2 report.
  DISCLOSED_UNCERTAINTY_REVIEW: text(
    'One of your answers was marked "unsure," and a person needs to confirm that answer before any path can be confirmed.',
    'Salah satu jawaban Anda ditandai "tidak yakin," dan memerlukan konfirmasi oleh seseorang atas jawaban tersebut sebelum jalur apa pun dapat dikonfirmasi.',
  ),
  // `_apply_minor_privacy_hold` (evaluate_path.py:1033-1094): a categorical
  // privacy-policy hold on ANY known minor, distinct from the pack's own
  // MINOR_WITHOUT_CONFIRMED_GUARDIAN rule (`family.sponsor_confirmed ==
  // false`) — this one fires because the public evaluation contract has no
  // guardian-identity/consent fact at all, so no automated supported
  // outcome can ever be safe for a minor here, regardless of what the pack
  // itself concluded. Resolution is necessarily off-platform (a person
  // reviewing guardian identity/consent directly) since this adapter "may
  // only abstain" by its own docstring.
  MINOR_GUARDIAN_PRIVACY_REVIEW: text(
    "This case involves a minor, and this tool cannot confirm guardian consent on its own — a person needs to review the guardian's identity and consent directly before this case can be resolved.",
    "Kasus ini melibatkan anak di bawah umur, dan alat ini tidak dapat mengonfirmasi persetujuan wali dengan sendirinya — diperlukan peninjauan langsung oleh seseorang atas identitas dan persetujuan wali sebelum kasus ini dapat diselesaikan.",
  ),
  // `_apply_safety_critical_source_hold` (evaluate_path.py:1201-1301): same
  // source-integrity pattern as the DECISIVE_* trio above, but global to
  // every currently active `safety_critical: true` rule rather than only
  // the specific citations a given result relied on. Same D2-bis rule 1
  // caveat as the DECISIVE_* trio: not an applicant-fact code.
  SAFETY_CRITICAL_PRIMARY_SOURCE_NOT_APPLICABLE: text(
    "One of the safety-critical rules used in this evaluation relies on a source that could not be confirmed as valid and currently applicable — verifying that source is what a person must do before this result can stand.",
    "Salah satu aturan safety-critical yang digunakan dalam evaluasi ini bergantung pada sumber yang tidak dapat dikonfirmasi valid dan berlaku saat ini — memverifikasi sumber tersebut adalah yang harus dilakukan oleh seseorang sebelum hasil ini dapat dipastikan.",
  ),
  SAFETY_CRITICAL_SOURCE_FRESHNESS_UNKNOWN: text(
    "One of the safety-critical rules used in this evaluation relies on a source whose currency could not be established automatically — confirming whether that source is still current is what a person must do before this result can stand.",
    "Salah satu aturan safety-critical yang digunakan dalam evaluasi ini bergantung pada sumber yang keberlakuannya belum dapat dipastikan secara otomatis — memastikan apakah sumber tersebut masih berlaku adalah yang harus dilakukan oleh seseorang sebelum hasil ini dapat dipastikan.",
  ),
  SAFETY_CRITICAL_SOURCE_STALE: text(
    "One of the safety-critical rules used in this evaluation relies on a source confirmed out of date — replacing it with a current source is what a person must do before this result can stand.",
    "Salah satu aturan safety-critical yang digunakan dalam evaluasi ini bergantung pada sumber yang telah dipastikan usang — menggantinya dengan sumber yang berlaku saat ini adalah yang harus dilakukan oleh seseorang sebelum hasil ini dapat dipastikan.",
  ),
};

const GENERIC_REVIEW_REASON: LocalizedText = text(
  "Some of your answers need a person's judgment before we can confirm a path.",
  "Beberapa jawaban Anda memerlukan penilaian dari seseorang sebelum kami dapat mengonfirmasi jalur.",
);

// D3-4 (PR-D3, owner ruling SHWEB-20260911): `DISCLOSED_AMBIGUOUS_SPONSOR_
// REVIEW`'s generic copy ("has not been established here") is true for an
// `unsure` answer but would be FALSE for a STEPCHILD applicant who told the
// interview their sponsor holds NO KITAS/KITAP — that fact IS established,
// just not one any seq-20 rule reads. D2-bis forbids reusing an
// "unresolved" sentence for a resolved-negative answer, so this one trigger
// gets its own two variants, selected in `reviewReason` below from the
// interview facts already threaded through `BuildEngineOutcomeOptions`. Not
// the general D3-6 mechanism (deferred, three OTHER parameter-less codes) —
// scoped to this one code and this one question.
const STEPCHILD_SPONSOR_PERMIT_NO_REVIEW: LocalizedText = text(
  "You told us your sponsor does not hold a valid KITAS/KITAP of their own. A sponsor without a stay permit cannot sponsor the Family Reunification Visa — Stepchild (E31D); this does not affect the Multiple-Entry Visa (C1), which stays available on its own terms. A person needs to confirm the E31D sponsorship route separately before it can be resolved.",
  "Anda menyatakan bahwa sponsor Anda tidak memiliki KITAS/KITAP yang sah. Sponsor tanpa izin tinggal sendiri tidak dapat mensponsori Visa Penyatuan Keluarga — Anak Tiri (E31D); hal ini tidak memengaruhi Visa Kunjungan Berkali-kali (C1), yang tetap tersedia dengan syaratnya sendiri. Diperlukan konfirmasi terpisah oleh seseorang atas jalur sponsor E31D sebelum dapat diselesaikan.",
);
const STEPCHILD_SPONSOR_PERMIT_UNSURE_REVIEW: LocalizedText = text(
  "Whether your sponsor holds a valid KITAS/KITAP of their own has not been established — confirming your sponsor's own stay permit is what resolves it before the Family Reunification Visa — Stepchild (E31D) can be confirmed.",
  "Belum dapat dipastikan apakah sponsor Anda memiliki KITAS/KITAP yang sah — konfirmasi izin tinggal sponsor Anda sendiri adalah yang akan menyelesaikannya sebelum Visa Penyatuan Keluarga — Anak Tiri (E31D) dapat dipastikan.",
);

function reviewReason(
  code: string,
  sourceIds: readonly string[],
  trustedIds: ReadonlySet<string>,
  facts?: OracleFacts,
): OutcomeReason {
  const stepchildSponsorPermitAnswer =
    code === "DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW" &&
    facts?.family_relation === "STEPCHILD"
      ? facts.family_stepchild_sponsor_permit_confirmed
      : undefined;
  const message =
    stepchildSponsorPermitAnswer === "no"
      ? STEPCHILD_SPONSOR_PERMIT_NO_REVIEW
      : stepchildSponsorPermitAnswer === "unsure"
        ? STEPCHILD_SPONSOR_PERMIT_UNSURE_REVIEW
        : (REVIEW_REASON_COPY[code] ?? GENERIC_REVIEW_REASON);
  return {
    code,
    message,
    sourceIds: sourceIds.filter((id) => trustedIds.has(id)),
  };
}

function outcomeSource(source: VisaOracleSourceRecord): OutcomeSource | null {
  const url = trustedPrimarySourceUrl(source.canonical_url);
  if (!url) return null;
  return {
    id: source.source_record_id,
    title: source.title,
    publisher: source.publisher,
    url,
    authority: source.authority_type,
    primary: source.is_primary_authority,
    // These two feed a line that reads "Effective X · observed Y" ABOUT THE
    // SOURCE, so they must carry the document's own dates.
    //
    // They used to read `source.applicability.*`, which is not a property of
    // the document at all: the backend writes the decision's evaluation clock
    // into every cited source's applicability block (`_build_sources_dto` in
    // evaluate_path.py sets effective_at/observed_at from `decision.*`, itself
    // `now`). The result on screen was every source claiming it took legal
    // effect at the instant the reader pressed the button — a date that reads
    // as a freshness guarantee while carrying no information about the source.
    //
    // `verified_at` rather than `retrieved_at` for "observed": the only
    // freshness policy the schema can express is MAX_AGE_SINCE_VERIFIED_AT,
    // so this is the date that explains the freshness badge rendered beside
    // it. Narrower than it sounds — `freshness_policy` is optional for packs
    // signed under the older schema, and a source without one is reported
    // UNKNOWN; there the badge has no rule to explain, and `verified_at` is
    // simply the better of two dates rather than the one the policy names.
    effectiveAtIso: source.legal_period_from,
    observedAtIso: source.verified_at,
    freshness: source.freshness.status,
  };
}

function decisiveSource(
  source: VisaOracleSourceRecord | undefined,
  decisionEffectiveAt: string,
  decisionObservedAt: string,
): boolean {
  if (!source) return false;
  const effectiveAt = Date.parse(decisionEffectiveAt);
  const observedAt = Date.parse(decisionObservedAt);
  const legalFrom = Date.parse(source.legal_period_from);
  const legalTo = source.legal_period_to
    ? Date.parse(source.legal_period_to)
    : null;
  const recordedFrom = Date.parse(source.recorded_period_from);
  const retrievedAt = Date.parse(source.retrieved_at);
  const verifiedAt = Date.parse(source.verified_at);
  const applicabilityEffectiveAt = Date.parse(
    source.applicability.effective_at,
  );
  const applicabilityObservedAt = Date.parse(source.applicability.observed_at);
  const freshnessEvaluatedAt = Date.parse(source.freshness.evaluated_at);
  const freshnessVerifiedAt = Date.parse(source.freshness.verified_at);
  return (
    source.is_primary_authority &&
    source.status === "VERIFIED" &&
    source.applicability.status === "APPLICABLE" &&
    source.freshness.status === "CURRENT" &&
    trustedPrimarySourceUrl(source.canonical_url) !== null &&
    legalFrom <= effectiveAt &&
    (legalTo === null || effectiveAt < legalTo) &&
    recordedFrom <= observedAt &&
    retrievedAt <= verifiedAt &&
    verifiedAt <= observedAt &&
    applicabilityObservedAt <= observedAt &&
    freshnessEvaluatedAt <= observedAt &&
    freshnessVerifiedAt <= observedAt &&
    applicabilityEffectiveAt === effectiveAt &&
    applicabilityObservedAt === observedAt &&
    freshnessEvaluatedAt === observedAt &&
    freshnessVerifiedAt === verifiedAt
  );
}

function reviewHoldSource(source: VisaOracleSourceRecord | undefined): boolean {
  return (
    source !== undefined &&
    source.is_primary_authority &&
    trustedPrimarySourceUrl(source.canonical_url) !== null
  );
}

function operationalStatus(
  status: "AVAILABLE" | "UNAVAILABLE" | "UNKNOWN",
): OperationalAvailabilityStatus {
  if (status === "AVAILABLE") return "AVAILABLE";
  if (status === "UNAVAILABLE") return "TEMPORARILY_UNAVAILABLE";
  return "UNKNOWN";
}

function serviceStatus(
  status: "AVAILABLE" | "UNAVAILABLE" | "UNKNOWN",
): ServiceAvailabilityStatus {
  if (status === "AVAILABLE") return "AVAILABLE";
  if (status === "UNAVAILABLE") return "NOT_OFFERED";
  return "UNKNOWN";
}

function timeline(candidate: VisaOracleCandidateDisplay): OutcomeTimeline {
  const value = candidate.processing_timeline;
  if (
    value.status === "AVAILABLE" &&
    value.anchor_date &&
    value.estimated_completion_from &&
    value.estimated_completion_to
  ) {
    return {
      status: "AVAILABLE",
      basisDateIso: value.anchor_date,
      earliestDateIso: value.estimated_completion_from,
      latestDateIso: value.estimated_completion_to,
      note: reasonMessage(value.reason_code),
    };
  }
  return {
    status: "UNAVAILABLE",
    message: text(
      "A verified operational processing timeline is not available.",
      "Timeline proses operasional terverifikasi belum tersedia.",
    ),
  };
}

function documents(candidate: VisaOracleCandidateDisplay): OutcomeDocument[] {
  if (candidate.documentation.status !== "AVAILABLE") return [];
  const result: OutcomeDocument[] = [];
  const seen = new Set<string>();
  for (const [kind, items] of [
    ["requirement", candidate.documentation.requirements],
    ["checklist", candidate.documentation.checklist],
  ] as const) {
    for (const [index, label] of items.entries()) {
      const dedupe = `${label.en}\u0000${label.id}`;
      if (seen.has(dedupe)) continue;
      seen.add(dedupe);
      result.push({
        id: `${candidate.product_version_id}:${kind}:${index}`,
        label,
        status: "REQUIRED",
        sourceIds: [],
      });
    }
  }
  return result;
}

function price(
  candidate: VisaOracleCandidateDisplay,
  response: VisaOracleEvaluateResponse,
): OutcomePrice {
  const quote = response.decision.quotes.find(
    (item) => item.product_version_id === candidate.product_version_id,
  );
  if (
    candidate.pricing.status === "AVAILABLE" &&
    quote?.status === "AVAILABLE" &&
    quote.amount !== null
  ) {
    return {
      status: "AVAILABLE",
      currency: "IDR",
      amount: quote.amount,
      allInclusive: true,
      quotedAtIso: quote.quoted_at,
      ...(quote.valid_until ? { validUntilIso: quote.valid_until } : {}),
    };
  }
  if (candidate.pricing.status === "CONTACT_REQUIRED") {
    return {
      status: "CONTACT_REQUIRED",
      message: text(
        "An all-inclusive verified quote requires contact.",
        "Penawaran all-inclusive terverifikasi memerlukan kontak.",
      ),
    };
  }
  return {
    status: "UNAVAILABLE",
    message: text(
      "No verified all-inclusive price is available.",
      "Harga all-inclusive terverifikasi belum tersedia.",
    ),
  };
}

/**
 * The one question that collects `path`, plus whether this interview has
 * already asked it.
 *
 * Two-layer lookup, strictly additive (2026-09-06). Layer 1 is the
 * pre-existing rule verbatim: exactly one question IN THIS INTERVIEW'S
 * HISTORY collects the fact → reopen it (`followUp: false`); more than one
 * → ambiguous, fall back to the human handoff. Layer 2 only runs when
 * history holds NONE of them: if the whole registry has exactly one
 * question for the fact AND this interview's answers satisfy that
 * question's prerequisites, the interview can simply ASK it
 * (`followUp: true`) instead of rendering a row the user cannot act on.
 * Three fact paths are collected by two questions each
 * (`immigration.current_status_code`, `work.indonesia_source_compensation`,
 * `investment.pt_pma_committed`) and are therefore never followed up —
 * guessing which branch's question to splice in would be exactly the kind
 * of inference this adapter is forbidden to make.
 *
 * The prerequisite conjunct is the narrowing the adversarial review of
 * 2026-09-06 (finding 1) imposed: a question whose branch condition the
 * applicant's own answers contradict is never appended, because asking it
 * would bypass the tree's ordering. Such a fact keeps the handoff row.
 * `facts` absent is treated as prerequisites unmet — fail-closed, so a
 * caller that forgets to pass the interview state gets the pre-existing
 * behaviour rather than an unguarded push.
 */
function questionForFact(
  path: string,
  editableQuestionIds: readonly string[] = [],
  facts?: OracleFacts,
): { questionId: string; followUp: boolean } | undefined {
  const collecting = Object.values(QUESTIONS).filter(
    (question) =>
      question.decisionMapping.kind !== "HUMAN_CONTEXT" &&
      question.decisionMapping.factPaths.includes(path),
  );
  const asked = collecting.filter((question) =>
    editableQuestionIds.includes(question.id),
  );
  if (asked.length === 1) {
    return { questionId: asked[0].id, followUp: false };
  }
  if (asked.length > 1) return undefined;
  if (collecting.length !== 1) return undefined;
  if (!facts) return undefined;
  return followUpPrerequisitesMet(collecting[0].id, facts)
    ? { questionId: collecting[0].id, followUp: true }
    : undefined;
}

function nonEmpty<T>(values: T[]): [T, ...T[]] {
  if (values.length === 0) {
    throw new VisaOracleResponseError("RESPONSE_INVARIANT");
  }
  return values as unknown as [T, ...T[]];
}

export interface BuildEngineOutcomeOptions {
  assumptions?: readonly InterviewAssumption[];
  facts?: OracleFacts;
  interviewBranchesRemaining?: number;
  /** Question nodes in the current, pruning-aware interview history. */
  editableQuestionIds?: readonly string[];
}

/**
 * Translate one already-validated authoritative response. Candidate order and
 * membership are copied verbatim; this adapter contains no ranking or rules.
 */
function buildValidatedOutcome(
  response: VisaOracleEvaluateResponse,
  options: BuildEngineOutcomeOptions = {},
): OutcomeViewModel {
  const sourcesById = new Map(
    response.sources.map((source) => [source.source_record_id, source]),
  );
  const sources = response.sources
    .map(outcomeSource)
    .filter((source): source is OutcomeSource => source !== null);
  const trustedIds = new Set(sources.map((source) => source.id));

  const requireDecisiveRefs = (sourceIds: readonly string[]) => {
    if (
      sourceIds.length === 0 ||
      sourceIds.some(
        (id) =>
          !decisiveSource(
            sourcesById.get(id),
            response.decision.effective_at,
            response.decision.observed_at,
          ),
      )
    ) {
      throw new VisaOracleResponseError("RESPONSE_INVARIANT");
    }
  };
  const requireReviewHoldRefs = (sourceIds: readonly string[]) => {
    if (sourceIds.some((id) => !reviewHoldSource(sourcesById.get(id)))) {
      throw new VisaOracleResponseError("RESPONSE_INVARIANT");
    }
  };

  const assessment = {
    ...(response.decision.public_id &&
    PUBLIC_ID.test(response.decision.public_id)
      ? { publicId: response.decision.public_id }
      : {}),
    effectiveAtIso: response.decision.effective_at,
    observedAtIso: response.decision.observed_at,
    evaluatedAtIso: response.decision.evaluated_at,
    ...(response.decision.rule_pack
      ? {
          ruleset: {
            id: response.decision.rule_pack.rule_pack_id,
            version: response.decision.rule_pack.version,
            sequence: response.decision.rule_pack.sequence,
          },
        }
      : {}),
  };
  const base = {
    provenance: "ENGINE" as const,
    assessment,
    assumptions: options.assumptions ?? [],
    sources,
    nextSteps: NEXT_STEPS,
  };

  switch (response.decision.state) {
    case "SUPPORTED_CANDIDATES": {
      const candidates = response.display.candidates.map((projected, index) => {
        const decisionCandidate = response.decision.candidates[index];
        requireDecisiveRefs(decisionCandidate.source_refs);
        const operational = projected.availability.operational_availability;
        const service = projected.availability.bali_zero_service_availability;
        if (operational.status !== "UNKNOWN") {
          requireDecisiveRefs(operational.source_refs);
        }
        if (service.status !== "UNKNOWN") {
          requireDecisiveRefs(service.source_refs);
        }
        return {
          id: projected.product_version_id,
          code: projected.product_code,
          rank: projected.rank,
          name: projected.name,
          ...(projected.tagline ? { tagline: projected.tagline } : {}),
          legal: {
            status: "SUPPORTED" as const,
            reasons: decisionCandidate.reason_codes.map((code) =>
              reason(code, decisionCandidate.source_refs, trustedIds),
            ),
          },
          operational: {
            status: operationalStatus(operational.status),
            reasons: [
              reason(
                operational.reason_code,
                operational.source_refs,
                trustedIds,
              ),
            ],
          },
          service: {
            status: serviceStatus(service.status),
            reasons: [
              reason(service.reason_code, service.source_refs, trustedIds),
            ],
          },
          decisionReasons: decisionCandidate.reason_codes.map((code) =>
            reason(code, decisionCandidate.source_refs, trustedIds),
          ),
          timeline: timeline(projected),
          price: price(projected, response),
          documents: documents(projected),
        } satisfies OutcomeCandidate;
      });
      if (candidates.length === 0) {
        throw new VisaOracleResponseError("RESPONSE_INVARIANT");
      }
      return {
        ...base,
        state: "SUPPORTED_CANDIDATES",
        pathsRemaining: candidates.length,
        candidates: nonEmpty(candidates),
      };
    }
    case "NEEDS_INPUT":
      return {
        ...base,
        state: "NEEDS_INPUT",
        candidates: [],
        pathsRemaining: Math.max(1, options.interviewBranchesRemaining ?? 1),
        missingInputs: nonEmpty(
          response.decision.missing_facts.map((path) => {
            const match = questionForFact(
              path,
              options.editableQuestionIds,
              options.facts,
            );
            const question = match ? QUESTIONS[match.questionId] : undefined;
            return {
              code: path,
              message: question
                ? text(
                    translate("en", question.i18nKey as I18nKey),
                    translate("id", question.i18nKey as I18nKey),
                  )
                : text(
                    "Bali Zero can help clarify an additional detail needed for this assessment.",
                    "Bali Zero dapat membantu memperjelas detail tambahan yang diperlukan untuk penilaian ini.",
                  ),
              sourceIds: [],
              ...(match ? { questionId: match.questionId } : {}),
              ...(match?.followUp ? { followUp: true as const } : {}),
            };
          }),
        ),
      };
    case "HUMAN_REVIEW_REQUIRED":
      return {
        ...base,
        state: "HUMAN_REVIEW_REQUIRED",
        candidates: [],
        pathsRemaining: Math.max(1, options.interviewBranchesRemaining ?? 1),
        reviewReasons: response.decision.review_reasons.map((item) => {
          requireReviewHoldRefs(item.source_refs);
          return reviewReason(
            item.code,
            item.source_refs,
            trustedIds,
            options.facts,
          );
        }) as [OutcomeReason, ...OutcomeReason[]],
      };
    case "NO_SUPPORTED_PATH":
      return {
        ...base,
        state: "NO_SUPPORTED_PATH",
        candidates: [],
        pathsRemaining: 0,
        noPathReasons: response.decision.no_path_reasons.map((item) => {
          requireDecisiveRefs(item.source_refs);
          return reason(item.code, item.source_refs, trustedIds);
        }) as [OutcomeReason, ...OutcomeReason[]],
        alternatives: [],
      };
    case "TEMPORARILY_UNAVAILABLE":
      return {
        ...base,
        state: "TEMPORARILY_UNAVAILABLE",
        candidates: [],
        pathsRemaining: 0,
        outage: {
          code: response.decision.outage?.code ?? "ENGINE_UNAVAILABLE",
          message: text(
            "The verified decision service is temporarily unavailable. No visa path is shown.",
            "Layanan keputusan terverifikasi sementara tidak tersedia. Tidak ada jalur visa yang ditampilkan.",
          ),
          retryable: response.decision.outage?.retryable ?? false,
        },
      };
  }
}

/** Public rendering boundary: CURATED can never become visible authority. */
export function buildEngineOutcome(
  input: VisaOracleEvaluateResponse,
  options: BuildEngineOutcomeOptions = {},
): OutcomeViewModel {
  return buildValidatedOutcome(requireEngineResponse(input), options);
}

/**
 * Shadow-only semantic adapter. The evaluation client has already applied
 * the runtime response guard; this entrypoint accepts either response mode
 * solely for parity comparison and must never feed a render path.
 */
export function buildShadowComparisonOutcome(
  input: VisaOracleEvaluateResponse,
  options: BuildEngineOutcomeOptions = {},
): OutcomeViewModel {
  if (input.mode !== "ENGINE" && input.mode !== "CURATED") {
    throw new VisaOracleResponseError("MALFORMED_RESPONSE");
  }
  return buildValidatedOutcome(input, options);
}

/**
 * INTERNAL PIN-GATED PREVIEW — a deliberately separate rendering boundary
 * from `buildEngineOutcome`, which stays the public one ("CURATED can never
 * become visible authority").
 *
 * Callers MUST have proven server-side PIN possession first (the `vo_internal`
 * httpOnly cookie, set only by `/api/visa-oracle-unlock` after a timing-safe
 * comparison). It exists so the Bali Zero team can exercise the real engine
 * while `VISA_ENGINE_EVALUATE_MODE` is still SHADOW: the backend already
 * computes and returns the full decision in that mode (`evaluate_path.py`
 * fills `decision`/`sources`/`display` unconditionally and only varies the
 * `mode` string), so nothing here reaches past what the response already
 * carries — no backend change, and NO durable ENFORCE write, which keys off
 * the global `engine_mode`, never off this string.
 *
 * A CURATED response rendered through here is comparison-grade, NOT
 * authoritative: the caller is responsible for labelling it as an internal
 * preview in the UI. Never call this for anonymous public traffic.
 */
export function buildInternalPreviewOutcome(
  input: VisaOracleEvaluateResponse,
  options: BuildEngineOutcomeOptions = {},
): OutcomeViewModel {
  if (input.mode !== "ENGINE" && input.mode !== "CURATED") {
    throw new VisaOracleResponseError("MALFORMED_RESPONSE");
  }
  return buildValidatedOutcome(input, options);
}
