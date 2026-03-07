# Bali Zero Carousel — Design Spec Definitivo

_Analisi live da reference \_Carousel Dea — 2026-03-03_

---

## Canvas

- **Formato:** 1080 × 1350 px (portrait 4:5)
- **Unità:** pixel

---

## Cornice (TUTTI i content slide)

```
┌──────────────────────────────────┐  ← border top: 45px (#1C1C1C)
│  ┌────────────────────────────┐  │  ← border left/right: 45px
│  │   INNER PANEL #4A5259      │  │
│  │   (990 × 1185 px)          │  │
│  └────────────────────────────┘  │
│                                  │  ← border bottom: 120px (#1C1C1C)
└──────────────────────────────────┘
```

- Border color: **#1C1C1C** (quasi nero)
- Inner panel: **#4A5259** (grigio-ardesia freddo)
- Inner panel size: 990 × 1185 px (da x=45,y=45 a x=1035,y=1230)

---

## Cover Slide (solo la prima)

- Foto **full-bleed** 1080×1350 (nessuna cornice)
- **Headline**: white #FFFFFF, bold, ~72px, allineato sinistra (margine 70px), Y~295-380px
  - Ogni riga di testo ha un **highlight box blu** dietro: #2B1BB5, padding 8px v / 12px h
- **Subtitle**: dark #2D2D2D, bold, ~32px
  - Dentro una **pill/capsula** giallo-crema #E8C95A, border-radius ~20px, padding 10px v / 20px h
  - Centrata orizzontalmente, Y~445px
- **Logo**: badge cerchio nero #000000, diametro 100px, centrato X, Y~1210px

---

## Content Slide (con foto)

Layout alternato: slide dispari → foto DESTRA | slide pari → foto SINISTRA

```
Inner panel (990×1185 @ x45,y45):
  ┌────────────────────────────────┐
  │  ┌──────────────────────────┐  │ y~75 from inner top
  │  │  HEADLINE (centrato)     │  │ font 48px, #E8B94A, bold italic
  │  └──────────────────────────┘  │ y~130
  │                                │
  │  ┌─TESTO──┐  ┌──────────────┐  │ y~220 from inner top
  │  │ body   │  │              │  │
  │  │ #D9D9D9│  │    FOTO      │  │ foto: 490×680px
  │  │ 22px   │  │  (no frame)  │  │
  │  │ justify│  │  no rotation │  │
  │  └────────┘  └──────────────┘  │ y~900 from inner top
  │                                │
  │        (spazio vuoto)          │ ~285px vuoti
  └────────────────────────────────┘
```

### Headline

- Y dall'inner top: **75px** → Y assoluto: 120px
- Colore: **#E8B94A** (giallo-oro caldo)
- Font: bold italic, ~48px, UPPERCASE
- Allineamento: **centrato** nella inner panel

### Foto (content slide)

- Dimensioni: **490 × 680 px**
- Y assoluto: **265px** (y_inner=45 + y_photo=220)
- Foto DESTRA (dispari): X assoluto = 1035 - 490 = **545px**
- Foto SINISTRA (pari): X assoluto = **45px**
- Nessun frame/bordo
- Nessuna rotazione
- Overlay scuro 30%: `(0,0,0,77)` per blend con background

### Body Text (accanto alla foto)

- X testo (foto destra): 45 + 20 = **65px**, larghezza: 545-65-20 = **460px**
- X testo (foto sinistra): 545+20 = **565px**, larghezza: 1035-565-20 = **450px**
- Y inizio: **265px** (allineato top foto)
- Font: sans-serif regular, **22px**, UPPERCASE
- Colore: **#D9D9D9**
- Allineamento: **giustificato** (fill width)
- Interlinea: **34px**
- Frasi chiave (accent): **#E8B94A**, bold (stesso giallo headline)

---

## Text-Only Slide (nessuna foto)

- Cornice identica ai content slide
- Headline top centrato (identico)
- Body text a piena larghezza inner panel (margine 60px per lato)
- Body Y: **280px** assoluto (~240px from inner top)
- Ampio spazio vuoto nella metà inferiore (intenzionale)

---

## Palette colori definitiva

| Elemento               | Colore         | Hex       |
| ---------------------- | -------------- | --------- |
| Outer border           | Quasi nero     | `#1C1C1C` |
| Inner panel background | Grigio-ardesia | `#373D42` |
| Headline / Accent      | Giallo-oro     | `#E8B94A` |
| Body text              | Bianco sporco  | `#D9D9D9` |
| Cover headline text    | Bianco puro    | `#FFFFFF` |
| Cover highlight box    | Blu-viola      | `#2B1BB5` |
| Cover pill background  | Giallo-crema   | `#E8C95A` |
| Cover pill text        | Quasi nero     | `#2D2D2D` |
| Logo badge             | Nero           | `#000000` |

---

## Font

- **Headline**: bold italic, UPPERCASE, ~48px (content) / ~72px (cover)
- **Body**: regular, UPPERCASE, ~22px, letter-spacing +0.5px
- **Accent nel body**: bold, UPPERCASE, stesso size
- Sistema: Impact (headline) / Helvetica (body) come fallback
- Brand fonts preferiti: LeagueSpartan-ExtraBold (headline), Montserrat-Medium (body)

---

## Errori da evitare

- ❌ Foto full-bleed su slide content
- ❌ Testo bianco come headline (deve essere giallo-oro)
- ❌ Testo allineato a sinistra per headline (deve essere centrato)
- ❌ Nessuna cornice (la cornice dark è fondamentale)
- ❌ Gradiente overlay su tutto lo slide
- ❌ Foto angolata/rotata
- ❌ Foto con frame bianco
- ❌ Spazio vuoto in basso riempito (è intenzionale)
- ❌ Headline a x=0 (width=W) senza align=center → tocca bordo sinistro
- ❌ mk_text senza alignment esplicito → Keynote default = left

## Fix applicati (2026-03-04)

- Headline: `x=MX` (60px), `w=IW` (960px), `align=center` — mai tocca i bordi
- Subhead: stesso schema, `align=center`
- Body: `align=justify`, altezza aumentata da 380 a **480px**
- `mk_text` ora accetta parametro `align` ('left'/'center'/'right'/'justify')
- Cover headline/subhead: stessa correzione con MX/IW + center
