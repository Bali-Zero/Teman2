import type { Language } from "../_lib/flow";

/**
 * Copy the road shell adds, EN/ID, component-local because `_lib/i18n.ts`
 * is frozen for this surface (BRIEF-v2 R-6) — the SESSION_COPY pattern in
 * OracleShell.tsx. Parity (same keys, no empty value, same `{placeholders}`)
 * is pinned by road-copy.test.ts. Voice: plain, no ranking words, never a
 * visa name, never an engine identifier.
 */
export const ROAD_COPY = {
  en: {
    railOutcomeTitle: "Where this road ends",
    roadLabel: "Your answers so far",
    stage: "Stage {n} of {total}",
    change: "Change",
    changeAria: "Change your answer: {question}",
    notSure: "Not sure yet",
    notAnswered: "Not answered",
    prunedOne: "1 other purpose set aside for now",
    prunedMany: "{count} other purposes set aside for now",
    answeredAbout: "{current} of about {total} answered",
    laneQualifier: "subject to conditions",
    earlierTitle: "Before your change — asked again only if still relevant",
    checkingTitle: "Checking your answers",
    lanesKicker: "Suggested visa path — subject to conditions",
    lanesTitle: "Paths to consider",
    lanesOrder:
      "Listed in the order the check returned them. The conditions of each are below.",
    edgeLine: "The road stops here for these answers. The reasons are below.",
    edgeBack: "Other purposes you can check lead back from here.",
    pencilLine:
      "More input is needed before a path can be suggested. What is missing is marked below.",
    specialistLine:
      "These answers need a person to read them; no path is suggested here. The consultant contact at the top of this page is how to reach one.",
    outageLine:
      "The check did not finish. Your answers are still here; try again when you are ready.",
  },
  id: {
    railOutcomeTitle: "Ujung jalan ini",
    roadLabel: "Jawaban Anda sejauh ini",
    stage: "Tahap {n} dari {total}",
    change: "Ubah",
    changeAria: "Ubah jawaban Anda: {question}",
    notSure: "Belum yakin",
    notAnswered: "Belum dijawab",
    prunedOne: "1 tujuan lain dikesampingkan untuk saat ini",
    prunedMany: "{count} tujuan lain dikesampingkan untuk saat ini",
    answeredAbout: "{current} dari sekitar {total} terjawab",
    laneQualifier: "dengan syarat",
    earlierTitle:
      "Sebelum perubahan Anda — ditanyakan lagi hanya jika masih relevan",
    checkingTitle: "Memeriksa jawaban Anda",
    lanesKicker: "Jalur visa yang disarankan — dengan syarat",
    lanesTitle: "Jalur yang layak dipertimbangkan",
    lanesOrder:
      "Disusun sesuai urutan hasil pemeriksaan. Syarat masing-masing ada di bawah.",
    edgeLine:
      "Jalan berhenti di sini untuk jawaban ini. Alasannya ada di bawah.",
    edgeBack: "Tujuan lain yang bisa Anda periksa mengarah kembali dari sini.",
    pencilLine:
      "Masih perlu jawaban tambahan sebelum jalur dapat disarankan. Yang kurang ditandai di bawah.",
    specialistLine:
      "Jawaban ini perlu dibaca oleh seseorang; tidak ada jalur yang disarankan di sini. Kontak konsultan di bagian atas halaman ini adalah cara menghubunginya.",
    outageLine:
      "Pemeriksaan tidak selesai. Jawaban Anda masih ada; coba lagi kapan pun Anda siap.",
  },
} as const satisfies Record<Language, Record<string, string>>;

export type RoadCopyKey = keyof (typeof ROAD_COPY)["en"];

/** `{name}` placeholders only — no plural grammar, no markup. */
export function roadCopy(
  language: Language,
  key: RoadCopyKey,
  vars: Record<string, string | number> = {},
): string {
  return (ROAD_COPY[language][key] as string).replace(
    /\{(\w+)\}/g,
    (whole, name: string) =>
      Object.prototype.hasOwnProperty.call(vars, name)
        ? String(vars[name])
        : whole,
  );
}
