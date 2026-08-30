# Streaming Results

A mapper method may return `Stream<T>` instead of `List<T>`. The rows then arrive one at
a time off an open cursor, which is the point: a result set too big to hold in memory
never becomes a list.

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY id")
Stream<User> streamAll();
```

```java
try (Stream<User> rows = mapper.streamAll()) {
    rows.filter(User::isActive).forEach(exporter::write);
}
```

## The caller owns the resources

!!! danger "`try`-with-resources is not optional here"

    This is the one generated shape whose JDBC resources outlive the method that opened
    them, so the generated body has **no `finally`**. Closing the stream is what closes
    the `ResultSet` and the `PreparedStatement` and releases the `Connection`.

    - **Outside a transaction**, a stream that is never closed holds a pooled
      `Connection` for as long as it is reachable. That is a pool leak.
    - **Inside a transaction**, the transaction still owns the connection, and the stream
      holds the statement and cursor until it ends.

The generated body makes the ownership visible:

```java
@Override
public Stream<Order> streamByStatus(Status status) {
    Connection c = s.conn();
    PreparedStatement ps = null;
    ResultSet rs = null;
    try {
        ps = c.prepareStatement(SQL_streamByStatus);
        JdbcCodec.setEnum(ps, 1, status);
        rs = ps.executeQuery();
        return s.stream(c, ps, rs, OrderRow::read, SQL_streamByStatus);  // (1)!
    } catch (SQLException e) {
        throw s.streamFailed(c, ps, rs, SQL_streamByStatus, e);          // (2)!
    }
}
```

1.  Hands the three resources to the stream, which releases them on `close()`.
2.  The failure path — anything that throws *before* the stream exists — undoes all of it
    by hand, with a cleanup failure suppressed into the real one rather than replacing it.

## Sequential on purpose

The returned stream is sequential and does not split. Parallelising a cursor means
reading ahead into memory, which is exactly what a `Stream` return was chosen to avoid.
If you want parallelism, collect a bounded chunk and parallelise that.

## What can be streamed

| | |
|---|---|
| `Stream<User>` over a bean | Yes — uses the generated row reader |
| `Stream<String>`, `Stream<Long>` — scalars | Yes — reads column 1, no bean, no reader |
| `SELECT *` | Yes — indexes resolve from `ResultSetMetaData` before the first row |
| A nested `<resultMap>` | **Compile error** |

The last one is worth understanding rather than working around. A parent spans several
rows, so it is only complete once the *next* parent starts. Answering that from a
one-row-at-a-time cursor means buffering, which defeats the purpose. Stream the flat
rows and group them yourself, or use `List` and accept the memory.

## The escape hatch also streams

`LightBatisSession.queryStream` is the streaming counterpart of `query`:

```java
default Stream<User> streamRecent(LightBatisSession s, int limit) {
    return s.queryStream(
            SqlFragment.unsafeRawSql(
                    "SELECT id, name, email, created_at FROM users"
                            + " ORDER BY created_at DESC LIMIT " + limit),
            ps -> { },
            UserRow.READER);
}
```

Same ownership rule: the caller closes it. See [Raw SQL](raw-sql.md#the-escape-hatch).

## Under Spring

`@Transactional` and streams compose, with the ownership rule unchanged:

```java
@Transactional(readOnly = true)
public void export(Writer out) {
    try (Stream<User> rows = users.streamAll()) {
        rows.forEach(u -> write(out, u));
    }
}
```

Inside a transaction, `release` is a no-op and the transaction keeps the connection;
outside one, closing the stream returns it to the pool. `try`-with-resources is right
either way — which is why the rule is stated as "always", not "sometimes".

## Fetch size

LightBatis does not set `setFetchSize` for you: the right value is driver- and
query-specific, and some drivers (PostgreSQL in particular) additionally require
auto-commit to be off before a cursor streams at all rather than materialising. If you
are streaming a large result, set it on the connection or the pool, or read inside a
transaction.
