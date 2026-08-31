# MyBatis Differences

Every entry here has a reason, and the reasons fall into three groups. Reading them in
that order makes the list look much less arbitrary than reading it alphabetically.

## Group 1: dropped outright

These need something that no longer exists: a runtime type model, a proxy, or an
interpreter.

| Feature | Why it cannot come back | What to do instead |
|---|---|---|
| **Full OGNL in `test`** | An expression evaluator over a runtime object model is precisely the interpreter being removed | The [narrow grammar](../usage/dynamic-sql.md#the-test-grammar) |
| **`<bind>`** | Introduces an OGNL variable | Compute the value in Java and pass it as a parameter |
| **`@SelectProvider` family** | SQL assembled by a Java method at runtime is invisible to the generator | Put the SQL in the mapper, or use the [escape hatch](../usage/raw-sql.md#the-escape-hatch) |
| **Lazy loading** | Needs a proxy per result object | Fetch eagerly with a join, or split into two statements |
| **Plugins / interceptors** | There is nothing to wrap: the four objects MyBatis intercepts are what a generated method body replaces | [Recipes below](#what-replaces-a-plugin) |
| **`Object` / `Map` parameters** | There is no type to resolve `#{}` against | A parameter object, or `@Param` arguments |
| **`<discriminator>`** | The result *class* would depend on a runtime column value | Separate statements with separate result types |
| **Nested `select=` in `<collection>`/`<association>`** | Issues N+1 queries through a runtime | Express it as a join |
| **Second-level cache** | No equivalent, and invalidation was always the hard part | Cache above the mapper, in the service, where invalidation is visible |
| **Runtime `addMapper()`** | The mapper set is closed at compile time | Nothing to do; it is closed because it can be |
| **`RowBounds`** | In-memory paging over a full ResultSet | Page in SQL with `LIMIT` and `OFFSET` as real parameters |
| **`<selectKey>`** | A second statement wearing the costume of an option | Write the second statement. [Example](../usage/generated-keys.md#selectkey-is-not-supported) |
| **`<constructor>` results** | Result classes are built with a no-arg constructor and setters | Setters |
| **`<parameterMap>`** | Deprecated in MyBatis too | `#{}` with typed parameters |
| **`objectFactory` / `objectWrapperFactory`** | Hooks into the reflection layer that no longer exists | |
| **Type aliases** | An alias is a runtime lookup table; this is a build | Fully-qualified class names |
| **First-level cache** | There is no session to hold one | |
| **`ExecutorType.BATCH` / `REUSE`** | There is no executor | Batch is a [method signature](../usage/foreach-and-batches.md#jdbc-batches) |

### What replaces a plugin

The most common blocker in a real migration, and the one worth spelling out, because
almost every long-lived MyBatis codebase has at least a paging plugin.

MyBatis applies an `Interceptor` to exactly four objects — `Executor`, `StatementHandler`,
`ParameterHandler` and `ResultSetHandler` — each built through a `Configuration` factory
method that ends in `interceptorChain.pluginAll(...)`, and each wrapped by
`Plugin.wrap` with a `Proxy.newProxyInstance`.

Both halves of that are gone here, and not by omission:

- **The four objects do not exist.** They are precisely what a generated method body
  replaces. A generated body borrows a `Connection`, calls `prepareStatement` on a
  constant SQL string, binds with typed `ps.setXxx` calls chosen at build time, and reads
  rows through a generated `RowReader`. There is no executor between the mapper call and
  JDBC to slip anything into.
- **The mechanism is `Proxy.newProxyInstance`**, the one call the runtime and generated
  code do not make. Keeping plugins would mean keeping the proxy, and the native-image
  promise is checkable exactly because there is none.

What each kind of plugin becomes:

| Plugin | What replaces it |
|---|---|
| Paging (PageHelper and friends) | `LIMIT` / `OFFSET` as ordinary `#{}` parameters, and a count statement of its own. The page size stops being ambient thread state, which is also the bug that class of plugin is famous for |
| Auditing — `created_at`, `updated_by` | Set the fields in the service before the call, or give the column a database default, or put the columns in a [`<sql>` fragment](../usage/xml-mappers.md) the inserts include |
| Soft delete | `AND deleted = false` in the statement, or a `<sql>` fragment every select includes. Explicit, greppable, and it cannot be forgotten by a query that bypassed the interceptor |
| Column encryption or masking | A [`LarkBatisTypeHandler`](../usage/types.md#custom-type-handlers), registered once for the type with [`-Alarkbatis.typeHandlers`](configuration.md#type-handlers-for-a-whole-build). This is the case that maps across almost exactly |
| SQL logging | The driver or the pool: `net.ttddyy:datasource-proxy`, p6spy |
| Multi-tenancy, dynamic table or schema names | A [`SqlFragment`](../usage/raw-sql.md) through `${}`, which is the one audited gate for SQL text |
| Timing, metrics, tracing | A decorator around the mapper bean, or Spring AOP on it |

!!! tip "A mapper bean is an ordinary object here"

    In MyBatis the mapper *is* a JDK proxy, which is a large part of why people reach for
    an interceptor to wrap behaviour around it. A LarkBatis mapper is a generated class
    (`UserMapper$$Impl`) registered as a normal bean, so Spring AOP applies to it, and a
    hand-written decorator implementing the same interface is a class anyone can read.

## Group 2: kept, but narrowed

These still work. The narrowing is what makes them compilable.

| Feature | Narrowed to | Why |
|---|---|---|
| **`<where>` / `<set>` / `<trim>`** | Literal attributes, constant-folded at build | The attributes never varied per call anyway |
| **`<foreach>`** | Statically-typed collections, arrays and `Map`. Empty collection throws. Optional `@PadPow2` | The element type is what picks `setLong` over `setString`. [Details](../usage/foreach-and-batches.md) |
| **`<sql>` / `<include>`** | Static `refid`, inlined at build | A computed `refid` is a runtime lookup |
| **Nested `<resultMap>`** | One level, via join, ResultSet ordered by parent key | Replaces a per-row `CacheKey` and a map with a typed comparison. [Details](../usage/result-maps.md) |
| **Custom TypeHandlers** | `@Handler` or `typeHandler=` at the site, or `-Alarkbatis.typeHandlers` per Java type; written out, never discovered | Discovery is a registry scan resolved per column read. Which handler runs is a build-time fact either way |
| **`${}`** | `SqlFragment`, closed-value types, or `@OrderBy(allowed = {...})` | Makes every raw-SQL splice type-checked and greppable. [Details](../usage/raw-sql.md) |
| **Multiple `DataSource`s** | Deferred; one session per `DataSource`, written by hand | No design without a real service that needs it |

## Group 3: moved to build time, losing nothing

You do not configure these any more because there is nothing left to configure.

| MyBatis concept | What replaced it |
|---|---|
| `TypeHandlerRegistry` lookup per parameter and per column | The `ps.setXxx` / `rs.getXxx` call is chosen at build time |
| `Reflector` / `MetaObject` / `BeanWrapper` | Direct setter calls in a generated row reader |
| `<typeHandlers>` registry | Registered per Java type at build time with `-Alarkbatis.typeHandlers`, or named at the site with `@Handler` / `typeHandler`. No package scan, no `@MappedTypes`, no `jdbcType` qualifier, no runtime lookup |
| `mapUnderscoreToCamelCase` setting | Applied at build time, and defaulted to *on* rather than off. `-Alarkbatis.mapUnderscoreToCamelCase=false` carries the MyBatis default across |
| `MapperProxy` + `MapperMethod` dispatch | A real class with a real method |
| `ResolverUtil` classpath scanning for mappers | The compilation already knows every mapper |
| XPath parse + DTD validation of every mapper at startup | Parsed once, at build |
| `SqlSourceBuilder` producing `ParameterMapping`s | `?` placeholders and positional binds, emitted |
| `@MapperScan` + `MapperFactoryBean` | A generated `@Configuration` with plain `@Bean` methods |

## Behavioural divergences to check when migrating

Four places where LarkBatis *runs* but does something different from MyBatis. These are
the ones that will not announce themselves as compile errors.

**1 · An empty `<foreach>` throws.** MyBatis contributes nothing at all, not even `open`
and `close`, which leaves `... WHERE id IN` to fail at the database. LarkBatis throws
`LarkBatisEmptyForeachException` naming the mapper and the parameter. To keep MyBatis's
behaviour, wrap the loop in `<if test="ids != null and !ids.isEmpty()">`.

**2 · Null comparisons are false, not zero.** OGNL coerces null to zero, so
`test="age <= 18"` is *true* in MyBatis when `age` is null. In LarkBatis a null anywhere
along either operand makes the comparison **false**. `== null` / `!= null` behave
identically in both.

**3 · A method call on a null receiver is false, not an exception.** `user.isActive()`
with a null `user` evaluates to `false`. MyBatis throws.

**4 · Whitespace in assembled SQL differs.** Fragments are joined with exactly one space
and trimmed. MyBatis's incidental whitespace differs between its own versions in `<trim>`
handling. Semantics match; character-by-character comparison will not.

## What is checked, and how

The differential test harness runs the same mapper through MyBatis's interpreted path and
through the generated code against a recording `DataSource`, comparing SQL text and
parameter bindings. A sweep over the mapper XML corpus in the MyBatis source tree is how
the expression grammar's real-world coverage was measured, not guessed. The scanner runs
on that same frontend, so a [scan report](migration.md) cannot drift away from what
actually compiles.
