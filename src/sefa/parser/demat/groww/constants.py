import typing as t

# Names, exactly as the Groww capital gains statement spells them, of the holdings
# that trade on the stock exchange but are not equity oriented. They sit in the
# stocks report alongside real shares while being taxed at the slab rate instead of
# under section 111A/112A, so they have to be listed out by name
NON_EQUITY_LINKED_SHARES: t.List[str] = [
    "ICICIPRAMC - ICICISILVE",
    "SBI-ETF GOLD",
]
