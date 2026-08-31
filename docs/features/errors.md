# Errors and Diagnostics

Because LarkBatis shifts validation from runtime to compile time, most configuration errors surface as build errors before tests or deployment even run.

## Build-Time Errors

Compile-time errors report the exact mapper method, XML line, and recommended fix:

| Compile Error | Resolution |
|---|---|
| `#{}` parameter name cannot be resolved | Check parameter spelling or annotate with `@Param`. If parameters are called `arg0`, see [Troubleshooting](../usage/troubleshooting.md) |
| Plain `String` parameter bound to `${}` | Use `SqlFragment`, closed-value types (enums/integers), or `@OrderBy(allowed = {...})` |
| `test="count"` truthiness | Use explicit comparison (`count != 0`, `user != null`, `!list.isEmpty()`) |
| Unsupported expression in `test=` | Simplify the test condition or compute the boolean in Java |
| Method has both annotation and XML statement, or neither | Define statement in either an annotation or XML, not both |
| Method takes untyped `Map` or `Object` parameter | Use a concrete typed parameter object or `@Param` annotations |
| `useGeneratedKeys = true` missing `keyProperty` | Specify target property name in `keyProperty` |
| Count mismatch between `keyColumn` and `keyProperty` | Ensure both lists have the same number of comma-separated entries |
| `@PadPow2` on non-`IN` `<foreach>` or on `INSERT` | Remove `@PadPow2`. Padding is only valid for simple `IN` clauses |
| Batch method contains dynamic SQL tags | Batch inserts must use an invariant SQL statement string |
| `Stream<T>` return over nested `<resultMap>` | Return `List<T>`, or stream flat rows and group them in memory |
| Result map nested more than one level | Limit join nesting to one level per query |
| `select=` attribute on `<association>` / `<collection>` | Join the tables in SQL instead of using nested queries |
| Missing `<id>` column in nested result map query | Include parent ID column in the `SELECT` list for row grouping |
| Type alias used in `type` / `ofType` / `javaType` | Use fully-qualified class names |
| Computed expression in `<include refid="...">` | Use a literal static fragment `refid` |
| Result class lacks no-arg constructor or setters | Add a public no-arg constructor and setters (or fix Lombok annotation processor ordering) |

## Build-Time Warnings

These warnings highlight potential runtime issues or suboptimal performance:

| Build Warning | Impact |
|---|---|
| `useGeneratedKeys without keyColumn` | Defaults to non-portable `RETURN_GENERATED_KEYS`. (Oracle returns `ROWID`, PostgreSQL returns all columns) |
| Fallback to name-based row reads | `SELECT *` or unaliased expressions prevent indexed reading; falls back to `ResultSetMetaData` lookup |
| Nested result map query missing `ORDER BY` | Result set must be sorted by parent key for single-pass grouping |
| Column in `<result>` not found in `SELECT` list | Property will not be populated from query results |
| Mapper XML `namespace` belongs to another module | XML file will be ignored during current compilation unit |

## Runtime Exceptions

All runtime exceptions extend `LarkBatisException`:

### `LarkBatisRejectedException`

Thrown when dynamic input fails validation against an allowed whitelist in `SqlFragment.allowed(...)` or `@OrderBy`:

```text
Rejected SQL fragment value: "id; DROP TABLE users" (allowed: id, name, created_at)
```

The invalid value is rejected before the SQL query is constructed.

### `LarkBatisEmptyForeachException`

Thrown when an empty collection is passed to an unguarded `<foreach>` loop:

```text
<foreach collection="ids"> is empty in statement com.example.app.UserBatchMapper.findByIds;
wrap the loop in an <if> testing the collection if an empty one should drop the fragment instead
```

### `LarkBatisNoKeyException`

Thrown when `useGeneratedKeys = true` was configured, but the JDBC driver returned an empty generated keys result set.

### `LarkBatisKeyCountMismatchException`

Thrown during batch inserts when the count of returned generated keys doesn't match the number of inserted batch rows.

```text
Statement com.example.app.OrderMapper.insertAll expected 500 generated keys
but the driver returned 1
```

### `LarkBatisUnboundedVariantsException`

Thrown when `fail-on-unbounded-fragment: true` is enabled and a statement exceeds `max-sql-variants`:

```text
LarkBatis statement com.example.app.UserMapper.search has produced more than 64 distinct
SQL texts; statement caches will keep growing. Prefer SqlFragment.allowed(...) or @OrderBy
over unbounded fragments.
```

### `LarkBatisRollbackOnlyException`

Thrown when an application calls `tx.commit()` on a transaction that was marked rollback-only by an inner failure or unvoted scope.

## Spring Exception Translation

When running inside Spring, `SpringLarkBatisSession` routes database errors through Spring's `SQLExceptionTranslator` (`SQLExceptionSubclassTranslator` by default).

JDBC errors are automatically translated into Spring's `DataAccessException` hierarchy (e.g. `DuplicateKeyException`, `CannotAcquireLockException`), maintaining direct compatibility with existing `@ExceptionHandler` and `@Retryable` annotations.

LarkBatis-specific validation exceptions (`LarkBatisRejectedException`, `LarkBatisEmptyForeachException`, etc.) are passed through directly.

## Logging

LarkBatis runtime logs via `java.util.logging`. It avoids injecting runtime logging branches into generated method bytecode. For detailed SQL and parameter logging, configure a logging proxy at the datasource or driver level (`datasource-proxy`, p6spy).

Because SQL statements are generated at compile time, you can also inspect generated SQL directly in the generated `Mapper$$Impl.java` source files in your build directory.
