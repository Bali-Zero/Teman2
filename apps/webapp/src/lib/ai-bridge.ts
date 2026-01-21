/**
 * AIBridge - Singleton per gestire l'accesso a Gemini Nano tramite window.ai
 *
 * Gestisce:
 * - Controllo di window.ai, window.model e varianti vendor-prefixed
 * - Inizializzazione asincrona del language model
 * - Monitoraggio automatico del download quando necessario
 * - Verifica del supporto per mostrare all'utente se attivare i flag Chrome
 */

// Tipi per window.ai API
interface AICapabilities {
  available: 'immediate' | 'after-download' | 'no';
}

interface AIModel {
  prompt(prompt: string, options?: any): Promise<any>;
  streamPrompt?(prompt: string, options?: any): AsyncIterable<any>;
}

interface AIAPI {
  model?: AIModel;
  capabilities(): AICapabilities;
}

// Estensione della Window interface per TypeScript
declare global {
  interface Window {
    ai?: AIAPI;
    model?: AIModel;
    // Vendor-prefixed variants
    webkitAI?: AIAPI;
    mozAI?: AIAPI;
    msAI?: AIAPI;
  }
}

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

class AIBridge {
  private static instance: AIBridge | null = null;
  private modelPromise: Promise<AIModel> | null = null;
  private isInitialized: boolean = false;
  private initializationError: Error | null = null;
  private downloadProgress: number = 0;
  private isDownloading: boolean = false;

  // Configurazione logging (disattivabile in produzione)
  private readonly enableDebugLogs: boolean = true;
  private readonly logPrefix = '[AIBridge]';

  private constructor() {
    this.log('debug', 'AIBridge singleton creato');
  }

  /**
   * Ottiene l'istanza singleton di AIBridge
   */
  public static getInstance(): AIBridge {
    if (!AIBridge.instance) {
      AIBridge.instance = new AIBridge();
    }
    return AIBridge.instance;
  }

  /**
   * Verifica se Gemini Nano è supportato nel browser corrente
   * @returns true se window.ai è disponibile, false altrimenti
   */
  public isSupported(): boolean {
    const aiAPI = this.getAIAPI();
    const supported = aiAPI !== null;

    this.log('debug', `isSupported() -> ${supported}`);

    if (!supported) {
      this.log(
        'info',
        'Gemini Nano non supportato. Attiva i flag Chrome: chrome://flags/#optimize-webui'
      );
    }

    return supported;
  }

  /**
   * Ottiene il language model, attendendo l'inizializzazione se necessario
   * @returns Promise che risolve con il modello AIModel
   * @throws Error se il modello non è disponibile o l'inizializzazione fallisce
   */
  public async getLanguageModel(): Promise<AIModel> {
    this.log('debug', 'getLanguageModel() chiamato');

    // Se già inizializzato, ritorna il modello immediatamente
    if (this.isInitialized && this.modelPromise) {
      try {
        const model = await this.modelPromise;
        this.log('debug', 'getLanguageModel() -> modello già inizializzato');
        return model;
      } catch (error) {
        // Se c'è stato un errore precedente, riprova l'inizializzazione
        this.log('warn', 'Errore precedente rilevato, riprovo inizializzazione');
        this.isInitialized = false;
        this.modelPromise = null;
      }
    }

    // Se c'è già un'inizializzazione in corso, attendila
    if (this.modelPromise && !this.isInitialized) {
      this.log('debug', 'getLanguageModel() -> attendo inizializzazione esistente');
      return this.modelPromise;
    }

    // Avvia nuova inizializzazione
    this.log('info', 'Avvio inizializzazione del language model');
    this.modelPromise = this.initializeModel();

    try {
      const model = await this.modelPromise;
      this.isInitialized = true;
      this.initializationError = null;
      this.log('info', 'Language model inizializzato con successo');
      return model;
    } catch (error) {
      this.initializationError = error instanceof Error ? error : new Error(String(error));
      this.log('error', `Errore durante inizializzazione: ${this.initializationError.message}`);
      throw this.initializationError;
    }
  }

  /**
   * Ottiene lo stato del download (se in corso)
   */
  public getDownloadProgress(): number {
    return this.downloadProgress;
  }

  /**
   * Verifica se il download è in corso
   */
  public isDownloadingModel(): boolean {
    return this.isDownloading;
  }

  /**
   * Ottiene l'ultimo errore di inizializzazione (se presente)
   */
  public getLastError(): Error | null {
    return this.initializationError;
  }

  /**
   * Resetta lo stato del bridge (utile per testing o retry)
   */
  public reset(): void {
    this.log('info', 'Reset dello stato del bridge');
    this.isInitialized = false;
    this.modelPromise = null;
    this.initializationError = null;
    this.downloadProgress = 0;
    this.isDownloading = false;
  }

  /**
   * Trova l'API window.ai disponibile (controlla anche varianti vendor-prefixed)
   */
  private getAIAPI(): AIAPI | null {
    // Controlla window.ai (standard)
    if (window.ai) {
      this.log('debug', 'Trovato window.ai (standard)');
      return window.ai;
    }

    // Controlla varianti vendor-prefixed
    if (window.webkitAI) {
      this.log('debug', 'Trovato window.webkitAI');
      return window.webkitAI;
    }

    if (window.mozAI) {
      this.log('debug', 'Trovato window.mozAI');
      return window.mozAI;
    }

    if (window.msAI) {
      this.log('debug', 'Trovato window.msAI');
      return window.msAI;
    }

    // Controlla anche window.model come fallback
    if (window.model) {
      this.log('debug', 'Trovato window.model (fallback)');
      // Crea un wrapper per compatibilità
      return {
        model: window.model,
        capabilities: () => ({ available: 'immediate' as const }),
      };
    }

    this.log('debug', 'Nessuna API window.ai trovata');
    return null;
  }

  /**
   * Inizializza il modello, gestendo anche il caso di download necessario
   */
  private async initializeModel(): Promise<AIModel> {
    const aiAPI = this.getAIAPI();

    if (!aiAPI) {
      throw new Error(
        'Gemini Nano non è disponibile. ' +
          'Assicurati di avere Chrome con i flag attivati: chrome://flags/#optimize-webui'
      );
    }

    // Controlla le capabilities
    const capabilities = aiAPI.capabilities();
    this.log('debug', `Capabilities disponibili: ${capabilities.available}`);

    // Se il modello è già disponibile immediatamente
    if (capabilities.available === 'immediate') {
      if (aiAPI.model) {
        this.log('info', 'Modello disponibile immediatamente');
        return aiAPI.model;
      } else {
        throw new Error('API disponibile ma modello non trovato');
      }
    }

    // Se il modello non è disponibile
    if (capabilities.available === 'no') {
      throw new Error(
        'Gemini Nano non è disponibile su questo dispositivo. ' +
          'Verifica che il tuo browser supporti questa funzionalità.'
      );
    }

    // Se il modello richiede download ('after-download')
    if (capabilities.available === 'after-download') {
      this.log('info', 'Modello richiede download, avvio monitoraggio...');
      return this.handleDownloadAndInitialize(aiAPI);
    }

    // Caso non previsto
    throw new Error(`Stato capabilities non riconosciuto: ${capabilities.available}`);
  }

  /**
   * Gestisce il download del modello e monitora il progresso
   */
  private async handleDownloadAndInitialize(aiAPI: AIAPI): Promise<AIModel> {
    this.isDownloading = true;
    this.downloadProgress = 0;

    this.log('info', 'Inizio monitoraggio download del modello...');

    // Polling per verificare quando il modello diventa disponibile
    const maxAttempts = 300; // 5 minuti max (300 * 1000ms)
    const pollInterval = 1000; // 1 secondo
    let attempts = 0;

    return new Promise<AIModel>((resolve, reject) => {
      const checkModel = () => {
        attempts++;

        // Aggiorna progresso simulato (in realtà non abbiamo un API per il progresso reale)
        // Possiamo solo verificare quando diventa disponibile
        this.downloadProgress = Math.min(95, (attempts / maxAttempts) * 100);

        this.log(
          'debug',
          `Tentativo ${attempts}/${maxAttempts} - Verifica disponibilità modello...`
        );

        // Verifica se il modello è ora disponibile
        const currentCapabilities = aiAPI.capabilities();

        if (currentCapabilities.available === 'immediate') {
          if (aiAPI.model) {
            this.downloadProgress = 100;
            this.isDownloading = false;
            this.log('info', `Modello scaricato e disponibile dopo ${attempts} tentativi`);
            resolve(aiAPI.model);
            return;
          }
        }

        // Timeout dopo max tentativi
        if (attempts >= maxAttempts) {
          this.isDownloading = false;
          this.downloadProgress = 0;
          const error = new Error(
            `Timeout durante il download del modello. ` +
              `Il modello potrebbe richiedere più tempo o potrebbe esserci un problema di connessione.`
          );
          this.log('error', error.message);
          reject(error);
          return;
        }

        // Continua il polling
        setTimeout(checkModel, pollInterval);
      };

      // Avvia il polling
      checkModel();
    });
  }

  /**
   * Sistema di logging per debug
   * Note: In webapp context, console.* is acceptable for browser debugging
   * This is a client-side utility that runs in the browser
   */
  private log(level: LogLevel, message: string, ...args: any[]): void {
    if (!this.enableDebugLogs && level === 'debug') {
      return;
    }

    const timestamp = new Date().toISOString();
    const logMessage = `${this.logPrefix} [${timestamp}] [${level.toUpperCase()}] ${message}`;

    // eslint-disable-next-line no-console
    switch (level) {
      case 'debug':
        // eslint-disable-next-line no-console
        console.debug(logMessage, ...args);
        break;
      case 'info':
        // eslint-disable-next-line no-console
        console.info(logMessage, ...args);
        break;
      case 'warn':
        // eslint-disable-next-line no-console
        console.warn(logMessage, ...args);
        break;
      case 'error':
        // eslint-disable-next-line no-console
        console.error(logMessage, ...args);
        break;
    }
  }
}

// Esporta l'istanza singleton e funzioni di utilità
export const aiBridge = AIBridge.getInstance();

/**
 * Verifica se Gemini Nano è supportato
 * @returns true se supportato, false altrimenti
 */
export function isSupported(): boolean {
  return aiBridge.isSupported();
}

/**
 * Ottiene il language model (convenience function)
 * @returns Promise che risolve con il modello AIModel
 */
export async function getLanguageModel(): Promise<AIModel> {
  return aiBridge.getLanguageModel();
}

// Esporta anche la classe per uso avanzato
export { AIBridge };
export type { AIModel, AIAPI, AICapabilities };
