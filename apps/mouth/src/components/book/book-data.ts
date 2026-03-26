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
  department: 'leadership' | 'setup' | 'tax' | 'accounting' | 'support';
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
    id: 'cover',
    index: 0,
    title: 'Bali Zero',
    subtitle: '',
    heroImage: '/static/image_art/zantara_gold_black_gradient_transparent.png',
    heroImageAlt: 'Bali Zero',
  },
  {
    id: 'manifesto',
    index: 1,
    title: "5.000 clienti. 6 anni. Un'eredità dal 2006.",
    subtitle: "Da CV Bayu Santero a Bali Zero — vent'anni di storia al tuo servizio.",
    heroImage:
      '/static/image_art/Bali_zero_hq_Luxury_gold_to_black_gradient,_smooth_color_transition,_premium_c_4ad0a879-3d92-41e8-beab-ff42dc499fb8.png',
    heroImageAlt: 'Manifesto Bali Zero',
  },
  {
    id: 'origin',
    index: 2,
    title: "L'incontro che ha cambiato tutto.",
    subtitle: "2020. Un bule con una visione. Un imprenditore balinese con 14 anni di esperienza. Insieme.",
    heroImage:
      '/static/image_art/Bali_zero_hq_Dark_luxury_gradient_background,_subtle_gold_foil_texture,_deep_n_4ccbbd81-3a9a-4ab6-b22a-948bb50a73c5.png',
    heroImageAlt: 'La storia di Bali Zero',
  },
  {
    id: 'team',
    index: 3,
    title: '22 persone. Un obiettivo.',
    subtitle: 'Esperti locali e internazionali. Tutti dedicati al tuo successo in Indonesia.',
    heroImage:
      '/static/image_art/Bali_zero_hq_Subtle_geometric_pattern,_golden_lines_on_dark_background,_minima_3d95f5d2-0f4e-477c-bc1f-a6f750466cce.png',
    heroImageAlt: 'Il team Bali Zero',
  },
  {
    id: 'services',
    index: 4,
    title: 'Prezzi reali. Nessuna sorpresa.',
    subtitle: 'Visti, aziende, tasse, proprietà. Tutto trasparente, tutto verificabile.',
    heroImage:
      '/static/image_art/Bali_zero_hq_Modern_checkmark_icon,_golden_gradient,_minimalist_success_symbol_b57bcd74-0803-4cd1-9af7-9caffae712be.png',
    heroImageAlt: 'Servizi Bali Zero',
    showZantaraCTA: true,
  },
  {
    id: 'impact',
    index: 5,
    title: "L'unica agenzia AI in Indonesia.",
    subtitle: 'I competitor shrinkano. Noi cresciamo.',
    heroImage:
      '/static/image_art/Bali_zero_hq_Abstract_AI_brain,_neural_network_visualization,_golden_glowing_c_bf1f9cb1-c9df-481c-9bc7-05928ddf38de.png',
    heroImageAlt: 'Impatto Bali Zero',
    showZantaraCTA: true,
  },
  {
    id: 'technology',
    index: 6,
    title: 'Zantara: il tuo consulente, 24/7.',
    subtitle: "L'unico AI assistant nel settore dei servizi legali e di immigrazione in Indonesia.",
    heroImage:
      '/static/image_art/Bali_zero_hq_Elegant_data_flow_visualization,_golden_particles_moving,_dark_te_15e4c14b-15d5-4cae-bb42-622662505408.png',
    heroImageAlt: 'Tecnologia Zantara',
    showZantaraCTA: true,
  },
  {
    id: 'contact',
    index: 7,
    title: 'Il primo passo è semplice.',
    subtitle: 'Un messaggio. Una chiamata. Il tuo futuro in Indonesia inizia qui.',
    heroImage:
      '/static/image_art/Bali_zero_hq_Dark_luxury_gradient_background,_subtle_gold_foil_texture,_deep_n_6c06b85d-1ad6-4a48-a729-23b80947e173.png',
    heroImageAlt: 'Contatti Bali Zero',
  },
];

// Source: apps/mouth/src/app/(blog)/team/page.tsx — verified
export const TEAM_MEMBERS: TeamMember[] = [
  // Leadership
  { name: 'Zainal Abidin', role: 'Chief Executive Officer', department: 'leadership' },
  { name: 'Ruslana', role: 'Board Member', department: 'leadership', photo: '/static/team/ruslana.jpg' },
  // Setup
  { name: 'Adit', role: 'Supervisor (Lead Setup)', department: 'setup', photo: '/static/team/adit.png' },
  { name: 'Anton', role: 'Executive Consultant', department: 'setup' },
  { name: 'Krisna', role: 'Executive Consultant', department: 'setup', photo: '/static/team/krisna.png' },
  { name: 'Dea', role: 'Executive Consultant', department: 'setup', photo: '/static/team/dea.png' },
  { name: 'Ari', role: 'Specialist Consultant', department: 'setup', photo: '/static/team/ari.png' },
  { name: 'Surya', role: 'Specialist Consultant', department: 'setup' },
  { name: 'Anna', role: 'Specialist Advisor', department: 'setup', photo: '/static/team/anna.jpeg' },
  { name: 'Marta', role: 'Setup Consultant', department: 'setup', photo: '/static/team/marta.jpeg' },
  { name: 'Olena', role: 'Setup Consultant', department: 'setup', photo: '/static/team/olena.jpeg' },
  { name: 'Vino', role: 'Junior Consultant', department: 'setup' },
  { name: 'Damar', role: 'Junior Consultant', department: 'setup' },
  // Tax
  { name: 'Veronika', role: 'Tax Manager', department: 'tax' },
  { name: 'Angel', role: 'Tax Expert', department: 'tax' },
  { name: 'Kadek', role: 'Tax Consultant', department: 'tax' },
  { name: 'Dewa Ayu', role: 'Tax Consultant', department: 'tax' },
  { name: 'Faisha', role: 'Tax Care', department: 'tax' },
  // Accounting
  { name: 'Asya Nadia', role: 'Accounting', department: 'accounting', photo: '/static/team/asya.jpg' },
  // Support
  { name: 'Rina', role: 'Reception', department: 'support' },
  { name: 'Sahira', role: 'Marketing Specialist', department: 'support', photo: '/static/team/sahira.png' },
  { name: 'Nina', role: 'Marketing Advisory', department: 'support' },
];

// Source: competitor intelligence report — verified March 2026
export const COMPETITORS: CompetitorStat[] = [
  { name: 'Emerhub', founded: 2011, yoyTrend: '-8.5%' },
  { name: 'InCorp', founded: 2012, yoyTrend: '-19%' },
  { name: 'LetsMoveIndonesia', founded: 2015, yoyTrend: '-23.5%' },
  { name: 'Seven Stones', founded: 2016, yoyTrend: '+1.8%' },
];

// Source: founder confirmed / codebase
export const STATS = {
  clients: '5.000+',
  yearsOfHistory: '20+', // 2006 CV Bayu Santero → 2026
  teamSize: 22,
  aiTools: 96, // MCP tools in production
  legalDocs: '66K+', // indexed legal documents
  kbliCodes: '9.612', // KBLI 2025 navigator
  channels: 4, // WhatsApp, Telegram, Web, Instagram
};

// Source: verified from codebase / WhatsApp
export const CONTACTS = {
  whatsapp: '+62 859 0436 9574',
  whatsappUrl: 'https://wa.me/6285904369574',
  email: 'info@balizero.com',
  web: 'balizero.com',
};

// Source: founder confirmed
export const MILESTONES: Milestone[] = [
  {
    year: '2006',
    label: 'CV Bayu Santero',
    description: 'Pak Zainal Abidin fonda CV Bayu Santero a Bali. Le radici.',
  },
  {
    year: '2020',
    label: 'Nasce Bali Zero',
    description:
      "L'incontro tra Zero e Pak Zainal genera qualcosa di nuovo. Una visione europea, un'expertise locale ventennale.",
  },
  {
    year: '2021',
    label: 'Portal clienti',
    description: 'Primo sistema di tracking pratiche per i clienti.',
  },
  {
    year: '2023',
    label: 'Zantara AI',
    description:
      'Lancio di Zantara — il primo AI assistant del settore in Indonesia. 24/7 su WhatsApp, Telegram, Web.',
  },
  {
    year: '2024',
    label: 'KBLI Navigator',
    description: '9.612 codici KBLI 2025 indicizzati e navigabili. Unico in Indonesia.',
  },
  {
    year: '2025',
    label: '5.000 clienti',
    description: 'Superata la soglia dei 5.000 clienti serviti. I competitor shrinkano. Noi cresciamo.',
  },
  {
    year: '2026',
    label: 'Il futuro',
    description:
      "Knowledge graph con 56K nodi. 66K documenti legali. L'unica agenzia AI-first in Indonesia.",
  },
];

// Pricing fallback — used when backend is cold-starting.
// Live prices come from usePricingData SWR hook → /api/pricing/calculate
export const PRICING_FALLBACK: Record<string, string> = {
  'B1 Visit Visa': 'Rp 5,8M',
  'C317 Single Entry': 'Rp 5,8M',
  'E33G Multiple Entry': 'Rp 9,5M',
  'KITAS Retirement': 'Rp 22M',
  'PT PMA': 'Rp 20M',
};
