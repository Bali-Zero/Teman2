# Dashboard Integration Notes — Nuzantara Prime

**Last Updated: 2026-03-22**

## Overview

Backend endpoints created for the **Nuzantara Prime** Streamlit interactive zoning map dashboard. Integration complete and ready for testing.

**Date:** 2026-02-26
**Status:** Phase 1 Complete (Backend endpoints ready)

---

## Changes Made

### 1. New Backend Router: `dashboard.py`

**File:** `apps/backend-rag/backend/app/routers/dashboard.py`  
**Size:** ~400 lines  
**Endpoints:** 5

#### Endpoints Created

```
POST   /api/dashboard/validate-property
GET    /api/dashboard/clients/geo
GET    /api/dashboard/compliance/risk-zones
POST   /api/dashboard/analytics/log-lookup
GET    /api/dashboard/stats
```

#### Endpoint Details

**1. `/api/dashboard/validate-property` (POST)**

- Validates KBLI codes using KBLIEye deterministic audit
- Args: `location`, `kbli_code`, `is_pma`, `skala` (optional)
- Returns: Audit state (APPROVED|RESTRICTED|WARNING|REJECTED), compliance details
- Use case: Validate business classification when user clicks property on map

**2. `/api/dashboard/clients/geo` (GET)**

- Returns all CRM clients with geolocation
- Returns: `[{id, name, email, phone, status, lat, lon, practices_count}, ...]`
- Use case: Plot client locations on map layer

**3. `/api/dashboard/compliance/risk-zones` (GET)**

- Returns compliance risk zones by level (HIGH/MEDIUM/LOW)
- Returns: Zone definitions with colors and example KBLI codes
- Use case: Display risk color-coded zones on map

**4. `/api/dashboard/analytics/log-lookup` (POST)**

- Logs map interactions for analytics
- Args: `user_email`, `property_code`, `kbli_code`, `location`, `notes`
- Returns: `{logged: true}`
- Use case: Track when users validate properties

**5. `/api/dashboard/stats` (GET)**

- Dashboard summary statistics
- Returns: Clients count, practices count, practice distribution, recent lookups
- Use case: Summary cards above map

---

### 2. Router Registration Updated

**File:** `apps/backend-rag/backend/app/setup/router_registration.py`

Changes:

```python
# Line 51: Added import
from backend.app.routers import (
    ...
    dashboard,  # [NEW] Interactive dashboard for Streamlit zoning map
    dashboard_featured_articles,
    ...
)

# Line 255: Added registration (in "Dashboard aggregation routers" section)
api.include_router(dashboard.router)  # [NEW] Interactive map dashboard for Streamlit
```

---

### 3. Streamlit Frontend Config Updated

**File:** `/Users/nuzantara/Desktop/nuzantara/app_dashboard.py`

Changed:

```python
# OLD
API_URL = "http://127.0.0.1:8000"

# NEW
API_URL = "http://192.168.0.19:8001"
```

This points to the Mac Air backend server (Fly.io local equivalent).

---

## Testing Checklist

### Backend Testing (Mac Air)

1. **Start backend on Mac Air:**

   ```bash
   cd ~/Projects/nuzantara/apps/backend-rag
   source .venv/bin/activate
   PYTHONPATH=. python -m uvicorn backend.main:app --reload --port 8001
   ```

2. **Test endpoints with curl:**

   ```bash
   # KBLI validation
   curl -X POST "http://192.168.0.19:8001/api/dashboard/validate-property" \
     -H "Content-Type: application/json" \
     -d '{"location":"Bali","kbli_code":"55203","is_pma":true}'

   # Client geolocation
   curl "http://192.168.0.19:8001/api/dashboard/clients/geo"

   # Risk zones
   curl "http://192.168.0.19:8001/api/dashboard/compliance/risk-zones"

   # Stats
   curl "http://192.168.0.19:8001/api/dashboard/stats"
   ```

### Frontend Testing (MacBook Pro)

1. **Run Streamlit dashboard:**

   ```bash
   cd ~/Desktop/nuzantara
   streamlit run app_dashboard.py
   ```

2. **Verify API_URL points to Mac Air:**
   - Should show "Status: ONLINE 🟢" if backend is accessible
   - Check Mac Air at `http://192.168.0.19:8001/health` for confirmation

3. **Test KBLI validation flow:**
   - Enter KBLI code (e.g., "55203" for accommodation)
   - Should return compliance status
   - Check browser console for network request to `/api/dashboard/validate-property`

4. **Monitor analytics:**
   - Each validation should create a log entry in `analytics_map_lookups` table
   - Verify `/api/dashboard/stats` shows updated `map_lookups_24h` count

---

## Database Requirements

The following tables must exist in PostgreSQL (on Mac Air):

```sql
-- Must have (already exist):
crm_clients
crm_practices
crm_client_status (enum: active, inactive, prospect, archived)

-- New table for analytics (create if missing):
CREATE TABLE analytics_map_lookups (
    id BIGSERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    property_code VARCHAR(100),
    kbli_code VARCHAR(10) NOT NULL,
    location VARCHAR(100),
    notes TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_analytics_lookup_email ON analytics_map_lookups(user_email);
CREATE INDEX idx_analytics_lookup_timestamp ON analytics_map_lookups(timestamp);
```

---

## Architecture Diagram

```
┌─────────────────────┐
│  MacBook Pro        │
│  Streamlit App      │
│ (Port 8501)         │
└──────────┬──────────┘
           │ HTTP/REST (requests library)
           ↓
┌─────────────────────────────────────────────┐
│  Mac Air Backend (192.168.0.19:8001)        │
├─────────────────────────────────────────────┤
│ /api/dashboard/validate-property            │
│ /api/dashboard/clients/geo                  │
│ /api/dashboard/compliance/risk-zones        │
│ /api/dashboard/analytics/log-lookup         │
│ /api/dashboard/stats                        │
└──────────┬──────────────────────────────────┘
           │
      ┌────┴────┬────────────────┐
      ↓         ↓                ↓
   PostgreSQL Qdrant      (External APIs)
  (Port 5432) (Port 6333)  - Overpass
   - KBLIEye  - KG vectors  - Elevations
   - Clients  - Search      - Tiles
   - Practices
```

---

## Next Steps

### Phase 2: Frontend Integration (Optional)

1. **KBLI Validation Popup**
   - Add button on property click → POST to `/validate-property`
   - Display result in popup with color-coded state badge

2. **Client Layer**
   - Load clients from `/clients/geo`
   - Plot as marker layer on map

3. **Risk Zone Coloring**
   - Load risk zones from `/compliance/risk-zones`
   - Color GeoJSON features by risk level

4. **Analytics Dashboard**
   - Show stats from `/stats` endpoint in sidebar
   - Refresh every 60s

### Deployment Path

- **Dev:** Mac Air local development (done ✅)
- **Production:** Deploy backend to Fly.io (when ready)
  - Update Streamlit `API_URL` to production backend URL
  - Update Streamlit hosting (Cloud, Docker, etc.)

---

## Debugging Tips

If frontend shows "Status: OFFLINE 🔴":

1. Check Mac Air is running: `ssh air 'curl http://localhost:8001/health'`
2. Check API_URL in `app_dashboard.py` is correct
3. Check network: `ping 192.168.0.19`
4. Check backend logs: SSH to Air and tail the backend logs

If endpoints return 404:

1. Verify router is registered in `router_registration.py`
2. Check prefix: All endpoints use `/api/dashboard` prefix
3. Restart backend: `CTRL+C` and re-run uvicorn

---

## Files Modified

| File                                                        | Lines     | Change                      |
| ----------------------------------------------------------- | --------- | --------------------------- |
| `apps/backend-rag/backend/app/routers/dashboard.py`         | 400 (new) | New router with 5 endpoints |
| `apps/backend-rag/backend/app/setup/router_registration.py` | 3         | Added import + registration |
| `app_dashboard.py`                                          | 1         | Updated API_URL             |

**Total changes:** 404 lines  
**Test syntax:** ✅ All files pass Python syntax check

---

## Notes

- **KBLIEye import:** Uses lazy import pattern from `kbli_notebook.py` (already in codebase)
- **Database pool:** Endpoints assume `db_pool` exists in `request.app.state` (standard setup)
- **Geolocation:** Currently uses placeholder lat/lon from `crm_clients` table
  - TODO: Integrate Google Maps API for real geocoding from address
- **Analytics table:** Not auto-created; SQL provided above
- **Rate limiting:** Not applied; add if needed for production

---

**Prepared by:** Claude Code  
**Approved by:** User ("si")  
**Ready for testing:** Yes ✅
