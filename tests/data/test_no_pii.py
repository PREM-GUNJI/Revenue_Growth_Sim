"""AC-003: the generated dataset contains no PII/PHI-shaped values.

Synthetic data only (CLAUDE.md). This scans every string-typed column for
email, phone, SSN-like and credit-card-like patterns — a real (if blunt)
check, not a trivial pass, since the dataset genuinely has no such fields.
"""

import re

from backend.data.generator import generate

EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
CREDIT_CARD = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

PATTERNS = {"email": EMAIL, "ssn": SSN, "phone": PHONE, "credit_card": CREDIT_CARD}


def test_no_pii_patterns_in_string_columns():
    df = generate(42)
    string_cols = df.select_dtypes(include=["object", "string"]).columns
    for col in string_cols:
        joined = " ".join(df[col].astype(str).unique())
        for name, pattern in PATTERNS.items():
            assert not pattern.search(joined), f"{name}-shaped value found in column '{col}'"


def test_sku_region_store_ids_are_synthetic_codes():
    # Store/SKU identifiers are generated codes (e.g. "N01", "Aurora-can_330ml"),
    # never anything resembling a real customer, account or case identifier.
    df = generate(42)
    assert set(df["store_id"].str.len().unique()) == {3}
    assert df["sku_id"].str.contains("-").all()
