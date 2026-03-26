// apps/mouth/src/components/book/book-data.ts
// Single source of truth for all book content.
// Primary language: English. Translations: IT, ID, RU, ZH.
// EVERY fact is sourced from verified codebase data or founder confirmation.

export interface Chapter {
  id: string;
  index: number;
  title: string;
  subtitle: string;
  heroImage: string;
  heroImageAlt: string;
  showZantaraCTA?: boolean;
}

export interface TeamMember {
  name: string;
  role: string;
  department: "leadership" | "setup" | "tax" | "accounting" | "support";
  photo?: string;
  whatsapp?: string;
}

export interface Milestone {
  year: string;
  label: string;
  description: string;
}

export interface CompetitorStat {
  name: string;
  founded: number;
  yoyTrend: string;
}

export interface ServiceItem {
  title: string;
  tagline: string;
  serviceKey: string;
  category: "visa" | "company" | "tax" | "property";
  features: string[];
  waMessage: string;
  badge?: string;
}

// ─── CHAPTERS ──────────────────────────────────────────────────────────────────
export const CHAPTERS: Chapter[] = [
  {
    id: "cover",
    index: 0,
    title: "Bali Zero",
    subtitle: "",
    heroImage: "/static/image_art/zantara_gold_black_gradient_transparent.png",
    heroImageAlt: "Bali Zero",
  },
  {
    id: "manifesto",
    index: 1,
    title: "5,000 clients. 20 years. Built from the ground up.",
    subtitle:
      "From CV Bayu Santero to Bali Zero — two decades at your service.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Luxury_gold_to_black_gradient,_smooth_color_transition,_premium_c_4ad0a879-3d92-41e8-beab-ff42dc499fb8.png",
    heroImageAlt: "Bali Zero Manifesto",
  },
  {
    id: "origin",
    index: 2,
    title: "The meeting that changed everything.",
    subtitle:
      "2020. A European founder with a vision. A Balinese entrepreneur with 14 years of expertise. Together.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Dark_luxury_gradient_background,_subtle_gold_foil_texture,_deep_n_4ccbbd81-3a9a-4ab6-b22a-948bb50a73c5.png",
    heroImageAlt: "The origin of Bali Zero",
  },
  {
    id: "team",
    index: 3,
    title: "22 people. One mission.",
    subtitle:
      "Local and international experts — all dedicated to your success in Indonesia.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Subtle_geometric_pattern,_golden_lines_on_dark_background,_minima_3d95f5d2-0f4e-477c-bc1f-a6f750466cce.png",
    heroImageAlt: "The Bali Zero team",
  },
  {
    id: "services",
    index: 4,
    title: "Real prices. No surprises.",
    subtitle:
      "Visas, companies, tax, property. Fully transparent. Fully accountable.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Modern_checkmark_icon,_golden_gradient,_minimalist_success_symbol_b57bcd74-0803-4cd1-9af7-9caffae712be.png",
    heroImageAlt: "Bali Zero Services",
    showZantaraCTA: true,
  },
  {
    id: "impact",
    index: 5,
    title: "Indonesia's only AI-native agency.",
    subtitle: "Competitors are shrinking. We are growing.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Abstract_AI_brain,_neural_network_visualization,_golden_glowing_c_bf1f9cb1-c9df-481c-9bc7-05928ddf38de.png",
    heroImageAlt: "Bali Zero Impact",
    showZantaraCTA: true,
  },
  {
    id: "technology",
    index: 6,
    title: "Zantara: your consultant, 24/7.",
    subtitle:
      "The only AI assistant in Indonesia covering legal services and immigration — in real time.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Elegant_data_flow_visualization,_golden_particles_moving,_dark_te_15e4c14b-15d5-4cae-bb42-622662505408.png",
    heroImageAlt: "Zantara Technology",
    showZantaraCTA: true,
  },
  {
    id: "contact",
    index: 7,
    title: "The first step is simple.",
    subtitle: "One message. One call. Your future in Indonesia starts here.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Dark_luxury_gradient_background,_subtle_gold_foil_texture,_deep_n_6c06b85d-1ad6-4a48-a729-23b80947e173.png",
    heroImageAlt: "Contact Bali Zero",
  },
];

// ─── TEAM ──────────────────────────────────────────────────────────────────────
// Source: apps/mouth/src/app/(blog)/team/page.tsx — verified
export const TEAM_MEMBERS: TeamMember[] = [
  // Leadership
  {
    name: "Zainal Abidin",
    role: "Chief Executive Officer",
    department: "leadership",
  },
  {
    name: "Ruslana",
    role: "Board Member",
    department: "leadership",
    photo: "/static/team/ruslana.jpg",
  },
  // Setup
  {
    name: "Adit",
    role: "Supervisor (Lead Setup)",
    department: "setup",
    photo: "/static/team/adit.png",
  },
  { name: "Anton", role: "Executive Consultant", department: "setup" },
  {
    name: "Krisna",
    role: "Executive Consultant",
    department: "setup",
    photo: "/static/team/krisna.png",
  },
  {
    name: "Dea",
    role: "Executive Consultant",
    department: "setup",
    photo: "/static/team/dea.png",
  },
  {
    name: "Ari",
    role: "Specialist Consultant",
    department: "setup",
    photo: "/static/team/ari.png",
  },
  { name: "Surya", role: "Specialist Consultant", department: "setup" },
  {
    name: "Anna",
    role: "Specialist Advisor",
    department: "setup",
    photo: "/static/team/anna.jpeg",
  },
  {
    name: "Marta",
    role: "Setup Consultant",
    department: "setup",
    photo: "/static/team/marta.jpeg",
  },
  {
    name: "Olena",
    role: "Setup Consultant",
    department: "setup",
    photo: "/static/team/olena.jpeg",
  },
  { name: "Vino", role: "Junior Consultant", department: "setup" },
  { name: "Damar", role: "Junior Consultant", department: "setup" },
  // Tax
  { name: "Veronika", role: "Tax Manager", department: "tax" },
  { name: "Angel", role: "Tax Expert", department: "tax" },
  { name: "Kadek", role: "Tax Consultant", department: "tax" },
  { name: "Dewa Ayu", role: "Tax Consultant", department: "tax" },
  { name: "Faisha", role: "Tax Care", department: "tax" },
  // Accounting
  {
    name: "Asya Nadia",
    role: "Accounting",
    department: "accounting",
    photo: "/static/team/asya.jpg",
  },
  // Support
  { name: "Rina", role: "Reception", department: "support" },
  {
    name: "Sahira",
    role: "Marketing Specialist",
    department: "support",
    photo: "/static/team/sahira.png",
  },
  { name: "Nina", role: "Marketing Advisory", department: "support" },
];

// ─── SERVICES ──────────────────────────────────────────────────────────────────
export const SERVICES: ServiceItem[] = [
  // VISA
  {
    title: "Single Entry Visa",
    tagline: "C317 / B1 — up to 180 days",
    serviceKey: "C317 Single Entry",
    category: "visa",
    badge: "Most popular",
    features: [
      "Initial consultation",
      "Document preparation",
      "Application filing",
      "Status tracking portal",
    ],
    waMessage:
      "Hi, I am interested in a Single Entry Visa. Can you give me more info?",
  },
  {
    title: "Multiple Entry Visa",
    tagline: "E33G — 12 months, unlimited entries",
    serviceKey: "E33G Multiple Entry",
    category: "visa",
    features: [
      "Initial consultation",
      "Document preparation",
      "Application filing",
      "Status tracking portal",
      "Renewal support",
    ],
    waMessage:
      "Hi, I am interested in the E33G Multiple Entry Visa. Can you give me more info?",
  },
  {
    title: "Retirement KITAS",
    tagline: "Annual residence permit",
    serviceKey: "KITAS Retirement",
    category: "visa",
    features: [
      "Eligibility check",
      "Document preparation",
      "Full application",
      "1st year renewal included",
    ],
    waMessage:
      "Hi, I am interested in a Retirement KITAS. Can you give me more info?",
  },
  {
    title: "Investor KITAS",
    tagline: "For PT PMA directors & shareholders",
    serviceKey: "KITAS Investor",
    category: "visa",
    badge: "For business owners",
    features: [
      "Linked to PT PMA",
      "Director or shareholder route",
      "Multi-year validity",
      "Work permit included",
    ],
    waMessage:
      "Hi, I am interested in an Investor KITAS. Can you give me more info?",
  },
  // COMPANY
  {
    title: "PT PMA Setup",
    tagline: "Foreign-owned company in Indonesia",
    serviceKey: "PT PMA",
    category: "company",
    badge: "Complete package",
    features: [
      "KBLI code selection (9,612 codes)",
      "Notary & Kemenkumham",
      "OSS RBA license",
      "NIB + NPWP company",
      "Bank account facilitation",
      "Status tracking portal",
    ],
    waMessage:
      "Hi, I am interested in setting up a PT PMA. Can you give me more info?",
  },
  {
    title: "PT Lokal Setup",
    tagline: "Indonesian-owned company",
    serviceKey: "PT Lokal",
    category: "company",
    features: [
      "Ideal for local partners",
      "Notary & registration",
      "OSS license",
      "NIB + NPWP",
    ],
    waMessage:
      "Hi, I am interested in setting up a PT Lokal. Can you give me more info?",
  },
  {
    title: "CV / UD Setup",
    tagline: "Simple Indonesian business structure",
    serviceKey: "CV Setup",
    category: "company",
    features: [
      "Fastest setup option",
      "Notary registration",
      "NIB",
      "For small-scale operations",
    ],
    waMessage:
      "Hi, I am interested in setting up a CV or UD. Can you give me more info?",
  },
  // TAX
  {
    title: "Annual Tax Return (SPT)",
    tagline: "Personal income tax filing",
    serviceKey: "SPT Annual",
    category: "tax",
    features: [
      "NPWP registration",
      "Income calculation",
      "SPT preparation & filing",
      "Compliance guarantee",
    ],
    waMessage: "Hi, I need help with my annual tax return (SPT) in Indonesia.",
  },
  {
    title: "Corporate Tax",
    tagline: "PT PMA / PT Lokal annual compliance",
    serviceKey: "Corporate Tax",
    category: "tax",
    badge: "For companies",
    features: [
      "Monthly tax reports (PPh 21/25)",
      "VAT filing (PPN)",
      "Annual SPT Badan",
      "LKPM reporting",
    ],
    waMessage:
      "Hi, I need help with corporate tax compliance for my Indonesian company.",
  },
  // PROPERTY
  {
    title: "Property Consulting",
    tagline: "Buy, lease, or structure ownership",
    serviceKey: "Property Consulting",
    category: "property",
    features: [
      "Legal due diligence",
      "Nominee structure advice",
      "Lease agreement review",
      "PT PMA property path",
    ],
    waMessage: "Hi, I need property consulting in Bali. Can you help?",
  },
];

// ─── COMPETITORS ───────────────────────────────────────────────────────────────
// Source: competitor intelligence report — verified March 2026
export const COMPETITORS: CompetitorStat[] = [
  { name: "Emerhub", founded: 2011, yoyTrend: "-8.5%" },
  { name: "InCorp", founded: 2012, yoyTrend: "-19%" },
  { name: "LetsMoveIndonesia", founded: 2015, yoyTrend: "-23.5%" },
  { name: "Seven Stones", founded: 2016, yoyTrend: "+1.8%" },
];

// ─── STATS ─────────────────────────────────────────────────────────────────────
// Source: founder confirmed / codebase
export const STATS = {
  clients: "5,000+",
  yearsOfHistory: "20+",
  teamSize: 22,
  aiTools: 96,
  legalDocs: "66K+",
  kbliCodes: "9,612",
  channels: 4,
};

// ─── CONTACTS ──────────────────────────────────────────────────────────────────
export const CONTACTS = {
  whatsapp: "+62 859 0436 9574",
  whatsappUrl: "https://wa.me/6285904369574",
  email: "info@balizero.com",
  web: "balizero.com",
};

// ─── MILESTONES ────────────────────────────────────────────────────────────────
// Source: founder confirmed
export const MILESTONES: Milestone[] = [
  {
    year: "2006",
    label: "CV Bayu Santero",
    description:
      "Pak Zainal Abidin founds CV Bayu Santero in Bali. The roots of everything that follows.",
  },
  {
    year: "2020",
    label: "Bali Zero is born",
    description:
      "The meeting between Zero and Pak Zainal creates something new. European vision meets two decades of Balinese expertise.",
  },
  {
    year: "2021",
    label: "Client portal",
    description:
      "First practice tracking system for clients — full visibility on every document and deadline.",
  },
  {
    year: "2023",
    label: "Zantara AI",
    description:
      "Launch of Zantara — the first AI assistant in the Indonesian legal services sector. Available 24/7 on WhatsApp, Telegram, and Web.",
  },
  {
    year: "2024",
    label: "KBLI Navigator",
    description:
      "9,612 KBLI 2025 codes indexed and searchable. The only such resource in Indonesia.",
  },
  {
    year: "2025",
    label: "5,000 clients",
    description:
      "We crossed the 5,000 clients milestone. Competitors are shrinking. We are growing.",
  },
  {
    year: "2026",
    label: "The future",
    description:
      "Knowledge graph with 56K nodes. 66K indexed legal documents. The only AI-first agency in Indonesia.",
  },
];

// ─── PRICING FALLBACK ──────────────────────────────────────────────────────────
// Live prices come from usePricingData SWR hook → /api/pricing/calculate
export const PRICING_FALLBACK: Record<string, string> = {
  "B1 Visit Visa": "Rp 5.8M",
  "C317 Single Entry": "Rp 5.8M",
  "E33G Multiple Entry": "Rp 9.5M",
  "KITAS Retirement": "Rp 22M",
  "PT PMA": "Rp 20M",
};

// ─── I18N TRANSLATIONS ─────────────────────────────────────────────────────────
export type Locale = "en" | "it" | "id" | "ru" | "zh";

export const LOCALE_LABELS: Record<Locale, string> = {
  en: "EN",
  it: "IT",
  id: "ID",
  ru: "RU",
  zh: "中文",
};

export interface BookTranslations {
  // Cover
  coverTagline: string;
  coverSubtitle: string;
  scrollDown: string;
  // Manifesto
  manifestoP1: string;
  manifestoP2: string;
  // Origin
  originP1: string;
  originP2: string;
  // Team
  teamDepts: Record<string, string>;
  // Services
  servicesCta: string;
  servicesCategories: Record<string, string>;
  askOnWhatsApp: string;
  mostPopular: string;
  forCompanies: string;
  forBusinessOwners: string;
  // Impact
  impactBody: string;
  headcountYoY: string;
  // Technology
  techBody: string;
  techStats: { n: string; l: string }[];
  // Contact
  contactBody: string;
  contactCta: string;
  copyright: string;
  // Nav
  chapters: string[];
  switchLang: string;
}

export const TRANSLATIONS: Record<Locale, BookTranslations> = {
  en: {
    coverTagline: "From CV Bayu Santero (2006) to Bali Zero (2020)",
    coverSubtitle: "Indonesia's only AI-first agency.",
    scrollDown: "scroll",
    manifestoP1:
      "It all started in 2006, when Pak Zainal Abidin founded CV Bayu Santero in Bali. Fourteen years of hands-on experience navigating the Indonesian market — clients helped, regulations decoded, success stories built one by one.",
    manifestoP2:
      "In 2020, a meeting changed everything. A new vision joined deep roots. From that encounter, Bali Zero was born — not a startup, but the evolution of twenty years of history.",
    originP1:
      "Pak Zainal had seen it all. Foreign clients lost in the Indonesian bureaucratic maze. Wrong visas. Companies opened with incorrect KBLI codes. Money wasted from lack of precise information.",
    originP2:
      "The partnership with Zero brought a different answer: complete price transparency, AI technology that responds in under 3 seconds, a team of 22 people fully dedicated to every client.",
    teamDepts: {
      leadership: "Leadership",
      setup: "Business Setup",
      tax: "Tax",
      accounting: "Accounting",
      support: "Support",
    },
    servicesCta: "Ask on WhatsApp",
    servicesCategories: {
      visa: "Visa & Permits",
      company: "Company Setup",
      tax: "Tax & Compliance",
      property: "Property",
    },
    askOnWhatsApp: "Ask on WhatsApp",
    mostPopular: "Most popular",
    forCompanies: "For companies",
    forBusinessOwners: "For business owners",
    impactBody:
      "While competitors lose headcount (-8% to -23% annually), Bali Zero grows. The difference? We're the only ones with a production AI stack.",
    headcountYoY: "headcount YoY",
    techBody:
      "Zantara is not a chatbot. It is a full AI consultant built on 66,000 indexed legal documents, a 56K-node knowledge graph, and real-time data from the Indonesian regulatory ecosystem.",
    techStats: [
      { n: "96", l: "MCP Tools in production" },
      { n: "56K", l: "Knowledge graph nodes" },
      { n: "66K+", l: "Indexed legal documents" },
      { n: "9,612", l: "KBLI 2025 codes" },
      { n: "4", l: "AI channels, 24/7" },
      { n: "< 3s", l: "Average response time" },
    ],
    contactBody:
      "Whether you need a visa, want to open a company, or have questions about Indonesian regulations — we are here.",
    contactCta: "Start a conversation",
    copyright: "© 2006–2026 CV Bayu Santero / Bali Zero. All rights reserved.",
    chapters: [
      "Cover",
      "Manifesto",
      "Origin",
      "Team",
      "Services",
      "Impact",
      "Technology",
      "Contact",
    ],
    switchLang: "Language",
  },

  it: {
    coverTagline: "Da CV Bayu Santero (2006) a Bali Zero (2020)",
    coverSubtitle: "L'unica agenzia AI-first in Indonesia.",
    scrollDown: "scorri",
    manifestoP1:
      "Tutto è iniziato nel 2006, quando Pak Zainal Abidin ha fondato CV Bayu Santero a Bali. Quattordici anni di esperienza nel mercato indonesiano — clienti aiutati, regolamenti navigati, storie di successo costruite mattone per mattone.",
    manifestoP2:
      "Nel 2020, un incontro ha cambiato tutto. Una visione nuova si è unita a radici profonde. Da quell'incontro è nato Bali Zero — non una startup, ma l'evoluzione di vent'anni di storia.",
    originP1:
      "Pak Zainal aveva già visto tutto. Clienti stranieri persi nel labirinto burocratico indonesiano. Visti sbagliati. Aziende aperte con codici KBLI errati. Soldi sprecati per mancanza di informazioni precise.",
    originP2:
      "L'incontro con Zero ha portato una risposta diversa: trasparenza totale sui prezzi, tecnologia AI che risponde in meno di 3 secondi, un team di 22 persone completamente dedicato.",
    teamDepts: {
      leadership: "Leadership",
      setup: "Business Setup",
      tax: "Fiscalità",
      accounting: "Contabilità",
      support: "Supporto",
    },
    servicesCta: "Chiedi su WhatsApp",
    servicesCategories: {
      visa: "Visti e Permessi",
      company: "Apertura Società",
      tax: "Tasse e Compliance",
      property: "Immobiliare",
    },
    askOnWhatsApp: "Chiedi su WhatsApp",
    mostPopular: "Più richiesto",
    forCompanies: "Per aziende",
    forBusinessOwners: "Per imprenditori",
    impactBody:
      "Mentre i competitor perdono personale (-8% a -23% annuo), Bali Zero cresce. La differenza? Siamo gli unici con un AI stack in produzione.",
    headcountYoY: "variazione annua personale",
    techBody:
      "Zantara non è un chatbot. È un consulente AI completo, costruito su 66.000 documenti legali indicizzati, un knowledge graph con 56K nodi e dati in tempo reale dall'ecosistema normativo indonesiano.",
    techStats: [
      { n: "96", l: "MCP Tool in produzione" },
      { n: "56K", l: "Nodi nel knowledge graph" },
      { n: "66K+", l: "Documenti legali indicizzati" },
      { n: "9.612", l: "Codici KBLI 2025" },
      { n: "4", l: "Canali AI, 24/7" },
      { n: "< 3s", l: "Tempo medio di risposta" },
    ],
    contactBody:
      "Che tu abbia bisogno di un visto, voglia aprire un'azienda o abbia domande sulla normativa indonesiana — siamo qui.",
    contactCta: "Inizia una conversazione",
    copyright:
      "© 2006–2026 CV Bayu Santero / Bali Zero. Tutti i diritti riservati.",
    chapters: [
      "Copertina",
      "Manifesto",
      "Origini",
      "Team",
      "Servizi",
      "Impatto",
      "Tecnologia",
      "Contatti",
    ],
    switchLang: "Lingua",
  },

  id: {
    coverTagline: "Dari CV Bayu Santero (2006) hingga Bali Zero (2020)",
    coverSubtitle: "Satu-satunya agensi AI-first di Indonesia.",
    scrollDown: "gulir",
    manifestoP1:
      "Semuanya dimulai pada 2006, ketika Pak Zainal Abidin mendirikan CV Bayu Santero di Bali. Empat belas tahun pengalaman langsung di pasar Indonesia — klien yang dibantu, peraturan yang diurai, kisah sukses yang dibangun satu per satu.",
    manifestoP2:
      "Pada 2020, sebuah pertemuan mengubah segalanya. Visi baru bergabung dengan akar yang dalam. Dari pertemuan itu, Bali Zero lahir — bukan startup, melainkan evolusi dari dua dekade sejarah.",
    originP1:
      "Pak Zainal sudah melihat semuanya. Klien asing tersesat dalam labirin birokrasi Indonesia. Visa yang salah. Perusahaan dibuka dengan kode KBLI yang keliru. Uang terbuang karena kurangnya informasi yang tepat.",
    originP2:
      "Kemitraan dengan Zero membawa jawaban yang berbeda: transparansi harga penuh, teknologi AI yang merespons dalam 3 detik, tim 22 orang yang sepenuhnya berdedikasi.",
    teamDepts: {
      leadership: "Pimpinan",
      setup: "Pendirian Bisnis",
      tax: "Perpajakan",
      accounting: "Akuntansi",
      support: "Dukungan",
    },
    servicesCta: "Tanya di WhatsApp",
    servicesCategories: {
      visa: "Visa & Izin",
      company: "Pendirian Perusahaan",
      tax: "Pajak & Kepatuhan",
      property: "Properti",
    },
    askOnWhatsApp: "Tanya di WhatsApp",
    mostPopular: "Paling populer",
    forCompanies: "Untuk perusahaan",
    forBusinessOwners: "Untuk pengusaha",
    impactBody:
      "Sementara pesaing kehilangan karyawan (-8% hingga -23% per tahun), Bali Zero terus berkembang. Bedanya? Kami satu-satunya yang memiliki AI stack di produksi.",
    headcountYoY: "perubahan karyawan YoY",
    techBody:
      "Zantara bukan chatbot biasa. Ini adalah konsultan AI lengkap yang dibangun di atas 66.000 dokumen hukum terindeks, knowledge graph 56K node, dan data regulasi Indonesia secara real-time.",
    techStats: [
      { n: "96", l: "MCP Tool aktif" },
      { n: "56K", l: "Node knowledge graph" },
      { n: "66K+", l: "Dokumen hukum terindeks" },
      { n: "9.612", l: "Kode KBLI 2025" },
      { n: "4", l: "Channel AI, 24/7" },
      { n: "< 3s", l: "Rata-rata waktu respons" },
    ],
    contactBody:
      "Butuh visa, ingin mendirikan perusahaan, atau punya pertanyaan soal regulasi Indonesia — kami siap membantu.",
    contactCta: "Mulai percakapan",
    copyright:
      "© 2006–2026 CV Bayu Santero / Bali Zero. Seluruh hak dilindungi.",
    chapters: [
      "Cover",
      "Manifesto",
      "Asal-usul",
      "Tim",
      "Layanan",
      "Dampak",
      "Teknologi",
      "Kontak",
    ],
    switchLang: "Bahasa",
  },

  ru: {
    coverTagline: "От CV Bayu Santero (2006) до Bali Zero (2020)",
    coverSubtitle: "Единственное AI-агентство в Индонезии.",
    scrollDown: "листать",
    manifestoP1:
      "Всё началось в 2006 году, когда Пак Зайнал Абидин основал CV Bayu Santero на Бали. Четырнадцать лет практического опыта на индонезийском рынке — помощь клиентам, изучение законов, истории успеха, построенные шаг за шагом.",
    manifestoP2:
      "В 2020 году одна встреча изменила всё. Новое видение соединилось с глубокими корнями. Из этой встречи родился Bali Zero — не стартап, а эволюция двадцати лет истории.",
    originP1:
      "Пак Зайнал видел всё. Иностранные клиенты, заблудившиеся в индонезийском бюрократическом лабиринте. Неправильные визы. Компании, открытые с ошибочными кодами KBLI. Деньги, потраченные из-за нехватки точной информации.",
    originP2:
      "Партнёрство с Zero принесло другой ответ: полная прозрачность цен, AI-технология с ответом за 3 секунды, команда из 22 человек, полностью преданных каждому клиенту.",
    teamDepts: {
      leadership: "Руководство",
      setup: "Открытие бизнеса",
      tax: "Налоги",
      accounting: "Бухгалтерия",
      support: "Поддержка",
    },
    servicesCta: "Написать в WhatsApp",
    servicesCategories: {
      visa: "Визы и разрешения",
      company: "Открытие компании",
      tax: "Налоги и соответствие",
      property: "Недвижимость",
    },
    askOnWhatsApp: "Написать в WhatsApp",
    mostPopular: "Самый популярный",
    forCompanies: "Для компаний",
    forBusinessOwners: "Для предпринимателей",
    impactBody:
      "Пока конкуренты теряют сотрудников (-8% до -23% в год), Bali Zero растёт. Разница? Мы единственные с production AI-стеком.",
    headcountYoY: "изм. персонала год к году",
    techBody:
      "Зантара — не чат-бот. Это полноценный AI-консультант, построенный на 66 000 проиндексированных юридических документах, графе знаний с 56К узлами и данных индонезийского законодательства в реальном времени.",
    techStats: [
      { n: "96", l: "MCP Tools в продакшне" },
      { n: "56K", l: "Узлов в графе знаний" },
      { n: "66K+", l: "Проиндексированных документов" },
      { n: "9 612", l: "Кодов KBLI 2025" },
      { n: "4", l: "AI-канала, 24/7" },
      { n: "< 3с", l: "Среднее время ответа" },
    ],
    contactBody:
      "Нужна виза, хотите открыть компанию или есть вопросы по индонезийскому законодательству — мы здесь.",
    contactCta: "Начать разговор",
    copyright: "© 2006–2026 CV Bayu Santero / Bali Zero. Все права защищены.",
    chapters: [
      "Обложка",
      "Манифест",
      "История",
      "Команда",
      "Услуги",
      "Результаты",
      "Технологии",
      "Контакты",
    ],
    switchLang: "Язык",
  },

  zh: {
    coverTagline: "从CV Bayu Santero（2006）到Bali Zero（2020）",
    coverSubtitle: "印度尼西亚唯一的AI原生机构。",
    scrollDown: "向下滚动",
    manifestoP1:
      "一切始于2006年，当时Pak Zainal Abidin在巴厘岛创立了CV Bayu Santero。十四年来深耕印度尼西亚市场的实战经验——帮助客户、解读法规、一步一个脚印地构建成功案例。",
    manifestoP2:
      "2020年，一次相遇改变了一切。全新愿景与深厚根基结合在一起。Bali Zero由此诞生——不是一家创业公司，而是二十年历史的进化。",
    originP1:
      "Pak Zainal见过各种情况：外国客户迷失在印度尼西亚的繁文缛节中，签证出错，公司以错误的KBLI代码注册，因信息不准确而浪费资金。",
    originP2:
      "与Zero的合作带来了不同的答案：完全的价格透明、3秒内响应的AI技术，以及一支22人的专业团队全力为每位客户服务。",
    teamDepts: {
      leadership: "领导层",
      setup: "商业注册",
      tax: "税务",
      accounting: "会计",
      support: "支持",
    },
    servicesCta: "在WhatsApp咨询",
    servicesCategories: {
      visa: "签证与许可",
      company: "公司注册",
      tax: "税务与合规",
      property: "房产",
    },
    askOnWhatsApp: "在WhatsApp咨询",
    mostPopular: "最受欢迎",
    forCompanies: "适合公司",
    forBusinessOwners: "适合企业家",
    impactBody:
      "竞争对手人员流失（每年-8%至-23%），而Bali Zero持续增长。区别在于：我们是唯一在生产中部署AI技术栈的机构。",
    headcountYoY: "人员年度变化",
    techBody:
      "Zantara不是聊天机器人，而是完整的AI顾问，建立在66,000份索引法律文件、56K节点知识图谱以及印度尼西亚监管生态系统实时数据的基础上。",
    techStats: [
      { n: "96", l: "生产中的MCP工具" },
      { n: "56K", l: "知识图谱节点" },
      { n: "66K+", l: "索引法律文件" },
      { n: "9,612", l: "KBLI 2025代码" },
      { n: "4", l: "AI渠道，全天候" },
      { n: "< 3秒", l: "平均响应时间" },
    ],
    contactBody:
      "无论您需要签证、想要开公司，还是对印度尼西亚法规有疑问——我们随时为您服务。",
    contactCta: "开始对话",
    copyright: "© 2006–2026 CV Bayu Santero / Bali Zero。版权所有。",
    chapters: [
      "封面",
      "宣言",
      "起源",
      "团队",
      "服务",
      "影响力",
      "技术",
      "联系我们",
    ],
    switchLang: "语言",
  },
};
