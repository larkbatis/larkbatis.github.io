# Raw SQL and SqlFragment

`#{}` creates a JDBC bind parameter (`?`). `${}` splices text directly into raw SQL—which is where SQL injection risks come from. LarkBatis does not ban `${}` outright because dynamic sorting or schema targeting are legitimate requirements. Instead, it forces every splice through types the compiler can verify and you can easily `grep` for.

## The Rule

!!! failure "Binding a plain `String` to `${}` is a compile error"

    ```java
    @Select("SELECT id, name FROM users ORDER BY ${sort}")
    List<User> all(String sort);        // compile error
    ```

    The compiler rejects this and lists the supported types.

| Type for `${}` | Why it is safe |
|---|---|
| `SqlFragment` | Created via audited factory methods (`allowed`, `identifier`, `unsafeRawSql`) |
| Closed-value types (`int`, `long`, `boolean`, `enum`) | Finite value ranges that cannot introduce SQL injection |
| `String` with `@OrderBy(allowed = {...})` | Compiled to a strict Java `switch` statement over string literals |

## `@OrderBy`

The most common use case for dynamic SQL text is column sorting. You can declare allowed column names directly:

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY ${sort}")
List<User> all(@OrderBy(allowed = {"id", "name", "created_at"}) String sort);
```

The generator emits a `switch` statement validating the input against this list. Any unrecognized string throws a `LarkBatisRejectedException` immediately, preventing invalid input from ever touching the database.

## `SqlFragment`

When building dynamic SQL fragments in Java, use `SqlFragment` factories:

```java
SqlFragment.allowed(value, "created_at", "name")   // (1)!
SqlFragment.identifier(value)                      // (2)!
SqlFragment.unsafeRawSql(value)                    // (3)!
```

1.  **`SqlFragment.allowed(...)`**: Validates against a static whitelist. (Recommended).
2.  **`SqlFragment.identifier(...)`**: Validates that the input is a valid SQL identifier (alphanumeric and underscores only). Ideal for dynamic table or schema names.
3.  **`SqlFragment.unsafeRawSql(...)`**: Slices arbitrary text into SQL without checks. This serves as the single searchable audit point for unescaped SQL across your entire codebase.

```java
@Select("SELECT id, name FROM users WHERE ${predicate} ORDER BY id")
List<User> where(SqlFragment predicate);
```

### Auditing raw SQL with `grep`

Because raw SQL creation is channeled through `unsafeRawSql`, security audits are straightforward:

```console
$ grep -rn 'unsafeRawSql' src/
```

In standard MyBatis, `${}` expressions and `@SelectProvider` methods are scattered across XML files and Java classes, requiring full codebase reviews to detect vulnerabilities.

## Tracking SQL variants

Both database engines and JDBC drivers cache execution plans by query text. Unbounded `${}` splices or fluctuating `<foreach>` sizes can flood statement caches with thousands of distinct query strings.

LarkBatis automatically monitors statements with dynamic SQL:

```java
LarkBatisSql.trackVariants(STMT_findByIds, sql);
```

If a statement exceeds the configured variant threshold, LarkBatis logs a warning:

```yaml title="application.yml"
larkbatis:
  max-sql-variants: 64                # default threshold
  fail-on-unbounded-fragment: false   # default
```

!!! tip "Enable `fail-on-unbounded-fragment` in CI/testing"

    Set `larkbatis.fail-on-unbounded-fragment: true` in your test environment to catch unbounded query generation before deploying to production.

To structurally bound `<foreach>` variants, use `@PadPow2`. See [foreach and Batches](foreach-and-batches.md#padpow2-bounding-the-sql-variants).

## Dynamic columns in select lists

Using `${}` inside a `SELECT` column list prevents the compiler from predicting column positions. The statement automatically falls back to reading columns by name from `ResultSetMetaData` on the first row. The build outputs a note whenever this fallback occurs.

## The manual escape hatch { #the-escape-hatch }

When you need to construct complex queries dynamically in Java, write a `default` method on your mapper interface:

```java
default List<User> recent(LarkBatisSession s, int limit) {
    return s.query(
            SqlFragment.unsafeRawSql(
                    "SELECT id, name, email, created_at FROM users"
                            + " ORDER BY created_at DESC LIMIT " + limit),
            ps -> { },                 // (1)!
            UserRow.READER);           // (2)!
}
```

1.  **`StatementBinder` lambda**: Bind JDBC parameters safely using `ps.setXxx` rather than string concatenation.
2.  **Generated `UserRow.READER`**: Reads rows positionally with zero reflection.

Core execution methods:

| Method | Return Type |
|---|---|
| `s.query(SqlFragment, StatementBinder, RowReader<T>)` | `List<T>` |
| `s.queryOne(SqlFragment, StatementBinder, RowReader<T>)` | `T` (or `null`) |
| `s.queryStream(SqlFragment, StatementBinder, RowReader<T>)` | `Stream<T>` (caller closes) |
| `s.update(SqlFragment, StatementBinder)` | `int` (affected rows) |

If you need a row reader for a class that isn't referenced in any mapper statement, annotate it with [`@LarkBatisRow`](../features/annotations.md#larkbatisrow):

```java
@LarkBatisRow
public class DomainCount {
    private String domain;
    private long total;
    // standard getters and setters
}
```

```java
default List<DomainCount> countByDomain(LarkBatisSession s, int minimum) {
    return s.query(
            SqlFragment.unsafeRawSql("SELECT domain, COUNT(*) AS total FROM contacts"
                    + " GROUP BY domain HAVING COUNT(*) >= ?"),
            ps -> ps.setInt(1, minimum),
            DomainCountRow.READER);
}
```

`DomainCountRow.READER` reads columns positionally based on property declaration order. If your custom SQL returns columns in a different order, use name-based reading:

```java
int[] columns = DomainCountRow.columns(rs);   // resolved once from metadata
DomainCount row = DomainCountRow.read(rs, columns);
```
