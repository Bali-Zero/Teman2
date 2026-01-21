# MediaPipe Vision Test

Pagina HTML statica per testare Google MediaPipe Object Detection lato client.

## 🚀 Come Usare

1. **Apri il file nel browser:**

   ```bash
   # Opzione 1: Apri direttamente il file
   open apps/webapp/public/vision_test.html

   # Opzione 2: Usa un server locale (consigliato per evitare problemi CORS)
   cd apps/webapp/public
   python3 -m http.server 8000
   # Poi apri: http://localhost:8000/vision_test.html
   ```

2. **Carica un'immagine:**
   - Clicca sul pulsante "📷 Carica Immagine"
   - Seleziona un'immagine dal tuo computer
   - Il modello analizzerà automaticamente l'immagine

3. **Visualizza i risultati:**
   - Gli oggetti rilevati appariranno nella colonna destra
   - Le bounding boxes verranno disegnate sull'immagine
   - Ogni oggetto mostra la confidence percentage

## 📋 Caratteristiche

- ✅ **Object Detection** con EfficientDet Lite0
- ✅ **CDN Integration** - Nessuna installazione npm richiesta
- ✅ **UI Moderna** - Interfaccia pulita e responsive
- ✅ **Visualizzazione** - Bounding boxes e confidence bars
- ✅ **Real-time** - Analisi immediata al caricamento

## 🔧 Tecnologie

- **MediaPipe Tasks Vision** v0.10.3 (CDN)
- **Modello:** efficientdet_lite0.tflite
- **Vanilla JavaScript** - Nessun framework richiesto

## 📝 Note

- Il modello viene scaricato automaticamente da Google Storage al primo utilizzo
- Il caricamento iniziale può richiedere alcuni secondi
- Funziona meglio con immagini di oggetti comuni (persone, animali, veicoli, elettronica, ecc.)
- Threshold minimo: 30% confidence

## 🐛 Troubleshooting

**Problema:** Il modello non si carica

- Verifica la connessione internet
- Controlla la console del browser per errori

**Problema:** Nessun oggetto rilevato

- Prova con un'immagine più chiara
- Assicurati che l'immagine contenga oggetti riconoscibili

**Problema:** Errori CORS

- Usa un server HTTP locale invece di aprire il file direttamente
