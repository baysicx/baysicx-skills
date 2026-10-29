# Performance Evidence

Apply this reference only for an explicit performance analysis or optimization
request, or when the repository declares a relevant performance budget. Ordinary
loops, batches, caches, and concurrency do not trigger performance work by
themselves.

## Define the claim before optimizing

- Name the metric and budget, representative workload and data distribution,
  target runtime, dependency versions, hardware, and relevant operating
  conditions.
- Establish a repeatable baseline before changing code. Keep inputs, environment,
  warm-up, measurement scope, and instrumentation consistent; run enough repeats
  to report variance rather than a single favorable sample.
- Profile the representative path to locate the actual bottleneck before choosing
  an algorithm, batch size, cache, concurrency model, or data structure.

## Preserve the whole contract

- Keep correctness and contract tests passing first. Compare optimized and prior
  outputs through their public behavior, including failure and ordering semantics
  where applicable.
- Evaluate the dimensions relevant to the task: latency, throughput, peak memory,
  I/O, startup cost, and algorithmic complexity. A microbenchmark improvement
  must not conceal a representative-workload regression elsewhere.
- A cache needs an explicit key, value owner, lifetime, invalidation rule,
  capacity policy, concurrency behavior, and failure semantics. A single cache
  hit is not evidence that the production workload improved.
- Choose concurrency from evidence about I/O waits, CPU work, interpreter and GIL
  behavior, serialization, scheduling, and process overhead in the target
  runtime. Do not assume that more workers are faster.

## State evidence limits

- Do not claim an improvement when the observed difference is within measurement
  noise or the workload is not representative.
- Report baseline and changed measurements, variance, correctness checks, resource
  tradeoffs, and the tested environment. State which production scale, hardware,
  contention, or remote behavior the local result did not prove.
