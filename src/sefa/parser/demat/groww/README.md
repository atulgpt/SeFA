# Groww

How to download the reports the Groww parsers read. Both are capital gains
statements, so pick the financial year you are filing for.

## [groww_indian_stocks_parser.py](https://github.com/atulgpt/SeFA/blob/main/parser/demat/groww/groww_indian_stocks_parser.py)

Reads the stocks capital gains statement, downloaded as
`Stocks_Capital_Gains_Report_<client code>_<from>_<to>.xlsx`.

1. Open the Groww app or [web](https://groww.in), go to your profile
2. Open [`Reports`](https://groww.in/user/profile/report)
3. Under `Tax` section pick `Stocks - Capital gains`
4. Choose the correct financial year and download the `.xlsx`

The statement carries the `Short Term trades` and `Long Term trades` blocks the
parser reads. `Intraday trades` is speculative business income and `Buyback trades`
is taxed under section 115QA, so neither is picked up.

Charges are stated only as a statement wide total. The parser deducts the
securities transaction tax from it, since STT is not allowed against a capital
gain, and splits the rest across the sales in proportion to their sale value.

A holding that trades on the exchange but is not equity oriented, a gold or silver
ETF for instance, is taxed at the slab rate rather than under section 111A/112A.
Those are listed by name in
[constants.py](https://github.com/atulgpt/SeFA/blob/main/parser/demat/groww/constants.py)
and have to be kept up to date by hand if your holding is not listed there.

## [groww_indian_mf_parser.py](https://github.com/atulgpt/SeFA/blob/main/parser/demat/groww/groww_indian_mf_parser.py)

Reads the mutual funds capital gains statement, downloaded as
`Mutual_Funds_Capital_Gains_Report_<from>_<to>.xlsx`.

1. Open the Groww app or [web](https://groww.in), go to your profile
2. Open [`Reports`](https://groww.in/user/profile/report)
3. Under `Tax` section pick `Mutual Funds - Capital gains`
4. Choose the financial year and download the `.xlsx`

The statement splits the redemptions into one block per asset class. Only the
`Equity Category` block is eligible for section 111A/112A; the debt blocks are
taxed at the slab rate. Whether a redemption is short or long term is read off
whichever of the two gain columns the statement populated, not recomputed.
