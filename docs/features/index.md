# Supported Features

The complete matrix. :material-check: means implemented and tested;
:material-alert: means narrowed with a documented rule; :material-close: means dropped by
design, with a compile error naming the replacement.

Version **`0.1.0-SNAPSHOT`** — milestones M1 through M4 are implemented, M5 is in
progress.

## Statements

| | | Notes |
|---|---|---|
| `@Select` `@Insert` `@Update` `@Delete` | :material-check: | `String[]` value, joined with a single space |
| `<select>` `<insert>` `<update>` `<delete>` in mapper XML | :material-check: | Namespace = the interface FQN, `id` = the method name. [Details](../usage/xml-mappers.md) |
| Mixing annotations and XML in one mapper | :material-check: | Resolved per method; having both or neither for a method is a compile error |
| `#{}` bind parameters | :material-check: | Resolved against the method's parameter types at build time |
| `${}` splices | :material-alert: | Only `SqlFragment`, closed-value types, or `@OrderBy`. [Details](../usage/raw-sql.md) |
| `@Param` | :material-check: | |
| `@Options(useGeneratedKeys, keyProperty, keyColumn)` | :material-check: | [Details](../usage/generated-keys.md) |
| `<selectKey>` | :material-close: | Write it as a second statement |
| `@SelectProvider` / `@InsertProvider` family | :material-close: | SQL built by a Java method at runtime is exactly what the generator cannot see |
| `Map` or `Object` parameters | :material-close: | Nothing to resolve `#{}` against. Use a parameter object or `@Param` arguments |
| `RowBounds` | :material-close: | In-memory paging over a full ResultSet. Page in SQL with `LIMIT`/`OFFSET` |

## Dynamic SQL

| | | Notes |
|---|---|---|
| `<if>` | :material-check: | Compiled to a `boolean` local, evaluated once |
| `<choose>` / `<when>` / `<otherwise>` | :material-check: | Mutual exclusion compiled in |
| `<where>` / `<set>` | :material-check: | Constant-folded, not a runtime string scan |
| `<trim>` | :material-alert: | Literal attributes only, folded at build time |
| `<sql>` / `<include>` | :material-alert: | Static `refid`, inlined at build time |
| `<foreach>` | :material-alert: | Statically-typed collections, arrays, maps. Empty collection throws. [Details](../usage/foreach-and-batches.md) |
| `@PadPow2` | :material-check: | Bounds `IN`-list SQL variants. Enforced to `IN`-list shape |
| `<bind>` | :material-close: | Introduces an OGNL variable. Compute it in Java and pass it in |
| OGNL in `test` | :material-close: | Replaced by a [narrow grammar](../usage/dynamic-sql.md#the-test-grammar); truthiness is a compile error |
| `databaseId` | :material-check: | Chosen once at startup |

## Results

| | | Notes |
|---|---|---|
| `resultType` with convention mapping | :material-check: | `snake_case` → `camelCase`, at build time, always |
| Positional row reads | :material-check: | When the select list parses |
| Name-based fallback | :material-check: | `SELECT *` etc. — indexes resolved once from `ResultSetMetaData` |
| Scalar results | :material-check: | `long`, `String`, … read from column 1 |
| `List<T>` returns | :material-check: | |
| `Stream<T>` returns | :material-check: | Caller closes. [Details](../usage/streaming.md) |
| `<resultMap>` | :material-alert: | Explicit mappings only, no auto-mapping |
| `<association>` / `<collection>` | :material-alert: | **One** level, via join, ResultSet ordered by parent key |
| Nested `select=` in a result mapping | :material-close: | That *is* the N+1 it claims to avoid. Write the join |
| `<discriminator>` | :material-close: | The result class would depend on a runtime value |
| `<constructor>` results | :material-close: | Result classes are built with a no-arg constructor and setters |
| `resultMap` `extends`, `columnPrefix`, `autoMapping` | :material-close: | Spell the mappings out |
| Lazy loading | :material-close: | Needs a proxy per result object |
| Type aliases | :material-close: | Use fully-qualified class names |

## Types

| | | Notes |
|---|---|---|
| Primitives and wrappers | :material-check: | Wrappers go through `JdbcCodec` for null handling |
| `String`, `BigDecimal`, `BigInteger`, `byte[]` | :material-check: | |
| `java.sql.Date` / `Time` / `Timestamp` | :material-check: | |
| `Instant`, `LocalDate`, `LocalTime`, `LocalDateTime` | :material-check: | |
| Enums (by `name()`) | :material-check: | Also a closed-value type, so valid for `${}` |
| `@Column` | :material-alert: | **Declared, not yet implemented.** Use a `<resultMap>` or a select-list alias |
| `@Handler` custom handlers | :material-alert: | **Declared, not yet implemented.** [Details](../usage/types.md#custom-type-handlers) |
| TypeHandler discovery / registry | :material-close: | There is no registry to discover into |

## Sessions, transactions, execution

| | | Notes |
|---|---|---|
| `LightBatisTx` scopes, nesting, vote-to-commit | :material-check: | [Details](../usage/transactions.md) |
| Spring `@Transactional` | :material-check: | Via `DataSourceUtils` |
| Spring exception translation | :material-check: | `SQLExceptionSubclassTranslator` by default |
| Spring Boot auto-configuration | :material-check: | Boot 3 and Boot 4 from one jar |
| Generated Spring `@Configuration` | :material-check: | `proxyBeanMethods = false` |
| Batch inserts | :material-check: | A method signature (`List<T>` parameter), not an executor mode |
| Multi-row `VALUES` via `<foreach>` | :material-check: | |
| The escape hatch (`query`, `queryOne`, `queryStream`, `update`) | :material-check: | Takes `SqlFragment`, never `String` |
| `ExecutorType.BATCH` / `REUSE` | :material-close: | There is no executor |
| Plugins / interceptors | :material-close: | Hook a runtime pipeline that does not exist. Spring AOP on a mapper bean still works |
| Second-level cache (`<cache>`, `<cache-ref>`) | :material-close: | Cache above the mapper, where invalidation is visible |
| First-level cache | :material-close: | No session to hold it |
| Runtime `addMapper()` | :material-close: | The mapper set is closed at compile time |
| Multiple `DataSource`s per mapper | :material-alert: | Deferred. Declare one session per `DataSource` and write the `@Bean` methods yourself |
| SQL logging (`log-sql`) | :material-close: | Belongs to the driver or the pool — datasource-proxy, p6spy |

## Build and packaging

| | | Notes |
|---|---|---|
| Annotation processor (javac) | :material-check: | javac only; ECJ is not supported |
| Gradle plugin | :material-check: | [Details](../getting-started/build-plugins.md) |
| Maven plugin | :material-check: | Needs `<extensions>true</extensions>` |
| JPMS named modules | :material-check: | All five published artifacts |
| Lombok interoperability | :material-check: | Declare the LightBatis processor *after* Lombok |
| Incremental builds | :material-alert: | Aggregating processor; compile with `-parameters` under Gradle |
| Test-scoped mappers | :material-close: | Only the `compile` source set is wired |
| GraalVM native image | :material-alert: | Structurally ready — no reflection to declare — but **not yet verified by a real build** |
| Legacy-mapper scanner | :material-check: | `lightbatis-scan`. [Details](migration.md) |

## Read next

- [MyBatis Differences](mybatis-differences.md) — the dropped and narrowed list, with the
  reason for each
- [Annotations](annotations.md) — every annotation and its attributes
- [Runtime API](runtime-api.md) — the public runtime surface
- [Configuration](configuration.md) — processor options, properties, system properties
