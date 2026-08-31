# Streaming Results

A mapper method can return `Stream<T>` instead of `List<T>`. Rows are read one by one from an open database cursor, allowing you to process massive result sets without blowing up the heap.

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY id")
Stream<User> streamAll();
```

```java
try (Stream<User> rows = mapper.streamAll()) {
    rows.filter(User::isActive).forEach(exporter::write);
}
```

## The caller owns resource cleanup

!!! danger "Always use `try`-with-resources with `Stream<T>`"

    Streaming queries are the only methods where underlying JDBC resources outlive the mapper method call. Closing the `Stream` closes the `ResultSet` and `PreparedStatement`, and releases the `Connection`.

    - **Outside transactions**: Leaving a stream unclosed leaks a connection from your connection pool.
    - **Inside transactions**: The connection is managed by the transaction, but leaving the stream open leaves the cursor and statement active until the transaction completes.

Generated streaming methods make resource ownership clear:

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

1.  Passes the three JDBC resources to the stream wrapper, which closes them when `stream.close()` is called.
2.  If an exception occurs *before* the stream is created, cleanup runs immediately and any secondary cleanup errors are suppressed into the root exception.

## Why streams are sequential

The returned stream is strictly sequential and does not support parallel splitting. Splitting database cursors in parallel would require buffering rows into memory, defeating the whole purpose of streaming. If you need parallel processing, read bounded batches and parallelize the batch processing.

## Supported stream types

| Return Type | Support | Notes |
|---|---|---|
| `Stream<User>` | Supported | Uses generated `RowReader` |
| `Stream<String>`, `Stream<Long>` | Supported | Reads column 1 directly |
| `SELECT *` queries | Supported | Column indexes resolved once from metadata |
| Nested `<resultMap>` | **Compile error** | Requires buffering multi-row parents |

Why nested `<resultMap>` is rejected: parent objects in a join span multiple rows, so a parent object is only complete when the *next* parent ID is encountered. Streaming one row at a time would require buffering the parent graph in memory. To stream relationships, stream flat rows and group them in memory, or use `List<T>` returns.

## Streaming via the escape hatch

`LarkBatisSession.queryStream` provides streaming for custom dynamic queries:

```java
default Stream<User> streamRecent(LarkBatisSession s, int limit) {
    return s.queryStream(
            SqlFragment.unsafeRawSql(
                    "SELECT id, name, email, created_at FROM users"
                            + " ORDER BY created_at DESC LIMIT " + limit),
            ps -> { },
            UserRow.READER);
}
```

The caller must close the stream in a `try`-with-resources block. See [Raw SQL](raw-sql.md#the-escape-hatch).

## Spring `@Transactional` with Streams

Streams work cleanly with Spring's `@Transactional`:

```java
@Transactional(readOnly = true)
public void export(Writer out) {
    try (Stream<User> rows = users.streamAll()) {
        rows.forEach(u -> write(out, u));
    }
}
```

## JDBC fetch size considerations

LarkBatis does not force a default `fetchSize`. The optimal fetch size depends on your database driver and available memory. Note that some drivers (such as PostgreSQL) require auto-commit to be turned off for cursor streaming to work; otherwise, the driver buffers the entire result set on the client. For large streams, wrap the call in `@Transactional(readOnly = true)`.
