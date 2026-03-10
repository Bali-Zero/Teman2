/**
 * GOOGLE APPS SCRIPT - RIORGANIZZAZIONE CRM
 *
 * Questo script riorganizza automaticamente tutti i clienti nella cartella CRM
 * Crea struttura pulita: Cliente/01_Passport/02_Company/03_Other_Documents
 *
 * ISTRUZIONI:
 * 1. Apri Google Drive web: https://drive.google.com
 * 2. Extensions → Apps Script
 * 3. Nuovo progetto
 * 4. Copia/incolla questo codice
 * 5. Salva (Ctrl+S)
 * 6. Run → Seleziona "dryRun" per vedere cosa farebbe
 * 7. Autorizza quando richiesto
 * 8. Guarda i log (View → Logs)
 * 9. Se OK, run "execute" per eseguire realmente
 */

// ============================================================================
// CONFIGURAZIONE
// ============================================================================

const CONFIG = {
  CRM_FOLDER_ID: '1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl',

  // Cartelle da escludere (non sono clienti)
  TEAM_FOLDERS: [
    'MAS ADIT', 'OM YOYOK', 'Om Oman', 'MAS ADI', 'OM FIRDA',
    'Titip Punya ARI FIRDA', 'FIRDA', 'ARI', 'MAS YOYOK',
    'Titip Punya Rina', 'Titip Punya Vino', 'Titip Punya'
  ],

  UTILITY_FOLDERS: [
    'Bali Zero', 'Draft', 'Foto', 'BS', 'Backup', 'Archive',
    'Template', 'Samples', 'Test', 'Old', 'Downloads', '.DS_Store'
  ],

  CATEGORY_FOLDERS: [
    'COMPANY', 'INDIVIDUAL', 'DATA BS', 'DATA ADI',
    'EXTEND VISA', 'ADITYA', 'ANGEL', 'MEGI', 'NOVI', 'YANTI'
  ],

  VISA_TYPES: ['ALTUS', 'ITAS', 'KITAP', 'KITAS', 'E-VISA', 'VOA'],

  STATUS_FOLDERS: ['Done', 'On Proses', 'Pending', 'Rejected', 'Cancelled'],

  // Keywords per categorizzazione file
  PASSPORT_KEYWORDS: ['passport', 'paspor', 'pp', 'pasaporte'],
  COMPANY_KEYWORDS: ['pt', 'pma', 'cv', 'company', 'perusahaan', 'npwp', 'nib', 'akta', 'deed']
};

// ============================================================================
// FUNZIONI UTILITY
// ============================================================================

function isClientFolder(name, parentPath) {
  /**
   * Determina se una cartella è un cliente
   */

  // Escludi categorie top-level
  if (CONFIG.CATEGORY_FOLDERS.includes(name)) return false;

  // Escludi lavoratori
  if (CONFIG.TEAM_FOLDERS.includes(name)) return false;

  // Escludi se contiene "titip"
  if (name.toLowerCase().includes('titip')) return false;

  // Escludi utility
  if (CONFIG.UTILITY_FOLDERS.includes(name)) return false;

  // Escludi visa types
  if (CONFIG.VISA_TYPES.includes(name)) return false;

  // Escludi status
  if (CONFIG.STATUS_FOLDERS.includes(name)) return false;

  // Escludi se parent contiene lavoratori o titip
  if (CONFIG.TEAM_FOLDERS.some(worker => parentPath.includes(worker))) return false;
  if (parentPath.toLowerCase().includes('titip')) return false;

  // Se parent è status o visa type, probabile cliente
  const parentParts = parentPath.split('/');
  if (parentParts.some(part => CONFIG.STATUS_FOLDERS.includes(part))) return true;
  if (parentParts.some(part => CONFIG.VISA_TYPES.includes(part))) return true;

  return true;
}

function categorizeFile(filename) {
  /**
   * Categorizza file in 01/02/03
   */
  const lowerName = filename.toLowerCase();

  // Passport
  if (CONFIG.PASSPORT_KEYWORDS.some(kw => lowerName.includes(kw))) {
    return '01_Passport';
  }

  // Company
  if (CONFIG.COMPANY_KEYWORDS.some(kw => lowerName.includes(kw))) {
    return '02_Company';
  }

  // Default
  return '03_Other_Documents';
}

// ============================================================================
// SCAN RICORSIVO
// ============================================================================

function scanFolderRecursive(folderId, path = '', depth = 0, maxDepth = 10) {
  /**
   * Scansiona ricorsivamente per trovare clienti
   */

  if (depth > maxDepth) return [];

  const clients = [];

  try {
    const folder = DriveApp.getFolderById(folderId);
    const subfolders = folder.getFolders();

    while (subfolders.hasNext()) {
      const subfolder = subfolders.next();
      const name = subfolder.getName();
      const currentPath = path ? `${path}/${name}` : name;

      // Check se è cliente
      if (isClientFolder(name, path)) {
        // Conta file
        const files = subfolder.getFiles();
        const fileList = [];

        while (files.hasNext()) {
          const file = files.next();
          fileList.push({
            id: file.getId(),
            name: file.getName(),
            mimeType: file.getMimeType()
          });
        }

        if (fileList.length > 0) {
          clients.push({
            name: name,
            id: subfolder.getId(),
            path: currentPath,
            fileCount: fileList.length,
            files: fileList
          });
        }
      }

      // Scan ricorsivo
      const subClients = scanFolderRecursive(subfolder.getId(), currentPath, depth + 1, maxDepth);
      clients.push(...subClients);
    }

  } catch (e) {
    Logger.log(`❌ Errore scanning ${path}: ${e.message}`);
  }

  return clients;
}

// ============================================================================
// RIORGANIZZAZIONE
// ============================================================================

function createClientStructure(crmFolder, clientName) {
  /**
   * Crea struttura 01/02/03 per cliente
   */

  // Crea cartella cliente nella root CRM
  const clientFolder = crmFolder.createFolder(clientName);

  // Crea 3 sottocartelle
  const passport = clientFolder.createFolder('01_Passport');
  const company = clientFolder.createFolder('02_Company');
  const other = clientFolder.createFolder('03_Other_Documents');

  return {
    client: clientFolder,
    folders: {
      '01_Passport': passport,
      '02_Company': company,
      '03_Other_Documents': other
    }
  };
}

function moveFile(fileId, targetFolderId, sourceFolderId) {
  /**
   * Muovi file da source a target
   */
  try {
    const file = DriveApp.getFileById(fileId);
    const targetFolder = DriveApp.getFolderById(targetFolderId);
    const sourceFolder = DriveApp.getFolderById(sourceFolderId);

    file.moveTo(targetFolder);
    return true;
  } catch (e) {
    Logger.log(`❌ Errore moving file: ${e.message}`);
    return false;
  }
}

function processClient(crmFolder, client, dryRun = true) {
  /**
   * Processa un cliente: crea struttura e muove file
   */

  if (dryRun) {
    Logger.log(`   [DRY] ${client.name} (${client.fileCount} files)`);

    // Mostra categorizzazione file
    const categories = { '01_Passport': 0, '02_Company': 0, '03_Other_Documents': 0 };
    client.files.forEach(file => {
      const category = categorizeFile(file.name);
      categories[category]++;
    });

    Logger.log(`         → Passport: ${categories['01_Passport']}, Company: ${categories['02_Company']}, Other: ${categories['03_Other_Documents']}`);

    return client.fileCount;
  }

  // Esecuzione reale
  Logger.log(`   [EXEC] ${client.name} (${client.fileCount} files)`);

  try {
    // Crea struttura
    const structure = createClientStructure(crmFolder, client.name);

    // Muovi file
    let filesMoved = 0;
    client.files.forEach(file => {
      const category = categorizeFile(file.name);
      const targetFolder = structure.folders[category];

      if (moveFile(file.id, targetFolder.getId(), client.id)) {
        filesMoved++;
      }
    });

    Logger.log(`         → Mossi ${filesMoved}/${client.fileCount} file`);
    return filesMoved;

  } catch (e) {
    Logger.log(`   ❌ Errore processing ${client.name}: ${e.message}`);
    return 0;
  }
}

// ============================================================================
// FUNZIONI PRINCIPALI
// ============================================================================

function dryRun() {
  /**
   * DRY RUN - Mostra cosa farebbe SENZA modificare
   */

  Logger.log('================================================================================');
  Logger.log('🔍 DRY RUN - RIORGANIZZAZIONE CRM');
  Logger.log('================================================================================\n');

  Logger.log('📂 Scansione CRM folder...');
  Logger.log('   Questo può richiedere 5-15 minuti...\n');

  const startTime = new Date();

  // Scan
  const clients = scanFolderRecursive(CONFIG.CRM_FOLDER_ID);

  // Ordina alfabeticamente
  clients.sort((a, b) => a.name.localeCompare(b.name));

  const scanTime = (new Date() - startTime) / 1000;

  Logger.log(`\n✅ Scan completato in ${scanTime.toFixed(1)}s`);
  Logger.log(`   Clienti trovati: ${clients.length}`);
  Logger.log(`   File totali: ${clients.reduce((sum, c) => sum + c.fileCount, 0)}\n`);

  Logger.log('================================================================================');
  Logger.log('📋 PRIMI 30 CLIENTI');
  Logger.log('================================================================================\n');

  clients.slice(0, 30).forEach((client, i) => {
    Logger.log(`${(i+1).toString().padStart(3)}. ${client.name.padEnd(40)} (${client.fileCount} file)`);
  });

  if (clients.length > 30) {
    Logger.log(`\n... e altri ${clients.length - 30} clienti`);
  }

  Logger.log('\n================================================================================');
  Logger.log('💡 SIMULAZIONE RIORGANIZZAZIONE');
  Logger.log('================================================================================\n');

  const crmFolder = DriveApp.getFolderById(CONFIG.CRM_FOLDER_ID);

  clients.slice(0, 30).forEach((client, i) => {
    Logger.log(`[${i+1}/${Math.min(30, clients.length)}]`);
    processClient(crmFolder, client, true);
  });

  Logger.log('\n================================================================================');
  Logger.log('✅ DRY RUN COMPLETATO');
  Logger.log('================================================================================\n');
  Logger.log('Questo era un DRY RUN - NESSUNA modifica effettuata.\n');
  Logger.log('Per eseguire la riorganizzazione REALE:');
  Logger.log('   Run → Seleziona "execute"\n');
  Logger.log('⚠️  ATTENZIONE: execute modificherà i file realmente!');
  Logger.log('   Assicurati di avere backup o essere sicuro.\n');
}

function execute() {
  /**
   * ESECUZIONE REALE - Modifica i file
   */

  Logger.log('================================================================================');
  Logger.log('⚠️  ESECUZIONE REALE - RIORGANIZZAZIONE CRM');
  Logger.log('================================================================================\n');

  Logger.log('⚠️  ATTENZIONE: Questa operazione modificherà i file!');
  Logger.log('   Stai per riorganizzare tutti i clienti.\n');

  // Scan
  Logger.log('📂 Scansione CRM folder...\n');
  const clients = scanFolderRecursive(CONFIG.CRM_FOLDER_ID);
  clients.sort((a, b) => a.name.localeCompare(b.name));

  Logger.log(`✅ Trovati ${clients.length} clienti\n`);

  Logger.log('================================================================================');
  Logger.log('⚡ RIORGANIZZAZIONE IN CORSO');
  Logger.log('================================================================================\n');

  const crmFolder = DriveApp.getFolderById(CONFIG.CRM_FOLDER_ID);
  let totalFilesMoved = 0;
  let clientsProcessed = 0;

  clients.forEach((client, i) => {
    Logger.log(`[${i+1}/${clients.length}]`);
    const filesMoved = processClient(crmFolder, client, false);
    totalFilesMoved += filesMoved;
    clientsProcessed++;

    // Pausa ogni 50 clienti per evitare timeout
    if ((i + 1) % 50 === 0) {
      Logger.log(`\n⏸️  Pausa (processati ${i+1}/${clients.length} clienti)...\n`);
      Utilities.sleep(2000);
    }
  });

  Logger.log('\n================================================================================');
  Logger.log('✅ RIORGANIZZAZIONE COMPLETATA!');
  Logger.log('================================================================================\n');
  Logger.log(`Clienti processati: ${clientsProcessed}`);
  Logger.log(`File spostati:      ${totalFilesMoved}\n`);
  Logger.log('🎉 CRM riorganizzata con successo!');
  Logger.log('   Tutti i clienti hanno ora la struttura 01/02/03.\n');
}

// ============================================================================
// FUNZIONI BATCH (per gestire timeout)
// ============================================================================

function executeBatch1() {
  Logger.log('⚡ Esecuzione BATCH 1 (primi 100 clienti)...\n');
  executeBatchRange(0, 100);
}

function executeBatch2() {
  Logger.log('⚡ Esecuzione BATCH 2 (clienti 101-200)...\n');
  executeBatchRange(100, 200);
}

function executeBatch3() {
  Logger.log('⚡ Esecuzione BATCH 3 (clienti 201-300)...\n');
  executeBatchRange(200, 300);
}

function executeBatchRange(start, end) {
  const clients = scanFolderRecursive(CONFIG.CRM_FOLDER_ID);
  clients.sort((a, b) => a.name.localeCompare(b.name));

  const batch = clients.slice(start, end);
  const crmFolder = DriveApp.getFolderById(CONFIG.CRM_FOLDER_ID);

  Logger.log(`Processando clienti ${start+1} - ${Math.min(end, clients.length)} di ${clients.length}\n`);

  let totalFilesMoved = 0;

  batch.forEach((client, i) => {
    Logger.log(`[${start + i + 1}/${clients.length}] ${client.name}`);
    const filesMoved = processClient(crmFolder, client, false);
    totalFilesMoved += filesMoved;
  });

  Logger.log(`\n✅ Batch completato: ${batch.length} clienti, ${totalFilesMoved} file spostati\n`);
}
