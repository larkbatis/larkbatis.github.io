# Errors and Diagnostics

Most things that go wrong in a MyBatis application at runtime go wrong in a LightBatis
application at build time. This page is split accordingly.

## Build-time errors

Every one of these names the mapper method and, where there is one, the replacement. Each
also has a test in the processor's `CompileFailTest`, so the promises on this site are
enforced rather than aspirational.

| Error | Fix |
|---|---|
| `#{}` name does not resolve against the parameter types | Check the name, or add `@Param`. If parameters are called `arg0`, see [Troubleshooting](../usage/troubleshooting.md) |
| A `String` parameter bound to `${}` | `SqlFragment`, a closed-value type, or `@OrderBy(allowed = {...})` |
| `test="count"` — OGNL truthiness | `count != 0`. Likewise `user != null`, `!list.isEmpty()` |
| `test=` outside the expression grammar | Rewrite it, or move the decision into Java and pass the result in |
| A method has both an annotation and an XML statement, or neither | Pick one |
| `Map` or `Object` parameter | A parameter object, or `@Param` arguments |
| `useGeneratedKeys` without `keyProperty` | Say where the key should go |
| `keyColumn` and `keyProperty` list different counts | Make the lists the same length |
| `@PadPow2` on a `<foreach>` that is not a single-bind `IN` list, or on an `INSERT` | Remove it — padding would duplicate rows |
| Batch method with dynamic SQL | A batch statement's text must be identical for every row |
| `Stream` return over a nested `<resultMap>` | Use `List`, or stream flat rows and group them yourself |
| Result map nested more than one level, or two nested mappings in one map | One join, one grouping key |
| `select=` on `<association>`/`<collection>` | Write the join |
| `resultMap=`, `columnPrefix`, `extends`, `<constructor>`, `<discriminator>`, `autoMapping` in a result map | See [Result Maps](../usage/result-maps.md#narrowed-on-purpose) |
| `<id>` column missing from the select list | That column is what the grouping loop reads |
| Type alias in `type` / `ofType` / `javaType` | Fully-qualified class name |
| Computed `refid` on `<include>` | `refid` is inlined at build time, so it must be literal |
| Result class with no no-arg constructor or no setters | Add them. If the class uses Lombok, the message says so — it is a [processor ordering problem](../usage/troubleshooting.md) |

## Build-time warnings

Worth treating as errors in review.

| Warning | Why it matters |
|---|---|
| `useGeneratedKeys without keyColumn falls back to RETURN_GENERATED_KEYS` | Oracle returns `ROWID`, PostgreSQL returns every column. Works on H2, wrong in production |
| A statement fell back to name-based row reads | The select list could not be parsed — `SELECT *`, a `${}` splice, an unaliased expression. Correct but measurably slower |
| A nested result map statement has no `ORDER BY` | The grouping loop requires the ResultSet ordered by the parent key |
| A `<result>` column is missing from the select list | That property stays unset |
| A mapper XML `namespace` names an interface in another module | The file is ignored |

## Runtime exceptions

All unchecked, all rooted at `LightBatisException`, which carries the SQL text via
`sql()`.

### `LightBatisRejectedException`

A value offered to a `SqlFragment` factory or an `@OrderBy` switch was rejected. **The
value never reached the SQL text** — this is the runtime edge of the `${}` discipline
working as intended, not a failure of it.

```text
Rejected SQL fragment value: "id; DROP TABLE users" (allowed: id, name, created_at)
```

### `LightBatisEmptyForeachException`

```text
<foreach collection="ids"> is empty in statement com.example.app.UserBatchMapper.findByIds;
wrap the loop in an <if> testing the collection if an empty one should drop the fragment instead
```

MyBatis would have let `... WHERE id IN` reach the database and fail there, with a syntax
error naming neither the mapper nor the parameter.

### `LightBatisNoKeyException`

A statement declared `useGeneratedKeys` and the driver returned none. Better than a `0`
id travelling through your code and failing somewhere unrelated.

### `LightBatisKeyCountMismatchException`

```text
Statement com.example.app.OrderMapper.insertAll expected 500 generated keys
but the driver returned 1
```

Drivers do this. Ignoring it would leave part of the batch with unset ids and nobody the
wiser — MyBatis documents the same failure mode.

### `LightBatisUnboundedVariantsException`

```text
LightBatis statement com.example.app.UserMapper.search has produced more than 64 distinct
SQL texts; statement caches will keep growing. Prefer SqlFragment.allowed(...) or @OrderBy
over unbounded fragments.
```

Only thrown when `fail-on-unbounded-fragment` is on. Otherwise the same condition produces
one log line. `statementId()` and `limit()` are on the exception.

### `LightBatisRollbackOnlyException`

`commit()` was called on a transaction an inner scope had already poisoned by leaving
without voting. Throwing beats a silent rollback that looks like success to the caller.

## Under Spring

`SpringLightBatisSession.translate` routes through Spring's `SQLExceptionTranslator`
instead — by default `SQLExceptionSubclassTranslator`, which reads the standard
`SQLException` subclass tree rather than a per-vendor error-code table.

So a unique-constraint violation arrives as `DuplicateKeyException`, a deadlock as
`CannotAcquireLockException`, exactly as they would from `JdbcTemplate`. Existing
`@ExceptionHandler`s and `@Retryable` rules keep working unchanged.

The LightBatis-specific exceptions above (`LightBatisRejectedException`,
`LightBatisEmptyForeachException`, …) are not `SQLException`s and pass through untouched.

## Logging

LightBatis logs through `java.util.logging` and says very little — the variant-tracking
warning is essentially all of it. There is deliberately no SQL logging: every generated
body would have to carry a logging branch. Use the driver or the pool
(`net.ttddyy:datasource-proxy`, p6spy) for that.

What replaces SQL logging in practice is that the SQL is *in your source tree*. Open
`UserMapper$$Impl.java` and read the `static final String`.
