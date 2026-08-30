# Generated Keys

`@Options(useGeneratedKeys = true, ...)` asks the driver for the key an `INSERT`
produced and assigns it to a property of the parameter object.

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

1.  Explicit key **column names**, because `RETURN_GENERATED_KEYS` means different
    things on different databases. See below.
2.  The setter and the accessor are both chosen at build time from `keyProperty` and the
    property's declared type.

## Always name the key columns

!!! warning "`keyColumn` is optional in the annotation and effectively mandatory in practice"

    `prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)` is not portable:

    - **Oracle** returns `ROWID`, not your sequence value.
    - **PostgreSQL** returns *every* column of the inserted row.

    Passing an explicit `String[]` of column names is the only form that means the same
    thing everywhere. When `keyColumn` is present the generator emits
    `prepareStatement(sql, String[])`. When it is missing it has no names to put in the
    array, so it falls back to `RETURN_GENERATED_KEYS` and raises a **mandatory build
    warning**:

    ```text
    warning: useGeneratedKeys without keyColumn falls back to RETURN_GENERATED_KEYS,
    which returns ROWID on Oracle and all columns on PostgreSQL. Name the key column(s)
    explicitly.
    ```

    Treat that warning as an error in review. It is the difference between working on H2
    and working in production.

`keyProperty`, by contrast, is **required**: `useGeneratedKeys` without it is a compile
error asking where the key should go.

Composite keys are comma-separated on both attributes, and the two lists must be the
same length, and a mismatch is a compile error naming both counts:

```java
@Options(useGeneratedKeys = true, keyProperty = "tenantId,id", keyColumn = "tenant_id,id")
```

## `keyProperty` with several parameters

With more than one method parameter, `keyProperty` must name the parameter as well:

```java
@Insert("INSERT INTO users (name) VALUES (#{u.name})")
@Options(useGeneratedKeys = true, keyProperty = "u.id", keyColumn = "id")
int insert(@Param("u") User u, @Param("audit") String audit);
```

A wrong name is a **compile-time error**, not a runtime `ReflectionException`.

## Batch inserts

An `@Insert` taking a `List<T>` compiles to `addBatch()` / `executeBatch()`, and the keys
come back as one `ResultSet` that has to line up with the list:

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

The count check is not defensive programming for its own sake: drivers exist that return
fewer keys than rows, and MyBatis documents the same failure mode. Silently accepting it
would leave part of your batch with unset ids and nobody the wiser, so
`LarkBatisKeyCountMismatchException` names the statement, the expected count and the
actual one.

## `<selectKey>` is not supported

Databases without generated-key support (or workflows that read a sequence *before* the
insert) used `<selectKey>` in MyBatis. It is not implemented, because it is a second
statement wearing the costume of an option. Write the second statement:

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

The [migration scanner](../features/migration.md) reports every `<selectKey>` it finds
with this as the fix.

## When no key comes back

If a statement declares `useGeneratedKeys` and the driver returns nothing,
`LarkBatisNoKeyException` is thrown naming the statement, instead of leaving a `0` id to
travel through your code and fail somewhere unrelated.
