import os

# Where the RBI/FBIL reference rates live
script_path = os.path.realpath(os.path.dirname(__file__))
RATES_FILE_ABS_PATH = os.path.join(
    script_path, os.pardir, os.pardir, "historic_data", "rates", "rbi", "rates.xlsx"
)
RATES_SHEET_NAME = "Reference Rates"
