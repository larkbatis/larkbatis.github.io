# Performance & Benchmarks

Here is the breakdown of performance differences between LarkBatis and standard MyBatis: theoretical differences you can verify directly in source code, microbenchmark measurements, and realistic database latency comparisons.

## Structural Differences

| Dimension | MyBatis | LarkBatis | Technical Explanation |
|---|---|---|---|
| Runtime footprint | 40,017 lines | ~1,500 lines | Direct line count of `org.apache.ibatis` vs. `larkbatis-runtime` |
| Runtime dependencies | OGNL, Javassist | None (only JDBC) | MyBatis loads OGNL/Javassist for dynamic SQL evaluation and lazy loading |
| Reflection call sites on query path | 4 call groups | 0 | MyBatis reflects during cache key generation, OGNL evaluation, parameter binding, and result mapping |
| Reflective operations per row | 1 × column count | 0 | MyBatis calls `metaObject.setValue()` per column via `BeanWrapper` and `MethodInvoker` |
| Native image reachability metadata | Complex configuration | Zero required | Standard MyBatis ships no native reachability metadata; LarkBatis uses zero runtime reflection |
| Parameter validation | Runtime error | Compile-time error | Mappers are compiled into standard Java classes; `javac` checks parameter types directly |
| Raw SQL security auditing | Inspect every XML file | Search for `unsafeRawSql` | Dynamic SQL splices pass through `SqlFragment.unsafeRawSql`, creating a single audit point |

## Benchmark Measurements

These numbers are measured using JMH 1.37 across 10,000-row result sets against H2 on JDK 21 (Apple M5 Pro):

| Metric | Stock MyBatis | LarkBatis | Difference |
|---|---|---|---|
| Memory allocation per row | ~1.0 KB | 129 B | **−87%** |
| Latency per row | 0.30 µs | 0.08 µs | **−73%** |
| 10k-row query execution time | ~3.0 ms | 0.8 ms | **−72%** |
| 10k-row query memory allocation | ~10 MB | 1.23 MB | **−88%** |
| Dynamic SQL query time | 15–20 µs | 9.5 µs | **−45%** |
| Dynamic SQL memory allocation | 28 KB | 12 KB | **−57%** |

### Key Takeaways

1. **Row reading gains exceed dynamic SQL gains**: Eliminating per-row reflection saves significantly more CPU cycles and memory than compile-time SQL string concatenation.
2. **Escape analysis cannot clean up MyBatis per-row allocations**: The `setValue → BeanWrapper → Invoker` reflection chain is too deep for HotSpot JIT to eliminate `PropertyTokenizer` and parameter array allocations.
3. **Performance benefits scale with row count**: On a single-row query, saving 0.2 µs of CPU overhead is negligible compared to network round-trip latency. On multi-row reports, list queries, and batch exports returning thousands of rows, eliminating per-row reflection reduces execution time and GC pressure substantially.

!!! quote "Realistic expectations"

    LarkBatis delivers significant performance improvements for multi-row queries, report exports, and list endpoints. For single-row `findById` lookups over a network connection, the latency difference is negligible.

## Detailed JMH Benchmarks

### Multi-Row Queries (`findAll`)

Benchmarking full table scans comparing narrow (4 columns) and wide (12 columns) rows:

| Rows | Columns | MyBatis | LarkBatis | Latency Δ | Allocation Δ |
|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 1.48 µs | 0.36 µs | **−75%** | 6.6 KB → 1.8 KB (−73%) |
| 1 | 12 | 3.29 µs | 0.43 µs | **−87%** | 10.7 KB → 1.9 KB (−83%) |
| 100 | 4 | 17.1 µs | 3.23 µs | **−81%** | 67.6 KB → 10.2 KB (−85%) |
| 100 | 12 | 39.4 µs | 5.78 µs | **−85%** | 107 KB → 19.1 KB (−82%) |
| 10,000 | 4 | 1.53 ms | 0.29 ms | **−81%** | 6.77 MB → 1.05 MB (−84%) |
| 10,000 | 12 | 3.38 ms | 0.54 ms | **−84%** | 10.2 MB → 1.88 MB (−82%) |

### Single-Row Lookup Over Real Network Protocol

Measuring `findById(7)` returning 1 row with 4 columns over loopback TCP:

| Connection Transport | MyBatis | LarkBatis | Latency Δ | Allocation Δ |
|---|---:|---:|---:|---:|
| In-memory direct call | 1.45 µs | 0.36 µs | −75% | 6.6 KB → 1.6 KB (−75%) |
| H2 via TCP socket (loopback) | 94.2 µs | 89.2 µs | **−5%** | 8.9 KB → 4.0 KB (−55%) |

Over a real TCP connection, network latency accounts for over 90% of total response time. However, memory allocation reductions (55%) still reduce GC churn under high throughput.

### Cold Startup Time

Measuring cold JVM startup to first query execution across 4 mapper interfaces (51 total statements) on JDK 17:

| Metric | MyBatis | LarkBatis | Improvement |
|---|---:|---:|---|
| Cold start to first query | 61.8 ms | **6.3 ms** | **−90%** |
| Memory allocated during startup | 27.0 MB | 15.8 MB | **−41%** |

LarkBatis avoids runtime XML parsing, OGNL class loading, reflection metadata construction, and statement map initialization at startup.

### JDK Version Impact

Thanks to JEP 416 (re-implementing core reflection using method handles), MyBatis reflection performance improved significantly in JDK 18+.

| Query (10,000 rows × 4 columns) | JDK 17 | JDK 21 | Difference |
|---|---:|---:|---|
| MyBatis | 2.13 ms | 1.53 ms | **−28%** |
| LarkBatis | 0.302 ms | 0.289 ms | −4% |
| **LarkBatis Performance Advantage** | **7.1×** | **5.3×** | |

LarkBatis maintains a 5.3× throughput advantage on JDK 21 without relying on reflection.

## Unverified Claims & Ongoing Work

| Area | Current Status |
|---|---|
| GraalVM Native Image | Structurally ready (zero reflection, zero dynamic proxies). Full end-to-end native build verification scheduled for M5 milestone. |
| High-Concurrency Throughput | Microbenchmarks are single-threaded; multi-threaded pool contention and GC pressure under high concurrency are currently being measured. |
| Large Codebase Compile Times | Incremental compilation works as expected in Gradle/Maven; compile-time impact on projects with thousands of mappers is being tracked. |

## The Biggest Practical Benefit

Beyond microsecond savings, the most immediate benefit of LarkBatis is **debuggability**.

Because queries compile directly into Java classes, you can set breakpoints inside generated mapper methods (`UserMapper$$Impl.java`), inspect parameters, and step through execution line by line in your IDE debugger. Stack traces point directly to real Java files rather than nested reflection layers.
