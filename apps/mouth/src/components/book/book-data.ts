// apps/mouth/src/components/book/book-data.ts
// Single source of truth for all book content.
// EVERY fact here is sourced from verified codebase data or founder confirmation.
// DO NOT add invented content.

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
    title: "5.000 clienti. 6 anni. Un'eredità dal 2006.",
    subtitle:
      "Da CV Bayu Santero a Bali Zero — vent'anni di storia al tuo servizio.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Luxury_gold_to_black_gradient,_smooth_color_transition,_premium_c_4ad0a879-3d92-41e8-beab-ff42dc499fb8.png",
    heroImageAlt: "Manifesto Bali Zero",
  },
  {
    id: "origin",
    index: 2,
    title: "L'incontro che ha cambiato tutto.",
    subtitle:
      "2020. Un bule con una visione. Un imprenditore balinese con 14 anni di esperienza. Insieme.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Dark_luxury_gradient_background,_subtle_gold_foil_texture,_deep_n_4ccbbd81-3a9a-4ab6-b22a-948bb50a73c5.png",
    heroImageAlt: "La storia di Bali Zero",
  },
  {
    id: "team",
    index: 3,
    title: "22 persone. Un obiettivo.",
    subtitle:
      "Esperti locali e internazionali. Tutti dedicati al tuo successo in Indonesia.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Subtle_geometric_pattern,_golden_lines_on_dark_background,_minima_3d95f5d2-0f4e-477c-bc1f-a6f750466cce.png",
    heroImageAlt: "Il team Bali Zero",
  },
  {
    id: "services",
    index: 4,
    title: "Prezzi reali. Nessuna sorpresa.",
    subtitle:
      "Visti, aziende, tasse, proprietà. Tutto trasparente, tutto verificabile.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Modern_checkmark_icon,_golden_gradient,_minimalist_success_symbol_b57bcd74-0803-4cd1-9af7-9caffae712be.png",
    heroImageAlt: "Servizi Bali Zero",
    showZantaraCTA: true,
  },
  {
    id: "impact",
    index: 5,
    title: "L'unica agenzia AI in Indonesia.",
    subtitle: "I competitor shrinkano. Noi cresciamo.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Abstract_AI_brain,_neural_network_visualization,_golden_glowing_c_bf1f9cb1-c9df-481c-9bc7-05928ddf38de.png",
    heroImageAlt: "Impatto Bali Zero",
    showZantaraCTA: true,
  },
  {
    id: "technology",
    index: 6,
    title: "Zantara: il tuo consulente, 24/7.",
    subtitle:
      "L'unico AI assistant nel settore dei servizi legali e di immigrazione in Indonesia.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Elegant_data_flow_visualization,_golden_particles_moving,_dark_te_15e4c14b-15d5-4cae-bb42-622662505408.png",
    heroImageAlt: "Tecnologia Zantara",
    showZantaraCTA: true,
  },
  {
    id: "contact",
    index: 7,
    title: "Il primo passo è semplice.",
    subtitle:
      "Un messaggio. Una chiamata. Il tuo futuro in Indonesia inizia qui.",
    heroImage:
      "/static/image_art/Bali_zero_hq_Dark_luxury_gradient_background,_subtle_gold_foil_texture,_deep_n_6c06b85d-1ad6-4a48-a729-23b80947e173.png",
    heroImageAlt: "Contatti Bali Zero",
  },
];

// Source: apps/mouth/src/app/(blog)/team/page.tsx — verified
export const TEAM_MEMBERS: TeamMember[] = [
  // Leadership
  {
    name: "Zainal Abidin",
    role: "Chief Executive Officer",
    department: "leadership",
    photo: "/static/team/batik_butterfly.jpg",
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
  {
    name: "Surya",
    role: "Specialist Consultant",
    department: "setup",
    photo: "/static/team/batik_kawung_organic.jpg",
  },
  {
    name: "Vino",
    role: "Junior Consultant",
    department: "setup",
    photo: "/static/team/batik_geometric_1.jpg",
  },
  {
    name: "Damar",
    role: "Junior Consultant",
    department: "setup",
    photo: "/static/team/batik_geometric_2.jpg",
  },
  // Tax
  {
    name: "Veronika",
    role: "Tax Manager",
    department: "tax",
    photo: "/static/team/batik_minimalist_1.jpg",
  },
  {
    name: "Angel",
    role: "Tax Expert",
    department: "tax",
    photo: "/static/team/batik_minimalist_2.jpg",
  },
  {
    name: "Kadek",
    role: "Tax Consultant",
    department: "tax",
    photo: "/static/team/batik_kawung.jpg",
  },
  {
    name: "Dewa Ayu",
    role: "Tax Consultant",
    department: "tax",
    photo: "/static/team/batik_truntum.jpg",
  },
  {
    name: "Faisha",
    role: "Tax Care",
    department: "tax",
    photo: "/static/team/batik_kawung_diamond.jpg",
  },
  // Accounting
  {
    name: "Asya Nadia",
    role: "Accounting",
    department: "accounting",
    photo: "/static/team/asya.jpg",
  },
  // Support
  {
    name: "Rina",
    role: "Reception",
    department: "support",
    photo: "/static/team/batik_geometric_1.jpg",
  },
  {
    name: "Sahira",
    role: "Marketing Specialist",
    department: "support",
    photo: "/static/team/sahira.png",
  },
  {
    name: "Nina",
    role: "Marketing Advisory",
    department: "support",
    photo: "/static/team/batik_minimalist_1.jpg",
  },
];

// Source: competitor intelligence report — verified March 2026
export const COMPETITORS: CompetitorStat[] = [
  { name: "Emerhub", founded: 2011, yoyTrend: "-8.5%" },
  { name: "InCorp", founded: 2012, yoyTrend: "-19%" },
  { name: "LetsMoveIndonesia", founded: 2015, yoyTrend: "-23.5%" },
  { name: "Seven Stones", founded: 2016, yoyTrend: "+1.8%" },
];

// Source: founder confirmed / codebase
export const STATS = {
  clients: "5.000+",
  yearsOfHistory: "20+", // 2006 CV Bayu Santero → 2026
  teamSize: 22,
  aiTools: 96, // MCP tools in production
  legalDocs: "66K+", // indexed legal documents
  kbliCodes: "9.612", // KBLI 2025 navigator
  channels: 4, // WhatsApp, Telegram, Web, Instagram
  kbliNavigatorUrl: "https://kita.balizero.com/kbli",
};

// Source: verified from codebase / WhatsApp
export const CONTACTS = {
  whatsapp: "+62 821 3107 363",
  whatsappUrl: "https://wa.me/628213107363",
  email: "info@balizero.com",
  web: "balizero.com",
};

// Source: founder confirmed
export const MILESTONES: Milestone[] = [
  {
    year: "2006",
    label: "CV Bayu Santero",
    description: "Pak Zainal Abidin fonda CV Bayu Santero a Bali. Le radici.",
  },
  {
    year: "2020",
    label: "Nasce Bali Zero",
    description:
      "L'incontro tra Zero e Pak Zainal genera qualcosa di nuovo. Una visione europea, un'expertise locale ventennale.",
  },
  {
    year: "2021",
    label: "Portal clienti",
    description: "Primo sistema di tracking pratiche per i clienti.",
  },
  {
    year: "2023",
    label: "Zantara AI",
    description:
      "Lancio di Zantara — il primo AI assistant del settore in Indonesia. 24/7 su WhatsApp, Telegram, Web.",
  },
  {
    year: "2024",
    label: "KBLI Navigator",
    description:
      "9.612 codici KBLI 2025 indicizzati e navigabili. Unico in Indonesia.",
  },
  {
    year: "2025",
    label: "5.000 clienti",
    description:
      "Superata la soglia dei 5.000 clienti serviti. I competitor shrinkano. Noi cresciamo.",
  },
  {
    year: "2026",
    label: "Il futuro",
    description:
      "Knowledge graph con 56K nodi. 66K documenti legali. L'unica agenzia AI-first in Indonesia.",
  },
];

// Pricing fallback — used when backend is cold-starting.
// Live prices come from usePricingData SWR hook → /api/pricing/calculate
export const PRICING_FALLBACK: Record<string, string> = {
  "B1 Visit Visa": "Rp 5,8M",
  "C317 Single Entry": "Rp 5,8M",
  "E33G Multiple Entry": "Rp 9,5M",
  "KITAS Retirement": "Rp 22M",
  "PT PMA": "Rp 20M",
};

// ─── i18n ────────────────────────────────────────────────────────────────────

export type Locale = "en" | "it" | "id" | "ru" | "zh";

export const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  it: "Italiano",
  id: "Bahasa Indonesia",
  ru: "Русский",
  zh: "中文",
};

export interface BookTranslations {
  chapters: string[];
  coverTagline: string;
  coverSubtitle: string;
  scrollDown: string;
  manifestoP1: string;
  manifestoP2: string;
  originP1: string;
  originP2: string;
  impactBody: string;
  headcountYoY: string;
  techBody: string;
  techStats: { n: string; l: string }[];
  contactBody: string;
  contactCta: string;
  copyright: string;
  askOnWhatsApp: string;
  mostPopular: string;
  forCompanies: string;
  forBusinessOwners: string;
  servicesCategories: {
    visa: string;
    company: string;
    tax: string;
    property: string;
  };
  teamDepts: Record<string, string>;
}

export const TRANSLATIONS: Record<Locale, BookTranslations> = {
  en: {
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
    coverTagline: "Bali Zero — The AI-first Indonesia experts",
    coverSubtitle:
      "Your guide to doing business in Bali, built on 20 years of expertise.",
    scrollDown: "Scroll to explore",
    manifestoP1:
      "It started in 2006 when Pak Zainal Abidin founded CV Bayu Santero in Bali. Fourteen years of experience in the Indonesian market. Clients helped. Regulations navigated. Success stories built brick by brick.",
    manifestoP2:
      "In 2020, a meeting changed everything. A new vision joined deep roots. From that meeting, Bali Zero was born — not a startup, but the evolution of twenty years of history.",
    originP1:
      "Pak Zainal Abidin had seen it all. Foreign clients lost in the Indonesian bureaucratic labyrinth. Wrong visas. Companies set up with wrong KBLI codes. Money wasted through lack of precise information.",
    originP2:
      "The solution was not just more staff — it was intelligence. A system that learns, adapts, and guides every client with precision.",
    impactBody:
      "While competitors lose personnel (−8% to −23% annually), Bali Zero grows. The difference? We are the only ones with an AI stack in production.",
    headcountYoY: "Headcount YoY",
    techBody:
      "Zantara — our AI assistant — runs across 4 channels simultaneously, grounded in a knowledge graph of 56,000 nodes and 10 live vector collections. No hallucinations. Just citations.",
    techStats: [
      { n: "56K", l: "Knowledge graph nodes" },
      { n: "93K", l: "Indexed documents" },
      { n: "4", l: "Live AI channels" },
      { n: "9,612", l: "KBLI 2025 codes" },
      { n: "<2s", l: "Avg. response time" },
      { n: "8/10", l: "RAG quality score" },
    ],
    contactBody:
      "Ready to set up your business in Bali? Our team is available on WhatsApp every day.",
    contactCta:
      "Hi, I found you through the Brand Book and would like to learn more.",
    copyright: "© 2025 Bali Zero · PT Bali Zero Investama",
    askOnWhatsApp: "Ask on WhatsApp",
    mostPopular: "Most popular",
    forCompanies: "For companies",
    forBusinessOwners: "For business owners",
    servicesCategories: {
      visa: "Visa",
      company: "Company Setup",
      tax: "Tax",
      property: "Property",
    },
    teamDepts: {
      leadership: "Leadership",
      setup: "Business Setup",
      tax: "Tax",
      accounting: "Accounting",
      support: "Support",
    },
  },
  it: {
    chapters: [
      "Copertina",
      "Manifesto",
      "Origine",
      "Team",
      "Servizi",
      "Impatto",
      "Tecnologia",
      "Contatti",
    ],
    coverTagline: "Bali Zero — Esperti AI-first in Indonesia",
    coverSubtitle:
      "La tua guida per fare business a Bali, costruita su 20 anni di esperienza.",
    scrollDown: "Scorri per esplorare",
    manifestoP1:
      "Tutto è iniziato nel 2006, quando Pak Zainal Abidin ha fondato CV Bayu Santero a Bali. Quattordici anni di esperienza nel mercato indonesiano.",
    manifestoP2:
      "Nel 2020, un incontro ha cambiato tutto. Da quell'incontro è nato Bali Zero — non una startup, ma l'evoluzione di vent'anni di storia.",
    originP1:
      "Pak Zainal Abidin aveva già visto tutto. Clienti stranieri persi nel labirinto burocratico indonesiano. Visti sbagliati. Aziende aperte con codici KBLI errati.",
    originP2:
      "La soluzione non era solo più personale — era intelligenza. Un sistema che impara, si adatta e guida ogni cliente con precisione.",
    impactBody:
      "Mentre i competitor perdono personale (−8% a −23% annuo), Bali Zero cresce. La differenza? Siamo gli unici con un AI stack in produzione.",
    headcountYoY: "Variazione organico YoY",
    techBody:
      "Zantara — il nostro assistente AI — opera su 4 canali simultaneamente, radicato in un knowledge graph di 56.000 nodi. Nessuna allucinazione. Solo citazioni.",
    techStats: [
      { n: "56K", l: "Nodi knowledge graph" },
      { n: "93K", l: "Documenti indicizzati" },
      { n: "4", l: "Canali AI attivi" },
      { n: "9.612", l: "Codici KBLI 2025" },
      { n: "<2s", l: "Tempo di risposta medio" },
      { n: "8/10", l: "Score qualità RAG" },
    ],
    contactBody:
      "Pronto ad aprire la tua azienda a Bali? Il nostro team è disponibile su WhatsApp ogni giorno.",
    contactCta:
      "Ciao, vi ho trovati attraverso il Brand Book e vorrei saperne di più.",
    copyright: "© 2025 Bali Zero · PT Bali Zero Investama",
    askOnWhatsApp: "Chiedi su WhatsApp",
    mostPopular: "Più richiesto",
    forCompanies: "Per aziende",
    forBusinessOwners: "Per imprenditori",
    servicesCategories: {
      visa: "Visto",
      company: "Apertura Azienda",
      tax: "Fiscale",
      property: "Immobiliare",
    },
    teamDepts: {
      leadership: "Leadership",
      setup: "Business Setup",
      tax: "Fiscale",
      accounting: "Contabilità",
      support: "Supporto",
    },
  },
  id: {
    chapters: [
      "Sampul",
      "Manifesto",
      "Asal-usul",
      "Tim",
      "Layanan",
      "Dampak",
      "Teknologi",
      "Kontak",
    ],
    coverTagline: "Bali Zero — Ahli Indonesia AI-first",
    coverSubtitle:
      "Panduan Anda berbisnis di Bali, dibangun dari 20 tahun pengalaman.",
    scrollDown: "Gulir untuk menjelajahi",
    manifestoP1:
      "Semuanya dimulai pada 2006 ketika Pak Zainal Abidin mendirikan CV Bayu Santero di Bali. Empat belas tahun pengalaman di pasar Indonesia.",
    manifestoP2:
      "Pada 2020, sebuah pertemuan mengubah segalanya. Dari pertemuan itu lahirlah Bali Zero — bukan startup, melainkan evolusi dari dua puluh tahun sejarah.",
    originP1:
      "Pak Zainal Abidin sudah melihat semuanya. Klien asing tersesat dalam labirin birokrasi Indonesia. Visa yang salah. Perusahaan dibuka dengan kode KBLI yang keliru.",
    originP2:
      "Solusinya bukan hanya lebih banyak staf — melainkan kecerdasan. Sistem yang belajar, beradaptasi, dan membimbing setiap klien dengan presisi.",
    impactBody:
      "Sementara pesaing kehilangan personel (−8% hingga −23% per tahun), Bali Zero tumbuh. Perbedaannya? Kami satu-satunya dengan AI stack dalam produksi.",
    headcountYoY: "Perubahan headcount YoY",
    techBody:
      "Zantara — asisten AI kami — beroperasi di 4 saluran secara bersamaan, didukung knowledge graph dengan 56.000 node.",
    techStats: [
      { n: "56K", l: "Node knowledge graph" },
      { n: "93K", l: "Dokumen terindeks" },
      { n: "4", l: "Saluran AI aktif" },
      { n: "9.612", l: "Kode KBLI 2025" },
      { n: "<2d", l: "Waktu respons rata-rata" },
      { n: "8/10", l: "Skor kualitas RAG" },
    ],
    contactBody:
      "Siap mendirikan bisnis Anda di Bali? Tim kami tersedia di WhatsApp setiap hari.",
    contactCta:
      "Halo, saya menemukan Anda melalui Brand Book dan ingin tahu lebih lanjut.",
    copyright: "© 2025 Bali Zero · PT Bali Zero Investama",
    askOnWhatsApp: "Tanya di WhatsApp",
    mostPopular: "Paling populer",
    forCompanies: "Untuk perusahaan",
    forBusinessOwners: "Untuk pemilik usaha",
    servicesCategories: {
      visa: "Visa",
      company: "Pendirian Perusahaan",
      tax: "Pajak",
      property: "Properti",
    },
    teamDepts: {
      leadership: "Kepemimpinan",
      setup: "Business Setup",
      tax: "Pajak",
      accounting: "Akuntansi",
      support: "Dukungan",
    },
  },
  ru: {
    chapters: [
      "Обложка",
      "Манифест",
      "История",
      "Команда",
      "Услуги",
      "Влияние",
      "Технологии",
      "Контакты",
    ],
    coverTagline: "Bali Zero — AI-first эксперты в Индонезии",
    coverSubtitle:
      "Ваш путеводитель по бизнесу на Бали, основанный на 20-летнем опыте.",
    scrollDown: "Прокрутите для изучения",
    manifestoP1:
      "Всё началось в 2006 году, когда Пак Заинал Абидин основал CV Bayu Santero на Бали. Четырнадцать лет опыта на индонезийском рынке.",
    manifestoP2:
      "В 2020 году одна встреча изменила всё. Из этой встречи родился Bali Zero — не стартап, а эволюция двадцати лет истории.",
    originP1:
      "Пак Заинал Абидин видел всё. Иностранные клиенты, потерявшиеся в индонезийском бюрократическом лабиринте. Неправильные визы. Компании с ошибочными кодами KBLI.",
    originP2:
      "Решение — не просто больше сотрудников, а интеллект. Система, которая учится, адаптируется и направляет каждого клиента с точностью.",
    impactBody:
      "Пока конкуренты теряют персонал (−8% до −23% в год), Bali Zero растёт. Разница? Мы единственные с AI-стеком в продакшне.",
    headcountYoY: "Изменение штата г/г",
    techBody:
      "Zantara — наш AI-ассистент — работает на 4 каналах одновременно, основан на графе знаний из 56 000 узлов.",
    techStats: [
      { n: "56К", l: "Узлов в графе знаний" },
      { n: "93К", l: "Индексированных документов" },
      { n: "4", l: "Активных AI-каналов" },
      { n: "9 612", l: "Кодов KBLI 2025" },
      { n: "<2с", l: "Среднее время ответа" },
      { n: "8/10", l: "Оценка качества RAG" },
    ],
    contactBody:
      "Готовы открыть бизнес на Бали? Наша команда доступна в WhatsApp каждый день.",
    contactCta:
      "Привет, я нашёл вас через Brand Book и хотел бы узнать больше.",
    copyright: "© 2025 Bali Zero · PT Bali Zero Investama",
    askOnWhatsApp: "Написать в WhatsApp",
    mostPopular: "Самый популярный",
    forCompanies: "Для компаний",
    forBusinessOwners: "Для владельцев бизнеса",
    servicesCategories: {
      visa: "Виза",
      company: "Открытие компании",
      tax: "Налоги",
      property: "Недвижимость",
    },
    teamDepts: {
      leadership: "Руководство",
      setup: "Регистрация бизнеса",
      tax: "Налоги",
      accounting: "Бухгалтерия",
      support: "Поддержка",
    },
  },
  zh: {
    chapters: ["封面", "宣言", "起源", "团队", "服务", "影响", "技术", "联系"],
    coverTagline: "Bali Zero — 印度尼西亚AI先行专家",
    coverSubtitle: "您的巴厘岛商业指南，建立在20年专业经验之上。",
    scrollDown: "滚动探索",
    manifestoP1:
      "一切始于2006年，Pak Zainal Abidin在巴厘岛创立了CV Bayu Santero。十四年的印度尼西亚市场经验。",
    manifestoP2:
      "2020年，一次相遇改变了一切。从那次相遇中，Bali Zero诞生了——不是初创企业，而是二十年历史的演变。",
    originP1:
      "Pak Zainal Abidin见过一切。外国客户在印度尼西亚繁杂的官僚迷宫中迷失。错误的签证。用错误的KBLI代码成立的公司。",
    originP2:
      "解决方案不只是更多员工——而是智慧。一个学习、适应并精准指导每位客户的系统。",
    impactBody:
      "当竞争对手失去员工（每年-8%至-23%）时，Bali Zero在增长。原因是什么？我们是唯一在生产中拥有AI技术栈的公司。",
    headcountYoY: "年度人员变化",
    techBody:
      "Zantara——我们的AI助手——同时在4个频道上运行，基于拥有56,000个节点的知识图谱。没有幻觉，只有引用。",
    techStats: [
      { n: "5.6万", l: "知识图谱节点" },
      { n: "9.3万", l: "已索引文档" },
      { n: "4", l: "活跃AI频道" },
      { n: "9,612", l: "KBLI 2025代码" },
      { n: "<2秒", l: "平均响应时间" },
      { n: "8/10", l: "RAG质量评分" },
    ],
    contactBody:
      "准备好在巴厘岛建立您的业务了吗？我们的团队每天在WhatsApp上为您服务。",
    contactCta: "您好，我通过品牌手册找到了您，想了解更多信息。",
    copyright: "© 2025 Bali Zero · PT Bali Zero Investama",
    askOnWhatsApp: "在WhatsApp上咨询",
    mostPopular: "最受欢迎",
    forCompanies: "面向公司",
    forBusinessOwners: "面向企业主",
    servicesCategories: {
      visa: "签证",
      company: "公司注册",
      tax: "税务",
      property: "房产",
    },
    teamDepts: {
      leadership: "领导层",
      setup: "企业设立",
      tax: "税务",
      accounting: "会计",
      support: "支持",
    },
  },
};

// ─── Services ─────────────────────────────────────────────────────────────────

export interface Service {
  serviceKey: string;
  title: string;
  tagline: string;
  category: "visa" | "company" | "tax" | "property";
  features: string[];
  waMessage: string;
  badge?: string;
}

export const SERVICES: Service[] = [
  {
    serviceKey: "b1-visit-visa",
    title: "B1 Visit Visa",
    tagline: "Short-term business visits",
    category: "visa",
    features: [
      "Single entry",
      "Up to 60 days",
      "Business activities allowed",
      "Fast processing",
    ],
    waMessage:
      "Hi, I am interested in the B1 Visit Visa. Can you give me more info?",
    badge: "Most popular",
  },
  {
    serviceKey: "c317-single-entry",
    title: "C317 Single Entry",
    tagline: "Short stay tourist & business",
    category: "visa",
    features: ["Single entry", "Up to 60 days", "Extendable", "Simple process"],
    waMessage:
      "Hi, I am interested in the C317 Single Entry visa. Can you give me more info?",
  },
  {
    serviceKey: "e33g-multiple-entry",
    title: "E33G Multiple Entry",
    tagline: "Flexible long-term visa",
    category: "visa",
    features: [
      "Multiple entries",
      "Up to 180 days total",
      "Business & leisure",
      "No sponsor needed",
    ],
    waMessage:
      "Hi, I am interested in the E33G Multiple Entry visa. Can you give me more info?",
  },
  {
    serviceKey: "kitas-retirement",
    title: "KITAS Retirement",
    tagline: "Long-term stay for retirees",
    category: "visa",
    features: [
      "1-year renewable",
      "For 55+ years old",
      "No work permit needed",
      "Full support",
    ],
    waMessage:
      "Hi, I am interested in the KITAS Retirement visa. Can you give me more info?",
  },
  {
    serviceKey: "pt-pma",
    title: "PT PMA",
    tagline: "Foreign investment company",
    category: "company",
    features: [
      "100% foreign ownership possible",
      "Full legal entity",
      "KBLI code selection",
      "NIB & licenses",
    ],
    waMessage:
      "Hi, I am interested in setting up a PT PMA. Can you give me more info?",
    badge: "Most popular",
  },
  {
    serviceKey: "cv-setup",
    title: "CV Setup",
    tagline: "Local partnership company",
    category: "company",
    features: [
      "Indonesian partnership",
      "Lower cost",
      "Fast setup",
      "NIB included",
    ],
    waMessage:
      "Hi, I am interested in setting up a CV. Can you give me more info?",
  },
  {
    serviceKey: "tax-compliance",
    title: "Annual Tax Compliance",
    tagline: "SPT & reporting done right",
    category: "tax",
    features: [
      "SPT Tahunan filing",
      "VAT reporting",
      "Withholding tax",
      "Deadline management",
    ],
    waMessage:
      "Hi, I am interested in annual tax compliance services. Can you give me more info?",
    badge: "For companies",
  },
  {
    serviceKey: "tax-id",
    title: "NPWP Registration",
    tagline: "Indonesian tax ID for foreigners",
    category: "tax",
    features: [
      "Individual NPWP",
      "Company NPWP",
      "Fast registration",
      "Online process",
    ],
    waMessage:
      "Hi, I am interested in NPWP registration. Can you give me more info?",
  },
  {
    serviceKey: "property-advisory",
    title: "Property Advisory",
    tagline: "Safe property acquisition in Bali",
    category: "property",
    features: [
      "Due diligence",
      "Title verification",
      "Nominee structure",
      "Legal protection",
    ],
    waMessage:
      "Hi, I am interested in property advisory services. Can you give me more info?",
    badge: "For business owners",
  },
  {
    serviceKey: "property-lease",
    title: "Lease Agreement",
    tagline: "Secure long-term leases",
    category: "property",
    features: [
      "Notarized contract",
      "Up to 25+25 years",
      "English translation",
      "Full legal review",
    ],
    waMessage:
      "Hi, I am interested in lease agreement services. Can you give me more info?",
  },
];
