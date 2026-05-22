from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from typing import Any

from scripts.whatsapp_export_backfill.parse_exports import canonical_phone


def score_contact_match(
    export_contact: dict[str, Any],
    candidate_clients: Iterable[dict[str, Any]],
    whatsapp_contacts: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    export_name = _norm_name(str(export_contact.get("display_name") or export_contact.get("name") or ""))
    export_phones = _phones_from(export_contact)
    clients = list(candidate_clients)
    wa_contacts = list(whatsapp_contacts)

    phone_clients = [client for client in clients if export_phones & _phones_from(client)]
    active_phone_clients = [client for client in phone_clients if _is_active_non_team(client)]
    deleted_phone_clients = [client for client in phone_clients if _status(client) == "deleted"]
    wa_phone_match = any(export_phones & _phones_from(contact) for contact in wa_contacts)

    if len(active_phone_clients) == 1 and not deleted_phone_clients:
        client = active_phone_clients[0]
        if wa_phone_match:
            return _result(0.95, "match", client.get("id"), "exact_phone_with_whatsapp_contact_and_client")
        if _names_match(export_name, client):
            return _result(1.0, "match", client.get("id"), "exact_one_active_non_team_client")
        return _result(0.80, "review", client.get("id"), "alias_mismatch")

    if len(active_phone_clients) > 1:
        return _result(0.80, "review", None, "multiple_active_clients_same_phone")

    if active_phone_clients and deleted_phone_clients:
        return _result(0.80, "review", active_phone_clients[0].get("id"), "deleted_duplicate")

    name_clients = [client for client in clients if _is_active_non_team(client) and _names_match(export_name, client)]
    if len(name_clients) == 1:
        return _result(0.65, "review", name_clients[0].get("id"), "name_only")
    if len(name_clients) > 1:
        return _result(0.65, "review", None, "multiple_name_only")

    return _result(0.0, "no_match", None, "no_rule_matched")


def _result(score: float, decision: str, client_id: Any, reason: str) -> dict[str, Any]:
    return {"score": score, "decision": decision, "client_id": client_id, "reason": reason}


def _phones_from(record: dict[str, Any]) -> set[str]:
    values: list[Any] = []
    for key in ("phone", "phones", "telephone", "tel", "waid", "waids", "whatsapp"):
        value = record.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            values.extend(value)
        else:
            values.append(value)
    return {phone for phone in (canonical_phone(str(value)) for value in values) if phone}


def _status(client: dict[str, Any]) -> str:
    return str(client.get("status") or client.get("lifecycle_status") or "").lower()


def _is_active_non_team(client: dict[str, Any]) -> bool:
    status = _status(client)
    if status and status != "active":
        return False
    return not (bool(client.get("is_team")) or str(client.get("kind") or "").lower() == "team")


def _norm_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", value.lower())).strip()


def _names_match(export_name: str, client: dict[str, Any]) -> bool:
    names = [client.get("name"), client.get("display_name"), client.get("full_name")]
    aliases = client.get("aliases") or client.get("alias") or []
    if isinstance(aliases, str):
        names.append(aliases)
    else:
        names.extend(aliases)
    normalized = {_norm_name(str(name)) for name in names if name}
    return bool(export_name and export_name in normalized)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score one exported WhatsApp contact against JSON candidate files.")
    parser.add_argument("--contact-json", required=True, help="JSON object for the exported contact")
    parser.add_argument("--clients-json", required=True, help="JSON array of candidate clients")
    parser.add_argument("--wa-contacts-json", default="[]", help="JSON array of WhatsApp contacts")
    args = parser.parse_args(argv)
    result = score_contact_match(
        json.loads(args.contact_json),
        json.loads(args.clients_json),
        json.loads(args.wa_contacts_json),
    )
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
