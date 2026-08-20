# INDmoney

How to download the report the INDmoney parser reads.

## [indmoney_us_stocks_parser.py](https://github.com/atulgpt/SeFA/blob/main/parser/demat/indmoney/indmoney_us_stocks_parser.py)

Reads the consolidated tax report, downloaded as
`consolidated_tax_report_<financial year>.xlsx`.

1. Go to [Indmoney](https://www.indmoney.com/) web and Login to your account.
2. On the Home page, click on the profile icon.
3. Click on [`Tax and Other Reports`](https://www.indmoney.com/widget/page?page=taxCenterHomePage) from the drop down menu.
4. Click on `Download Report`.
5. Click on `Tax P&L Report`, your download will start.

Currently this handles two sections:

- Experimental: the `STCG` and `LTCG` sheets hold the realized US stock sales. US listed shares
  are not eligible for section 111A/112A, so they are filed at the slab rate.
  Rule 115 converts the gain as a whole, so the transfer month's reference rate is
  applied to the purchase leg as well.
- the `Schedule FA` sheet holds section A3, one row per foreign holding, with the
  initial, peak and closing value already stated in INR. Section A2 above it, the
  foreign custodial accounts, is not read.

Unlike the ETRADE sources, nothing here is derived from a ticker or a historic
share price; every figure is read off the report.
