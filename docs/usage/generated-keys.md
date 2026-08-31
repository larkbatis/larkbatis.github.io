# Generated Keys

`@Options(useGeneratedKeys = true, ...)` retrieves database-generated primary keys after an `INSERT` and sets them directly on your parameter object.

```java
@Insert("INSERT INTO users (name, email, created_at) VALUES (#{name}, #{email}, #{createdAt})")
@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
int insert(User u);
```

```java
private static final String[] KEYS_insert = { "id" };

@Override
public int insert(User u) {
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(SQL_insert, KEYS_insert)) {  // (1)!
        ps.setString(1, u.getName());
        ps.setString(2, u.getEmail());
        JdbcCodec.setInstant(ps, 3, u.getCreatedAt());
        int n = ps.executeUpdate();
        try (ResultSet gk = ps.getGeneratedKeys()) {
            if (gk.next()) {
                u.setId(gk.getLong(1));                                          // (2)!
            }
        }
        return n;
    } catch (SQLException e) {
        throw s.translate(e, SQL_insert);
    } finally {
        s.release(c);
    }
}
```

1.  Explicit key **column names**: `RETURN_GENERATED_KEYS` behaves inconsistently across database drivers (see below).
2.  The property accessor is chosen at build time based on `keyProperty` and its declared Java type.

## Always name `keyColumn`

!!! warning "`keyColumn` is practically mandatory in production"

    Using `prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)` is not portable across drivers:

    - **Oracle** returns the database `ROWID`, not sequence IDs.
    - **PostgreSQL** returns *all* columns of the inserted row.

    Specifying explicit column names with `keyColumn` is the only way to get consistent behavior across all databases. If `keyColumn` is omitted, the generator falls back to `RETURN_GENERATED_KEYS` and prints a compiler warning.

`keyProperty` is **mandatory**: omitting it is a compile error because the generator must know where to store the returned key.

For composite keys, provide comma-separated lists of matching length:

```java
@Options(useGeneratedKeys = true, keyProperty = "tenantId,id", keyColumn = "tenant_id,id")
```

## `keyProperty` with multiple parameters

When a method accepts multiple arguments, prefix `keyProperty` with the parameter name:

```java
@Insert("INSERT INTO users (name) VALUES (#{u.name})")
@Options(useGeneratedKeys = true, keyProperty = "u.id", keyColumn = "id")
int insert(@Param("u") User u, @Param("audit") String audit);
```

Invalid property paths are caught as **compile-time errors**.

## Batch inserts and generated keys

Batch inserts taking a `List<T>` compile to JDBC `addBatch()` / `executeBatch()` calls:

```java
int n = LarkBatisSql.sum(ps.executeBatch());
try (ResultSet gk = ps.getGeneratedKeys()) {
    int i = 0;
    while (gk.next() && i < orders.size()) {
        orders.get(i).setId(gk.getLong(1));
        i++;
    }
    if (i != orders.size()) {
        throw new LarkBatisKeyCountMismatchException(STMT_insertAll, orders.size(), i);
    }
}
```

Some database drivers return fewer generated keys than inserted rows. Instead of silently leaving trailing list elements with null or zero IDs, LarkBatis throws `LarkBatisKeyCountMismatchException` immediately.

## `<selectKey>` is not supported

MyBatis used `<selectKey>` to fetch sequence values before running an insert. In LarkBatis, write the two statements explicitly:

```java
@Select("SELECT user_seq.NEXTVAL FROM dual")
long nextUserId();

@Insert("INSERT INTO users (id, name) VALUES (#{id}, #{name})")
int insert(User u);
```

```java
try (LarkBatisTx tx = session.begin()) {
    u.setId(mapper.nextUserId());
    mapper.insert(u);
    tx.commit();
}
```

## When no key is returned

If a statement declares `useGeneratedKeys = true` but the driver returns an empty `ResultSet`, LarkBatis throws `LarkBatisNoKeyException` to prevent uninitialized default IDs from propagating silently.
