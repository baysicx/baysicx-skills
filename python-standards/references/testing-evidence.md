# Testing Evidence

Apply this reference when adding or changing tests, fixing a bug, changing
behavior, reviewing whether tests are sufficient, or configuring test
infrastructure. Use the repository's testing system; this reference does not
mandate a framework or universal coverage target.

## Discover the test contract

- Identify the configured framework, supported entry points, test roots,
  fixtures, markers or tags, mocking conventions, and neighboring test style
  before writing or running tests.
- Verify which configuration the actual test command reads, including excludes,
  environment setup, plugins, and local suppressions.
- Select tests from the affected behavior and dependency closure. Do not assume
  the nearest filename is the complete validation surface.

## Match evidence to the change

- A bug fix or intentional behavior change needs a regression test that exercises
  the original observable problem, not merely adjacent successful behavior.
- When the old implementation is available and can run safely in an isolated,
  low-risk environment, demonstrate that the regression test fails before the
  fix and passes after it.
- If red-to-green evidence cannot be obtained safely or reproducibly, keep the
  valid regression test and report why the red state is unavailable and what
  remains unproven. Do not contact production systems, perform external side
  effects, or expand authorization merely to recreate a failure.
- For a behavior-preserving refactor, unchanged relevant tests passing are the
  primary evidence. Documentation, formatting, comments, and purely static type
  changes do not mechanically require new tests.

## Assert independent public behavior

- Assert public behavior and observable outcomes. Assert private calls or their
  order only when that interaction is itself part of the maintained contract.
- State expected protocol values independently. Do not import production
  constants, serializers, request builders, or field tables to construct the
  expectation that is meant to verify them.
- Do not obtain a green run by deleting or weakening an assertion, adding an
  unjustified skip or expected failure, swallowing warnings, or broadening a
  mock until the original behavior is no longer exercised.
- Keep tests independent of execution order, real network access, wall-clock
  timing, usernames, home directories, hostnames, and shared mutable state unless
  one is the explicit contract under test. Inject or control such dependencies.

## Choose advanced evidence deliberately

- For parsers, serializers, codecs, normalizers, or pure algorithms with useful
  round-trip, idempotence, or invariant properties, evaluate property-based
  testing. Introduce or use it only when the repository already supports the
  tool, the user requests it, or its benefit clearly justifies the added scope.
- Use coverage reports, mutation testing, or a full-suite run only when the
  repository configures them, the user asks for them, or the affected risk and
  dependency closure warrant them. Do not impose a universal percentage or run
  every test by default.
- During a repair loop, continue while failures are becoming more specific or
  fewer and the evidence is improving. Stop and reassess when results oscillate,
  repeat without progress, or expose a missing contract; do not use a generic
  fixed attempt count.

## Report the evidence boundary

Report the tests selected, their target runtime and configuration, whether
red-to-green was observed, and any behavior not established by the available
environment. A passing test is evidence only for the inputs, environment, and
observable contract it actually exercised.
