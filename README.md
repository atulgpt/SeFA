# SeFa
Python module to generate Indian ITR schedule FA under section A3 automatically

# How to run
## Download `BenefitHistory.xlsx`
1. Click on `Stock Plan` menu tab
2. Click on `Holdings` menu tab
3. Click on `Benefit History` link either on `Employee Stock Purchase Plan (ESPP)` or `Restricted Stock (RS)`
4. Click on `Download` button which will open the popup.
5. Click on `Download Expanded` which will prompt you to download the `BenefitHistory.xlsx` file

## Run the script
The script runs on Python3 make sure it is installed on the system

Below example, the command runs the script with the downloaded `BenefitHistory.xlsx`
```sh
./run.py -i "BenefitHistory.xlsx" -ay 2023
```
Detailed options are listed below
```sh
usage: run.py [-h] [-o OUTPUT_FOLDER] -i INPUT_EXCEL_FILE [-m {etrade_benefit_history}] [-cal {calendar,financial}] -ay ASSESSMENT_YEAR [-v]

This is a Python module to generate Indian ITR schedule FA under section A3 automatically

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_FOLDER, --output OUTPUT_FOLDER
                        Specify the absolute path of the output folder for JSON data, default = <current_folder_path_of_the_script>
  -i INPUT_EXCEL_FILE, --input INPUT_EXCEL_FILE
                        Specify the absolute path for input benefit history(BenefitHistory.xlsx) Excel file
  -m {etrade_benefit_history}, --source-mode {etrade_benefit_history}
                        Specify the source mode. Currently, only benefit history from etrade is supported, default = etrade_benefit_history
  -cal {calendar,financial}, --calendar-mode {calendar,financial}
                        Specify the calendar duration for consideration, default = calendar
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
-  Currently `historic_data` is only present for filing the ITR for AY2023-2024

# Author
[Atul Gupta](https://github.com/atulgpt)

# Disclaimer
In case of any issues, please create a bug report. Also, do not entirely depend on the script for ITR filing. Do your own due diligence before filing your ITR.

