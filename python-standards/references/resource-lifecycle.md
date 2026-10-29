# Resource Lifecycle

Apply this reference when work owns clients, generators, threads, pools,
processes, locks, connections, temporary files, durable output, or remote
publication.

## Ownership and shutdown

- Identify who creates, uses, stops, joins, and closes every resource.
- Make ownership visible in control flow through context managers or explicit
  `try`/`finally` scopes. Do not rely on garbage collection for timely release.
- On success, failure, cancellation, or early consumer exit, stop or finish
  dependent work before closing the shared resource it can still use.
- Treat asynchronous cancellation behavior as part of the public contract:
  define where cancellation is observed, which cleanup is shielded or awaited,
  and what state the caller can inspect afterward.
- A generator backed by a client, pool, connection, or file must either own that
  resource for its full iteration lifetime or make the caller's lifetime
  obligation explicit. It must not resume against an already closed resource.
- Release locks and temporary resources on every reachable exit path.

## Primary and cleanup failures

- A cleanup, finalization, close, or reporting failure must not silently replace
  the primary operation failure.
- Preserve the primary exception and attach the secondary failure through
  exception context, `add_note`, structured logging, or a separately inspectable
  result, as appropriate for the supported runtimes.
- If no primary failure exists, propagate or report cleanup failure according to
  the public contract; do not claim success after incomplete finalization.

## Concurrency, timeouts, and background work

- Name timeout parameters for what they actually bound: connection, individual
  request, result collection, graceful shutdown, or total operation.
- Keep these states distinct: the caller stopped waiting, cancellation was
  requested, local work terminated, and a remote side effect completed. Evidence
  for one state does not prove the others.
- Cancel or terminate work only through a supported mechanism and verify the
  resulting state when the contract permits it.
- Treat a timeout or lost acknowledgement after a side effect may have begun as
  an unknown outcome. Inspect durable or remote state before retrying.
- Background work must expose an inspectable handle or durable status, including
  process state, exit code, logs, or result/error files as appropriate.
- Do not silently fire and forget work whose completion affects the caller's
  outcome. Define shutdown, cancellation, and orphan-recovery behavior.
- Test concurrency and cancellation with events, barriers, fake clocks, or a
  controlled executor. Do not use arbitrary sleeps to guess when a state
  transition occurred.

## Durable output

- Define whether an operation creates, overwrites, resumes, or rejects existing
  output before mutation starts.
- Use staging names and ownership markers that cannot be mistaken for successful
  output. Make interrupted state discoverable and recoverable.
- Confirm success through read-back, manifest/hash comparison, schema checks, or
  another content-level verification appropriate to the contract.
- A successful API return alone is not sufficient evidence when publication can
  be delayed, partial, or redirected.

## Atomic publication and mounts

- Call publication atomic only when the destination backend guarantees the
  final rename or commit within the same namespace and failure domain.
- A move from local storage to FUSE, HDFS, an object-store mount, or another
  filesystem is a copy-and-delete boundary unless the backend explicitly proves
  stronger semantics. It is not an atomic publication primitive.
- For remote or mounted destinations, stage on the destination side, validate the
  staged content, use the backend's supported same-namespace finalization, and
  verify the published result.
- If the backend has no atomic finalization, document the weaker visibility
  contract and use manifests, versioned paths, completion markers, or another
  protocol that lets readers distinguish complete from incomplete output.
