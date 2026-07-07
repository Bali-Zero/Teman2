# Zoning Discovery Backlog

## Problem Statement

The multi-provider zoning system in `kg_subgraph_property.py` is ready to support Denpasar and other Bali regions via the National GISTARU ArcGIS REST API. However, the current endpoint for Bali RTRWP 2023-2043 returns a 404 error or requires a different MapServer ID.

## Goal

Identify and map the correct ArcGIS REST MapServer endpoints for all major Bali regencies to enable 100% spatial intelligence coverage.

## Targets

| Regency  | Prefix | Status     | Notes                                   |
| -------- | ------ | ---------- | --------------------------------------- |
| Badung   | 5103   | ✅ ACTIVE  | Using proprietary DPUPR API             |
| Denpasar | 5171   | 🔴 PENDING | Needs correct GISTARU/RDTR MapServer ID |
| Gianyar  | 5104   | 🔴 PENDING | Needs correct GISTARU/RDTR MapServer ID |
| Tabanan  | 5102   | 🔴 PENDING | Needs correct GISTARU/RDTR MapServer ID |

## Next Steps for AI Agent

1.  **Discovery**: Access `https://gistaru.atrbpn.go.id/arcgis/rest/services` and browse the folders (likely `RDTR` or `RTRW`) to find the latest service for "Kota Denpasar" and "Kabupaten Gianyar".
2.  **Mapping**: Update `_GISTARU_REST_URL` in `kg_subgraph_property.py` with the identified working endpoint.
3.  **Refinement**: If regencies use different servers, implement a mapping dict `KABUPATEN_PROVIDERS` to route requests to specific regency-level ArcGIS servers.

## Reference BPS Codes

- Sanur (Denpasar): 5171030001
- Ubud (Gianyar): 5104050005
