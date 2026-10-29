# Boundary Contracts

Apply this reference to public APIs, CLIs, parsers, schemas, external protocols,
and reviews where the contract itself is in scope.

## Contract review

For each affected boundary, compare all of the following rather than reviewing
the signature in isolation:

- annotations and defaults;
- inputs actually supported by the implementation;
- runtime validation and normalization;
- returned values and observable state;
- exception types, messages, and chaining;
- cost, I/O, mutation, blocking, and other side effects;
- docstrings and user-facing documentation;
- real callers and their assumptions;
- tests and the cases they independently establish.

Record mismatches as contract defects. A type of `T | None` means callers are
allowed to pass `None`; it must not be used merely to describe an input that is
accepted by the signature and then rejected as invalid. If `None` is invalid,
remove it from the public type and fail clearly at untyped or serialized input
boundaries.

## Validation ownership

- Validate an input in the layer that owns that input boundary and schema.
- A composition or orchestration layer should delegate to the owning component
  rather than reimplementing the same validation with different error semantics.
- Normalize once at the owner boundary. Downstream code may rely on the
  normalized internal representation and enforce only its own invariants.
- When tightening a type, default, accepted value, or failure rule, scan and fix
  all real call sites, tests, examples, exports, and command adapters in the same
  change.

## Definition ownership

- Constants, schema declarations, protocol fields, and data transformations
  belong to the component that owns the represented contract.
- Do not move a single-consumer definition to a generic utility module for
  possible future reuse.
- Share an implementation only when consumers operate on the same domain object
  under the same contract. Similar-looking code with different ownership,
  failures, or evolution pressure should remain separate.
- A stable public abstraction may legitimately use several private helpers or
  layers when each owns a distinct responsibility.

## Contract evidence

- Contract and protocol tests must compare production output with independently
  stated expected values or fixtures. Do not use the production constructor,
  serializer, schema constant, or field table to prove its own result.
- For regression evidence, assertion design, isolation, property tests, coverage,
  or test execution scope, apply
  [testing-evidence.md](testing-evidence.md).

## Contract changes

- Determine from the user request and repository policy whether compatibility is
  required; do not infer it from generic conservatism.
- For an intentional breaking change, remove obsolete entry points, forwarding
  layers, documentation, examples, and tests in the same change, and update all
  maintained callers.
- Add an adapter or deprecation path only when the governing contract explicitly
  requires a migration window. Give it an owner and removal condition.
