/**
 * Round 2 written assessment — Finance & Client Services Coordinator.
 *
 * Content is the on-screen twin of the printed booklet rendered 2026-08-30
 * (`Bali-Zero-Round2-Assessment-Booklet-EN.pdf`). The figures below were
 * machine-verified before that print: bank closing 133.750.000, cash-book
 * closing 116.385.000, difference 17.365.000, reconciled exactly by the four
 * planted items (MDR 850.000 · cut-off 27.000.000 · double payment 8.750.000 ·
 * bank charge 35.000). Do not "tidy" a number here without re-running that
 * arithmetic — a test whose numbers do not add up punishes the candidate who
 * is good enough to notice.
 *
 * All company names, figures and documents are invented. They describe no
 * Bali Zero client.
 */

export interface Field {
  id: string;
  label: string;
  placeholder?: string;
  /** Single-line input instead of a textarea. */
  short?: boolean;
  /** Minimum characters before the exercise counts as attempted. */
  hint?: string;
}

export interface Exercise {
  key: string;
  letter: string;
  title: string;
  minutes: number;
  /** Language rule shown in the exercise header. */
  language: string;
  intro: string;
  fields: Field[];
}

export interface LedgerRow {
  date: string;
  description: string;
  amount: string;
  balance: string;
}

export const BANK_ROWS: LedgerRow[] = [
  {
    date: "01/07",
    description: "SALDO AWAL",
    amount: "—",
    balance: "96.500.000",
  },
  {
    date: "03/07",
    description: "TRSF E-BANKING CR — AGODA PAYOUT JULI",
    amount: "+38.400.000",
    balance: "134.900.000",
  },
  {
    date: "05/07",
    description: "PAYROLL — GAJI KARYAWAN JULI",
    amount: "−62.300.000",
    balance: "72.600.000",
  },
  {
    date: "07/07",
    description: "PLN / PDAM — UTILITAS",
    amount: "−7.840.000",
    balance: "64.760.000",
  },
  {
    date: "08/07",
    description: "TRSF MASUK — PT SANDALWOOD",
    amount: "+15.000.000",
    balance: "79.760.000",
  },
  {
    date: "10/07",
    description: "TRSF KELUAR — CV BALI SEGAR",
    amount: "−11.250.000",
    balance: "68.510.000",
  },
  {
    date: "12/07",
    description: "SETTLEMENT EDC BCA — PERIODE 01-11/07",
    amount: "+41.650.000",
    balance: "110.160.000",
  },
  {
    date: "14/07",
    description: "TRSF KELUAR — CV TIRTA BERSIH",
    amount: "−8.750.000",
    balance: "101.410.000",
  },
  {
    date: "16/07",
    description: "TRSF KELUAR — CV TIRTA BERSIH",
    amount: "−8.750.000",
    balance: "92.660.000",
  },
  {
    date: "18/07",
    description: "TRSF E-BANKING CR — AIRBNB PAYOUT",
    amount: "+22.150.000",
    balance: "114.810.000",
  },
  {
    date: "20/07",
    description: "TRSF KELUAR — SEWA KANTOR JULI",
    amount: "−15.000.000",
    balance: "99.810.000",
  },
  {
    date: "22/07",
    description: "TRSF KELUAR — KOMISI OTA",
    amount: "−6.100.000",
    balance: "93.710.000",
  },
  {
    date: "25/07",
    description: "TRSF MASUK — BPK. WIJAYA",
    amount: "+18.000.000",
    balance: "111.710.000",
  },
  {
    date: "28/07",
    description: "TRSF KELUAR — BPJS TK + KESEHATAN",
    amount: "−4.925.000",
    balance: "106.785.000",
  },
  {
    date: "31/07",
    description: "TRSF MASUK — K. LINDQVIST",
    amount: "+27.000.000",
    balance: "133.785.000",
  },
  {
    date: "31/07",
    description: "BIAYA ADMINISTRASI",
    amount: "−35.000",
    balance: "133.750.000",
  },
];

export const CASHBOOK_ROWS: LedgerRow[] = [
  {
    date: "01/07",
    description: "Saldo awal",
    amount: "—",
    balance: "96.500.000",
  },
  {
    date: "03/07",
    description: "Agoda payout July",
    amount: "+38.400.000",
    balance: "134.900.000",
  },
  {
    date: "05/07",
    description: "Payroll July",
    amount: "−62.300.000",
    balance: "72.600.000",
  },
  {
    date: "07/07",
    description: "Utilities — PLN / PDAM",
    amount: "−7.840.000",
    balance: "64.760.000",
  },
  {
    date: "08/07",
    description: "Management fee — PT Sandalwood",
    amount: "+15.000.000",
    balance: "79.760.000",
  },
  {
    date: "10/07",
    description: "Food supplier — CV Bali Segar",
    amount: "−11.250.000",
    balance: "68.510.000",
  },
  {
    date: "12/07",
    description: "Card sales settlement (EDC)",
    amount: "+42.500.000",
    balance: "111.010.000",
  },
  {
    date: "14/07",
    description: "Laundry & linen — CV Tirta Bersih",
    amount: "−8.750.000",
    balance: "102.260.000",
  },
  {
    date: "18/07",
    description: "Airbnb payout",
    amount: "+22.150.000",
    balance: "124.410.000",
  },
  {
    date: "20/07",
    description: "Office rent — July",
    amount: "−15.000.000",
    balance: "109.410.000",
  },
  {
    date: "22/07",
    description: "OTA commission",
    amount: "−6.100.000",
    balance: "103.310.000",
  },
  {
    date: "25/07",
    description: "Owner transfer — Bpk. Wijaya",
    amount: "+18.000.000",
    balance: "121.310.000",
  },
  {
    date: "28/07",
    description: "BPJS TK + Kesehatan",
    amount: "−4.925.000",
    balance: "116.385.000",
  },
];

export interface OtherExpenseRow {
  item: string;
  june: string;
  july: string;
}

export const OTHER_EXPENSES: OtherExpenseRow[] = [
  {
    item: "Perizinan — permit extension, agent fee",
    june: "—",
    july: "1.200.000",
  },
  {
    item: "Bank administration & transfer charges",
    june: "340.000",
    july: "385.000",
  },
  { item: "Staff medical reimbursement", june: "—", july: "2.150.000" },
  {
    item: "Repairs — pool pump replacement",
    june: "1.200.000",
    july: "3.500.000",
  },
  { item: "Entertainment / client meals", june: "1.100.000", july: "900.000" },
  {
    item: "Legal translation — notaris document",
    june: "—",
    july: "1.750.000",
  },
  {
    item: "Miscellaneous — no description",
    june: "5.760.000",
    july: "1.875.000",
  },
];

export const EXERCISES: Exercise[] = [
  {
    key: "A",
    letter: "A",
    title: "Reconciliation",
    minutes: 20,
    language: "English or Bahasa Indonesia — your choice.",
    intro:
      "Sunset Villas & Kitchen is a villa management and restaurant operator in Seminyak and a client of ours. Below is its bank statement for July 2026 and the cash book the client's own staff kept for the same month. The two closing balances do not agree.",
    fields: [
      {
        id: "a_differences",
        label:
          "1 — Every difference you find, one per line, with its amount and a one-line cause.",
        placeholder: "1. 850.000 — ...\n2. ...\n3. ...\n4. ...",
        hint: "Cash book 116.385.000 · bank statement 133.750.000.",
      },
      {
        id: "a_reconciliation",
        label:
          "2 — The reconciliation. Start from the cash book balance and finish at the bank balance.",
        placeholder:
          "Cash book balance 31/07          116.385.000\n+ ...\n= Bank balance 31/07             133.750.000",
      },
      {
        id: "a_actions",
        label:
          "3 — Anything that needs doing beyond an accounting entry. If nothing, write none and say why.",
        placeholder: "",
      },
    ],
  },
  {
    key: "B",
    letter: "B",
    title: "Judgement",
    minutes: 15,
    language: "English or Bahasa Indonesia — your choice.",
    intro:
      "Same client. The July management report is due to the owner tomorrow. Other expenses have risen 40% against June. You have the ledger detail below and you do not yet know why.",
    fields: [
      {
        id: "b_checks",
        label: "1 — What do you check, and in what order?",
        placeholder: "",
      },
      {
        id: "b_owner",
        label:
          "2 — What do you tell the owner tomorrow, before you have the full answer?",
        placeholder: "",
      },
      {
        id: "b_not_real",
        label: "3 — Is anything here not a real increase in cost? Say why.",
        placeholder: "",
      },
    ],
  },
  {
    key: "C",
    letter: "C",
    title: "Client email",
    minutes: 15,
    language:
      "English only — the English is the exercise. We will not explain wording here.",
    intro:
      "It is 21:40. This email arrives from an Italian client. Write the reply you would send tonight. No phone, no dictionary.",
    fields: [
      {
        id: "c_reply",
        label: "Your reply",
        placeholder: "Dear Mr Ferrari,",
      },
    ],
  },
  {
    key: "D",
    letter: "D",
    title: "Fact sheet",
    minutes: 10,
    language: "English or Bahasa Indonesia — your choice.",
    intro:
      "Every line, please. Where a line asks for a number or a date, give a number or a date.",
    fields: [
      {
        id: "d_software",
        label: "Accounting software you have used, by name",
        short: true,
      },
      {
        id: "d_coretax",
        label: "Coretax / e-Faktur — used, seen, or neither",
        short: true,
      },
      {
        id: "d_volume",
        label: "Entities handled at once, and transactions per month",
        short: true,
      },
      {
        id: "d_managed",
        label: "People you managed, and their roles",
        short: true,
      },
      {
        id: "d_reported",
        label: "Who you reported to, and their title",
        short: true,
      },
      { id: "d_leaving", label: "Reason for leaving your current role" },
      { id: "d_notice", label: "Notice period, as a date", short: true },
      {
        id: "d_salary",
        label: "Salary expectation, as a monthly number (IDR)",
        short: true,
      },
      {
        id: "d_availability",
        label: "Availability over the first 90 days",
        short: true,
      },
      {
        id: "d_dates",
        label:
          "Two dates we need to fix — your file records the start of your Toshiba role as 1993 in one place and 1998 in another. Write the correct year, and where the other came from.",
      },
      {
        id: "d_question",
        label:
          "One last question, and it is not a test — what do you want to know about this job that nobody has told you yet?",
      },
    ],
  },
];

export const TOTAL_MINUTES = EXERCISES.reduce((n, e) => n + e.minutes, 0);
