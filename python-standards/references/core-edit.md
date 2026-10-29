# Core Python Edit

Use this as the operating checklist for ordinary Python edits, cleanup, and
validation.

## Establish the runtime matrix

Before editing, map each affected path or artifact to its target runtime and the
commands that can validate it:

| Path or artifact | Target runtime | Repository-native validation |
| --- | --- | --- |
| Affected source or package | Declared interpreter(s) | Focused tests, lint, type check, compile |
| CLI or import surface | Runtime that executes it | Entry-point and import smoke tests |
| Built artifact | Runtime that installs or loads it | Build, install, and artifact inspection |

Build the real matrix from repository evidence; do not copy the example rows
literally. A single repository may have separate runtime closures, and their
checks need not use the same interpreter.

Inspect, in order:

1. User and repository instructions.
2. `pyproject.toml`, lock files, tool configuration, packaging metadata, and
   supported-version classifiers.
3. Test, CI, build, launcher, container, or platform configuration.
4. Existing project environments and documented commands.

A configuration file's presence does not prove that the invoked tool reads it.
Resolve the effective configuration and actual tool version, and check for
duplicate or shadowing configuration, inherited settings, excludes, and local
suppressions that could change the result.

Prefer the repository's managed interpreter and entry points. Do not provision a
new environment solely to perform a check unless the task or project requires
it. If the environment remains ambiguous, ask only when the alternatives would
materially change the implementation or evidence.

Keep these compatibility dimensions separate:

- **Syntax compatibility:** the code parses or compiles on a target interpreter.
- **Dependency compatibility:** required imports and versions are available.
- **Runtime behavior:** execution produces the expected result.
- **Installed-artifact behavior:** the built wheel, package, archive, or entry
  point contains and loads the intended code.
- **Remote-platform behavior:** an external service or managed runtime accepts
  and executes it. Local checks do not prove this dimension.

The type checker's target Python version belongs to the source closure being
checked. It need not match the interpreter that happens to run the checker.

## Inspect before changing

- Locate the implementation, callers, imports, exports, tests, configuration,
  and documentation with `rg` or repository-native navigation.
- Decide whether the target is internal, public, CLI-facing, packaging-facing,
  generated, or externally executed.
- Read the complete implementation path before changing signatures or moving
  ownership.
- When a shared definition changes, search all actual use sites rather than
  trusting the first caller or test found.

Apply the additional reference that owns each affected concern:

- public or protocol contracts: [boundary-contracts.md](boundary-contracts.md);
- test changes or test evidence: [testing-evidence.md](testing-evidence.md);
- untrusted data at sensitive boundaries:
  [security-boundaries.md](security-boundaries.md);
- resource ownership and durable publication:
  [resource-lifecycle.md](resource-lifecycle.md);
- built and installed distribution behavior:
  [packaging-contracts.md](packaging-contracts.md);
- actual tabular processing: [tabular-data.md](tabular-data.md);
- explicitly requested or repository-budgeted performance work:
  [performance-evidence.md](performance-evidence.md).

## Design and implementation

- Prefer a direct control flow with the fewest useful boundaries.
- Add an abstraction only when it has a clear responsibility, such as an
  algorithm, lifecycle, runtime isolation, domain invariant, or public contract.
- Avoid pass-through wrappers, synonym APIs, speculative utilities, and chains
  of helpers that obscure ownership without simplifying behavior.
- Multiple focused private helpers are appropriate when they name distinct
  decisions, reduce duplication within one owner, or make complex behavior
  independently testable.
- Do not mix unrelated cleanup, renaming, or formatting into a focused change.

## Types and documentation

- Use the typing syntax supported by every runtime that imports the file. Follow
  the repository's configured type checker and annotation policy.
- Keep annotations aligned with real accepted inputs, returned values, and
  failure behavior. Do not use permissive types to conceal an unresolved
  contract.
- Give public modules, classes, functions, and methods concise English docstrings
  unless the repository explicitly defines another convention.
- Document contracts, costs, side effects, lifecycle, and non-obvious decisions;
  do not narrate obvious line-by-line mechanics.

## Failure behavior

- Required fields must fail explicitly in the boundary that owns their schema.
  Either direct indexing or explicit validation may be appropriate; the error
  must identify enough of the field and protocol context to be actionable.
- Validate untrusted input before performing irreversible or costly work.
- Catch narrow exception types only when adding context, translating at a real
  boundary, retrying safely, or performing necessary cleanup.
- Preserve exception chaining when translating failures. Avoid blanket catches,
  silent fallbacks, and logging followed by accidental success.
- Treat assertions as developer invariants, not validation for external input.

## Common Python hazards

- Do not use mutable objects as default argument values.
- Distinguish `None` from falsy values such as `0`, `False`, `""`, and empty
  containers when the contract distinguishes them.
- Avoid broad `except Exception` unless it is a deliberate top-level containment
  boundary that preserves the failure state.
- Use context managers or explicit `try`/`finally` ownership for resources.
- Be deliberate about iterator consumption, late-bound closures, shallow copies,
  timezone-naive datetimes, text encodings, and path semantics.
- Do not mutate `sys.path` to hide packaging or import problems.

## Conservative cleanup

- Remove an import, helper, class, module, configuration entry, or compatibility
  path only after searching definitions, imports, dynamic lookup, entry points,
  tests, documentation, and packaging metadata.
- Keep cleanup behavior-preserving unless contract change is explicitly in
  scope.
- After deletion or movement, rerun search and import-oriented checks to catch
  stale references.

## Review findings

- Classify an actionable finding as a correctness defect, contract risk, or
  optional improvement. Do not present style preference as a correctness issue.
- Report only findings supported by repository evidence, a reproducible behavior,
  or a clear contract mismatch. State the affected behavior and a practical
  remedy.
- Prioritize findings by likely impact and confidence. Omit speculative warnings
  that the available code or configuration does not make actionable.

## Smallest sufficient validation

Choose checks based on the changed contract:

- **Internal implementation:** focused behavior tests, configured lint and
  formatting checks, relevant type checks, and compilation for the affected
  runtime.
- **Public interface:** scan callers, run contract and behavior tests, and smoke
  test public imports.
- **CLI:** exercise both the installed console script and `python -m` route when
  both are supported.
- **Package boundary:** follow
  [packaging-contracts.md](packaging-contracts.md) to validate the real built and
  installed artifact rather than only the source tree.
- **Multiple runtimes:** validate each affected closure with its own target
  interpreter and commands; do not substitute one version for another.
- **External system:** run only authorized checks and state plainly which remote
  behavior local validation did not prove.

Start focused. Expand when a public contract, shared owner, packaging boundary,
or broad dependency graph makes the wider check necessary. If a configured tool
is unavailable, report the gap rather than silently replacing it with a weaker,
unrelated check.

## Completion report

Summarize:

- the behavior and contracts changed or preserved;
- each new or changed public interface or abstraction and its responsibility;
- validation commands and target runtimes;
- skipped or failed checks and the behavior they leave unproven.
