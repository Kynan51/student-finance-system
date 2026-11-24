"""
Parse pasted M-Pesa confirmation SMS text into a draft transaction.

This is the proposal's "copy-pasted text structures" input method. There is
NO connection to Safaricom or any bank: the student pastes the message and
reviews the pre-filled form before saving.

Privacy: phone numbers are stripped from the description and balances are
ignored, so neither is ever stored.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

AMOUNT = r"Ksh\s?([\d,]+(?:\.\d{1,2})?)"
DATE = r"on\s+(\d{1,2}/\d{1,2}/\d{2,4})"
CODE_RE = re.compile(r"^\s*([A-Z0-9]{10})\b")
PHONE_RE = re.compile(r"(?:\+?254|0)(?:7|1)\d{8}")

PATTERNS = [
    # Received money -> income
    ("income", "received", re.compile(rf"You have received\s+{AMOUNT}\s+from\s+(.+?)\s+{DATE}", re.I)),
    # Paid to a till / paybill -> expense
    ("expense", "paid", re.compile(rf"{AMOUNT}\s+paid to\s+(.+?)\.?\s+{DATE}", re.I)),
    # Sent to a paybill account -> expense
    ("expense", "paybill", re.compile(rf"{AMOUNT}\s+sent to\s+(.+?)\s+for account\s+(.+?)\s+{DATE}", re.I)),
    # Sent to a person -> expense
    ("expense", "sent", re.compile(rf"{AMOUNT}\s+sent to\s+(.+?)\s+{DATE}", re.I)),
    # Airtime
    ("expense", "airtime", re.compile(rf"You bought\s+{AMOUNT}\s+of airtime(?:\s+for\s+\S+)?\s+{DATE}", re.I)),
    # Withdrawal: cash conversion, not spending
    ("withdrawal", "withdraw", re.compile(rf"{DATE}.*?Withdraw\s+{AMOUNT}\s+from\s+(.+?)\s+New", re.I | re.S)),
]


@dataclass
class ParsedTransaction:
    kind: str  # "income", "expense" or "withdrawal"
    amount: Decimal
    date: date
    counterparty: str = ""
    reference: str = ""
    description: str = ""
    warnings: list = field(default_factory=list)

    def as_dict(self):
        return {
            "kind": self.kind,
            "amount": str(self.amount),
            "date": self.date.isoformat(),
            "counterparty": self.counterparty,
            "reference": self.reference,
            "description": self.description,
            "warnings": self.warnings,
        }


class ParseError(ValueError):
    pass


def _to_decimal(raw):
    try:
        return Decimal(raw.replace(",", ""))
    except (InvalidOperation, AttributeError) as exc:
        raise ParseError("Could not read the amount.") from exc


def _to_date(raw):
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ParseError("Could not read the date.")


def _clean_party(text):
    text = PHONE_RE.sub("", text or "")
    text = re.sub(r"\s{2,}", " ", text).strip(" .-")
    return text.title()


def parse_mpesa_message(message):
    if not message or not message.strip():
        raise ParseError("Paste an M-Pesa confirmation message first.")
    text = " ".join(message.split())
    code_match = CODE_RE.match(text)
    reference = code_match.group(1) if code_match else ""

    for kind, label, pattern in PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        groups = match.groups()
        warnings = []
        if label == "withdraw":
            raw_date, raw_amount, party = groups
        elif label == "airtime":
            raw_amount, raw_date = groups
            party = "Airtime"
        elif label == "paybill":
            raw_amount, party, _account, raw_date = groups
        else:
            raw_amount, party, raw_date = groups

        amount = _to_decimal(raw_amount)
        if amount <= 0:
            raise ParseError("The amount must be greater than zero.")
        when = _to_date(raw_date)
        party = _clean_party(party)

        if label == "received":
            description = f"Received from {party}"
        elif label == "withdraw":
            description = f"Cash withdrawal at {party}"
            warnings.append(
                "Withdrawals turn M-Pesa into cash; they are not spending. "
                "Record what you buy with the cash as expenses instead."
            )
        elif label == "airtime":
            description = "Airtime purchase"
        else:
            description = f"Paid to {party}"

        return ParsedTransaction(
            kind=kind,
            amount=amount,
            date=when,
            counterparty=party,
            reference=reference,
            description=description[:200],
            warnings=warnings,
        )

    raise ParseError(
        "This message format was not recognised. You can still enter the transaction manually."
    )
