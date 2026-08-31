# Migrating from MyBatis

A smooth migration path is the whole point of this project—it's what sets LarkBatis apart from Micronaut Data or jOOQ. That's why we treat migration tooling as a first-class feature.

## Start with a scan

`larkbatis-scan` scans your existing MyBatis codebase and reports what migrating will take, complete with file paths and line numbers. It doesn't compile anything or download dependencies, so you can run it on a freshly cloned repo before even building it.

If your project already uses the LarkBatis Gradle plugin, you can run the task directly:

```console
$ ./gradlew larkbatisScan
$ ./gradlew larkbatisScan --args="--summary --min=BLOCKER src/main"
```

The scanner runs in an isolated process, so it never touches your application classpath. To scan an unmigrated project before configuring any build plugins, build and run the standalone CLI:

```console
$ ./gradlew :larkbatis-scanner:installDist
$ ./build/install/larkbatis-scanner/bin/larkbatis-scan /path/to/legacy-service
```

```text
larkbatis-scan — migration analysis for LarkBatis

usage: larkbatis-scan [options] <path>...

  --summary            counts only, no per-line detail
  --min=LEVEL          detail level: BLOCKER, EDIT, REVIEW, INFO (default REVIEW)
  --limit=N            most findings listed per file (default 40)
  --out=FILE           also write the report to FILE
  --fail-on-blocker    exit 1 when anything is blocked on a dropped feature
```

The scanner only reports findings—it never modifies your files without your input.

### Real compiler frontend

The scanner uses `larkbatis-processor` directly, running **the exact same XML parser and expression grammar checker** used during compilation. The scan results will match what javac actually compiles.

### Four severity levels

Findings are sorted by how much manual decision-making they require. On a 300-mapper project, your first question isn't "how many total findings are there," but "how many architectural decisions do we need to make?"

| Severity | Meaning |
|---|---|
| **BLOCKER** | Feature dropped by design. Requires changing how the mapper or service is structured |
| **EDIT** | Straightforward syntax rewrite with a clear replacement pattern |
| **REVIEW** | Supported feature, but requires verifying intent (e.g. dynamic parameters or missing keys) |
| **INFO** | Compiles as-is; listed for awareness (e.g. dynamic SQL variant tracking) |

### The unit of measure is the statement

We evaluate individual SQL statements, not whole files. One unsupported `<bind>` tag in a 90-statement mapper shouldn't condemn the other 89 statements. Metrics like *"280 of 300 statements compile without changes"* give your team a clear, actionable picture.

The report also highlights **concentration**: which specific files contain the majority of issues. In the MyBatis project's own test suite, over 1,000 grammar rejections are concentrated in just 3 test files (and 1,000 of those in a single synthetic fixture). Seeing concentration prevents a few complex edge cases from looking like a project-wide blocker.

## What the scanner checks

| Finding | Severity | Recommended Fix |
|---|---|---|
| `${}` parameter splice | EDIT | Wrap parameter in `SqlFragment`, use an enum/closed-value type, or add `@OrderBy(allowed={...})` |
| `${}` inside a select column list | REVIEW | Falls back to name-based column reading. Consider making the column list static |
| `test=` expression outside supported grammar | EDIT | Simplify the expression or evaluate in Java before calling mapper |
| OGNL truthiness (`test="count"`) | EDIT | Be explicit: `count != 0`, `user != null`, `!list.isEmpty()` |
| `Map` or untyped `Object` parameter | BLOCKER | Use a typed parameter object or `@Param` annotations |
| `@SelectProvider` annotations | BLOCKER | Put SQL in mapper XML/annotations, or use the escape hatch |
| MyBatis interceptors / plugins | BLOCKER | Replace with explicit SQL, custom `LarkBatisTypeHandler`, or Spring AOP. [See recipes](mybatis-differences.md#what-replaces-a-plugin) |
| Lazy loading | BLOCKER | Fetch eagerly using SQL joins or split into two explicit queries |
| Nested `select=` in result maps | BLOCKER | Rewrite as a single SQL join query |
| Result map nested deeper than 1 level | BLOCKER | Assemble multi-level object graphs in Java from two queries |
| Result map `extends` | BLOCKER | Write mappings explicitly |
| `<discriminator>` tags | BLOCKER | Split into separate queries with distinct return types |
| `<constructor>` mapping | BLOCKER | Add standard no-arg constructor and setters |
| `<bind>` tags | BLOCKER | Compute value in Java and pass as parameter |
| `<parameterMap>` | BLOCKER | Use standard `#{}` with typed parameters |
| Second-level cache | BLOCKER | Cache at the service level (e.g. Spring Cache or Redis) |
| `RowBounds` in-memory paging | BLOCKER | Use database `LIMIT` and `OFFSET` parameters |
| Stored procedures (`statementType != PREPARED`) | BLOCKER | Run stored procedures through the manual escape hatch |
| `<include>` with computed `refid` | BLOCKER | Use static, literal `refid` values |
| `<selectKey>` | REVIEW | Use `@Options(useGeneratedKeys=true)` or run sequence query as separate statement |
| Custom `TypeHandler` | REVIEW | Update class to implement `LarkBatisTypeHandler` |
| Annotation with `<script>` tags | REVIEW | Supported, but verify dynamic tags against LarkBatis grammar rules |
| Direct `SqlSession` usage | REVIEW | Call mapper methods directly or use `session.query(...)` |
| `mapUnderscoreToCamelCase` is off | REVIEW | LarkBatis defaults to `true`. Pass `-Alarkbatis.mapUnderscoreToCamelCase=false` if your database columns already use camelCase |
| `<foreach>` loops | INFO | Supported. Monitored for distinct SQL variant caching |
| Dynamic SQL statements | INFO | Compiled to boolean locals and guarded string builders |

## Recommended Migration Workflow

1. **Scan the codebase and inspect concentration first.** If 90% of blockers are in two legacy mappers, the migration is much simpler than raw counts suggest.
2. **Migrate one mapper at a time.** A mapper interface is the independent unit of compilation.
3. **Check annotation processor ordering first if using Lombok.** Always place `larkbatis-processor` *after* Lombok in your build configuration.
4. **Update `${}` parameter call sites.** These are mechanical edits that provide an immediate security benefit by auditing all raw SQL splices.
5. **Update `test=` expressions.** Mostly converting truthiness expressions (`count` → `count != 0`). Keep in mind that `null <= 18` evaluates to `false` in LarkBatis.
6. **Address blockers.** Decide whether to rewrite dropped features using joins, service-level code, or the escape hatch.
7. **Run your existing unit and integration test suite.** Your tests are the ultimate validation that semantics were preserved.

## Field experience

During a trial migration of an internal production service, the existing test suite passed completely. Two edge cases were uncovered and addressed: Lombok processor ordering and Spring Boot 4 auto-configuration package changes. Both are now covered by automated regression tests in the core repository.

## Workflow changes to expect

1. **Editing SQL requires rebuilding.** Changing XML or annotations requires a recompile so javac can regenerate implementation classes.
2. **Build times increase slightly.** Code generation runs during compilation instead of reflection running on every query in production.
3. **Dynamic `${}` splices require explicit typing.** Every `${}` must be typed as `SqlFragment`, an enum, or allowlisted with `@OrderBy`.

See [Performance](../wiki/performance.md) for detailed benchmarks comparing memory allocation and latency.
