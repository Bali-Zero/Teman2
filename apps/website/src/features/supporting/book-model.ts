import source from "./book-content.json";
import { getServiceDossier } from "../../content/service-dossiers";

export type BookLocale = keyof typeof source.locales;
export const bookLocales = source.locales;
export const bookChapters = source.chapters;
export function bookLocale(value: string | string[] | undefined): BookLocale {
  const candidate = Array.isArray(value) ? value[0] : value;
  return candidate && Object.hasOwn(bookLocales, candidate)
    ? (candidate as BookLocale)
    : "en";
}
export function bookHref(chapter: string, locale: BookLocale) {
  return `${chapter === "cover" ? "/book" : `/book/${chapter}`}?lang=${locale}`;
}

export type BookService = {
  serviceKey: string;
  title: string;
  category: string;
  waMessage: string;
  pricingCategory?: string;
  pricingItemKey?: string;
  description: string;
  scope: readonly string[];
  preparation: readonly string[];
  limit: string;
  href: string;
};
const dossierNames: Record<string, string> = {
  "pt-pma": "PT PMA/PMDN Setup",
  "tax-compliance": "SPT Annual Company (Operational)",
  "tax-id": "NPWP Personal + Coretax",
  "property-advisory": "Legal Due Diligence",
  "property-lease": "Leasehold Agreement (Hak Sewa)",
};

/** Preserve the book's service identities; R19's reviewed dossiers supply scope, not stale marketing claims. */
export function bookServices(): BookService[] {
  return source.services.map((service) => {
    if (service.serviceKey === "cv-setup")
      return {
        ...service,
        description: "Local partnership company.",
        scope: ["Indonesian partnership", "NIB registration"],
        preparation: [
          "Describe the partners and planned business activities to the setup team.",
        ],
        limit:
          "Ask the setup team to confirm the structure, scope and timing for your case.",
        href: "/services/company-setup",
      };
    const dossier = getServiceDossier(
      dossierNames[service.serviceKey] ?? service.title,
    );
    return {
      ...service,
      description: dossier.explanation,
      scope: dossier.scope,
      preparation: dossier.preparation,
      limit: dossier.limit,
      href: `/services/${dossier.domain}#${dossier.id}`,
    };
  });
}

// Limited replacements for unsupported legacy competitor and AI guarantees.
// The full field inventory and reasons are recorded in the supporting-page handoff.
export const bookAssist = {
  en: {
    contents: "In this book",
    previous: "Previous",
    next: "Next chapter",
    start: "Start reading",
    impact: "From information to a next step.",
    impactBody:
      "Explore the service, understand its scope and prepare the questions that matter for your case.",
    tech: "Tools to help you prepare.",
    techBody:
      "Explore KBLI activities, compare services and bring your questions to the Bali Zero team.",
    steps: [
      "Understand your activity",
      "Review the service scope",
      "Discuss your case",
    ],
    team: "The people behind the work.",
    fullTeam: "Meet the full team",
    services: "Explore the services",
    serviceNote:
      "Service descriptions and scope are available in English. Your WhatsApp enquiry carries your selected language.",
    toolLabels: [
      "Explore KBLI activities",
      "Compare service scope",
      "Talk to Bali Zero",
    ],
  },
  it: {
    contents: "In questo libro",
    previous: "Precedente",
    next: "Capitolo successivo",
    start: "Inizia a leggere",
    impact: "Dalle informazioni al prossimo passo.",
    impactBody:
      "Esplora il servizio, comprendi il suo ambito e prepara le domande importanti per il tuo caso.",
    tech: "Strumenti per prepararti.",
    techBody:
      "Esplora le attività KBLI, confronta i servizi e porta le tue domande al team Bali Zero.",
    steps: [
      "Comprendi la tua attività",
      "Esamina l'ambito del servizio",
      "Parla del tuo caso",
    ],
    team: "Le persone dietro il lavoro.",
    fullTeam: "Conosci tutto il team",
    services: "Esplora i servizi",
    serviceNote:
      "Le descrizioni e gli ambiti dei servizi sono in inglese. La richiesta WhatsApp indica la lingua selezionata.",
    toolLabels: [
      "Esplora le attività KBLI",
      "Confronta i servizi",
      "Parla con Bali Zero",
    ],
  },
  id: {
    contents: "Isi buku",
    previous: "Sebelumnya",
    next: "Bab berikutnya",
    start: "Mulai membaca",
    impact: "Dari informasi ke langkah berikutnya.",
    impactBody:
      "Jelajahi layanan, pahami ruang lingkupnya, dan siapkan pertanyaan yang penting untuk kasus Anda.",
    tech: "Alat untuk membantu persiapan Anda.",
    techBody:
      "Jelajahi kegiatan KBLI, bandingkan layanan, dan sampaikan pertanyaan Anda kepada tim Bali Zero.",
    steps: [
      "Pahami kegiatan Anda",
      "Tinjau ruang lingkup layanan",
      "Diskusikan kasus Anda",
    ],
    team: "Orang-orang di balik pekerjaan ini.",
    fullTeam: "Kenali seluruh tim",
    services: "Jelajahi layanan",
    serviceNote:
      "Deskripsi dan ruang lingkup layanan tersedia dalam bahasa Inggris. Pertanyaan WhatsApp mencantumkan bahasa pilihan Anda.",
    toolLabels: [
      "Jelajahi kegiatan KBLI",
      "Bandingkan layanan",
      "Hubungi Bali Zero",
    ],
  },
  ru: {
    contents: "В этой книге",
    previous: "Назад",
    next: "Следующая глава",
    start: "Начать чтение",
    impact: "От информации к следующему шагу.",
    impactBody:
      "Изучите услугу, её объём и подготовьте вопросы, важные для вашего случая.",
    tech: "Инструменты для подготовки.",
    techBody:
      "Изучайте виды деятельности KBLI, сравнивайте услуги и обращайтесь с вопросами к команде Bali Zero.",
    steps: [
      "Изучите свою деятельность",
      "Уточните объём услуги",
      "Обсудите ваш случай",
    ],
    team: "Люди, которые делают эту работу.",
    fullTeam: "Познакомиться с командой",
    services: "Изучить услуги",
    serviceNote:
      "Описание и объём услуг доступны на английском. В обращении через WhatsApp будет указан выбранный язык.",
    toolLabels: [
      "Изучить виды деятельности KBLI",
      "Сравнить услуги",
      "Связаться с Bali Zero",
    ],
  },
  zh: {
    contents: "本书目录",
    previous: "上一章",
    next: "下一章",
    start: "开始阅读",
    impact: "从信息到下一步。",
    impactBody: "了解服务及其范围，准备与您情况相关的重要问题。",
    tech: "帮助您做好准备的工具。",
    techBody: "探索KBLI业务活动、比较服务，并向Bali Zero团队提出问题。",
    steps: ["了解您的业务活动", "查看服务范围", "讨论您的情况"],
    team: "工作背后的团队。",
    fullTeam: "认识整个团队",
    services: "探索服务",
    serviceNote: "服务说明与范围以英文提供。您的WhatsApp咨询将注明所选语言。",
    toolLabels: ["探索KBLI业务活动", "比较服务范围", "联系Bali Zero"],
  },
} as const;
