# CRM Evidence Dossier Design

## Goal

Build the first dynamic CRM intelligence surface for kita: a team-only dossier that reads CRM database rows and the CRM knowledge graph, then presents a person-first story: person -> company -> tax -> documents -> evidence -> next action.

## Scope

- Add a backend service that reads `clients`, `client_company_links`, `companies`, `documents`, `crm_kg_nodes`, and `crm_kg_edges`.
- Add a team-only CRM endpoint for the dossier.
- Keep the response compatible with the existing tax pilot workspace shape where practical.
- Fall back to the existing Ocean/Bimala pilot maps when no dynamic rows exist.
- Keep client portal behavior unchanged: clients never receive Drive navigation, only approved document downloads through existing portal document surfaces.

## Architecture

The backend owns the intelligence shape. A focused service builds `TaxCompanyPilotMap`-compatible dossiers from dynamic CRM/KG data. The router enforces `require_team_member` and exposes the dossier under `/api/crm/intelligence/evidence-dossiers`.

The frontend adds an API method and changes the current tax pilot page to request the live dossier endpoint first. The existing `TaxCompanyPilotWorkspace` renders the result, so the first increment stays small and business-facing without a second UI system.

## Safety

- No Drive writes.
- No portal route changes.
- All Drive URLs in this feature are team-only because the endpoint requires an authenticated non-client user.
- If CRM/KG tables are empty or unavailable for a requested pilot company, the endpoint returns the existing curated pilot evidence instead of failing the workspace.
