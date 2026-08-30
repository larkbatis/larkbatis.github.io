# Runtime API

Everything in `io.github.lightbatis.runtime`. Zero dependencies beyond JDBC, and nothing
here inspects a type, resolves a name or consults a registry — that all happened at build
time.

## `LightBatisSession`

The whole environment a generated mapper needs.

```java
public interface LightBatisSession {

    Connection conn();                                    // (1)!
    void release(Connection c);                           // (2)!
    RuntimeException translate(SQLException e, String sql);

    // the manual escape hatch
    default <T> List<T>   query(SqlFragment, StatementBinder, RowReader<T>);
    default <T> T         queryOne(SqlFragment, StatementBinder, RowReader<T>);
    default <T> Stream<T> queryStream(SqlFragment, StatementBinder, RowReader<T>);
    default int           update(SqlFragment, StatementBinder);

    // used by generated Stream-returning bodies
    default <T> Stream<T> stream(Connection, PreparedStatement, ResultSet, RowReader<T>, String);
    default RuntimeException streamFailed(Connection, PreparedStatement, ResultSet, String, SQLException);
}
```

1.  Borrow a connection. Inside an active transaction scope this returns the
    transaction's connection; otherwise a fresh auto-commit one.
2.  Return a connection borrowed with `conn()`. A no-op when the connection belongs to an
    active transaction; closes it otherwise.

Two implementations: `JdbcLightBatisSession` (standalone) and `SpringLightBatisSession`
(in `lightbatis-spring`).

Note what the escape-hatch signatures refuse: there is no `String` overload anywhere.
Arbitrary SQL text enters only through `SqlFragment`.

## `JdbcLightBatisSession`

```java
public JdbcLightBatisSession(DataSource dataSource)

public LightBatisTx begin()
public LightBatisTx begin(boolean readOnly)
public boolean hasActiveTransaction()
```

## `LightBatisTx`

One transaction scope, for try-with-resources.

```java
try (LightBatisTx tx = session.begin()) {
    mapper.insert(user);
    tx.commit();
}
```

| Method | |
|---|---|
| `commit()` | **Votes** to commit. The actual commit happens when the outermost scope closes. Throws `LightBatisRollbackOnlyException` if an inner scope already poisoned the transaction |
| `rollbackOnly()` | Marks the transaction rollback-only explicitly |
| `close()` | Leaving without voting marks the whole transaction rollback-only |

Scopes nest: an inner `begin()` joins the outer transaction, and only the outermost close
touches the connection. [Details](../usage/transactions.md)

## `SqlFragment`

The single gate arbitrary SQL text passes through.

```java
public static SqlFragment allowed(String value, String... allowed)   // (1)!
public static SqlFragment identifier(String value)                    // (2)!
public static SqlFragment unsafeRawSql(String value)                  // (3)!
public String text()
```

1.  Closed allow-list. Anything else throws `LightBatisRejectedException`. **Prefer this.**
2.  A plain SQL identifier — letters, digits, underscore, optionally dot-qualified.
3.  Anything. The one audit point: `grep -rn unsafeRawSql src/`.

## `LightBatisSql`

Static helpers referenced by generated code.

| | |
|---|---|
| `trackVariants(String statementId, String sql)` | Counts distinct SQL texts per statement. Emitted for every statement whose text is not fixed at build time |
| `maxSqlVariants(int limit)` | Threshold. Default **64**, or `-Dlightbatis.maxSqlVariants` |
| `failOnUnboundedVariants(boolean)` | Throw instead of warning. Default `false`, or `-Dlightbatis.failOnUnboundedVariants` |
| `padPow2(int n)` | Next power of two, for `@PadPow2` |
| `sum(int[] updateCounts)` | Total of `executeBatch()` counts |

## `JdbcCodec`

Null-aware and converting read/write helpers — the inlined remains of the `TypeHandler`
layer. The *choice* of helper was made at build time; only the value work happens here.

**Reads:** `booleanOrNull` `byteOrNull` `shortOrNull` `intOrNull` `longOrNull`
`floatOrNull` `doubleOrNull` `instant` `localDateTime` `localDate` `localTime` `enumValue`

**Writes:** `setBoolean` `setByte` `setShort` `setInt` `setLong` `setFloat` `setDouble`
`setInstant` `setLocalDateTime` `setLocalDate` `setLocalTime` `setEnum`

```java
public static Long longOrNull(ResultSet rs, int column) throws SQLException {
    long v = rs.getLong(column);
    return rs.wasNull() ? null : v;   // rs.getLong returns 0 for SQL NULL
}
```

Types whose accessor is already correct (`String`, `BigDecimal`, `byte[]`,
`java.sql.Timestamp`) are called directly and do not appear here.

## `RowReader<T>` and `StatementBinder`

```java
@FunctionalInterface public interface RowReader<T> { T read(ResultSet rs) throws SQLException; }
@FunctionalInterface public interface StatementBinder { void bind(PreparedStatement ps) throws SQLException; }
```

Every generated row-reader class exposes `public static final RowReader<T> READER`, so
the escape hatch reuses generated readers rather than reflecting.

## Exceptions

All unchecked, all rooted at `LightBatisException`, which carries the SQL text (or a
pseudo-statement id such as `tx:commit`) via `sql()`.

| | Thrown when |
|---|---|
| `LightBatisException` | Root. Wraps a `SQLException` with its SQL text |
| `LightBatisRejectedException` | A value offered to a `SqlFragment` factory or an `@OrderBy` switch was rejected. The value never reached the SQL |
| `LightBatisEmptyForeachException` | A `<foreach>` collection was empty. Names the statement and the parameter |
| `LightBatisNoKeyException` | A statement expected a generated key and the driver returned none |
| `LightBatisKeyCountMismatchException` | A batch insert got fewer keys back than it had rows |
| `LightBatisUnboundedVariantsException` | A statement exceeded `max-sql-variants` and the deployment asked to fail rather than warn |
| `LightBatisRollbackOnlyException` | `commit()` on a transaction an inner scope already poisoned |

Under Spring, `translate` produces Spring's `DataAccessException` tree instead — so a
unique-constraint violation arrives as `DuplicateKeyException`, exactly as from
`JdbcTemplate`. [Details](errors.md)
