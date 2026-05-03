# Video Retention Playbook — Automatizzabile con ffmpeg
**Source:** Research da 15+ articoli (2025-2026) su video retention, hooks, engagement

## I DATI CHIAVE
- **85% degli utenti** guardano video SENZA audio → sottotitoli e text overlay sono OBBLIGATORI
- **3 secondi** decidono se lo spettatore resta → hook visivo+testuale immediato
- **Layered hooks** (visivo + testo + audio) = **3x engagement** vs singolo elemento
- **Text overlay: 5-8 parole max**, font alto contrasto, on-screen 2+ secondi
- **Rapid zooms** superano immagini statiche di **2.5x** in playback silenzioso
- **Video con sottotitoli** = **+40% completion rate**

## TECNICHE AUTOMATIZZABILI CON FFMPEG

### 1. DYNAMIC SUBTITLES (Whisper + ffmpeg)
- Trascrizione automatica con Whisper (gratis, locale)
- Stile: parola per parola evidenziata (karaoke style), font bold, sfondo semi-trasparente
- Posizione: centro-basso, lontano da lower third
- Font: sans-serif bold (simile Montserrat), bianco con ombra nera
- **Automazione:** `whisper audio.mp3 --model medium --output_format srt` → `ffmpeg -vf subtitles=subs.srt`

### 2. TOPIC TITLE CARDS (ogni 30-45 secondi)
- Testo grande che appare/scompare per 3-4 secondi
- Introduce la prossima sezione del video
- Posizione: centro superiore, con barra accent #d4845a sotto
- Effetto: fade-in 0.5s, hold 3s, fade-out 0.5s
- **Automazione:** `ffmpeg -vf "drawtext=text='THE 183-DAY TRAP':enable='between(t,45,49)':fontsize=48:fontcolor=white:borderw=3"`

### 3. PROGRESS BAR / SECTION INDICATOR
- Barra sottile in alto che si riempie progressivamente
- Colore: #d4845a (terracotta brand)
- Dà senso di progresso → riduce abbandono
- **Automazione:** `ffmpeg -vf "drawbox=x=0:y=0:w=iw*t/duration:h=4:color=#d4845a:t=fill"`

### 4. LOWER THIRD PERSISTENTE
- "BALI ZERO | balizero.com" sempre visibile
- Background bar: #0c0c0e al 85% opacity
- Accent line: 3px bordo sinistro #d4845a
- Font: bianco warm (#edeae4)
- Posizione: bottom-left, padding 20px
- **Automazione:** `ffmpeg -vf "drawbox=...:drawtext=text='BALI ZERO | balizero.com'"`

### 5. LOGO WATERMARK
- BZ logo PNG bottom-right
- Opacity 70-80%
- Size: ~80-100px
- Fade in a 2 secondi dall'inizio
- **Automazione:** `ffmpeg -i video.mp4 -i logo.png -filter_complex "overlay=W-w-20:H-h-20:enable='gte(t,2)'"`

### 6. INTRO ZANTARA (5 secondi)
- Clip dal video Flow (Zantara + Palantir)
- Crop da 9:16 a 16:9 (o usare full vertical per X mobile)
- Fade-in + cross-dissolve verso contenuto
- **Automazione:** `ffmpeg -i zantara.mp4 -i main.mp4 -filter_complex "xfade=transition=fade:duration=1:offset=4"`

### 7. OUTRO + CTA (5 secondi)
- Fade dal contenuto al video Zantara
- Overlay testo: "Follow @Balizero0 for more"
- URL: "balizero.com/kbli"
- **Automazione:** `ffmpeg -filter_complex "xfade + drawtext"`

### 8. NUMBER CALLOUTS / STAT POPS
- Numeri importanti che appaiono grandi al centro per 2s
- Es: "IDR 2.5 BILLION" o "183 DAYS" o "98.5%"
- Font enorme (72pt), terracotta #d4845a
- Effetto: scale-up con fade
- **Automazione:** `ffmpeg drawtext con enable=between(t,X,Y)`

### 9. EMOJI/ICON INDICATORS
- ⚠️ per warning, ✅ per confermato, ❌ per errore
- Appaiono accanto al testo del sottotitolo
- Rafforzano il messaggio visivamente senza audio
- **Automazione:** drawtext con font che supporta emoji

### 10. HOOK FRAME (frame 0-3 secondi)
- Il frame più provocatorio/interessante del video
- Testo grande: la domanda o affermazione più forte
- Es: "YOUR COMPANY COULD BE CANCELED IN 54 DAYS"
- Pattern interrupt visivo: zoom rapido o flash
- **Automazione:** trim + scale + drawtext overlay nei primi 3 secondi

## PIPELINE COMPLETA AUTOMATIZZATA

```bash
#!/bin/bash
# process_video.sh — Bali Zero X Video Pipeline
INPUT=$1
OUTPUT=$2
SUBS="${INPUT%.mp4}.srt"

# 1. Trascrivi audio → sottotitoli
whisper "$INPUT" --model medium --output_format srt --language en

# 2. Assembla: intro + main + outro con tutti gli overlay
ffmpeg -i zantara_intro.mp4 \
       -i "$INPUT" \
       -i zantara_outro.mp4 \
       -i bz_logo.png \
       -filter_complex "
         [0:v]trim=0:5,setpts=PTS-STARTPTS[intro];
         [2:v]trim=0:5,setpts=PTS-STARTPTS[outro];
         [1:v]subtitles=$SUBS:force_style='FontName=Montserrat,FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Shadow=1,MarginV=60'[subbed];
         [subbed]drawtext=text='BALI ZERO | balizero.com':fontfile=Montserrat-Bold.ttf:fontsize=18:fontcolor=#edeae4:x=30:y=h-50:enable='gte(t,3)',
         drawbox=x=0:y=h-65:w=250:h=35:color=#0c0c0e@0.85:t=fill:enable='gte(t,3)',
         drawbox=x=0:y=h-65:w=3:h=35:color=#d4845a:t=fill:enable='gte(t,3)',
         drawbox=x=0:y=0:w=iw*t/duration:h=4:color=#d4845a:t=fill[main_branded];
         [main_branded][3:v]overlay=W-w-20:H-h-20:enable='gte(t,2)'[with_logo];
         [intro][with_logo][outro]concat=n=3:v=1:a=0[final]
       " -map "[final]" -c:v libx264 -crf 18 "$OUTPUT"
```

## REGOLE PER X/TWITTER
- Upload nativo (mai link YouTube → -90% reach)
- Max 140 secondi per feed visibility ottimale (2:20)
- 16:9 landscape per desktop, 9:16 per mobile (fai entrambi)
- Primi 3 secondi: hook testuale forte + visual interrupt
- Sottotitoli SEMPRE (85% guarda muto)
- Nessun watermark di altri tool (TikTok logo = penalizzato)
