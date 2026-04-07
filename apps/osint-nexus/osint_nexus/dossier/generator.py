"""Dossier generator — assembles target profile from graph data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from osint_nexus.graph.queries import TacticalQueries
from osint_nexus.utils.logging import get_logger

logger = get_logger("dossier")

DOSSIER_TEMPLATE = """# TARGET DOSSIER: {name}
**Generated:** {timestamp}
**Classification:** CONFIDENTIAL — INTERNAL USE ONLY

---

## 1. IDENTITÀ

| Campo | Valore |
|---|---|
| Nome | {name} |
| NIP | {nip} |
| Jabatan | {jabatan} |
| Kantor | {kantor} |
| Pangkat | {pangkat} |
| TTL | {ttl} |
| Asal | {asal} |
| Angkatan | {angkatan} |

---

## 2. POWER POSITION

| Metrica | Valore |
|---|---|
| Power Score | {power_score} |
| Degree (connessioni) | {degree} |
| Posizioni ricoperte | {positions} |
| Connessioni sociali | {social} |
| Asset collegati | {assets} |

---

## 3. NETWORK ({network_node_count} nodi, {network_edge_count} archi)

### Connessioni Dirette
{network_table}

---

## 4. FINANCIAL PROFILE

### LHKPN (Dichiarazione Patrimoniale)
{lhkpn_section}

### Asset Anomalies
{financial_anomalies}

---

## 5. PROCUREMENT (Tender)
{procurement_section}

---

## 6. APPROACHABILITY

### Interessi Condivisi & Bridge Persons
{approach_section}

### Opzioni di Approccio
{approach_options}

---

## 7. VULNERABILITÀ
{vulnerability_section}

---

## 8. PERCORSI (Path Analysis)
{paths_section}

---

*Generato da OSINT Nexus — Mosaic Intelligence System*
*Tutte le informazioni derivano da fonti pubbliche (LHKPN, LPSE, AHU, Putusan MA)*
"""


class DossierGenerator:
    """Generates structured dossiers from Neo4j graph data."""

    def __init__(self, queries: TacticalQueries) -> None:
        self.queries = queries

    async def generate(self, target_name: str) -> tuple[str, dict[str, Any]]:
        """Generate a full dossier for a target.

        Returns:
            Tuple of (markdown_string, structured_json_dict)
        """
        logger.info("Generating dossier for: %s", target_name)

        # Gather all intelligence in parallel-ish
        power = await self.queries.power_score(target_name)
        network = await self.queries.network_map(target_name, depth=2)
        approach = await self.queries.approachability(target_name)
        anomalies = await self.queries.financial_anomaly()
        procurement = await self.queries.procurement_ring()

        # Filter anomalies/procurement for this target
        target_anomalies = [a for a in anomalies if a.get("official") == target_name]
        target_procurement = [p for p in procurement if p.get("official") == target_name]

        # Build sections
        network_nodes = network.get("nodes", []) if isinstance(network, dict) else []
        network_edges = network.get("edges", []) if isinstance(network, dict) else []

        network_table = self._format_network(network_nodes, network_edges)
        lhkpn = self._format_lhkpn(power)
        fin_anomalies = self._format_anomalies(target_anomalies)
        proc_section = self._format_procurement(target_procurement)
        approach_section = self._format_approach(approach)
        approach_options = self._format_approach_options(power, approach)
        vuln_section = self._format_vulnerability(power, target_anomalies)
        paths_section = "*(Esegui query specifica con --path-to per analisi percorsi)*"

        # Assemble markdown
        markdown = DOSSIER_TEMPLATE.format(
            name=target_name,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            nip=power.get("nip", "N/A") if power else "N/A",
            jabatan=power.get("jabatan", "N/A") if power else "N/A",
            kantor=power.get("kantor", "N/A") if power else "N/A",
            pangkat=power.get("pangkat", "N/A") if power else "N/A",
            ttl=power.get("ttl", "N/A") if power else "N/A",
            asal=power.get("asal", "N/A") if power else "N/A",
            angkatan=power.get("angkatan", "N/A") if power else "N/A",
            power_score=f"{power.get('power_score', 0):.1f}" if power else "N/A",
            degree=power.get("degree", 0) if power else 0,
            positions=power.get("positions", 0) if power else 0,
            social=power.get("social", 0) if power else 0,
            assets=power.get("assets", 0) if power else 0,
            network_node_count=len(network_nodes),
            network_edge_count=len(network_edges),
            network_table=network_table,
            lhkpn_section=lhkpn,
            financial_anomalies=fin_anomalies,
            procurement_section=proc_section,
            approach_section=approach_section,
            approach_options=approach_options,
            vulnerability_section=vuln_section,
            paths_section=paths_section,
        )

        # Build structured JSON
        structured = {
            "target": target_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "power": power or {},
            "network": {"nodes": network_nodes, "edges": network_edges},
            "approach": approach,
            "financial_anomalies": target_anomalies,
            "procurement_connections": target_procurement,
        }

        return markdown, structured

    def _format_network(
        self, nodes: list[dict], edges: list[dict]
    ) -> str:
        if not nodes:
            return "*Nessuna connessione trovata nel grafo*"

        lines = ["| Entità | Tipo | Jabatan |", "|---|---|---|"]
        for n in nodes[:30]:
            name = n.get("name", "?")
            labels = ", ".join(n.get("labels", []))
            jabatan = n.get("jabatan", "")
            lines.append(f"| {name} | {labels} | {jabatan} |")

        if edges:
            lines.append("")
            lines.append("### Relazioni")
            lines.append("| Da | Tipo | A |")
            lines.append("|---|---|---|")
            for e in edges[:30]:
                lines.append(f"| {e.get('from', '?')} | {e.get('type', '?')} | {e.get('to', '?')} |")

        return "\n".join(lines)

    def _format_lhkpn(self, power: dict) -> str:
        if not power:
            return "*Dati LHKPN non disponibili — eseguire scraper LHKPN*"

        # Try multi-year LHKPN data from scraper records (raw_data list)
        lhkpn_records = power.get("lhkpn_records", [])
        if lhkpn_records:
            lines = [
                "| Tahun | Jabatan | Lembaga | Total Harta | PDF |",
                "|---|---|---|---|---|",
            ]
            for rec in sorted(lhkpn_records, key=lambda r: r.get("tahun_data", ""), reverse=True):
                tahun = rec.get("tahun_data", "?")
                jabatan = rec.get("jabatan", "-")[:30]
                lembaga = rec.get("lembaga", "-")[:30]
                harta = rec.get("total_harta_raw", "?")
                pdf = rec.get("pdf_path", "")
                pdf_name = pdf.split("/")[-1] if pdf else "-"
                lines.append(f"| {tahun} | {jabatan} | {lembaga} | {harta} | {pdf_name} |")

            # Trend analysis
            values = [
                (r.get("tahun_data", ""), r.get("total_harta", 0))
                for r in lhkpn_records
                if r.get("total_harta")
            ]
            if len(values) >= 2:
                values.sort()
                first_year, first_val = values[0]
                last_year, last_val = values[-1]
                if first_val > 0:
                    growth = ((last_val - first_val) / first_val) * 100
                    lines.append("")
                    lines.append(
                        f"**Trend {first_year}→{last_year}:** "
                        f"Rp {first_val:,.0f} → Rp {last_val:,.0f} "
                        f"(**{growth:+.1f}%**)"
                    )

            return "\n".join(lines)

        # Fallback: single value from graph
        lhkpn = power.get("lhkpn_total")
        if lhkpn:
            return f"**Total Harta Kekayaan:** Rp {lhkpn:,}" if isinstance(lhkpn, (int, float)) else f"**Total:** {lhkpn}"
        return "*LHKPN non ancora recuperato — eseguire `nexus scrape lhkpn \"{}\"`*".format(power.get("name", ""))

    def _format_anomalies(self, anomalies: list[dict]) -> str:
        if not anomalies:
            return "*Nessuna anomalia finanziaria rilevata*"
        lines = ["| Asset | Valore Stimato | Dichiarato | Ratio |", "|---|---|---|---|"]
        for a in anomalies:
            lines.append(
                f"| {a.get('asset', '?')} | {a.get('asset_value', '?')} | {a.get('declared', '?')} | {a.get('ratio', '?'):.1f}x |"
            )
        return "\n".join(lines)

    def _format_procurement(self, procurement: list[dict]) -> str:
        if not procurement:
            return "*Nessuna connessione procurement-famiglia rilevata*"
        lines = ["| Vendor | Tender | Valore | Relazione |", "|---|---|---|---|"]
        for p in procurement:
            lines.append(
                f"| {p.get('vendor', '?')} | {p.get('tender', '?')} | {p.get('value', '?')} | family link |"
            )
        return "\n".join(lines)

    def _format_approach(self, approach: list[dict]) -> str:
        if not approach:
            return "*Nessun punto di contatto trovato — arricchire grafo con dati sociali*"
        lines = ["| Interesse Condiviso | Tipo | Bridge Person | Nostra Connessione |", "|---|---|---|---|"]
        for a in approach:
            lines.append(
                f"| {a.get('shared_interest', '?')} | {a.get('interest_type', '?')} "
                f"| {a.get('bridge_person', 'N/A')} | {a.get('our_connection', 'N/A')} |"
            )
        return "\n".join(lines)

    def _format_approach_options(
        self, power: dict, approach: list[dict]
    ) -> str:
        options = []
        if approach:
            options.append("**A — Bridge Introduction**: Contatto tramite persona ponte → kopi → basa-basi → graduale")
        options.append("**B — Institutional**: Surat resmi, konsultasi prosedur, professionale, zero risk")
        options.append("**C — Lateral Pressure**: Via patron/Kakanwil — non menzionare target, ma il CASO")
        options.append("**D — Tempo-Based**: Se mutasi imminente → aspetta nuovo Kasi")
        return "\n".join(options)

    def _format_vulnerability(
        self, power: dict, anomalies: list[dict]
    ) -> str:
        items = []
        if anomalies:
            items.append("- **Financial**: Anomalie patrimoniali rilevate (vedi sezione 4)")
        if power and power.get("degree", 0) < 5:
            items.append("- **Isolamento**: Poche connessioni → potenzialmente raggiungibile direttamente")
        if power and power.get("social", 0) > 10:
            items.append("- **Esposizione sociale**: Molte connessioni sociali → più punti di pressione/contatto")
        if not items:
            items.append("*Insufficienti dati per analisi vulnerabilità — arricchire profilo*")
        return "\n".join(items)
