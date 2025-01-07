# SeFA
Python module to generate Indian ITR schedule FA under section A3 automatically

# How to run
## Download `BenefitHistory.xlsx` from `ETRADE`
1. Click on `At Work` top menu bar
2. Click on `Holdings` top submenu bar
3. Click on `Benefit History` link either on `Employee Stock Purchase Plan (ESPP)` or `Restricted Stock (RS)`
4. Click on `Download` button which will open the popup.
5. Click on `Download Expanded` which will prompt you to download the `BenefitHistory.xlsx` file

## Run the script
The script requires Python 3.8 or higher. Please ensure that it is installed on your system. In newer versions of Python, you may encounter an [`externally-managed-environment`](https://peps.python.org/pep-0668/). In this case, you can create a [Python virtual environment](https://docs.python.org/3/library/venv.html#creating-virtual-environments) and then run the script after activating the virtual environment.

Below example, the command runs the script with the downloaded `BenefitHistory.xlsx`
```sh
./run.py -i "<absolute_folder_of_benefit_history_file>/BenefitHistory.xlsx" -ay 2023
```
You may also have to install the missing Python3 dependencies using command `pip3 install <dependency_name>`

Detailed options are listed below
```txt
usage: run.py [-h] [-o OUTPUT_FOLDER] -i INPUT_EXCEL_FILE [-m {etrade_benefit_history}] [-cal {calendar,financial}] -ay ASSESSMENT_YEAR [-v]

This is a Python module to generate Indian ITR schedule FA under section A3 automatically

options:
  -h, --help            show this help message and exit
  -o OUTPUT_FOLDER, --output OUTPUT_FOLDER
                        Specify the absolute path of the output folder for JSON data, default = <current_folder_path_of_the_script>
  -i INPUT_EXCEL_FILE, --input INPUT_EXCEL_FILE
                        Specify the absolute path for input benefit history(BenefitHistory.xlsx) Excel file
  -m {etrade_benefit_history}, --source-mode {etrade_benefit_history}
                        Specify the source mode. Currently, only benefit history from etrade is supported, default = etrade_benefit_history
  -cal {calendar,financial}, --calendar-mode {calendar,financial}
                        Specify the calendar period for consideration, default = calendar
  -ay ASSESSMENT_YEAR, --assessment-year ASSESSMENT_YEAR
                        Current year of assessment year. For AY 2019-2020, input will be 2019. Input will be of type integer
  -v, --verbose         Enable the debug logs
```

## Output
Inside the `output` folder(if nothing else is specified), the `ticker` folder will be created under which `fa_entries.csv` will be generated. For example, if your `BenefitHistory.xlsx`
contains entries related to `adbe` then the folder will be `output/adbe/fa_entries.csv`

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