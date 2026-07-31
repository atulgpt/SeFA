# SeFA — Agent Rules

Rules apply to every AI coding agent (Claude Code, Cowork, Cursor, Codex CLI, Aider).
`AGENTS.md` points here rather than repeating any of it.

## Helper placement

A helper whose only input is a type belongs **on that type**, not inside the module that
happens to call it first. A caller-local helper over a foreign type hides the API from the
next caller and gets duplicated.

Bad (`asset_aggregator` and `groww_indian_stocks_parser` each grew their own copy):

```python
# aggregator/asset_aggregator.py
def __original_value(transaction: Transaction) -> float:
    return round(transaction.fmv.price * transaction.quantity, 2)

# parser/demat/groww/groww_indian_stocks_parser.py
def __sale_value(sale: AssetSale) -> float:
    return sale.sale_transaction.fmv.price * sale.sale_transaction.quantity
```

Good (lives with the type it serves, discoverable from any call site):

```python
# models/transaction.py
@dataclass
class Transaction:
    date: DateObj
    fmv: Price
    quantity: float

    def total_value(self) -> float:
        """
        Value of the whole leg in the currency it was traded in
        """
        return round(self.fmv.price * self.quantity, 2)
```

Keep a helper module private only when it reads that module's own constants or state — a
sheet's column map, a report's block labels.

A helper that serves a type but cannot live on it (needs `pandas`, needs a rate lookup)
goes in the `utils` module for that concern, never in the first caller.

## Enums over parallel constants

A closed set of string values is an `enum.StrEnum`. Never a `t.Literal` plus a matching
block of module constants — the two drift, and a value that falls out of the `Literal` is
not caught at runtime.

Bad (the value and the type have to be edited in lockstep):

```python
SectionType = t.Literal["111A_short", "112A_long", "other_slab_short"]
SECTION_111A: SectionType = "111A_short"
SECTION_SLAB_SHORT: SectionType = "slab_short"   # not in the Literal any more
```

Good:

```python
class SectionType(enum.StrEnum):
    SECTION_111A = "111A_short"
    SECTION_112A = "112A_long"
    SECTION_SLAB_SHORT = "slab_short"
```

`StrEnum` members are real `str`s, so they still work as sheet names, CSV cells, dict keys
and comparison operands. Iterating the type yields declaration order, so a separate ordering
tuple is not needed either.

## Fail loud, never guess

Missing columns, unexpected empty results and broken invariants must **surface**. Do not log
a warning and return an empty list, and do not fall back to a default that produces a wrong
but plausible output.

Bad (a wrong input file silently produces an empty report):

```python
if not sales:
    logger.log(f"Excel sheet don't have any block matching {list(BLOCK_SECTION_TYPES)}")
    return []
```

Good:

```python
assert sales, (
    "Excel sheet don't have any block matching " + f"{list(BLOCK_SECTION_TYPES)}"
)
```

An assert message names what was expected **and** what was found, so the report can be fixed
without reading the parser:

```python
assert not missing_headers, (
    f"Groww stocks table is missing the column(s) {missing_headers}."
    + f" Found columns = {sorted(column_map)}"
)
```

Delete a fallback once it is unreachable. `assert len(codes) <= 1` plus a
`DEFAULT_REPORTING_CURRENCY_CODE` was dead the moment the caller stopped passing empty
lists; it became `assert len(codes) == 1`.

## Tax figures are read, not derived

Where a broker's report states a figure the statute defines — the holding period, the
grandfathered NAV, the realized gain — read it off the report. Recomputing risks disagreeing
with the source the taxpayer will be assessed against.

Derive only what the report does not state, and comment why:

```python
# Per unit value is derived from the total rather than read off the report's own
# per unit column, which is rounded and does not always multiply back to the total
```

A figure that cannot be read and cannot be safely derived asserts. Grandfathering under
section 55(2)(ac) needs the 31-Jan-2018 fair market value; a report that does not state it
fails rather than filing a wrong cost.

## Rounding

Money is `round(x, 2)`. A figure the ITR utility rejects as fractional is whole rupees via
`math.floor(x + 0.5)`, never Python's banker's `round`.

When a rounded total is split across rows, the **last row absorbs the remainder** so the
parts add back to the stated total exactly. Same rule for the charge split and for the
quarter wise breakup.

## Minimal diffs

Change only what the task requires. Do not reformat, re-document, rename or restructure code
you were not asked to touch, even when it violates a rule in this file.

When fixing a bug, prefer the smallest patch over a rewrite of the enclosing function. Do not
add docstrings to members you did not otherwise change.

Do not report unrelated issues unless asked.

## Documentation

Docstrings and comments state **what** a function returns from the caller's perspective and
**why** a non-obvious rule exists — a statutory reference, a quirk of the source report.
Never the implementation steps, which go stale on the first rewrite.

Bad:

```python
def __quarter_index(sale: AssetSale) -> int:
    """
    Formats the month and day, converts to a financial year key, then loops the
    QUARTERS tuple comparing keys and returns the matching index
    """
```

Good:

```python
def __financial_year_key(month: int, day: int) -> t.Tuple[int, int]:
    """
    Orders a `(month, day)` inside the financial year, which opens in April
    """
```

## Explicit types

Annotate parameters and return types. Annotate a container being built up
(`sales: t.List[AssetSale] = []`) so the element type is visible at the declaration.

## Output layout

A file the taxpayer uploads or files goes at the root of the output folder. Anything that
only backs those figures is written with `is_raw=True`, which puts it under `raw/`.

`file_utils` owns the folder resolution — a writer never joins `raw` itself.

## Parser conventions

- One parser per source report, under `parser/demat/<broker>/`.
- A parser exposes `parse(input_file_abs_path, time_bounds=None) -> t.List[AssetSale]` for a
  realized sale source, and is registered in `run.py` under `SALE_OPERATION_PARSERS`.
- Column and block labels are module constants, never inline strings, so a rename on the
  broker's side is a one line change.
- Match a sheet or a block by pattern or by label constant, never by index.
- Broker specific data that is not in the report (a list of non equity linked scrips) lives
  in that broker's `constants.py`.
