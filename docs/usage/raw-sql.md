# Raw SQL and SqlFragment

`#{}` is a bind parameter. `${}` splices text straight into the SQL, and that is where
SQL injection lives. LarkBatis does not ban `${}`, because sorting by a user-chosen
column is a real requirement. It makes every splice go through a type the compiler can
check and a name you can `grep` for.

## The rule

!!! failure "A `String` parameter bound to `${}` is a compile error"

    ```java
    @Select("SELECT id, name FROM users ORDER BY ${sort}")
    List<User> all(String sort);        // compile error
    ```

    The error names the parameter and lists the three accepted forms.

| Accepted for `${}` | Why it is safe |
|---|---|
| `SqlFragment` | Constructed through a factory that validated the value, or through `unsafeRawSql`, the one audit point |
| Closed-value types: `int`, `long`, `short`, `byte`, `boolean`, enums | Their entire value space is already SQL-safe |
| `String` annotated `@OrderBy(allowed = {...})` | Compiled to a `switch` over the literal list |

## `@OrderBy`

The common case, and the one that needs no ceremony at the call site:

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY ${sort}")
List<User> all(@OrderBy(allowed = {"id", "name", "created_at"}) String sort);
```

The generator emits a `switch` over the three literals. A value outside the list is
rejected with `LarkBatisRejectedException` naming the value and the allowed set. The
value never reaches the SQL text.

## `SqlFragment`

Three factories, and the difference between them is the whole point:

```java
SqlFragment.allowed(value, "created_at", "name")   // (1)!
SqlFragment.identifier(value)                      // (2)!
SqlFragment.unsafeRawSql(value)                    // (3)!
```

1.  A closed allow-list. Anything else throws `LarkBatisRejectedException`. **Prefer
    this.**
2.  Accepts a plain SQL identifier (letters, digits, underscore, optionally
    dot-qualified) and rejects everything else. For column and table names that genuinely
    come from configuration.
3.  Accepts anything. The single audit point for arbitrary SQL text in the entire
    codebase.

```java
@Select("SELECT id, name FROM users WHERE ${predicate} ORDER BY id")
List<User> where(SqlFragment predicate);
```

### Why `unsafeRawSql` has that name

The name carries the warning because the method is the one place arbitrary text becomes
SQL. Auditing raw-SQL insertion in a LarkBatis codebase is:

```console
$ grep -rn 'unsafeRawSql' src/
```

MyBatis has no equivalent convergence point. `${}` is scattered through XML,
`@SelectProvider` bodies are scattered through Java, and finding all of them means reading
every mapper.

## Tracking SQL variants

Statement caches, both the driver's and the database's, are keyed by the **SQL text**. A
fragment whose value set is not bounded grows them without limit, and you find out about
it as a memory or a latency incident rather than as a bug.

Two kinds of statement have text that is not fixed at build time: a `${}` splice, and a
`<foreach>`, whose element count changes the text just as much. Both get a generated call:

```java
LarkBatisSql.trackVariants(STMT_findByIds, sql);
```

It counts distinct SQL texts per statement. Past the threshold you get **one** log line
naming the statement, and the counter stops retaining texts.

```yaml title="application.yml"
larkbatis:
  max-sql-variants: 64                # default
  fail-on-unbounded-fragment: false   # default
```

Outside Spring the same settings are system properties
(`-Dlarkbatis.maxSqlVariants=64`, `-Dlarkbatis.failOnUnboundedVariants=true`) or the
static methods `LarkBatisSql.maxSqlVariants(int)` and
`LarkBatisSql.failOnUnboundedVariants(boolean)`.

!!! tip "Turn `fail-on-unbounded-fragment` on in staging"

    A production system should not start throwing because of a log-worthy trend, which is
    why the default is a warning. A test or staging profile that throws
    `LarkBatisUnboundedVariantsException` finds the unbounded fragment before it ships.

`@PadPow2` is the other half of this story for `<foreach>`: it bounds the variants
structurally instead of reporting on them. See
[foreach and Batches](foreach-and-batches.md#padpow2-bounding-the-sql-variants).

## `${}` in a select list

A `${}` inside the select list means the generator cannot parse the columns, so that one
statement falls back to a name-based row reader resolved from `ResultSetMetaData` on the
first row. Correct, measurably slower, and **reported at build time**, so the trade-off is
visible when you make it.

## The escape hatch

Sometimes the SQL genuinely has to be assembled in Java. A `default` method on the mapper
interface is where that goes, and it keeps two properties that matter:

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

1.  A `StatementBinder`, a lambda over the `PreparedStatement`. Bind your `?` here;
    prefer this over splicing values into the text.
2.  The **generated** row reader. No reflection, and the result type is checked by javac.

The entry points:

| Method | Returns |
|---|---|
| `s.query(SqlFragment, StatementBinder, RowReader<T>)` | `List<T>` |
| `s.queryOne(SqlFragment, StatementBinder, RowReader<T>)` | `T` or `null` |
| `s.queryStream(SqlFragment, StatementBinder, RowReader<T>)` | `Stream<T>`, caller closes |
| `s.update(SqlFragment, StatementBinder)` | `int` |

Note what the signature refuses: there is no `String` overload. Even here, arbitrary SQL
text enters through the same audited gate.

A reader exists for every class used as a statement's `resultType`. A class used *only*
here has no statement to trigger one, so mark it
[`@LarkBatisRow`](../features/annotations.md#larkbatisrow):

```java
@LarkBatisRow
public class DomainCount {
    private String domain;
    private long total;
    // no-arg constructor + setters
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

`READER` reads **positionally, in the class's declaration order**, because there was no
select list at build time to check the order against. Where hand-assembled SQL cannot
promise that order, resolve by name instead:

```java
int[] c = DomainCountRow.columns(rs);   // once, from ResultSetMetaData
DomainCount row = DomainCountRow.read(rs, c);
```
