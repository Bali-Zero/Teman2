"""Bank statement CSV parser — per-bank config adapter (Monopoly-pattern).

No maintained library parses Indonesian-bank exports, so this is a thin,
config-driven normalizer: each bank has a BankConfig describing its column
layout, and parse_csv() emits a canonical list of ParsedTxn. PII (payer names)
stays local — this runs on the box, never sends rows to a cloud LLM.

Indonesian gotchas handled:
  - dd/mm/yyyy (and dd/mm with no year) dates
  - decimal-comma / thousands-dot amounts ("1.234.567,89") OR plain ("1234567")
  - separate Debit/Credit columns OR one signed amount OR amount + DB/CR flag
  - leading-apostrophe text guards ("'04/09)

CIMB Niaga is the company's bank (PT BAYU BALI NOL, acct 800198149700). The
exact column names get finalized once Asya sends a real OCTO export; until then
CIMB_NIAGA below is a best-effort default and `auto` sniffs the header.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import date, datetime

logger = logging.getLogger(__name__)


@dataclass
class ParsedTxn:
    txn_date: date
    description: str
    amount_idr: int
    direction: str  # 'credit' (money in) | 'debit' (money out)
    running_balance_idr: int | None = None
    raw_row: dict[str, str] = field(default_factory=dict)


@dataclass
class BankConfig:
    """Describes how to read one bank's CSV layout."""

    bank_code: str
    date_col: str
    desc_col: str
    date_formats: tuple[str, ...] = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y")
    # amount handling — exactly one of these modes:
    debit_col: str | None = None      # two-column mode: debit / credit
    credit_col: str | None = None
    amount_col: str | None = None     # single-amount mode
    flag_col: str | None = None       # amount + DB/CR flag mode
    credit_flag_values: tuple[str, ...] = ("CR", "C", "K", "KREDIT", "CREDIT")
    balance_col: str | None = None
    decimal_comma: bool = False       # True => "1.234.567,89"; False => "1,234,567.89"/plain
    delimiter: str = ","              # decimal-comma exports must use ';' (else comma collides)


# Best-effort default for CIMB Niaga (OCTO). Refine column names from a real export.
CIMB_NIAGA = BankConfig(
    bank_code="cimb_niaga",
    date_col="Tanggal",
    desc_col="Keterangan",
    debit_col="Debet",
    credit_col="Kredit",
    balance_col="Saldo",
    decimal_comma=True,
    delimiter=";",  # decimal-comma export -> semicolon-separated (comma is the decimal)
)

# A generic single-signed-amount layout (many CSV exports).
GENERIC_SIGNED = BankConfig(
    bank_code="generic",
    date_col="date",
    desc_col="description",
    amount_col="amount",
    balance_col="balance",
    decimal_comma=False,
)

_CONFIGS: dict[str, BankConfig] = {
    "cimb_niaga": CIMB_NIAGA,
    "generic": GENERIC_SIGNED,
}


class BankParseError(Exception):
    pass


def _clean_cell(v: str | None) -> str:
    if v is None:
        return ""
    return v.strip().lstrip("'").strip()


def _parse_amount(raw: str, decimal_comma: bool) -> int:
    """Parse an IDR amount string to integer rupiah. Empty -> 0."""
    s = _clean_cell(raw)
    if not s:
        return 0
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("-()").replace(" ", "")
    if decimal_comma:
        # "1.234.567,89" -> dots are thousands, comma is decimal
        s = s.replace(".", "").replace(",", ".")
    else:
        # "1,234,567.89" -> commas are thousands
        s = s.replace(",", "")
    try:
        val = int(round(float(s)))
    except ValueError as exc:
        raise BankParseError(f"cannot parse amount {raw!r}") from exc
    return -val if neg else val


def _parse_date(raw: str, formats: tuple[str, ...]) -> date:
    s = _clean_cell(raw)
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise BankParseError(f"cannot parse date {raw!r} with {formats}")


def _row_direction_amount(row: dict[str, str], cfg: BankConfig) -> tuple[str, int]:
    """Return (direction, positive amount_idr) for one row, per the config mode."""
    if cfg.debit_col is not None and cfg.credit_col is not None:
        debit = _parse_amount(row.get(cfg.debit_col, ""), cfg.decimal_comma)
        credit = _parse_amount(row.get(cfg.credit_col, ""), cfg.decimal_comma)
        if credit > 0:
            return "credit", credit
        return "debit", abs(debit)
    if cfg.amount_col is not None and cfg.flag_col is not None:
        amt = abs(_parse_amount(row.get(cfg.amount_col, ""), cfg.decimal_comma))
        flag = _clean_cell(row.get(cfg.flag_col, "")).upper()
        direction = "credit" if flag in cfg.credit_flag_values else "debit"
        return direction, amt
    if cfg.amount_col is not None:
        amt = _parse_amount(row.get(cfg.amount_col, ""), cfg.decimal_comma)
        return ("credit" if amt >= 0 else "debit"), abs(amt)
    raise BankParseError("BankConfig has no usable amount mode")


def parse_csv(content: str, bank_code: str = "cimb_niaga") -> list[ParsedTxn]:
    """Parse a bank statement CSV into canonical transactions.

    `content` is the decoded file text. Rows that can't be parsed (header noise,
    totals) are skipped with a warning, never silently dropped from the count.
    """
    cfg = _CONFIGS.get(bank_code)
    if cfg is None:
        raise BankParseError(f"unknown bank_code {bank_code!r}; known: {list(_CONFIGS)}")

    reader = csv.DictReader(io.StringIO(content), delimiter=cfg.delimiter)
    if reader.fieldnames is None:
        raise BankParseError("empty CSV / no header row")

    out: list[ParsedTxn] = []
    skipped = 0
    for row in reader:
        # need a date and an amount-bearing cell to be a real transaction row
        if not _clean_cell(row.get(cfg.date_col, "")):
            skipped += 1
            continue
        try:
            txn_date = _parse_date(row[cfg.date_col], cfg.date_formats)
            direction, amount = _row_direction_amount(row, cfg)
            if amount == 0:
                skipped += 1
                continue
            balance = (
                _parse_amount(row.get(cfg.balance_col, ""), cfg.decimal_comma)
                if cfg.balance_col
                else None
            )
            out.append(
                ParsedTxn(
                    txn_date=txn_date,
                    description=_clean_cell(row.get(cfg.desc_col, "")),
                    amount_idr=amount,
                    direction=direction,
                    running_balance_idr=balance,
                    raw_row={k: _clean_cell(v) for k, v in row.items()},
                )
            )
        except BankParseError as exc:
            logger.warning("bank_parser: skipping unparseable row: %s (%s)", row, exc)
            skipped += 1

    if skipped:
        logger.info("bank_parser[%s]: parsed %d txns, skipped %d rows", bank_code, len(out), skipped)

    # D7 (superscar #2: no green-but-empty): if the file clearly had data rows
    # but we parsed NOTHING, that's almost certainly a wrong delimiter / wrong
    # bank_code / unexpected layout — fail loudly instead of returning [] silently.
    if not out and skipped > 0:
        raise BankParseError(
            f"parsed 0 transactions from {skipped} non-empty row(s) for bank_code={bank_code!r} "
            f"(delimiter={cfg.delimiter!r}) — likely wrong delimiter, bank_code, or column layout"
        )
    return out


def verify_balance(
    txns: list[ParsedTxn], opening_balance_idr: int, closing_balance_idr: int
) -> bool:
    """Golden-rule check: opening + sum(credits) - sum(debits) == closing.

    Returns True if the running total reconciles (within 1 rupiah). The caller
    surfaces a failure loudly (superscar #2) instead of trusting a bad parse.
    """
    delta = sum(t.amount_idr if t.direction == "credit" else -t.amount_idr for t in txns)
    return abs((opening_balance_idr + delta) - closing_balance_idr) <= 1
