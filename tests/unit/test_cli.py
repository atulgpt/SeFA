import pathlib
import shutil
import subprocess
import sysconfig
import typing as t

import pytest
from openpyxl import Workbook

from sefa import cli

# `pythonpath` lets a test import `sefa` straight out of `src`, so the console
# script only exists once the project itself has been installed. It is looked up
# in the scripts folder of the interpreter running the tests rather than on PATH,
# which a runner that never activated its environment does not carry
SEFA_COMMAND = shutil.which("sefa", path=sysconfig.get_path("scripts"))

# One Groww stocks capital gains statement. The charges block runs up to the first
# row carrying no label, so the blank row is what ends it before the trades block
TEST_GROWW_STOCKS_ROWS: t.List[t.List[t.Any]] = [
    ["Charges", None],
    ["STT", 10],
    ["Total", 50],
    [None, None],
    ["Short Term trades", None],
    [
        "Stock name",
        "ISIN",
        "Quantity",
        "Buy date",
        "Buy price",
        "Sell date",
        "Sell price",
        "Realised P&L",
    ],
    ["ACME", "INE0001A01011", 10, "01-02-2025", 100, "01-06-2025", 120, 200],
]

TEST_ASSESSMENT_YEAR = "2026"


@pytest.fixture(name="groww_stocks_report")
def fixture_groww_stocks_report(tmp_path: pathlib.Path) -> pathlib.Path:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None, "a new workbook opens with an active sheet"
    for row in TEST_GROWW_STOCKS_ROWS:
        sheet.append(row)
    report = tmp_path / "Stocks_Capital_Gains_Report.xlsx"
    workbook.save(report)
    return report


def test_default_output_path_is_top_output():
    print(cli.default_output_folder_abs_path)
    assert cli.default_output_folder_abs_path.endswith("/output")
    assert not cli.default_output_folder_abs_path.endswith("/src/sefa/output")


def test_returns_zero_and_writes_the_upload(groww_stocks_report, tmp_path):
    output_folder = tmp_path / "out"
    exit_code = cli.main(
        [
            "-i",
            f"groww_indian_stocks:{groww_stocks_report}",
            "-ay",
            TEST_ASSESSMENT_YEAR,
            "-o",
            str(output_folder),
            "--skip-refresh",
        ]
    )
    assert exit_code == 0
    assert (output_folder / "capital_gain_summary.xlsx").exists()
    assert (output_folder / "raw" / "asset_sales.xlsx").exists()


def test_unreadable_report_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        cli.main(
            [
                "-i",
                f"groww_indian_stocks:{tmp_path / 'missing.xlsx'}",
                "-ay",
                TEST_ASSESSMENT_YEAR,
                "-o",
                str(tmp_path / "out"),
                "--skip-refresh",
            ]
        )


def test_unsupported_operation_mode_raises(tmp_path):
    with pytest.raises(AssertionError, match="unsupported operation mode"):
        cli.main(
            [
                "-i",
                f"nope:{tmp_path / 'report.xlsx'}",
                "-ay",
                TEST_ASSESSMENT_YEAR,
                "-o",
                str(tmp_path / "out"),
                "--skip-refresh",
            ]
        )


def test_missing_required_input_exits_with_the_usage_code():
    with pytest.raises(SystemExit) as exit_info:
        cli.main([])
    assert exit_info.value.code == 2


def test_keyboard_interrupt_returns_the_interrupt_code(monkeypatch):
    def interrupt(_argv):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "__run", interrupt)
    assert cli.main([]) == 130


@pytest.mark.skipif(
    SEFA_COMMAND is None, reason="the console script needs the project installed"
)
def test_console_script_runs_the_pipeline(groww_stocks_report, tmp_path):
    """
    The `sefa` command the entry point declares resolves and reports the exit code
    of the run it wrapped
    """
    output_folder = tmp_path / "out"
    completed = subprocess.run(
        [
            t.cast(str, SEFA_COMMAND),
            "-i",
            f"groww_indian_stocks:{groww_stocks_report}",
            "-ay",
            TEST_ASSESSMENT_YEAR,
            "-o",
            str(output_folder),
            "--skip-refresh",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert (output_folder / "capital_gain_summary.xlsx").exists()
