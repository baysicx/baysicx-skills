---
name: python-standards
description: Use when writing, editing, reviewing, or validating Python in an existing repository or workspace. Applies repository-declared runtimes and tooling, contract-aware interfaces, justified structure, explicit failure and resource ownership, and sufficient validation.
---

# Python Standards

Use this Skill as a repository-aware supplement for Python work. Do not replace
the repository's architecture, runtime, or release policy with generic rules.

## Authority and scope

Apply instructions in this order:

1. The user's goal and authorization boundary.
2. Repository instructions, project configuration, and established contracts.
3. The general guidance in this Skill.

Preserve agreed external contracts unless the requested change intentionally
changes them. For an explicit breaking change, update affected callers, tests,
documentation, and entry points together. Do not add compatibility layers unless
the user or repository contract requires them.

For review-only requests, stay read-only. Report evidence, impact, and priority;
do not modify code unless the user also asks for a fix.

## Reference routing

Read only the references that apply, but read each selected file completely:

- For every actual Python edit, cleanup, or validation task, read
  [references/core-edit.md](references/core-edit.md).
- For public APIs, CLIs, parsers, schemas, protocol boundaries, or
  contract-level review, also read
  [references/boundary-contracts.md](references/boundary-contracts.md).
- When adding or changing tests, fixing a bug, changing behavior, reviewing test
  sufficiency, or configuring test infrastructure, also read
  [references/testing-evidence.md](references/testing-evidence.md).
- When untrusted input reaches a shell, query, template, deserializer, file path,
  URL, secret, authentication or authorization decision, or dependency boundary,
  also read
  [references/security-boundaries.md](references/security-boundaries.md).
- For concurrency, generators, clients, subprocesses, locks, background tasks,
  atomic publication, durable output, or remote mounts, also read
  [references/resource-lifecycle.md](references/resource-lifecycle.md).
- When changing `pyproject.toml`, a build backend, wheel or sdist contents,
  package data, `py.typed`, a console script, or installed-package behavior, also
  read [references/packaging-contracts.md](references/packaging-contracts.md).
- When actually reading, transforming, or writing CSV, XLS, or XLSX data, or
  implementing their parsers or converters, also read
  [references/tabular-data.md](references/tabular-data.md).
- Read [references/performance-evidence.md](references/performance-evidence.md)
  only when the user explicitly requests performance analysis or optimization,
  or the repository declares a relevant latency, throughput, memory, I/O, or
  startup budget. A loop, batch, cache, or concurrency construct alone does not
  trigger this reference.
- For explanation-only questions, load only the references genuinely needed to
  answer the question.

When scopes overlap, read every applicable reference. Each reference owns the
detailed rules for its topic; do not substitute one reference for another. For
example, a packaged public CLI implementation change normally needs core,
boundary, and packaging guidance, plus testing guidance when behavior or tests
change.

## Working principles

### Discover the project contract

- Inspect repository instructions and the configuration for packaging, Python,
  linting, typing, testing, and CI before choosing an environment or command.
- Identify every target runtime that applies to the affected path or artifact.
  A repository may intentionally use more than one Python version.
- Prefer repository-native entry points and tools. Do not create a new
  environment or introduce a tool merely because it is familiar.
- Ask only when a consequential choice cannot be resolved from the user request
  or repository evidence.

### Understand ownership before editing

- Find the definition, its real callers, tests, public exports, and relevant
  configuration with `rg` or the repository's native index.
- Classify the target as internal implementation, public interface, CLI,
  packaging boundary, generated artifact, or external-system integration.
- Place validation, schemas, constants, conversions, and lifecycle decisions in
  the layer that owns their contract.

### Keep structure proportional to responsibility

- Prefer direct, readable code and limit valueless indirection along the same
  execution path.
- An abstraction is justified when it owns a non-trivial algorithm, resource
  lifecycle, runtime isolation, domain invariant, or stable public contract.
- Do not reject sound structure because it uses several private helpers or more
  than one architectural layer. Do not extract code merely because two snippets
  look similar.

### Make contracts and failures explicit

- Type annotations and syntax must be valid for every declared runtime that
  loads the affected code.
- Public modules, classes, functions, and methods should have concise English
  documentation consistent with repository style.
- Required input must fail explicitly at the boundary that owns it, with enough
  field and protocol context to diagnose the problem.
- Catch only exceptions that can be handled meaningfully. Preserve primary
  failures when cleanup or reporting also fails.

### Validate what changed

- Use the smallest sufficient validation for the affected contract and runtime
  closure; broader validation is warranted when the blast radius is broad.
- Distinguish what local syntax, import, behavior, packaging, and integration
  checks actually prove.
- Report changed public interfaces and abstractions with their responsibilities,
  the validation performed, and any external behavior that remains unproven.
