import os
import json
import csv


class MapEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, map):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def write_to_file(output_file_path, name, obj, override):
    if not os.path.exists(output_file_path):
        os.makedirs(output_file_path)

    final_file_path = os.path.join(output_file_path, name)

    if os.path.exists(final_file_path) and not override:
        raise Exception(
            f"Path {final_file_path} already exists and force(-f) flag is not added to delete the path"
        )
    with open(os.path.join(output_file_path, name), "w") as f:
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

    return final_file_path


def write_csv_to_file(output_file_path, name, keys, objs, override):
    if not os.path.exists(output_file_path):
        os.makedirs(output_file_path)

    final_file_path = os.path.join(output_file_path, name)
    if os.path.exists(final_file_path) and not override:
        raise Exception(
            f"Path {final_file_path} already exists and force(-f) flag is not added to delete the path"
        )
    with open(final_file_path, "w", newline="") as file:
        writer = csv.writer(file, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(keys)
        for obj in objs:
            writer.writerow(obj)
