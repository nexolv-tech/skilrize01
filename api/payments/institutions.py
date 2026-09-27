"""
Where a freelancer can be paid through Swich IBFT (D56).

Swich identifies a payout's destination by `bankCode` and `bankName`,
"provided by Swich". Its documented example pairs `BAHL` with Bank Al Habib
and an IBAN `PK00BAHL…`: the four-letter bank code every Pakistani IBAN
carries, which this list follows. Easypaisa and JazzCash are paid as the
microfinance banks behind them. **Check this list against the one Swich
issues with the merchant account before switching payouts on**
(`deploy/README.md`, step 11); a code Swich does not recognise is refused
with "No bank found", and nothing is sent.
"""

from __future__ import annotations

BANK = "bank"
WALLET = "wallet"

#: (code, name, kind), wallets first, then banks by name.
INSTITUTIONS: list[tuple[str, str, str]] = [
    ("TMFB", "Easypaisa", WALLET),
    ("JCMA", "JazzCash", WALLET),
    ("AIIN", "Al Baraka Bank", BANK),
    ("ABPA", "Allied Bank", BANK),
    ("ASCM", "Askari Bank", BANK),
    ("BAHL", "Bank Al Habib", BANK),
    ("ALFH", "Bank Alfalah", BANK),
    ("BKIP", "BankIslami", BANK),
    ("CITI", "Citibank", BANK),
    ("DUIB", "Dubai Islamic Bank", BANK),
    ("FAYS", "Faysal Bank", BANK),
    ("HABB", "Habib Bank (HBL)", BANK),
    ("MPBL", "Habib Metropolitan Bank", BANK),
    ("JSBL", "JS Bank", BANK),
    ("MUCB", "MCB Bank", BANK),
    ("MCIB", "MCB Islamic Bank", BANK),
    ("MEZN", "Meezan Bank", BANK),
    ("NBPA", "National Bank of Pakistan", BANK),
    ("SIND", "Sindh Bank", BANK),
    ("SONE", "Soneri Bank", BANK),
    ("SCBL", "Standard Chartered", BANK),
    ("SUMB", "Summit Bank", BANK),
    ("KHYB", "The Bank of Khyber", BANK),
    ("BPUN", "The Bank of Punjab", BANK),
    ("UNIL", "United Bank (UBL)", BANK),
]

BY_CODE = {code: (name, kind) for code, name, kind in INSTITUTIONS}


def name_of(code: str) -> str:
    return BY_CODE.get(code, ("", ""))[0]


def is_wallet(code: str) -> bool:
    return BY_CODE.get(code, ("", ""))[1] == WALLET
