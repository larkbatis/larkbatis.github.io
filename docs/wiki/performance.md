# Performance

Two kinds of number, kept separate on purpose: what can be read off the source and is
therefore certain, and what had to be measured. Plus a third section for what is still
only an argument.

## Read off the source — certain

| Metric | MyBatis | LightBatis | Basis |
|---|---|---|---|
| Lines on the runtime classpath | 40,017 | ~1,500 | Direct count of `src/main/java/org/apache/ibatis` (393 files). The LightBatis figure is a design target |
| Runtime dependencies | ognl 3.4.11, javassist 3.32 | none beyond JDBC | Both are `compile` + `optional` in MyBatis's POM — optional, but needed the moment you use dynamic SQL or lazy loading |
| Reflection call sites on the hot query path | 4 groups | 0 | `createCacheKey`, `getBoundSql` (OGNL), `setParameters`, `handleResultSets` |
| Reflective operations per row | 1 × column count | 0 | `applyAutomaticMappings` calls `metaObject.setValue(property, value)` per column, through `BeanWrapper` → `MethodInvoker.invoke` |
| Hand-written `META-INF/native-image` files | several | 0 | mybatis-3 ships no reachability metadata; its GraalVM issue has been open since 2019 |
| Wrong parameter type caught at | runtime | compile time | The mapper is an ordinary interface with a real implementation, so javac checks it |
| Auditing raw SQL insertion | read every mapper | one `grep` | All arbitrary text — `${}` and the escape hatch alike — goes through `SqlFragment.unsafeRawSql`. MyBatis has no equivalent convergence point |

## Measured on the codegen POC

These come from a build-time codegen proof of concept for MyBatis, not from an estimate.
Best of three, `findAll` over 10,000 rows.

| Metric | Stock MyBatis | Full AOT | Δ |
|---|---|---|---|
| Allocation per row | ≈ 1.0 KB | 129 B | **−87%** |
| Latency per row | 0.30 µs | 0.08 µs | **−73%** |
| 10k-row query · time | ≈ 3.0 ms | 0.8 ms | **−72%** |
| 10k-row query · allocation | ≈ 10 MB | 1.23 MB | **−88%** |
| Dynamic search · time | 15–20 µs | 9.5 µs | **−45%** |
| Dynamic search · allocation | 28 KB | 12 KB | **−57%** |

The 129 B per row that remains is very nearly all payload — the bean itself plus the
`String`s the driver returns. That is a floor, not a first step.

### Three things the measurements contradicted

**1 · The row-read path wins by more than the dynamic-SQL path** (−73%/−87% versus
−45%/−57%). The design's own expectations were *most* cautious about the row-read path,
on the theory that the JIT would inline `MethodInvoker` well. That caution was wrong.

**2 · Escape analysis does not clean up the per-column garbage.** If it did, stock would
not allocate ~1.0 KB per row. The `setValue` → `BeanWrapper` → `Invoker` chain is too deep
for the JIT to scalar-replace the `PropertyTokenizer` and the `Object[]`.

**3 · The benefit is proportional to rows returned, and that has to be said out loud.**
3.0 ms → 0.8 ms over 10,000 rows is real. On a `findById` returning one row, the saving is
about 0.2 µs beside a round trip of roughly 1 ms — noise.

!!! quote "The honest sentence"

    **LightBatis is an investment for report queries, exports, batches and list screens.
    It changes almost nothing for single-record lookups.**

    A migration proposal that omits this loses credibility the first time somebody runs
    their own benchmark.

### What has to be reported alongside any number

Four things, without which a benchmark is not usable as evidence:

- **How many distinct bean types** the run exercised. With one, the call sites are
  monomorphic and the JIT is in its most favourable state *for stock* — meaning the real
  production gap would be larger, not smaller.
- **Columns per row**, because both allocation and latency scale with it.
- **JMH or a hand-rolled loop**, and how allocation was captured (JFR, `ThreadMXBean`,
  `-prof gc`).
- **The JDK version.** Since JDK 18, `Method.invoke` is much faster thanks to JEP 416, so
  the same suite on 17 and on 21 tells two different stories.

## The M5 benchmark suite

`lightbatis-benchmarks` exists and re-measures the above against the real implementation
rather than the POC. Its published results table is not final at the time of writing;
what is already settled is the methodology, and the methodology is most of the value:

- **A pinned session on both sides.** MyBatis's `SqlSession` holds one connection for its
  lifetime; `JdbcLightBatisSession` acquires and closes one per statement. Comparing them
  directly would measure H2 connect cost on one side only.
- **MyBatis's first-level cache turned down to `STATEMENT` scope.** It defaults to
  `SESSION`, and every benchmark holds one session open — so the second `findById(1)` would
  return a cached object without touching JDBC. That single default is the difference
  between a benchmark and a `HashMap` lookup.
- **H2 over its own TCP server** as the "real database at the other end" case: a genuine
  socket and wire protocol on loopback. It is *not* MySQL over a LAN, so it is a lower
  bound on how far a round trip drowns the mapper layer.
- **JDK 17 versus 21**, straddling JEP 416. The design asked for 11 versus 21; LightBatis
  requires 17, and 17-vs-21 straddles the same change since JEP 416 landed in 18.
- **The megamorphic experiment generates its 50 result classes and 200 call sites from the
  build script.** Reaching them by reflection would have put the very cost being measured
  back into both sides.
- **Never run another build while JMH runs.** The first full pass was discarded because
  concurrent builds polluted it.

## Still an argument, not a measurement

| Claim | Why to believe it | Why to doubt it |
|---|---|---|
| Startup time drops | XPath parsing, DTD validation, classpath scanning by `ResolverUtil`, and a `Reflector` per class all disappear | In a real Spring Boot app this is usually buried under context init and connection-pool startup |
| Single-query end-to-end latency is unchanged | Follows from the measured numbers — savings scale with rows | Not yet measured against a real database rather than an in-memory one. This is the most important honest sentence in a migration pitch, so it deserves evidence |
| Megamorphic behaviour is better than measured | With hundreds of mappers, the call sites inside `BeanWrapper`/`MethodInvoker` go megamorphic and stop inlining, while generated code stays an ordinary virtual call | Entirely unmeasured; this is an argument about inlining. The test is the same suite with 50 interleaved bean types |

## Native image

!!! warning "Structurally ready, not yet verified"

    LightBatis contains no `Proxy.newProxyInstance`, no `Class.forName` and no
    `setAccessible`, in the runtime module or in generated code — so there is no
    reachability metadata to write for the mapper layer. That is a property of the design
    you can check by reading it.

    **An actual native-image build has not been run yet.** The smoke test is open M5 work.
    Until there is a real build, this is the project's strongest *qualitative* promise and
    it is unverified — it should not be presented as a result.

Your JDBC driver may still need metadata of its own. That is a driver concern, not a
mapper-layer one.

## The benefit that gets talked about least

**You can read the SQL that will run, in your IDE.** Open `UserMapper$$Impl.java`, put a
breakpoint inside an `<if>` branch, and watch a stack trace point at a real Java line
instead of `MapperProxy.invoke → MapperMethod.execute → …`.

For a codebase with 300 mapper methods, that is worth more day to day than a few
microseconds per query — and it is the thing users notice first.
