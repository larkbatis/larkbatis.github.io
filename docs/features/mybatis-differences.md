# MyBatis Differences

Every item here has a specific reason behind it, falling into three distinct groups. Looking at them this way makes the design decisions clear.

## Group 1: Dropped by design

These features require something that no longer exists in LarkBatis: a runtime type model, dynamic proxies, or an expression interpreter.

| Feature | Why it cannot return | What to do instead |
|---|---|---|
| **Full OGNL in `test`** | Evaluating arbitrary runtime expressions requires the exact interpreter we removed | Use the [narrow test grammar](../usage/dynamic-sql.md#the-test-grammar) |
| **`<bind>`** | Declares an OGNL variable | Compute the value in Java and pass it as a parameter |
| **`@SelectProvider` family** | SQL assembled by custom Java methods at runtime is invisible to the compiler | Put the SQL in mapper XML / annotations, or use the [escape hatch](../usage/raw-sql.md#the-escape-hatch) |
| **Lazy loading** | Requires a proxy per result object | Fetch eagerly with a SQL join, or run two queries explicitly |
| **Plugins / interceptors** | There is nothing to wrap: the four objects MyBatis intercepts are what generated methods replace | [See recipes below](#what-replaces-a-plugin) |
| **`Object` / `Map` parameters** | There is no concrete type to resolve `#{}` against | Use typed parameter objects or `@Param` annotations |
| **`<discriminator>`** | The result *class* would depend on a runtime column value | Use separate queries with distinct result types |
| **Nested `select=` in `<collection>`/`<association>`** | Causes N+1 queries at runtime | Write a SQL join |
| **Second-level cache** | Cache invalidation is hard without application context | Cache above the mapper layer (e.g. in your service layer or Redis) |
| **Runtime `addMapper()`** | The mapper set is closed at compile time | No action needed; all mappers are discovered at build time |
| **`RowBounds`** | Memory-heavy paging over a full ResultSet | Page in SQL using `LIMIT` and `OFFSET` parameters |
| **`<selectKey>`** | A second statement disguised as an option | Write the second query explicitly. [See example](../usage/generated-keys.md#selectkey-is-not-supported) |
| **`<constructor>` results** | Result classes are built with no-arg constructors and setters | Use standard getters and setters |
| **`<parameterMap>`** | Deprecated in MyBatis itself | Use `#{}` with typed parameters |
| **`objectFactory` / `objectWrapperFactory`** | Hooks into the removed reflection engine | Direct constructor and setter calls in generated readers |
| **Type aliases** | Type aliases are runtime lookup tables | Use fully-qualified class names in XML |
| **First-level cache** | There is no stateful session object | Connections are returned to the pool immediately |
| **`ExecutorType.BATCH` / `REUSE`** | There is no executor object | Batching is a [method signature](../usage/foreach-and-batches.md#jdbc-batches) |

### What replaces a plugin?

This is the most common blocker in real-world migrations. Almost every existing MyBatis codebase uses at least a paging plugin.

MyBatis applies interceptors to four objects (`Executor`, `StatementHandler`, `ParameterHandler`, and `ResultSetHandler`) by wrapping each in `Proxy.newProxyInstance`.

Both parts of that design are gone in LarkBatis:

- **The four objects do not exist.** They are replaced entirely by generated method bodies. A generated method borrows a `Connection`, prepares the SQL, binds parameters with indexed `ps.setXxx` calls, and reads rows with a generated `RowReader`. There is no intermediate executor layer.
- **No dynamic proxies.** Avoiding `Proxy.newProxyInstance` is what keeps the runtime lightweight and GraalVM native-image ready out of the box.

Here is how common plugin use cases map to LarkBatis:

| Plugin | What replaces it |
|---|---|
| Paging (PageHelper, etc.) | Pass `LIMIT` and `OFFSET` as regular `#{}` parameters, and write a separate count query. Page numbers stop being ambient thread-local state |
| Auditing (`created_at`, `updated_by`) | Set auditing fields in the service before calling the mapper, use database defaults, or include a reusable [`<sql>` fragment](../usage/xml-mappers.md) in your inserts |
| Soft delete | Add `AND deleted = false` to your queries or `<sql>` fragments. Explicit, searchable in code, and impossible to bypass accidentally |
| Column encryption / masking | A [`LarkBatisTypeHandler`](../usage/types.md#custom-type-handlers), registered globally with [`-Alarkbatis.typeHandlers`](configuration.md#type-handlers-for-a-whole-build). This maps almost 1:1 with MyBatis |
| SQL logging | Configure logging at the connection pool or driver level (e.g. `datasource-proxy`, p6spy) |
| Multi-tenancy / dynamic tables | Pass a [`SqlFragment`](../usage/raw-sql.md) via `${}`—the single audited path for dynamic SQL |
| Metrics & tracing | Wrap mapper beans with standard decorators or use Spring AOP |

!!! tip "Mapper beans are standard Java objects"

    In MyBatis, mappers are JDK dynamic proxies, which often forced developers to write interceptors for simple cross-cutting concerns. In LarkBatis, mappers are normal classes (`UserMapper$$Impl`) registered as regular Spring beans. You can apply Spring AOP to them or wrap them in plain decorator classes that anyone can read and debug.

## Group 2: Kept, but narrowed

These features work, but with strict compile-time boundaries:

| Feature | How it's narrowed | Why |
|---|---|---|
| **`<where>` / `<set>` / `<trim>`** | Literal attributes only, constant-folded at compile time | Prefix/suffix rules don't need runtime evaluation |
| **`<foreach>`** | Statically-typed collections, arrays, and `Map`. Throws on empty collections unless guarded. Optional `@PadPow2` | Element types determine JDBC setter calls at compile time. [Details](../usage/foreach-and-batches.md) |
| **`<sql>` / `<include>`** | Static `refid` only, inlined at build time | Computed `refid` values require runtime lookups |
| **Nested `<resultMap>`** | One level deep via SQL join; ResultSet must be ordered by parent key | Replaces per-row `CacheKey` allocations with direct primitive comparisons. [Details](../usage/result-maps.md) |
| **Custom TypeHandlers** | Declared with `@Handler` or `typeHandler=` in XML, or configured globally via `-Alarkbatis.typeHandlers` | No runtime classpath scanning. Handlers are wired at compile time |
| **`${}` splices** | Requires `SqlFragment`, closed-value types, or `@OrderBy(allowed = {...})` | Prevents SQL injection at compile time and makes all splices easily searchable. [Details](../usage/raw-sql.md) |
| **Multiple `DataSource`s** | One session per `DataSource`, configured manually | Handled via standard Spring bean configuration |

## Group 3: Moved to build time (zero runtime overhead)

These features work without runtime configuration because they are fully resolved during compilation:

| MyBatis concept | How LarkBatis handles it |
|---|---|
| `TypeHandlerRegistry` lookups per parameter/column | `ps.setXxx` / `rs.getXxx` calls are generated directly |
| `Reflector` / `MetaObject` / `BeanWrapper` | Direct setter calls in generated row readers |
| `<typeHandlers>` package scans | Configured at compile time via `-Alarkbatis.typeHandlers` or per-field annotations |
| `mapUnderscoreToCamelCase` setting | Baked into generated readers at compile time (defaults to `true`) |
| `MapperProxy` + `MapperMethod` dispatch | Concrete classes and direct method calls |
| `ResolverUtil` classpath scanning for mappers | Handled directly by javac during compilation |
| XML parsing and DTD validation at startup | Parsed once during the build |
| `SqlSourceBuilder` runtime parameter mapping | Replaced with static `?` placeholders and generated bindings |
| `@MapperScan` + `MapperFactoryBean` | Generated `@Configuration` with standard `@Bean` methods |

## Behavioral differences when migrating

Here are four cases where LarkBatis compiles fine but behaves slightly differently from MyBatis at runtime:

**1. An empty `<foreach>` throws an exception.** MyBatis outputs nothing at all (not even `(` or `)`), leaving `WHERE id IN` to crash at the database with a syntax error. LarkBatis throws `LarkBatisEmptyForeachException` immediately, naming the mapper and parameter. To omit the clause when a list is empty, wrap it in `<if test="ids != null and !ids.isEmpty()">`.

**2. Null comparisons evaluate to false, not zero.** OGNL coerces `null` to zero, meaning `test="age <= 18"` evaluates to *true* in MyBatis if `age` is null. In LarkBatis, any `null` operand makes the comparison `false`. (`== null` and `!= null` work identically in both).

**3. Calling methods on null receivers returns false.** `user.isActive()` evaluates to `false` if `user` is null. MyBatis throws a runtime exception.

**4. Whitespace formatting in assembled SQL.** LarkBatis joins fragments with a single space and trims the output. MyBatis whitespace handling varies across its own versions in `<trim>` tags. The SQL semantics match, but exact character-for-character whitespace may differ.

## Verification and testing

Our differential test harness executes mappers through both MyBatis's interpreted engine and LarkBatis's generated code against a recording `DataSource`, comparing generated SQL text and parameter bindings. We tested the expression grammar against the entire mapper XML corpus in the MyBatis repository to ensure real-world compatibility. See [Migration](migration.md) for automated migration scanning tools.
