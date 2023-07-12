import pprint
import json

debug = False


def __print_json(json_data):
    json_formatted_str = json.dumps(json_data, indent=2, sort_keys=True, default=vars)
    print(json_formatted_str)


def debug_log_json(obj):
    if debug:
        __print_json(obj)


def log_json(obj):
    __print_json(obj)


def __print_pretty(msg):
    pp = pprint.PrettyPrinter(indent=2, sort_dicts=True)
    pp.pprint(msg)


def debug_log(msg):
    if debug:
        __print_pretty(msg)


def log(msg):
    __print_pretty(msg)
