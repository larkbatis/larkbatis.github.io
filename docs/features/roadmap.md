# Roadmap

We ordered our milestones around one rule: **tackle the biggest semantic risks first and prove real performance gains as early as possible.**

## Milestone Status

| Milestone | Scope | Status |
|---|---|---|
| **M0** | Proof of concept: an `ObjectWrapperFactory` experiment on stock MyBatis to test the core thesis before writing any LarkBatis code | :material-check: |
| **M1** | Runtime core: annotation-based processor for static SQL and `#{}`; `$$Impl` + row readers; `useGeneratedKeys`; `SqlFragment` | :material-check: |
| **M2** | Gradle plugin: mapper XML; dynamic tags; expression grammar parser; differential test harness against MyBatis | :material-check: |
| **M3** | `<foreach>`, power-of-two padding (`@PadPow2`), batch inserts | :material-check: |
| **M4** | 1-level join `<resultMap>`, `Stream` returns, transaction scopes, Spring Boot integration | :material-check: |
| **M5** | Extended JMH benchmarks, legacy-mapper scanner CLI, design documentation | :material-check: (except native-image smoke test) |

Completed alongside these: Maven build plugin, JPMS named module descriptors for all published artifacts, and unified Spring Boot 3 / Boot 4 compatibility.

## M0: Proving the thesis cheaply

This milestone was about validating our core assumption with minimal effort. MyBatis has an `ObjectWrapperFactory` SPI, which lets you plug in a generated `ObjectWrapper` per result class without modifying MyBatis itself. If eliminating `Reflector` and `MetaObject` on the row-reading path made a measurable difference, our thesis was validated with just a few hundred lines of test code. If not, we could walk away before investing months of effort.

It proved the thesis decisively. See [Performance](../wiki/performance.md).

## M5: Remaining items

| Task | Status |
|---|---|
| `larkbatis-benchmarks` (JMH; pinned sessions; STATEMENT-scope cache; H2 over TCP; JDK 17 vs 21; 50-bean megamorphic benchmark) | Done. [Results](../wiki/performance.md#measured-on-larkbatis-itself) |
| `larkbatis-scanner` (`larkbatis-scan` CLI) | Done. [Details](migration.md) |
| **Native-image smoke test** | **Not yet run.** Development environment lacks GraalVM setup |
| Extended 1-week production soak test of migrated service | Pending. (The initial trial migration passed 100% of its test suite) |
| Architecture documentation revision | Done |

!!! warning "Native image verification status"

    Zero runtime reflection is a structural guarantee: there are no dynamic proxies, no `Class.forName`, and no `setAccessible` calls in runtime or generated code. However, **an end-to-end native-image build has not been executed yet**. We treat this as an architectural design property rather than a benchmarked claim until that smoke test runs.

## Deliberately deferred

| Feature | Reason |
|---|---|
| **Multiple `DataSource`s** (`@LarkBatisDataSource`) | We want real production usage before locking in an API. Today: define one `SpringLarkBatisSession` per `DataSource` and wire mapper `@Bean` methods manually |
| **Test-scoped mappers** | Build plugins only configure main source sets |
| **`log-sql`** | Handled more cleanly at the JDBC pool or driver level (`datasource-proxy`, p6spy) |

## Features that will not be added

These are not backlog items. Each sits on the wrong side of our [shape vs value boundary](../wiki/shape-vs-value.md), and adding them would re-introduce runtime reflection and interpretation:

Full OGNL expressions · `<bind>` · `@SelectProvider` annotations · Lazy loading · Interceptor plugins · Untyped `Object`/`Map` parameters · `<discriminator>` · Nested `select=` queries in `<collection>` · Second-level caches · Dynamic runtime `addMapper()` · `RowBounds` · Runtime classpath scanning · `ExecutorType`.

Each unsupported feature produces a clear compile-time error with its recommended alternative. See [MyBatis Differences](mybatis-differences.md).

## Versioning

Documentation is versioned alongside releases. Use the version selector in the header to view documentation for specific releases.
