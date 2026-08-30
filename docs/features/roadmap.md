# Roadmap

Milestones were ordered by one criterion: **lowest semantic risk first, provable benefit
earliest.**

## Status

| | Scope | |
|---|---|---|
| **M0** | Benchmark groundwork: an `ObjectWrapperFactory` experiment on mybatis-3 itself, to test the central claim before writing any LarkBatis code | :material-check: |
| **M1** | Runtime core; annotation-only processor for static SQL and `#{}`; `$$Impl` + row readers; `useGeneratedKeys`; `SqlFragment` | :material-check: |
| **M2** | Gradle plugin; mapper XML; dynamic tags; the expression grammar. *The highest semantic risk in the project*, hence the differential harness against MyBatis | :material-check: |
| **M3** | `<foreach>`, power-of-two padding, batch insert | :material-check: |
| **M4** | One-level join `<resultMap>`, `Stream` returns, transactions, Spring integration | :material-check: |
| **M5** | Extended benchmarks, legacy-mapper scanner, design revision | :material-check: except the native-image smoke test |

Also landed alongside these: the Maven plugin, JPMS descriptors for all five published
artifacts, and Spring Boot 3 / Boot 4 compatibility from one jar.

## M0: the cheapest possible falsification

Worth describing because of what it says about the project's method. MyBatis already has
an `ObjectWrapperFactory` SPI, so you can generate an `ObjectWrapper` per result class and
plug it into `Configuration` **without patching MyBatis at all**. If removing `Reflector`
and `MetaObject` from the row-read path measurably improved things, LarkBatis's central
claim was proven on a real codebase for a few hundred lines of experiment. If it did not,
several months were saved.

It improved things, by more than the design expected. See
[Performance](../wiki/performance.md).

## M5: what is actually left

| | Status |
|---|---|
| `larkbatis-benchmarks` (JMH; pinned sessions; STATEMENT-scope cache; H2 over TCP; JDK 17 vs 21; 50-bean megamorphic experiment) | Done. [Results](../wiki/performance.md#measured-on-larkbatis-itself), including two findings that contradict the design |
| `larkbatis-scanner` (`larkbatis-scan`) | Implemented. [Details](migration.md) |
| **Native-image smoke test** | **Not run.** The development machine has no GraalVM |
| A migrated service running in a real environment for a week | Not done. The trial migration passed its whole test suite on a copy |
| The design revision, rewritten around what was learned | Done, alongside a workspace-wide removal of section-number references, whose numbering was never a stable thing for code comments and error messages to point at |

!!! warning "The native-image promise is unverified"

    Zero reflection is the project's strongest qualitative claim, and it is structural:
    no `Proxy`, no `Class.forName`, no `setAccessible` to declare, and you can check that
    by reading the code. But **no real native-image build has been done**. It should not be
    presented as a result until there is one.

## Deliberately deferred

| | Why |
|---|---|
| **Multiple `DataSource`s** (`@LarkBatisDataSource`) | No design without a real service that needs it. Today: one `SpringLarkBatisSession` per `DataSource`, mapper `@Bean` methods written by hand |
| **Test-scoped mappers** | Only the `compile` source set is wired, in both build plugins |
| **`log-sql`** | Every generated body would need a logging branch. Driver- or pool-level logging instead |
| **Maven plugin functional tests** | Blocked on the artifacts being publishable to a local repository, the same status as the Gradle plugin's TestKit tests |

## What will not be added

None of those are backlog items. Each sits on the wrong side of the
[shape/value cut](../wiki/shape-vs-value.md), and adding one would mean adding back a
runtime that can inspect types.

Full OGNL · `<bind>` · the `@SelectProvider` family · lazy loading · plugins and
interceptors · `Object`/`Map` parameters · `<discriminator>` · nested selects in
`<collection>` · second-level cache · runtime `addMapper()` · `RowBounds` · TypeHandler
discovery · `ExecutorType`.

Each already has a compile error naming its replacement. See
[MyBatis Differences](mybatis-differences.md).

## Versioning

`0.1.0-SNAPSHOT`, not yet published to Maven Central. Until then, build the repositories
locally and publish to your Maven local repository. Documentation is versioned alongside
releases. The version selector in the header switches between them, and `latest` always
points at the most recent release.
