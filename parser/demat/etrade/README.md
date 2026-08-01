# ETRADE

How to download the reports the ETRADE parsers read.

## [etrade_benefit_history_parser.py](https://github.com/atulgpt/SeFA/blob/main/parser/demat/etrade/etrade_benefit_history_parser.py)

Reads `BenefitHistory.xlsx`, the ESPP/RSU benefit history, and feeds schedule FA
under section A3.

1. Click on `At Work` top menu bar
2. Click on `Holdings` top submenu bar
3. Click on `Benefit History` link either on `Employee Stock Purchase Plan (ESPP)` or `Restricted Stock (RS)`
4. Click on `Download` button which will open the popup.
5. Click on `Download Expanded` which will prompt you to download the `BenefitHistory.xlsx` file

## [etrade_holdings_bystatus_parser.py](https://github.com/atulgpt/SeFA/blob/main/parser/demat/etrade/etrade_holdings_bystatus_parser.py)

Reads the holdings by status report, which lists the sellable quantity per grant,
and feeds schedule FA under section A3.

1. Click on `At Work` top menu bar
2. Click on `Holdings` top submenu bar
3. Click on `Download` and pick the holdings by status export
