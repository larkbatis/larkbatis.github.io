# Performance

Two kinds of number, kept separate: what can be read off the source and is therefore
certain, and what had to be measured. Plus a third section for what is still
only an argument.

## Read off the source: certain

| Metric | MyBatis | LarkBatis | Basis |
|---|---|---|---|
| Lines on the runtime classpath | 40,017 | ~1,500 | Direct count of `src/main/java/org/apache/ibatis` (393 files). The LarkBatis figure is a design target |
| Runtime dependencies | ognl 3.4.11, javassist 3.32 | none beyond JDBC | Both are `compile` + `optional` in MyBatis's POM: optional, but needed the moment you use dynamic SQL or lazy loading |
| Reflection call sites on the hot query path | 4 groups | 0 | `createCacheKey`, `getBoundSql` (OGNL), `setParameters`, `handleResultSets` |
| Reflective operations per row | 1 × column count | 0 | `applyAutomaticMappings` calls `metaObject.setValue(property, value)` per column, through `BeanWrapper` → `MethodInvoker.invoke` |
| Hand-written `META-INF/native-image` files | several | 0 | mybatis-3 ships no reachability metadata; its GraalVM issue has been open since 2019 |
| Wrong parameter type caught at | runtime | compile time | The mapper is an ordinary interface with a real implementation, so javac checks it |
| Auditing raw SQL insertion | read every mapper | one `grep` | All arbitrary text, `${}` and the escape hatch alike, goes through `SqlFragment.unsafeRawSql`. MyBatis has no equivalent convergence point |

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

The 129 B per row that remains is very nearly all payload: the bean itself plus the
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
about 0.2 µs beside a round trip of roughly 1 ms, which is noise.

!!! quote "The honest sentence"

    **LarkBatis is an investment for report queries, exports, batches and list screens.
    It changes almost nothing for single-record lookups.**

    A migration proposal that omits this loses credibility the first time somebody runs
    their own benchmark.

### What has to be reported alongside any number

Four things, without which a benchmark is not usable as evidence:

- **How many distinct bean types** the run exercised. With one, the call sites are
  monomorphic and the JIT is in its most favourable state *for stock*, meaning the real
  production gap would be larger, not smaller.
- **Columns per row**, because both allocation and latency scale with it.
- **JMH or a hand-rolled loop**, and how allocation was captured (JFR, `ThreadMXBean`,
  `-prof gc`).
- **The JDK version.** Since JDK 18, `Method.invoke` is much faster thanks to JEP 416, so
  the same suite on 17 and on 21 tells two different stories.

## Measured on LarkBatis itself

`larkbatis-benchmarks` re-runs the comparison against the real implementation rather than
the POC. Everything below is JMH 1.37, 2 forks × 5 warmup × 5 measurement iterations of
one second, allocation from `-prof gc` (`gc.alloc.rate.norm`), against MyBatis 3.5.19 and
H2 2.3.232 on an Apple M5 Pro.

!!! info "All figures are Temurin **21**"

    MyBatis's reflective path got measurably faster after JEP 416. Quoting the JDK 17
    numbers without saying so would overstate the case by about a fifth. See
    [JDK version matters](#jdk-version-matters) below.

### Reading rows

`findAll()` over the whole table. `NarrowRow` is 4 columns, `WideRow` is 12.

| Rows | Columns | MyBatis | LarkBatis | Time | Allocation |
|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 1.48 µs | 0.36 µs | **−75%** | 6.6 KB → 1.8 KB (−73%) |
| 1 | 12 | 3.29 µs | 0.43 µs | **−87%** | 10.7 KB → 1.9 KB (−83%) |
| 100 | 4 | 17.1 µs | 3.23 µs | **−81%** | 67.6 KB → 10.2 KB (−85%) |
| 100 | 12 | 39.4 µs | 5.78 µs | **−85%** | 107 KB → 19.1 KB (−82%) |
| 10,000 | 4 | 1.53 ms | 0.29 ms | **−81%** | 6.77 MB → 1.05 MB (−84%) |
| 10,000 | 12 | 3.38 ms | 0.54 ms | **−84%** | 10.2 MB → 1.88 MB (−82%) |

Per row at 10,000 rows and 12 columns: **338 ns → 54 ns**, and **1,018 B → 188 B**.

The POC's numbers hold up. They were, if anything, slightly conservative: −72%/−88% there,
−84%/−82% here with a real JDBC driver in *both* columns and on a JDK that favours MyBatis.

The saving scales with **columns**, not only rows. Going from 4 to 12 columns roughly
doubles MyBatis's per-row cost and barely moves LarkBatis's. MyBatis pays a
`PropertyTokenizer`, an `Object[]`, a map lookup and a reflective call per column, while
the generated reader pays a `getX` and a `putfield`.

### A single-row lookup, with a real round trip

`findById(7)`: one row, four columns.

| Transport | MyBatis | LarkBatis | Time | Allocation |
|---|---:|---:|---:|---:|
| in process | 1.45 µs | 0.36 µs | −75% | 6.6 KB → 1.6 KB (−75%) |
| H2 over loopback TCP | 94.2 µs ± 1.7 | 89.2 µs ± 1.0 | **−5%** | 8.9 KB → 4.0 KB (−55%) |

**The honest sentence above now has evidence.** With a genuine socket and wire protocol in
the way, the mapper-layer difference is five percent. Loopback TCP is the *cheapest*
possible round trip, so a database on another host makes the difference smaller still, not
larger. The allocation saving survives and still matters for GC pressure under load; the
latency saving does not.

### Dynamic SQL

Three `<if>` branches inside a `<where>`. **Every setting returns exactly one row**, because
the statement pins `id = #{pinnedId}` and the optional predicates are all non-restrictive,
so row reading is a constant and the only thing that varies is how much SQL gets assembled.
The benchmark asserts the row count, because the first version of it let the count vary from
100 to 1 and two of its three numbers were really the row-read result under another name.

| Live branches | MyBatis | LarkBatis | Time | Allocation |
|---|---:|---:|---:|---:|
| none | 2.15 µs | 0.41 µs | **−81%** | 10.4 KB → 2.1 KB (−79%) |
| one | 3.60 µs | 1.48 µs | **−59%** | 15.9 KB → 6.9 KB (−56%) |
| all three | 4.86 µs | 2.14 µs | **−56%** | 18.4 KB → 7.8 KB (−57%) |

The shape of that column is the interesting part. With no branch live, LarkBatis has
nothing to assemble, since the statement is a constant `String`, and wins by 81%. As
branches come alive it has to do `StringBuilder` work too, and the gap settles at about 56%:
the honest steady-state cost of dynamic SQL once both sides are really building a string.

The POC's most counter-intuitive finding therefore survives: it measured −45% on the
dynamic path against −73% on the row-read path and called the ordering surprising. Here it
is **−56% against −84%**. Assembling SQL is string work both sides have to do, and the
interpreter's overhead on top of it is smaller than the per-column reflection overhead the
row-read path removes.

### Startup

Cold JVM, one shot per fork, ten forks. Both sides bring up the same application: four
mapper interfaces (one carrying 50 statements), one mapper XML, and a real query at the
end. Quoted on JDK 17, the only run whose error bars are tight enough to mean anything.

| | MyBatis | LarkBatis |
|---|---:|---:|
| Cold start to first row | 61.8 ms ± 3.7 | **6.3 ms ± 0.8** |
| Allocation | 27.0 MB | 15.8 MB |

**−90%, and previously unmeasured.** The 55 ms is XML parsing, `Reflector` construction,
the type-handler registry, OGNL and XPath class loading, and `MappedStatement` construction
for 51 statements. LarkBatis does none of it, because that work happened during `javac`.

The old caveat still stands: in a real Spring Boot application this sits under context
creation and pool warmup. But 55 ms is not noise in a serverless or native-image context,
which is exactly where the claim is made.

### Megamorphic behaviour: the prediction was wrong

50 single-row reads of a 6-column table. `mono` reads one result class 50 times; `mega`
reads 50 different result classes once each.

| | MyBatis | LarkBatis | LarkBatis advantage |
|---|---:|---:|---:|
| monomorphic (1 bean type) | 103.5 µs | 22.8 µs | 4.54× |
| megamorphic (50 bean types) | 123.4 µs | 26.2 µs | 4.71× |
| megamorphic penalty | **+19.3%** | **+15.0%** | |

The mechanism is real and the effect is small. MyBatis does pay 19% more for 50 types than
for one, but LarkBatis pays 15% for the same change, and the advantage widens only from
4.54× to 4.71×.

Allocation gives it away: 394 KB versus 398 KB for MyBatis, 100.4 KB versus 100.8 KB for
LarkBatis. Nothing changes. Whatever megamorphic dispatch costs here, it costs it in
inlining, not in extra work, and MyBatis's per-column allocation, the actual bulk of its
cost, is identical either way.

!!! warning "Do not argue 'it gets worse at scale'"

    The design expected the gap to widen substantially with many mappers. It does not. The
    honest claim is that the advantage is already large with one bean type and stays
    roughly constant, which is the better argument anyway, because it does not depend on
    the reader's codebase being big.

### JDK version matters

The design asked for the suite on two JDKs straddling JEP 416, which put core reflection on
method handles. It named 11 and 21; LarkBatis requires 17, and JEP 416 landed in 18, so
17-versus-21 straddles the same change.

| | JDK 17 | JDK 21 | change |
|---|---:|---:|---:|
| MyBatis, 10,000 × 4 cols | 2.13 ms | 1.53 ms | **−28%** |
| MyBatis, 10,000 × 12 cols | 3.95 ms | 3.38 ms | **−14%** |
| MyBatis, 100 × 4 cols | 22.8 µs | 17.1 µs | **−25%** |
| LarkBatis, 10,000 × 4 cols | 0.302 ms | 0.289 ms | −4% |
| LarkBatis, 10,000 × 12 cols | 0.582 ms | 0.541 ms | −7% |
| LarkBatis, 100 × 4 cols | 3.56 µs | 3.23 µs | −9% |

**MyBatis gets meaningfully faster on a newer JDK; LarkBatis barely moves**, exactly what
the mechanism predicts, since MyBatis's per-column path ends in `Method.invoke` and
generated code has no reflection to accelerate. Allocation moved the same way (MyBatis
9.00 → 6.77 MB per 10,000 narrow rows).

The advantage therefore narrows on newer JDKs: **7.1× on JDK 17, 5.3× on JDK 21** for the
same 10,000 × 4 workload. Always say which JDK a number came from.

### Methodology, and why each choice was forced

- **A pinned session on both sides.** MyBatis's `SqlSession` holds one connection for its
  lifetime; `JdbcLarkBatisSession` acquires and closes one per statement. Comparing them
  directly would measure H2 connect cost on one side only. The startup benchmark is the
  exception, where connection setup is part of what is measured.
- **MyBatis's first-level cache turned down to `STATEMENT` scope.** It defaults to
  `SESSION`, and every benchmark holds one session open, so the second `findById(1)` would
  return a cached object without touching JDBC. That single default is the difference
  between a benchmark and a `HashMap` lookup. The second-level cache is off, because
  LarkBatis dropped it and comparing different feature sets is not a comparison.
- **A real JDBC driver in both columns.** A stubbed `ResultSet` would isolate the mapper
  layer and flatter LarkBatis; H2's cost is inside both numbers, which makes every gap
  above a *lower bound*.
- **H2 over its own TCP server** for the round-trip case: a genuine socket and wire
  protocol on loopback. Not MySQL over a LAN, and used only as a lower bound.
- **The megamorphic experiment generates its 50 result classes and 200 call sites from the
  build script.** Reaching them by reflection would have put the very cost being measured
  back into both sides.
- **Never run another build while JMH runs.** The first full pass of this suite was
  discarded because concurrent builds polluted it.

## Still an argument, not a measurement

| Claim | Why to believe it | Why to doubt it |
|---|---|---|
| Native image works out of the box | No `Proxy`, no `Class.forName`, no `setAccessible` anywhere in the runtime or generated code, so there is no reachability metadata to write | No native-image build has been run. See below |
| It holds up under concurrency | Nothing in the generated code is shared mutable state; the session is the only seam | Every benchmark here is single-threaded. Contention, pool behaviour and GC under parallel load are untested |
| Build time stays acceptable | Generation is per-mapper and incremental | Not measured on a large codebase. This is the cost side of the trade and it is the one still missing |

## Native image

!!! warning "Structurally ready, not yet verified"

    LarkBatis contains no `Proxy.newProxyInstance`, no `Class.forName` and no
    `setAccessible`, in the runtime module or in generated code, so there is no
    reachability metadata to write for the mapper layer. That is a property of the design
    you can check by reading it.

    **An actual native-image build has not been run yet.** The smoke test is open M5 work.
    Until there is a real build, this is the project's strongest *qualitative* promise and
    it is unverified. It should not be presented as a result.

Your JDBC driver may still need metadata of its own. That is a driver concern, not a
mapper-layer one.

## The benefit that gets talked about least

**You can read the SQL that will run, in your IDE.** Open `UserMapper$$Impl.java`, put a
breakpoint inside an `<if>` branch, and watch a stack trace point at a real Java line
instead of `MapperProxy.invoke → MapperMethod.execute → …`.

For a codebase with 300 mapper methods, that is worth more day to day than a few
microseconds per query, and it is the thing users notice first.
