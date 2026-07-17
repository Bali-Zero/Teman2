/**
 * Visa Oracle v2 — mock interview tree (Track C PR C1, foundation only)
 *
 * MOCK DATA ONLY, per docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md
 * §4 "The interview". Every function here is PURE (no I/O, no wall-clock
 * dependency except where explicitly noted in `answer()`) — this models
 * question routing and mock outcomes; the real deterministic engine
 * (`visa_engine`) is not wired. Copy quality is prototype-grade (EN
 * authoritative; ID is plausible placeholder pending an NB-INTEL grounding
 * pass — see design doc §4's ⚑ note).
 *
 * Scope of this file: Q0 (in-Indonesia branch + date-driven lane routing),
 * the 10 top-level categories (soft router, design doc §4), and ONE
 * simplified behavioral tree for 'remote-worker' (3 mock questions). Every
 * other category resolves to an honest HUMAN_REVIEW_REQUIRED placeholder —
 * their full behavioral trees are PR C2+ (design doc §10.4, "lane-by-lane
 * during build").
 */

import type {
  Assumption,
  I18nText,
  InterviewQuestion,
  InterviewState,
  Lane,
  MockOutcome,
  QuestionOption,
} from "./types";

// ────────────────────────────────────────────────────────────────────────
// Q0 — the master branch (design doc §4)
// ────────────────────────────────────────────────────────────────────────

export const Q0_IN_INDONESIA: InterviewQuestion = {
  id: "q0-in-indonesia",
  categoryId: "q0",
  kind: "single",
  prompt: {
    en: "Are you in Indonesia right now?",
    id: "Apakah Anda sedang berada di Indonesia sekarang?",
  },
  whyWeAsk: {
    en: "Onshore and offshore paths diverge immediately — offshore a visa is a plan, onshore it's a countdown, and the catalog itself narrows to what's convertible.",
    id: "Jalur onshore dan offshore langsung berbeda — di luar negeri visa adalah rencana, di dalam negeri adalah hitung mundur, dan katalog itu sendiri menyempit ke apa yang dapat dikonversi.",
    regulationRef: "Permenkumham 11/2024 (Bridging Visa)",
  },
  options: [
    { key: "yes", label: { en: "Yes, I'm here", id: "Ya, saya di sini" } },
    {
      key: "no",
      label: {
        en: "No, I'm planning ahead",
        id: "Belum, saya sedang merencanakan",
      },
    },
  ],
  // Deliberately no skipAssumption: this is a factual "where are you"
  // question, not one where a conservative default is meaningful. The
  // three escape valves (dual citizen / just left / visa run) are deferred
  // to a later PR per the task's foundation-only scope.
};

export const Q0_EXPIRY_DATE: InterviewQuestion = {
  id: "q0-expiry-date",
  categoryId: "q0",
  kind: "date",
  prompt: {
    en: "When does your current stay permit expire?",
    id: "Kapan izin tinggal Anda saat ini berakhir?",
  },
  hint: {
    en: "Check the date stamped in your passport or ITAS/ITAP card.",
    id: "Periksa tanggal yang tertera di paspor atau kartu ITAS/ITAP Anda.",
  },
  whyWeAsk: {
    en: "Days remaining decide which lane applies — a Bridging Visa must be filed at least 3 days before expiry.",
    id: "Sisa hari menentukan jalur yang berlaku — Visa Bridging harus diajukan setidaknya 3 hari sebelum berakhir.",
    regulationRef: "Permenkumham 11/2024",
  },
  options: [],
  skipAssumption: {
    key: "unknown",
    label: {
      en: "I don't know my exact expiry date",
      id: "Saya tidak tahu tanggal pasti berakhirnya",
    },
  },
};

// ────────────────────────────────────────────────────────────────────────
// Q1 — ten categories, category-first, equal weight (design doc §4)
// ────────────────────────────────────────────────────────────────────────

export const CATEGORIES: QuestionOption[] = [
  {
    key: "tourism-short-visit",
    label: { en: "Tourism & short visit", id: "Wisata & kunjungan singkat" },
  },
  {
    key: "business-no-work",
    label: { en: "Business (no work)", id: "Bisnis (tanpa bekerja)" },
  },
  {
    key: "work-employment",
    label: { en: "Work & employment", id: "Kerja & ketenagakerjaan" },
  },
  {
    key: "invest-golden",
    label: { en: "Invest & golden", id: "Investasi & golden visa" },
  },
  {
    key: "remote-worker",
    label: { en: "Remote worker", id: "Pekerja jarak jauh" },
  },
  {
    key: "family-marriage",
    label: { en: "Family & marriage", id: "Keluarga & pernikahan" },
  },
  {
    key: "retirement-second-home",
    label: { en: "Retirement & second home", id: "Pensiun & rumah kedua" },
  },
  { key: "study", label: { en: "Study", id: "Studi" } },
  {
    key: "diaspora-ex-wni",
    label: { en: "Diaspora & ex-WNI", id: "Diaspora & eks-WNI" },
  },
  {
    // Mandatory, same tile weight (GOV.UK's "never dead-end" at the top
    // of the funnel, design doc §4).
    key: "something-else",
    label: { en: "Something else", id: "Lainnya" },
  },
];

export const Q1_CATEGORY: InterviewQuestion = {
  id: "q1-category",
  categoryId: "q1",
  kind: "category",
  prompt: {
    en: "What best describes why you're coming to (or staying in) Indonesia?",
    id: "Apa yang paling menggambarkan alasan Anda datang ke (atau tinggal di) Indonesia?",
  },
  whyWeAsk: {
    en: "Category is a soft router — it narrows the catalog but never rules out a path until the detailed questions confirm.",
    id: "Kategori adalah penyaring lunak — ini mempersempit katalog tetapi tidak pernah menutup jalur sampai pertanyaan rinci mengonfirmasi.",
    regulationRef: "Kepmen M.IP-08.GR.01.01/2025",
  },
  options: CATEGORIES,
  // No skipAssumption — "Something else" IS the equal-weight escape valve.
};

// ────────────────────────────────────────────────────────────────────────
// Remote worker — the one simplified behavioral tree in this PR
// (design doc §4 "Remote worker (5q modal)", simplified to 3 mock
// questions per the task's foundation-only scope)
// ────────────────────────────────────────────────────────────────────────

export const RW_WHO_PAYS: InterviewQuestion = {
  id: "rw-who-pays",
  categoryId: "remote-worker",
  kind: "single",
  prompt: { en: "Who pays you?", id: "Siapa yang membayar Anda?" },
  whyWeAsk: {
    en: "Foreign clients paying you from abroad is a different lane than being employed and paid by an Indonesian-registered company.",
    id: "Klien asing yang membayar Anda dari luar negeri adalah jalur berbeda dari dipekerjakan dan dibayar oleh perusahaan yang terdaftar di Indonesia.",
    regulationRef: "Permen Imipas 10/2026",
  },
  options: [
    {
      key: "foreign-clients",
      label: {
        en: "Foreign clients or employer, paid abroad",
        id: "Klien atau pemberi kerja asing, dibayar dari luar negeri",
      },
    },
    {
      key: "indonesian-clients",
      label: {
        en: "Indonesian clients or employer, paid locally",
        id: "Klien atau pemberi kerja Indonesia, dibayar secara lokal",
      },
    },
    // In-band "not sure" — NOT a skipAssumption. Design doc §4 load-bearing
    // rule: "on 'not sure,' never guess on money, payer, or clients — hold
    // for a human." Answering this key routes straight to
    // HUMAN_REVIEW_REQUIRED in resolveOutcome(), never a conservative guess.
    {
      key: "not-sure",
      label: {
        en: "I don't know / it's complicated",
        id: "Saya tidak tahu / rumit",
      },
    },
  ],
};

export const RW_INCOME_BAND: InterviewQuestion = {
  id: "rw-income-band",
  categoryId: "remote-worker",
  kind: "single",
  prompt: {
    en: "Roughly, what is your annual income band?",
    id: "Kira-kira berapa kisaran penghasilan tahunan Anda?",
  },
  whyWeAsk: {
    en: "Remote-worker products carry an income floor; falling below it doesn't kill the path — it's disclosed honestly on the outcome.",
    id: "Produk pekerja jarak jauh memiliki batas bawah penghasilan; berada di bawahnya tidak menutup jalur — ini diungkapkan secara jujur pada hasil.",
    regulationRef: "Permen Imipas 10/2026",
  },
  options: [
    {
      key: "above-floor",
      label: { en: "Above USD 60,000/year", id: "Di atas USD 60.000/tahun" },
    },
    {
      key: "below-floor",
      label: { en: "Below USD 60,000/year", id: "Di bawah USD 60.000/tahun" },
    },
    // Same in-band "not sure" doctrine as RW_WHO_PAYS — money is covered by
    // the same load-bearing "hold for a human" rule.
    {
      key: "not-sure",
      label: {
        en: "I don't know / it's complicated",
        id: "Saya tidak tahu / rumit",
      },
    },
  ],
};

export const RW_DURATION: InterviewQuestion = {
  id: "rw-duration",
  categoryId: "remote-worker",
  kind: "single",
  prompt: {
    en: "How long do you plan to stay?",
    id: "Berapa lama Anda berencana tinggal?",
  },
  whyWeAsk: {
    en: "Duration shapes which product tier fits — and, as a courtesy, whether you're approaching Indonesia's 183-day tax-residency threshold. That's not a gate, it's something you deserve to know before you choose.",
    id: "Durasi memengaruhi tingkat produk yang cocok — dan, sebagai kebaikan, apakah Anda mendekati ambang residensi pajak 183 hari di Indonesia. Ini bukan penghalang, ini sesuatu yang layak Anda ketahui sebelum memilih.",
    regulationRef: "UU PPh Pasal 2 ayat (4) — ambang 183 hari",
  },
  options: [
    {
      key: "short-term",
      label: { en: "Under 6 months", id: "Kurang dari 6 bulan" },
    },
    {
      key: "long-term",
      label: { en: "6 months or more", id: "6 bulan atau lebih" },
    },
  ],
  // Duration is NOT money/payer/clients — the §4 load-bearing rule doesn't
  // apply, so a normal conservative skip-with-assumption is honest here.
  skipAssumption: {
    key: "short-term",
    label: {
      en: "Not sure — assume under 6 months (conservative)",
      id: "Tidak yakin — asumsikan kurang dari 6 bulan (konservatif)",
    },
  },
};

export const QUESTIONS_BY_ID: Record<string, InterviewQuestion> = {
  [Q0_IN_INDONESIA.id]: Q0_IN_INDONESIA,
  [Q0_EXPIRY_DATE.id]: Q0_EXPIRY_DATE,
  [Q1_CATEGORY.id]: Q1_CATEGORY,
  [RW_WHO_PAYS.id]: RW_WHO_PAYS,
  [RW_INCOME_BAND.id]: RW_INCOME_BAND,
  [RW_DURATION.id]: RW_DURATION,
};

// ────────────────────────────────────────────────────────────────────────
// Lane copy (design doc §4 "Handoff-screen principles" + the table)
// ────────────────────────────────────────────────────────────────────────

export type LaneTone = "urgent" | "amber" | "neutral";

export const LANE_COPY: Record<Lane, { tone: LaneTone; text: I18nText }> = {
  "overstay-help": {
    // "Reassuring, straight to human review, no alarm copy" (design doc §4
    // table) — deliberately NOT the urgent tone.
    tone: "neutral",
    text: {
      en: "Overstay is fixable. It is not the end of your story here.",
      id: "Overstay bisa diselesaikan. Ini bukan akhir dari cerita Anda di sini.",
    },
  },
  "urgent-review": {
    tone: "urgent",
    text: {
      en: "Your window is very tight — this goes straight to a human, not an algorithm.",
      id: "Waktu Anda sangat sempit — ini langsung ditangani oleh manusia, bukan algoritma.",
    },
  },
  "bridging-urgent": {
    tone: "amber",
    text: {
      en: "You're inside the Bridging Visa filing window — it must be filed at least 3 days before expiry.",
      id: "Anda berada dalam jendela pengajuan Visa Bridging — harus diajukan setidaknya 3 hari sebelum berakhir.",
    },
  },
  "extend-convert": {
    tone: "neutral",
    text: {
      en: "You have room to extend or convert your stay — let's find the right path.",
      id: "Anda punya waktu untuk memperpanjang atau mengonversi izin tinggal — mari temukan jalur yang tepat.",
    },
  },
  plan: {
    tone: "neutral",
    text: {
      en: "Plenty of runway — this is planning, not a countdown.",
      id: "Waktu masih banyak — ini perencanaan, bukan hitung mundur.",
    },
  },
};

// ────────────────────────────────────────────────────────────────────────
// Pure interview functions
// ────────────────────────────────────────────────────────────────────────

/** Fresh interview state, Q0 first. */
export function createInterview(): InterviewState {
  return {
    answers: {},
    assumptions: [],
    currentQuestionId: Q0_IN_INDONESIA.id,
  };
}

function isIsoDate(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function daysBetween(fromISO: string, toISO: string): number {
  const from = Date.parse(`${fromISO}T00:00:00Z`);
  const to = Date.parse(`${toISO}T00:00:00Z`);
  return Math.round((to - from) / (1000 * 60 * 60 * 24));
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Q0 date → lane routing (design doc §4 table). Boundaries are inclusive
 * on the lower bound of each band: 1-2 urgent, 3-7 bridging, 8-60
 * extend-convert, 61+ plan. `daysRemaining <= 0` is "already expired".
 */
export function computeLane(daysRemaining: number): Lane {
  if (daysRemaining <= 0) return "overstay-help";
  if (daysRemaining <= 2) return "urgent-review";
  if (daysRemaining <= 7) return "bridging-urgent";
  if (daysRemaining <= 60) return "extend-convert";
  return "plan";
}

/**
 * Next unanswered question, or `null` once the interview reaches a
 * terminal state for this PR's scope (any category other than
 * 'remote-worker' is terminal — its full behavioral tree is a later PR).
 */
export function nextQuestion(state: InterviewState): InterviewQuestion | null {
  if (!(Q0_IN_INDONESIA.id in state.answers)) return Q0_IN_INDONESIA;

  if (
    state.answers[Q0_IN_INDONESIA.id] === "yes" &&
    !(Q0_EXPIRY_DATE.id in state.answers)
  ) {
    return Q0_EXPIRY_DATE;
  }

  if (!(Q1_CATEGORY.id in state.answers)) return Q1_CATEGORY;

  if (state.answers[Q1_CATEGORY.id] !== "remote-worker") {
    return null;
  }

  if (!(RW_WHO_PAYS.id in state.answers)) return RW_WHO_PAYS;
  if (!(RW_INCOME_BAND.id in state.answers)) return RW_INCOME_BAND;
  if (!(RW_DURATION.id in state.answers)) return RW_DURATION;

  return null;
}

/**
 * Records an answer. Never mutates `state` — returns a new InterviewState.
 * When answering the expiry-date question, also derives `lane` (wall-clock
 * dependent by necessity; `computeLane()` itself stays pure and is what
 * the test suite exercises directly for boundary behavior). A non-ISO key
 * (e.g. the date question's "unknown" skip sentinel) resolves to the most
 * conservative lane, `urgent-review`, rather than throwing.
 */
export function answer(
  state: InterviewState,
  qid: string,
  key: string,
): InterviewState {
  const nextAnswers = { ...state.answers, [qid]: key };
  const nextAssumptions = state.assumptions.filter((a) => a.qid !== qid);

  let lane = state.lane;
  if (qid === Q0_EXPIRY_DATE.id) {
    lane = isIsoDate(key)
      ? computeLane(daysBetween(todayISO(), key))
      : "urgent-review";
  }

  const next: InterviewState = {
    answers: nextAnswers,
    assumptions: nextAssumptions,
    currentQuestionId: null,
    lane,
  };
  next.currentQuestionId = nextQuestion(next)?.id ?? null;
  return next;
}

/**
 * "Not sure?" affordance (design doc §3). Only meaningful on questions
 * that declare `skipAssumption` (date + RW_DURATION in this PR) — a no-op
 * on any other question id, so it is always safe to call.
 */
export function skip(state: InterviewState, qid: string): InterviewState {
  const question = QUESTIONS_BY_ID[qid];
  if (!question?.skipAssumption) {
    return state;
  }
  const assumedKey = question.skipAssumption.key;
  const answered = answer(state, qid, assumedKey);
  const newAssumption: Assumption = { qid, assumedKey };
  return {
    ...answered,
    assumptions: [...answered.assumptions, newAssumption],
  };
}

// ────────────────────────────────────────────────────────────────────────
// Mock candidate-paths table — backs pathsRemaining()
// ────────────────────────────────────────────────────────────────────────

interface MockPathRow {
  categoryId: string;
  payer?: "foreign-clients" | "indonesian-clients";
  incomeBand?: "above-floor" | "below-floor";
}

// 4 synthetic remote-worker paths (payer × income-band) + 1 placeholder
// path per remaining category = 13 total. Each filter in pathsRemaining()
// only INTERSECTS this table, so the count is monotonically non-increasing
// by construction as more answers accumulate.
const MOCK_PATH_TABLE: MockPathRow[] = [
  {
    categoryId: "remote-worker",
    payer: "foreign-clients",
    incomeBand: "above-floor",
  },
  {
    categoryId: "remote-worker",
    payer: "foreign-clients",
    incomeBand: "below-floor",
  },
  {
    categoryId: "remote-worker",
    payer: "indonesian-clients",
    incomeBand: "above-floor",
  },
  {
    categoryId: "remote-worker",
    payer: "indonesian-clients",
    incomeBand: "below-floor",
  },
  { categoryId: "tourism-short-visit" },
  { categoryId: "business-no-work" },
  { categoryId: "work-employment" },
  { categoryId: "invest-golden" },
  { categoryId: "family-marriage" },
  { categoryId: "retirement-second-home" },
  { categoryId: "study" },
  { categoryId: "diaspora-ex-wni" },
  { categoryId: "something-else" },
];

/**
 * "Paths remaining" counter (design doc §3 signature interaction #2:
 * "12 → 3 → 1"). Monotonically non-increasing as answers accumulate —
 * each known answer only narrows (never widens) the mock candidate-paths
 * table above.
 */
export function pathsRemaining(state: InterviewState): number {
  let rows = MOCK_PATH_TABLE;

  const categoryKey = state.answers[Q1_CATEGORY.id];
  if (typeof categoryKey === "string") {
    rows = rows.filter((row) => row.categoryId === categoryKey);
  }

  const payerKey = state.answers[RW_WHO_PAYS.id];
  if (payerKey === "foreign-clients" || payerKey === "indonesian-clients") {
    rows = rows.filter(
      (row) => row.payer === undefined || row.payer === payerKey,
    );
  }

  const incomeKey = state.answers[RW_INCOME_BAND.id];
  if (incomeKey === "above-floor" || incomeKey === "below-floor") {
    rows = rows.filter(
      (row) => row.incomeBand === undefined || row.incomeBand === incomeKey,
    );
  }

  return rows.length;
}

// ────────────────────────────────────────────────────────────────────────
// Mock outcome resolution
// ────────────────────────────────────────────────────────────────────────

/**
 * Resolves a MockOutcome once enough of the interview is answered, or
 * `null` if it's too early to resolve. Every category other than
 * 'remote-worker' resolves to an honest HUMAN_REVIEW_REQUIRED placeholder
 * (their behavioral trees are a later PR, design doc §10.4). Within
 * 'remote-worker', an in-band "not sure" on payer or income forces
 * HUMAN_REVIEW_REQUIRED per the §4 load-bearing "never guess on money,
 * payer, or clients" rule — never a guessed candidate.
 */
export function resolveOutcome(state: InterviewState): MockOutcome | null {
  const categoryKey = state.answers[Q1_CATEGORY.id];
  if (typeof categoryKey !== "string") return null;

  if (categoryKey !== "remote-worker") {
    return { state: "HUMAN_REVIEW_REQUIRED" };
  }

  const payer = state.answers[RW_WHO_PAYS.id];
  const incomeBand = state.answers[RW_INCOME_BAND.id];
  const duration = state.answers[RW_DURATION.id];
  if (
    typeof payer !== "string" ||
    typeof incomeBand !== "string" ||
    typeof duration !== "string"
  ) {
    return null;
  }

  if (payer === "not-sure" || incomeBand === "not-sure") {
    return { state: "HUMAN_REVIEW_REQUIRED" };
  }

  if (payer === "indonesian-clients") {
    // Employed and paid locally is a different lane entirely, not a
    // remote-worker product (design doc §4 splitter).
    return { state: "HUMAN_REVIEW_REQUIRED" };
  }

  const eligibility = incomeBand === "above-floor" ? "eligible" : "conditional";

  return {
    state: "SUPPORTED_CANDIDATES",
    candidates: [
      {
        code: "E33F-MOCK",
        name: {
          en: "Remote Worker Visa (mock)",
          id: "Visa Pekerja Jarak Jauh (mock)",
        },
        eligibility,
        priceAllInclusive: { amountIDR: 12_345_000, mock: true },
      },
    ],
  };
}
