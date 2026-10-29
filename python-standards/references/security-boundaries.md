# Security Boundaries

Apply this reference when untrusted data can influence a sensitive operation.
Trace each relevant flow as source, normalization or validation, then sink. This
is a scoped boundary review, not a requirement to run a generic security suite.

## Trace trust and sensitive sinks

- Treat user input, files, network responses, environment variables, database
  values, and external-service results as untrusted until the owning boundary
  establishes otherwise.
- Follow that data through decoding, canonicalization, validation, storage, and
  reuse. Validation before a representation-changing normalization may not
  constrain the final value.
- Inspect command and shell arguments, SQL or other queries, template rendering,
  file paths, dynamic evaluation, and regular expressions for injection or
  resource-exhaustion paths. Prefer structured APIs and parameter binding over
  escaping assembled strings.
- Do not deserialize untrusted data with a mechanism capable of arbitrary object
  construction or code execution. Select parser modes and permitted types that
  match the actual trust model.

## Files, URLs, and remote targets

- For externally influenced file access or writes, address absolute paths,
  parent traversal, normalization, resolved containment, symlinks, overwrite
  policy, and time-of-check/time-of-use races.
- Keep file and publication lifetime rules in
  [resource-lifecycle.md](resource-lifecycle.md); security validation does not by
  itself make a write durable or atomic.
- For externally influenced URLs or hosts, constrain schemes, credentials,
  address ranges and destinations, ports, redirects, and name-resolution changes
  according to the repository's SSRF and egress contract.

## Secrets, identity, and authorization

- Do not expose secrets in logs, exceptions, tracebacks, fixtures, snapshots,
  generated documentation, or committed output. Redact at every representation
  that may cross the trust boundary, not only in the final UI.
- Authentication, authorization, permission, and other security decisions must
  fail closed on missing, malformed, indeterminate, or failed checks unless the
  governing contract explicitly defines a safe alternative.
- Do not use `assert` for external security conditions because optimized
  execution may remove it.
- For passwords, tokens, random identifiers, signatures, and secret comparisons,
  use primitives and parameters approved by the repository's contract. Do not
  invent cryptography or substitute ordinary randomness and equality where a
  security property is required.

## Dependencies and evidence limits

- Treat a changed dependency source, name, version constraint, lock entry, build
  hook, or install script as part of the supply-chain boundary. Preserve the
  repository's provenance, integrity, and review policy.
- Lint, type checking, and static scanning are useful minimum evidence, not proof
  that a flow is safe.
- Use only security scanners already configured by the repository or explicitly
  requested by the user. Do not install tools, launch active attacks, access a
  real network, or test production systems without specific authorization.
- In a security review, rank findings by required attacker control, reachable
  impact, and confidence in the supporting data flow. Distinguish demonstrated
  vulnerabilities from hardening opportunities.
