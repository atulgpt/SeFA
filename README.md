# SeFA
Python module to generate Indian ITR schedule FA under section A3 automatically

# How to run
## Download `BenefitHistory.xlsx` from `ETRADE`
1. Click on `At Work` top menu bar
2. Click on `Holdings` top submenu bar
3. Click on `Benefit History` link either on `Employee Stock Purchase Plan (ESPP)` or `Restricted Stock (RS)`
4. Click on `Download` button which will open the popup.
5. Click on `Download Expanded` which will prompt you to download the `BenefitHistory.xlsx` file

## Setup
The script requires Python 3.8 or higher. Please ensure that it is installed on your system. In newer versions of Python, you may encounter an [`externally-managed-environment`](https://peps.python.org/pep-0668/), so create and activate a [Python virtual environment](https://docs.python.org/3/library/venv.html#creating-virtual-environments) before installing the dependencies.

```sh
# From the repository root
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip3 install .
```

This installs all required dependencies (`pandas`, `openpyxl`, `yfinance`, `requests`).

## Run the script
With the virtual environment activated, run the script with the downloaded `BenefitHistory.xlsx`:
```sh
./run.py -i "etrade_benefit_history:<absolute_folder_of_benefit_history_file>/BenefitHistory.xlsx" -ay 2023
```

Every input is a `<source mode>:<absolute path of the input Excel file>` pair, so a single run
can read one report per source. The same source mode may be repeated when a source is split
across more than one file:
```sh
./run.py -ay 2026 -cal financial \
  -i "groww_indian_stocks:<folder>/Stocks_Capital_Gains_Report.xlsx" \
     "groww_indian_mf:<folder>/Mutual_Funds_Capital_Gains_Report.xlsx" \
     "indmoney_us_stocks:<folder>/INDmoney_Tax_Report.xlsx"
```

### Source modes
| Source mode | Expected report | Feeds |
| --- | --- | --- |
| `etrade_benefit_history` | `BenefitHistory.xlsx` from ETRADE | schedule FA |
| `etrade_holdings_bystatus` | Holdings by status from ETRADE | schedule FA |
| `indmoney_us_stocks` | INDmoney consolidated tax report | realized sales |
| `groww_indian_stocks` | Groww stocks capital gains statement | realized sales |
| `groww_indian_mf` | Groww mutual funds capital gains statement | realized sales |

The realized sale modes report capital gains and do not feed the schedule FA generation. Their
sales are pooled across every input and then split by the schedule CG section they are reported
under: `111A_short`/`112A_long` for STT paid listed Indian equity shares and equity oriented
mutual funds, `other_slab_short`/`other_slab_long` for everything else.

Detailed options are listed below
```txt
usage: run.py [-h] [-o OUTPUT_FOLDER] -i SOURCE_MODE:INPUT_EXCEL_FILE [SOURCE_MODE:INPUT_EXCEL_FILE ...] [-cal {calendar,financial}] -ay ASSESSMENT_YEAR [-v] [--skip-refresh]

This is a Python module to generate Indian ITR schedule FA under section A3 automatically

options:
  -h, --help            show this help message and exit
  -o OUTPUT_FOLDER, --output OUTPUT_FOLDER
                        Specify the absolute path of the output folder for JSON data, default = <current_folder_path_of_the_script>
  -i SOURCE_MODE:INPUT_EXCEL_FILE [SOURCE_MODE:INPUT_EXCEL_FILE ...], --input SOURCE_MODE:INPUT_EXCEL_FILE [SOURCE_MODE:INPUT_EXCEL_FILE ...]
                        Specify one or more <source mode>:<absolute path of the input Excel file> pairs
  -cal {calendar,financial}, --calendar-mode {calendar,financial}
                        Specify the calendar period for consideration, default = calendar
  -ay ASSESSMENT_YEAR, --assessment-year ASSESSMENT_YEAR
                        Current year of assessment year. For AY 2019-2020, input will be 2019. Input will be of type integer
  -v, --verbose         Enable the debug logs
  --skip-refresh        Skip refreshing historic share prices from Yahoo Finance and use the bundled historic_data CSVs instead
```

## Historic data auto-refresh
`run.py` refreshes both data sources automatically before generating the schedule, so you
do not need to run the refresh scripts yourself:

- **Share FMV** (`historic_data/shares/<ticker>/data.csv`) from Yahoo Finance via `yfinance`,
  for every ticker in your `BenefitHistory.xlsx`.
- **RBI/FBIL reference rates** (`historic_data/rates/rbi/rates.xls`) from the FBIL benchmark
  via the public [Frankfurter API](https://frankfurter.dev), for every currency used by those
  tickers. FBIL data is available from 2018-07-10 onwards; only the refreshed currency pairs
  are replaced, other pairs already in the file are left untouched.

If a dependency is missing or there is no network, the run logs a warning and falls back to
the bundled data. Pass `--skip-refresh` to force the bundled data (useful when offline). You
can still run `refresh_historic_data.py` or `refresh_rbi_rates.py` manually.

## Output
Inside the `output` folder(if nothing else is specified), the `ticker` folder will be created under which `fa_entries.csv` will be generated. For example, if your `BenefitHistory.xlsx`
contains entries related to `adbe` then the folder will be `output/adbe/fa_entries.csv`

The realized sale modes write `asset_sales.xlsx` into the same folder, holding one sheet per
schedule CG section present, each named after that section.

# Limitations
- Only parsing data from `BenefitHistory.xlsx` is supported.
-  If you have sold any shares, the script will not adjust those. You have to subtract the `BenefitHistory.xlsx` manually
-  This script is only tested under Mac, with a single `adbe` ticker with `calendar` `--calendar-mode` mode
-  Currently script works based on `historic_data`. Share FMV values is  present in [data.csv][data csv file]([ref][data csv ref])(check the first and last data in the file) and [rates.xls][SBI rates]([ref][SBI rates ref]) for RBI rate conversion

# Author
[Atul Gupta](https://github.com/atulgpt)

# Disclaimer
In case of any issues, please create a bug report. Also, do not entirely depend on the script for ITR filing. Do your own due diligence before filing your ITR.


 [data csv file]: https://github.com/atulgpt/SeFA/blob/main/historic_data/shares/adbe/data.csv
 [data csv ref]: https://finance.yahoo.com/quote/ADBE/history/
 [SBI rates]: https://github.com/atulgpt/SeFA/blob/main/historic_data/rates/rbi/rates.xls
 [SBI rates ref]: https://www.fbil.org.in/#/home