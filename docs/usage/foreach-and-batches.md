# foreach and Batches

`<foreach>` requires dynamic SQL generation because the number of parameter placeholders is only known at runtime. LarkBatis compiles `<foreach>` into **two parallel loops**: the first generates the placeholder string (`?, ?, ?`), and the second binds the typed values.

```xml
<select id="findByIds" resultType="com.example.app.User">
  SELECT id, name, email, created_at FROM users WHERE id IN
  <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
  ORDER BY id
</select>
```

```java
@Override
public List<User> findByIds(List<Long> ids) {
    StringBuilder sb = new StringBuilder(144);
    sb.append("SELECT id, name, email, created_at FROM users WHERE id IN");
    int n0 = ids.size();
    if (n0 == 0) {
        throw new LarkBatisEmptyForeachException(STMT_findByIds, "ids");   // (1)!
    }
    sb.append(" (");
    for (int k0 = 0; k0 < n0; k0++) sb.append(k0 == 0 ? " ?" : " , ?");
    sb.append(" )");
    sb.append(" ORDER BY id");
    String sql = sb.toString();
    LarkBatisSql.trackVariants(STMT_findByIds, sql);                       // (2)!
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(sql)) {
        int i = 1;
        for (Long id : ids) {                                               // (3)!
            JdbcCodec.setLong(ps, i++, id);
        }
        // ... read rows
    }
}
```

1.  Throws immediately on empty collections (see below).
2.  Monitors generated SQL variants to prevent unbounded query cache growth.
3.  Direct iteration binds values positionally with zero intermediate map lookups.

## Supported collection types

| Collection Type | `item` | `index` |
|---|---|---|
| `List<T>`, `Collection<T>` | Element value | Zero-based index integer |
| `T[]` (arrays) | Element value | Zero-based index integer |
| `Map<K, V>` | Entry **value** | Entry **key** |

Collections must have **concrete generic types** (e.g. `List<Long>`, not raw `List`). The element type determines the typed `ps.setXxx` call generated at compile time.

Nested loops are fully supported:

```xml
<select id="findByIdGroups" resultType="com.example.app.User">
  SELECT id, name, email, created_at FROM users WHERE
  <foreach collection="groups" item="group" separator=" OR ">
    id IN
    <foreach collection="group" item="id" open="(" separator="," close=")">#{id}</foreach>
  </foreach>
  ORDER BY id
</select>
```

```java
List<User> findByIdGroups(List<List<Long>> groups);
```

## Using `index`

`index` represents the item's index (or map key) and can be bound like any parameter. For example, preserving custom ordering:

```xml
<select id="findByIdsOrdered" resultType="com.example.app.User">
  SELECT id, name, email, created_at FROM users WHERE id IN
  <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
  ORDER BY CASE id
  <foreach collection="ids" item="orderedId" index="position">
    WHEN #{orderedId} THEN #{position}
  </foreach>
  END
</select>
```

When iterating over a `Map`, `index` binds the key and `item` binds the value:

```xml
<foreach collection="filters" item="value" index="column" separator=" OR ">
  (name = #{column} AND email = #{value})
</foreach>
```

## Binding nested properties

You can bind properties on collection items directly:

```xml
<foreach collection="probes" item="p" open="(" separator="," close=")">#{p.email}</foreach>
```

## Empty collections throw immediately

!!! danger "An empty `<foreach>` throws `LarkBatisEmptyForeachException`"

    ```text
    LarkBatisEmptyForeachException:
      <foreach collection="ids"> is empty in statement com.example.app.UserBatchMapper.findByIds;
      wrap the loop in an <if> testing the collection if an empty one should drop the fragment instead
    ```

    In MyBatis, an empty collection generates an empty string (omitting `open` and `close`), leaving `WHERE id IN` to fail at the database with a vague syntax error. LarkBatis catches this early with a clear exception naming the mapper and parameter.

    If you want the SQL clause omitted entirely when a collection is empty, wrap it in an `<if>` condition:

    ```xml
    <if test="ids != null and !ids.isEmpty()">
      AND id IN
      <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
    </if>
    ```

## `@PadPow2`: Bounding SQL variants { #padpow2-bounding-the-sql-variants }

Because `<foreach>` generates dynamic SQL strings based on collection length, variable collection sizes can flood statement caches.

`@PadPow2` rounds the parameter count up to the nearest power of two by repeating the last element, bounding the number of distinct SQL variants to $\log_2(N)$ instead of $N$ (similar to Hibernate's parameter padding).

```java
@PadPow2
List<User> findByIdsPadded(List<Long> ids);
```

```java
int p0 = LarkBatisSql.padPow2(n0);
// ... emits p0 placeholders (?, ?, ?, ?)
Long last0 = null;
for (Long id : ids) {
    JdbcCodec.setLong(ps, i++, id);
    last0 = id;
}
for (int k0 = n0; k0 < p0; k0++) {
    JdbcCodec.setLong(ps, i++, last0);      // pads remaining positions with the last element
}
```

!!! warning "Padding rules"

    Repeating elements is only safe where duplicate arguments don't affect query semantics (e.g. `IN` clauses). The compiler enforces this: `@PadPow2` is only permitted on `SELECT`/`UPDATE`/`DELETE` queries with simple `#{}` binds, and is rejected on `INSERT` statements.

## Multi-row `VALUES` inserts

Use `<foreach>` in `<insert>` statements to insert multiple rows in a single SQL statement:

```xml
<insert id="insertAll">
  INSERT INTO users (name, email, created_at) VALUES
  <foreach collection="users" item="u" separator=",">
    (#{u.name}, #{u.email}, #{u.createdAt})
  </foreach>
</insert>
```

## JDBC batch inserts

Batching in LarkBatis is declared via **method signatures**: an `@Insert` taking a `List<T>` compiles directly to JDBC `addBatch()` / `executeBatch()` calls:

```java
@Insert("INSERT INTO orders (status, total, placed_at) VALUES (#{status}, #{total}, #{placedAt})")
@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
int insertAll(List<Order> orders);
```

```java
public int insertAll(List<Order> orders) {
    if (orders.isEmpty()) {
        return 0;                                   // (1)!
    }
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(SQL_insertAll, KEYS_insertAll)) {
        for (Order order : orders) {
            JdbcCodec.setEnum(ps, 1, order.getStatus());
            ps.setBigDecimal(2, order.getTotal());
            JdbcCodec.setInstant(ps, 3, order.getPlacedAt());
            ps.addBatch();
        }
        int n = LarkBatisSql.sum(ps.executeBatch());
        try (ResultSet gk = ps.getGeneratedKeys()) {
            int i = 0;
            while (gk.next() && i < orders.size()) {
                orders.get(i).setId(gk.getLong(1));
                i++;
            }
            if (i != orders.size()) {
                throw new LarkBatisKeyCountMismatchException(STMT, orders.size(), i); // (2)!
            }
        }
        return n;
    } catch (SQLException e) {
        throw s.translate(e, SQL_insertAll);
    } finally {
        s.release(c);
    }
}
```

1.  An empty list returns `0` immediately without touching the database.
2.  Validates that returned generated key counts match the batch size. See [Generated Keys](generated-keys.md).

!!! note "Batch methods cannot contain dynamic SQL"

    JDBC batching requires a single, invariant SQL statement string. Statements containing dynamic tags (`<if>`, `<choose>`, etc.) cannot be used with batch execution and trigger a compile error.
