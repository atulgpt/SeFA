import os
import json
import csv
import typing as t


class MapEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, map):
            return list(o)
        return json.JSONEncoder.default(self, o)


def write_to_file(
    output_folder_abs_path: str,
    file_name: str,
    obj,
    override: bool,
    print_path_to_console: bool = False,
) -> str:
    if not os.path.exists(output_folder_abs_path):
        os.makedirs(output_folder_abs_path)

    final_file_abs_path = os.path.join(output_folder_abs_path, file_name)

    if os.path.exists(final_file_abs_path) and not override:
        raise AssertionError(
            f"Path {final_file_abs_path} already exists and force(-f) flag is not added to delete the path"
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
    output_file_abs_path: str,
    file_name: str,
    keys: t.List[str],
    objs,
    override: bool,
    print_path_to_console: bool = False,
) -> str:
    if not os.path.exists(output_file_abs_path):
        os.makedirs(output_file_abs_path)

    final_file_abs_path = os.path.join(output_file_abs_path, file_name)
    if os.path.exists(final_file_abs_path) and not override:
        raise AssertionError(
            f"Path {final_file_abs_path} already exists and force(-f) flag is not added to delete the path"
        )
    with open(final_file_abs_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(keys)
        for obj in objs:
            writer.writerow(obj)
        if print_path_to_console:
            __print_file_path(final_file_abs_path)
    return final_file_abs_path


def __print_file_path(final_path: str):
    print(f"Output file created at {final_path}")
