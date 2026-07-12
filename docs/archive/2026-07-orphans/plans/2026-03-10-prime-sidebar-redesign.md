# Prime Intelligence — Sidebar Redesign + Reverse Geocoding + Zone Colors

**Date:** 2026-03-10
**Status:** Approved

---

## What We're Building

Three coordinated improvements to `prime.balizero.com`:

1. **Sidebar** — replace the floating panel with a true full-height sidebar (resizable), Bali Zero logo, liquid glassmorphism, accordion sections
2. **Reverse geocoding** — show the precise street address when a point is clicked
3. **Zone colors layer** — toggle that fetches GeoJSON from PostGIS and draws colored zone polygons on the 3D map
4. **Filter button** — bottom-right of map, opens a layer control panel

---

## Layout

```
┌─────────────────────────────────────────────────────────┐
│  [Sidebar 300-480px, resizable]  │  [Map flex-1 h-screen]│
│  bg-black, border-r border-white/10                      │
│                                  │  [Search bar top-center]
│  ┌─ Header ─────────────────┐    │                        │
│  │ [BZ logo] / MAP          │    │                        │
│  └──────────────────────────┘    │                        │
│                                  │                        │
│  (idle state: "Tap map…")        │                        │
│                                  │  [Coordinates]         │
│  (active: accordion sections)    │  [Filter btn ⊞]        │
│                                  │  bottom-right          │
│  ─────────────────────────────   │                        │
│  [CTA button]                    │                        │
└─────────────────────────────────────────────────────────┘
```

Height: `h-screen` (full viewport). The page wrapper (`apps/mouth/src/app/prime/page.tsx`) already has `bg-slate-950`.

---

## Sidebar Design — Liquid Glassmorphism

- **Outer shell:** `bg-black border-r border-white/10` (solid, not transparent — sits outside the map)
- **Section cards:** `bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl` (glassmorphism)
- **Active accent:** terracotta `#d4845a` on open section title + chevron
- **Resize handle:** `w-1 cursor-col-resize bg-white/5 hover:bg-white/20` on the right edge, drag changes sidebar width (min 260px, max 480px)
- **Collapse toggle:** arrow button at top-right of sidebar to collapse to 48px icon-only strip

### Header

```
[BZ logo 28px] / MAP
```

- Logo: `balizero-logo-clean.png` from `/public/`
- "/ MAP" in `text-slate-400 font-mono text-xs tracking-widest`

### Accordion Sections (in order)

| #   | Title              | Icon          | Default  | Content                                                      |
| --- | ------------------ | ------------- | -------- | ------------------------------------------------------------ |
| 1   | Location           | MapPin        | **Open** | Subdistrict, district, **street address** (reverse geocoded) |
| 2   | Zone               | Layers        | **Open** | Zone code + color swatch + EN label + ID name + risk badge   |
| 3   | What you can open  | Building2     | **Open** | Business list with category chips                            |
| 4   | Development Limits | Ruler         | Closed   | KDB/height/green area grid + notes                           |
| 5   | Overlays & Risks   | AlertTriangle | Closed   | KKOP, LP2B, tsunami, heritage flags                          |
| 6   | Land Price         | TrendingUp    | Closed   | Est. price per are                                           |
| 7   | Latest Intel       | Newspaper     | Closed   | Semantic news articles                                       |

Each section header: `flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-white/5`
Title: `flex items-center gap-2 text-sm font-semibold text-white` (open) or `text-slate-400` (closed)
Chevron: rotates 180° when open, terracotta when open

### CTA (sticky bottom)

```
[Get a Free Business Setup Quote →]
```

`sticky bottom-0 p-4 bg-black border-t border-white/10`

---

## Reverse Geocoding

**Approach:** client-side fetch in parallel with zoning API call.

```typescript
// In analyzeLocation(), parallel Promise.all
const [zoningData, geoData] = await Promise.all([
  fetch(`/api/prime/zoning?lat=...&lng=...`).then((r) => r.json()),
  fetch(
    `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${MAPS_KEY}`,
  ).then((r) => r.json()),
]);
```

- Extract `results[0].formatted_address` or better: `address_components` to build `route + street_number`
- Store as `streetAddress` in component state (separate from `ZoningInfo`)
- Show in Location section: bold street, then subdistrict/district below

**Fallback:** if geocoding fails or returns nothing, show only subdistrict/district as before.

---

## Zone Colors Layer (GeoJSON from PostGIS)

### Backend: new endpoint

`GET /api/prime/zones-geojson`

```python
# Returns GeoJSON FeatureCollection of all bali_zoning_layers polygons
# Each feature has properties: zone_code, zone_color_hex
# Uses ST_AsGeoJSON + ST_Simplify (tolerance 0.0001) to reduce size
# Cached: in-memory after first load (zones don't change)
# Response size target: < 2MB (simplified polygons)
```

Query:

```sql
SELECT
  ST_AsGeoJSON(ST_Simplify(geom, 0.0001)) as geometry,
  zone_code,
  COALESCE(zone_color_hex, '#6B7280') as color
FROM bali_zoning_layers
WHERE geom IS NOT NULL
```

### Frontend: Polygon3DElement rendering

When "Zone colors" filter toggle is ON:

1. Fetch `/api/prime/zones-geojson` (cached in React ref after first fetch)
2. For each feature, create `Polygon3DElement` with:
   - `fillColor`: zone color at 40% opacity
   - `strokeColor`: zone color at 80% opacity
   - `strokeWidth`: 1
   - `altitudeMode`: CLAMP_TO_GROUND
3. Append all polygons to `map3DElement`
4. On toggle OFF: remove all polygon elements

```typescript
const zonesGeoJsonRef = useRef<any>(null);
const zonePolygonsRef = useRef<any[]>([]);

const toggleZoneColors = async (enabled: boolean) => {
  if (!enabled) {
    zonePolygonsRef.current.forEach(p => p.remove());
    zonePolygonsRef.current = [];
    return;
  }
  if (!zonesGeoJsonRef.current) {
    const res = await fetch('/api/prime/zones-geojson');
    zonesGeoJsonRef.current = await res.json();
  }
  const { Polygon3DElement } = await google.maps.importLibrary("maps3d");
  for (const feature of zonesGeoJsonRef.current.features) {
    const poly = new Polygon3DElement({ ... });
    map3DElement.append(poly);
    zonePolygonsRef.current.push(poly);
  }
};
```

---

## Filter Button + Layer Panel

**Position:** `absolute bottom-6 right-6` on the map (not sidebar)

**Button:** `w-10 h-10 rounded-xl bg-black/80 backdrop-blur border border-white/20 flex items-center justify-center`
Icon: `SlidersHorizontal` from lucide-react

**Panel** (opens above button, `absolute bottom-16 right-6`):
`bg-black/90 backdrop-blur-xl border border-white/10 rounded-2xl p-4 w-56 shadow-2xl`

Layers:

| Toggle      | Label                 | Default |
| ----------- | --------------------- | ------- |
| Zone colors | 🎨 Zone overlay       | OFF     |
| KKOP        | ✈ Aviation zones      | OFF     |
| LP2B        | 🌾 Protected farmland | OFF     |
| Tsunami     | 🌊 Tsunami risk       | OFF     |
| Land prices | 💰 Price heatmap      | OFF     |

_v1: only Zone colors is functional. Others show as "Coming soon" or are disabled._

Toggle style: standard iOS-style pill switch with terracotta `#d4845a` active color.

---

## Files to Change

| File                                            | Change                                                |
| ----------------------------------------------- | ----------------------------------------------------- |
| `apps/mouth/src/components/maps/PrimeMap3D.tsx` | Full rewrite of layout + sidebar + filter + geocoding |
| `apps/mouth/src/app/prime/page.tsx`             | Remove explicit height, use h-screen                  |
| `apps/backend-rag/backend/app/routers/prime.py` | Add `GET /zones-geojson` endpoint                     |

---

## Out of Scope (this iteration)

- Live KKOP / LP2B / tsunami polygon layers (need separate GeoJSON sources)
- Land price heatmap (needs grid aggregation)
- Backend street address lookup (client-side geocoding is sufficient)
- Sidebar persistence (collapsed state saved to localStorage)
