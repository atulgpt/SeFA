import os
import json
import csv
import typing as t


# A raw file backs the figures that are filed rather than being filed itself, so it
# sits one level under the output folder instead of beside the filed ones
RAW_OUTPUT_FOLDER_NAME = "raw"


class MapEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, map):
            return list(o)
        return json.JSONEncoder.default(self, o)


def __resolve_file_path(
    output_folder_abs_path: str, file_name: str, is_raw: bool, override: bool
) -> str:
    """
    Creates the folder the file goes into and returns its absolute path
    """
    folder_abs_path = (
        os.path.join(output_folder_abs_path, RAW_OUTPUT_FOLDER_NAME)
        if is_raw
        else output_folder_abs_path
    )
    if not os.path.exists(folder_abs_path):
        os.makedirs(folder_abs_path)

    final_file_abs_path = os.path.join(folder_abs_path, file_name)
    if os.path.exists(final_file_abs_path) and not override:
        raise AssertionError(
            f"Path {final_file_abs_path} already exists and force(-f) flag is not added to delete the path"
        )
    return final_file_abs_path


def write_to_file(
    output_folder_abs_path: str,
    file_name: str,
    obj,
    override: bool,
    is_raw: bool = False,
    print_path_to_console: bool = False,
) -> str:
    final_file_abs_path = __resolve_file_path(
        output_folder_abs_path, file_name, is_raw, override
    )
    with open(final_file_abs_path, "w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                obj,
                indent=2,
                cls=MapEncoder,
                ensure_ascii=True,
                sort_keys=True,
                default=vars,
            )
        )
        if print_path_to_console:
            __print_file_path(final_file_abs_path)

    return final_file_abs_path


def write_csv_to_file(
    output_folder_abs_path: str,
    file_name: str,
    keys: t.List[str],
    objs,
    override: bool,
    is_raw: bool = False,
    print_path_to_console: bool = False,
    data_quoting: int = csv.QUOTE_MINIMAL,
) -> str:
    final_file_abs_path = __resolve_file_path(
        output_folder_abs_path, file_name, is_raw, override
    )
    with open(final_file_abs_path, "w", newline="", encoding="utf-8") as file:
        csv.writer(file, delimiter=",", quoting=csv.QUOTE_MINIMAL).writerow(keys)
        writer = csv.writer(file, delimiter=",", quoting=data_quoting, escapechar="\\")
        for obj in objs:
            writer.writerow(obj)
        if print_path_to_console:
            __print_file_path(final_file_abs_path)
    return final_file_abs_path


def write_excel_sheets_to_file(
    output_folder_abs_path: str,
    file_name: str,
    sheets: t.List[t.Tuple[str, t.List[str], t.Any]],
    override: bool,
    is_raw: bool = False,
    print_path_to_console: bool = False,
) -> str:
    """
    Writes one workbook holding a `(sheet name, keys, objs)` triple per sheet, each
    sheet carrying its own set of keys
    """
    from utils.runtime_utils import warn_missing_module

    warn_missing_module("pandas")
    warn_missing_module("openpyxl")
    import pandas as pd

    final_file_abs_path = __resolve_file_path(
        output_folder_abs_path, file_name, is_raw, override
    )
    with pd.ExcelWriter(final_file_abs_path, engine="openpyxl") as writer:
        for sheet_name, keys, objs in sheets:
            pd.DataFrame(list(objs), columns=keys).to_excel(
                writer, sheet_name=sheet_name, index=False
            )
    if print_path_to_console:
        __print_file_path(final_file_abs_path)
    return final_file_abs_path


def __print_file_path(final_path: str):
    print(f"Output file created at {final_path}")
