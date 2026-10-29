# Tabular Data

Apply this reference only when the task actually reads, transforms, or writes
CSV, XLS, or XLSX data, or implements the corresponding parser or converter. A
filename, string literal, or incidental `.csv` mention in source code is not
enough to route here.

## Parse from the data contract

- Decide column types from the producing and consuming contract, not solely from
  library inference.
- Preserve string identifiers, leading zeros, and integers larger than the exact
  range of downstream numeric representations.
- Define how empty strings, missing cells, null markers, whitespace, and mixed
  types are represented. Do not let default NA or dtype inference silently
  rewrite meaningful values.
- Validate required columns, duplicate headers, row shape, and domain constraints
  before publishing transformed output.
- When converting types, report invalid values with column and row context rather
  than silently coercing them unless coercion is part of the contract.

## Spreadsheet fidelity

- Treat XLS and XLSX as display or exchange formats when that is their role; do
  not repeatedly round-trip them through inferred dataframes as a storage
  workflow.
- Account for spreadsheet date systems, formatted numbers, formulas versus
  cached values, merged cells, and library support before claiming fidelity.
- Keep an authoritative machine-readable source only when the user or repository
  contract defines one. Do not automatically create an adjacent CSV backup or
  assume an existing CSV is more authoritative than a workbook.
- Any backup, re-synchronization, or source-of-truth policy must be explicit about
  direction, ownership, and conflict handling.

## Text encoding

- Prefer a declared encoding or producer contract.
- If detection is necessary, use conservative candidates and validate the entire
  file, delimiters, headers, and representative values before accepting one.
- When more than one encoding remains plausible, fail explicitly and request or
  require the source encoding. Do not guess and then publish potentially
  corrupted text.
- Preserve newline and quoting behavior when byte-level compatibility matters.

## Publication

For create, overwrite, resume, staging, verification, or remote output behavior,
apply [resource-lifecycle.md](resource-lifecycle.md). This file does not redefine
publication or atomicity rules.

When a parser or converter has a meaningful round-trip, idempotence, or data
invariant, use [testing-evidence.md](testing-evidence.md) to decide whether
example-based or property-based evidence is warranted. This file does not make a
property-testing dependency mandatory.
