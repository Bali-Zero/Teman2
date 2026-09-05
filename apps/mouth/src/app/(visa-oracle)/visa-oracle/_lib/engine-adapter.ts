import {
  requireEngineResponse,
  VisaOracleResponseError,
} from "./engine-response";
import { QUESTIONS, type OracleFacts } from "./tree";
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
  REQUIRED_RPTKA_APPROVAL: text(
    "Your employer must obtain RPTKA approval before this permit can be issued.",
    "Pemberi kerja Anda harus memperoleh persetujuan RPTKA sebelum izin ini dapat diterbitkan.",
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
  D12_CUMULATIVE_STAY_ADVISOR_CHECK: text(
    "Long or repeated stays are counted cumulatively. We check your total against the limit with one of our advisors.",
    "Masa tinggal panjang atau berulang dihitung secara kumulatif. Kami memeriksa total Anda terhadap batasnya bersama konsultan kami.",
  ),
  BRIDGING_T3_WINDOW_ADVISOR_CHECK: text(
    "The filing window for this bridging route is tight. We check your dates with one of our advisors.",
    "Jendela pengajuan jalur peralihan ini sempit. Kami memeriksa tanggal Anda bersama konsultan kami.",
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
  CALLING_VISA_REVIEW: text(
    "Your nationality is on the Calling Visa list, which always requires manual review before a visa can be confirmed.",
    "Kewarganegaraan Anda termasuk dalam daftar Calling Visa, yang selalu memerlukan peninjauan manual sebelum visa dapat dikonfirmasi.",
  ),
  ACTIVE_OVERSTAY: text(
    "An active overstay on record needs a person to review before any path can be confirmed.",
    "Overstay aktif yang tercatat memerlukan peninjauan oleh seseorang sebelum jalur apa pun dapat dikonfirmasi.",
  ),
  // Renamed from CITIZENSHIP_EVIDENCE_CONFLICT (QW-4a, 2026-08-17): that key
  // named no code in any pack from seq-6 onward. CITIZENSHIP_LIST_DIVERGENCE
  // is its current name (services/visa_engine/contracts/packs/
  // rulepack-prod-007.source.json). Copy text unchanged — only the key moved.
  CITIZENSHIP_LIST_DIVERGENCE: text(
    "Your answers about citizenship do not fully agree with each other and need a person to confirm.",
    "Jawaban Anda tentang kewarganegaraan tidak sepenuhnya cocok satu sama lain dan memerlukan konfirmasi dari seseorang.",
  ),
  MINOR_WITHOUT_CONFIRMED_GUARDIAN: text(
    "This case involves a minor without a confirmed guardian on file and needs a person to review it.",
    "Kasus ini melibatkan anak di bawah umur tanpa wali yang terkonfirmasi dan memerlukan peninjauan oleh seseorang.",
  ),
  // Wording follows the pack's own product names verbatim — "Foreign Diplomat
  // House Assistant (E23U)" / "Asisten Rumah Tangga Diplomat Asing" and "Trade
  // and Economic Office (E23V)" / "Kantor Dagang dan Ekonomi". An adversarial
  // review of the first draft caught it narrowing E23V to "trade representative
  // office", dropping "and Economic": the applicant would then be told about a
  // category that is not the one the rule actually names.
  E23U_DIPLOMATIC_HOUSEHOLD_STAFF_REVIEW: text(
    "This case involves a house assistant employed by a foreign diplomat and needs a person to review it.",
    "Kasus ini melibatkan asisten rumah tangga yang dipekerjakan oleh diplomat asing dan memerlukan peninjauan oleh seseorang.",
  ),
  E23V_TRADE_OFFICE_STAFF_REVIEW: text(
    "This case involves staff of a trade and economic office and needs a person to review it.",
    "Kasus ini melibatkan staf kantor dagang dan ekonomi dan memerlukan peninjauan oleh seseorang.",
  ),
  // Renamed from STATUS_BRIDGING_REVIEW (QW-4a, 2026-08-17): same stale
  // situation — BRIDGING_ADVERSE_HISTORY is the current name for this rule
  // in rulepack-prod-007+. Copy text unchanged.
  BRIDGING_ADVERSE_HISTORY: text(
    "Bridging between immigration statuses needs a person to check the timing and conditions involved.",
    "Peralihan antar status keimigrasian memerlukan pemeriksaan oleh seseorang atas waktu dan ketentuan yang berlaku.",
  ),
  LOCAL_MARKET_ACTIVITY_REVIEW: text(
    "The activity you described needs a person to confirm it does not cross into locally reserved business.",
    "Aktivitas yang Anda jelaskan memerlukan konfirmasi oleh seseorang agar tidak melanggar bidang usaha yang dicadangkan untuk lokal.",
  ),
  DISCLOSED_ACTIVITY_BOUNDARY_REVIEW: text(
    "The activity you disclosed sits close to a legal boundary that needs a person to confirm.",
    "Aktivitas yang Anda ungkapkan berada dekat batas hukum yang memerlukan konfirmasi dari seseorang.",
  ),
};

const GENERIC_REVIEW_REASON: LocalizedText = text(
  "Some of your answers need a person's judgment before we can confirm a path.",
  "Beberapa jawaban Anda memerlukan penilaian dari seseorang sebelum kami dapat mengonfirmasi jalur.",
);

function reviewReason(
  code: string,
  sourceIds: readonly string[],
  trustedIds: ReadonlySet<string>,
): OutcomeReason {
  return {
    code,
    message: REVIEW_REASON_COPY[code] ?? GENERIC_REVIEW_REASON,
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

function questionForFact(
  path: string,
  editableQuestionIds: readonly string[] = [],
): string | undefined {
  const matches = Object.values(QUESTIONS).filter(
    (question) =>
      editableQuestionIds.includes(question.id) &&
      question.decisionMapping.kind !== "HUMAN_CONTEXT" &&
      question.decisionMapping.factPaths.includes(path),
  );
  // Several branches can collect the same fact. Only offer an Edit that
  // identifies one question in this interview's current history.
  return matches.length === 1 ? matches[0].id : undefined;
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
            const questionId = questionForFact(
              path,
              options.editableQuestionIds,
            );
            const question = questionId ? QUESTIONS[questionId] : undefined;
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
              ...(questionId ? { questionId } : {}),
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
          return reviewReason(item.code, item.source_refs, trustedIds);
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
