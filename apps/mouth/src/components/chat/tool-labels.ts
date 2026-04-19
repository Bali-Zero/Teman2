/**
 * Human-readable labels for the agent tools we expose in the chat UI.
 *
 * Built as a flat data structure (not i18n JSON) because the `/chat` route
 * is not currently wrapped in `<I18nProvider>` — see `apps/mouth/src/i18n/index.tsx`.
 * If/when the chat moves under that provider, swap this for `t("chat.tool.<key>")`
 * lookups; the keys here mirror the JSON namespace already added to the
 * locale files for forward compatibility.
 */

import type { Locale } from '@/i18n/types';

type LabelTriple = {
  /** Active form, e.g. "searching emails". Shown while the tool is running. */
  using: string;
  /** Past form, e.g. "searched emails". Shown after the tool completes. */
  done: string;
};

type LabelTable = Record<Locale, LabelTriple>;

const GENERIC: LabelTable = {
  en: { using: 'running tool', done: 'tool finished' },
  it: { using: 'uso uno strumento', done: 'strumento completato' },
  id: { using: 'menjalankan alat', done: 'alat selesai' },
  fr: { using: "exécution de l'outil", done: 'outil terminé' },
  ru: { using: 'запуск инструмента', done: 'инструмент завершён' },
};

const TOOL_LABELS: Record<string, LabelTable> = {
  search_emails: {
    en: { using: 'searching emails', done: 'searched emails' },
    it: { using: 'cerco nelle email', done: 'email controllate' },
    id: { using: 'mencari email', done: 'email diperiksa' },
    fr: { using: 'recherche dans les emails', done: 'emails consultés' },
    ru: { using: 'поиск в письмах', done: 'письма проверены' },
  },
  search_threads: {
    en: { using: 'searching email threads', done: 'searched email threads' },
    it: {
      using: 'cerco le conversazioni email',
      done: 'conversazioni email controllate',
    },
    id: { using: 'mencari thread email', done: 'thread email diperiksa' },
    fr: { using: "recherche des fils d'emails", done: 'fils consultés' },
    ru: { using: 'поиск веток писем', done: 'ветки писем проверены' },
  },
  send_email: {
    en: { using: 'sending email', done: 'email sent' },
    it: { using: 'invio email', done: 'email inviata' },
    id: { using: 'mengirim email', done: 'email terkirim' },
    fr: { using: "envoi de l'email", done: 'email envoyé' },
    ru: { using: 'отправка письма', done: 'письмо отправлено' },
  },
  search_kbli: {
    en: { using: 'looking up KBLI codes', done: 'KBLI lookup complete' },
    it: { using: 'consulto i codici KBLI', done: 'codici KBLI consultati' },
    id: { using: 'mencari kode KBLI', done: 'kode KBLI ditemukan' },
    fr: { using: 'consultation KBLI', done: 'KBLI consultés' },
    ru: { using: 'поиск кодов KBLI', done: 'KBLI готовы' },
  },
  get_pricing: {
    en: { using: 'fetching prices', done: 'prices fetched' },
    it: { using: 'recupero i prezzi', done: 'prezzi caricati' },
    id: { using: 'mengambil harga', done: 'harga ditemukan' },
    fr: { using: 'récupération des prix', done: 'prix récupérés' },
    ru: { using: 'получение цен', done: 'цены получены' },
  },
  search_service_pricing: {
    en: { using: 'searching service prices', done: 'service prices found' },
    it: { using: 'cerco i prezzi del servizio', done: 'prezzi trovati' },
    id: { using: 'mencari harga layanan', done: 'harga layanan ditemukan' },
    fr: { using: 'recherche tarifs', done: 'tarifs trouvés' },
    ru: { using: 'поиск цен услуг', done: 'цены услуг найдены' },
  },
  list_clients: {
    en: { using: 'listing clients', done: 'clients loaded' },
    it: { using: 'elenco i clienti', done: 'clienti caricati' },
    id: { using: 'menampilkan klien', done: 'klien dimuat' },
    fr: { using: 'liste des clients', done: 'clients chargés' },
    ru: { using: 'загрузка клиентов', done: 'клиенты загружены' },
  },
  get_client: {
    en: { using: 'loading client profile', done: 'client loaded' },
    it: { using: 'carico il profilo cliente', done: 'cliente caricato' },
    id: { using: 'memuat profil klien', done: 'klien dimuat' },
    fr: { using: 'chargement du client', done: 'client chargé' },
    ru: { using: 'загрузка клиента', done: 'клиент загружен' },
  },
  search_drive: {
    en: { using: 'searching Drive', done: 'Drive search complete' },
    it: { using: 'cerco su Drive', done: 'ricerca Drive completata' },
    id: { using: 'mencari di Drive', done: 'pencarian Drive selesai' },
    fr: { using: 'recherche dans Drive', done: 'recherche Drive terminée' },
    ru: { using: 'поиск в Drive', done: 'поиск в Drive завершён' },
  },
  list_drive_files: {
    en: { using: 'listing Drive files', done: 'Drive files listed' },
    it: { using: 'elenco i file di Drive', done: 'file Drive elencati' },
    id: { using: 'menampilkan file Drive', done: 'file Drive ditampilkan' },
    fr: { using: 'liste des fichiers Drive', done: 'fichiers listés' },
    ru: { using: 'список файлов Drive', done: 'файлы Drive получены' },
  },
  web_search: {
    en: { using: 'searching the web', done: 'web search complete' },
    it: { using: 'cerco sul web', done: 'ricerca web completata' },
    id: { using: 'mencari di web', done: 'pencarian web selesai' },
    fr: { using: 'recherche web', done: 'recherche web terminée' },
    ru: { using: 'поиск в сети', done: 'поиск завершён' },
  },
  search_intel: {
    en: { using: 'querying intelligence sources', done: 'intelligence ready' },
    it: { using: 'interrogo le fonti intelligence', done: 'intelligence pronta' },
    id: { using: 'memeriksa sumber intel', done: 'intel siap' },
    fr: { using: 'consultation intelligence', done: 'intelligence prête' },
    ru: { using: 'запрос intelligence', done: 'intelligence готова' },
  },
  ask_legal: {
    en: { using: 'consulting legal references', done: 'legal answer ready' },
    it: { using: 'consulto i riferimenti legali', done: 'risposta legale pronta' },
    id: { using: 'memeriksa rujukan hukum', done: 'jawaban hukum siap' },
    fr: { using: 'consultation juridique', done: 'réponse juridique prête' },
    ru: { using: 'юридический поиск', done: 'ответ готов' },
  },
  generate_image: {
    en: { using: 'generating image', done: 'image ready' },
    it: { using: "genero un'immagine", done: 'immagine pronta' },
    id: { using: 'membuat gambar', done: 'gambar siap' },
    fr: { using: "génération d'image", done: 'image prête' },
    ru: { using: 'генерация изображения', done: 'изображение готово' },
  },
};

const FALLBACK_LOCALE: Locale = 'en';

export function getToolLabel(toolName: string, locale: Locale, status: 'running' | 'done'): string {
  const table = TOOL_LABELS[toolName];
  if (table) {
    const entry = table[locale] ?? table[FALLBACK_LOCALE];
    return status === 'running' ? entry.using : entry.done;
  }
  // Unknown tool: surface its raw name with a localised verb.
  const generic = GENERIC[locale] ?? GENERIC[FALLBACK_LOCALE];
  const verb = status === 'running' ? generic.using : generic.done;
  return `${verb}: ${toolName}`;
}

export function isKnownTool(toolName: string): boolean {
  return toolName in TOOL_LABELS;
}
