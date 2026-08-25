"""Framework-independent domain enumerations."""

from enum import StrEnum


class InstrumentType(StrEnum):
    """Asset forms supported by the first local portfolio slice."""

    FUND = "fund"
    ETF = "etf"
    QDII_FUND = "qdii_fund"
    CASH = "cash"


class AssetClass(StrEnum):
    """Broad exposure groups used by later portfolio risk calculations."""

    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    MIXED = "mixed"
    CASH = "cash"
    COMMODITY = "commodity"
    OTHER = "other"
