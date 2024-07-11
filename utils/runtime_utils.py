import types
import typing as t


def warn_missing_module(package: str) -> t.Optional[types.ModuleType]:
    try:
        return __import__(package)
    except ImportError as e:
        print(
            f"You don't have `{package}` installed to run the script. Please run: python3 -m pip install {package}"
        )
        return None
