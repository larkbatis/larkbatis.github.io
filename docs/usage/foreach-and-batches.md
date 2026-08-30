# foreach and Batches

`<foreach>` is the hardest case in dynamic SQL, because the number of placeholders is
the one thing about the SQL text that genuinely is not known until runtime. LarkBatis
compiles it to **two loops that walk the same elements in the same order**: one appends
placeholders, one binds values.

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

1.  See [Empty collections](#empty-collections) below.
2.  Cardinality changes the SQL text, so this statement is tracked like a `${}` splice.
3.  The second loop. No `__frch_id_0` naming layer routes values through, because the
    loop index already connects placeholder *k* to value *k*.

## What can be iterated

| Collection type | `item` | `index` |
|---|---|---|
| `List<T>`, any `Collection<T>` | the element | the position |
| `T[]` | the element | the position |
| `Map<K, V>` | the **value** | the **key** |

All of them must be **statically typed**: `List<Long>`, not `List`. The element type is
what chooses `ps.setLong` over `ps.setString` at build time.

Loops nest, and the outer `item` can be the inner loop's `collection`:

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

Sibling loops may reuse the same `index` name; the generator renames them apart.

## Using `index`

`index` is the position (or the map key), and it binds like any other value. The standard
"preserve the input order" trick:

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

With a `Map`, `index` is the key and `item` is the value:

```xml
<foreach collection="filters" item="value" index="column" separator=" OR ">
  (name = #{column} AND email = #{value})
</foreach>
```

## Binding a property of the element

The body does not have to bind the element itself:

```xml
<foreach collection="probes" item="p" open="(" separator="," close=")">#{p.email}</foreach>
```

## Empty collections

!!! danger "An empty `<foreach>` throws"

    ```text
    LarkBatisEmptyForeachException:
      <foreach collection="ids"> is empty in statement com.example.app.UserBatchMapper.findByIds;
      wrap the loop in an <if> testing the collection if an empty one should drop the fragment instead
    ```

MyBatis contributes *nothing* for an empty collection, not even `open` and `close`. That
leaves `... WHERE id IN` to reach the database and fail there, with a syntax error that
names neither the mapper nor the parameter. Failing here instead names both, at the call
site that owns the empty list.

If you genuinely want the fragment to disappear, say so, and you keep MyBatis's
behaviour exactly:

```xml
<if test="ids != null and !ids.isEmpty()">
  AND id IN
  <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
</if>
```

## `@PadPow2`: bounding the SQL variants { #padpow2-bounding-the-sql-variants }

The SQL text of a `<foreach>` statement changes with the number of elements, so the
driver's and the database's statement caches grow with **every cardinality ever seen**.
`@PadPow2` rounds the placeholder count up to the next power of two, repeating the last
element, which bounds that at log₂(n) variants instead of n. Hibernate calls the same
trick `in_clause_parameter_padding`.

```java
@PadPow2
List<User> findByIdsPadded(List<Long> ids);
```

```java
int p0 = LarkBatisSql.padPow2(n0);
// ... p0 placeholders emitted
Long last0 = null;
for (Long id : ids) {
    JdbcCodec.setLong(ps, i++, id);
    last0 = id;
}
for (int k0 = n0; k0 < p0; k0++) {
    JdbcCodec.setLong(ps, i++, last0);      // repeat the last element
}
```

On an interface it applies to every statement; on a method, to that one.

!!! warning "Opt-in, and enforced"

    Repeating the last element is invisible only where duplicates cannot change the
    result, which means an `IN` list. The generator enforces that: the `<foreach>` body
    must be a single `#{}` bind and the statement must not be an `INSERT`. Outside those
    limits padding is a **compile error**, never silently duplicated rows.

## Multi-row `VALUES`

A `<foreach>` in an `INSERT` builds one statement with many value tuples:

```xml
<insert id="insertAll">
  INSERT INTO users (name, email, created_at) VALUES
  <foreach collection="users" item="u" separator=",">
    (#{u.name}, #{u.email}, #{u.createdAt})
  </foreach>
</insert>
```

## JDBC batches

Batching is not an executor mode you configure, because there is no executor. It is a
**method signature**: an `@Insert` whose parameter is a `List<T>` compiles to `addBatch()` /
`executeBatch()`.

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

1.  An empty batch is a no-op returning 0. Unlike an empty `<foreach>`, it produces no
    malformed SQL to protect you from.
2.  Drivers exist that return fewer keys than rows. Ignoring that would leave part of the
    batch with null ids and nobody the wiser. See [Generated Keys](generated-keys.md).

!!! note "Batch and dynamic SQL do not combine"

    A batch statement's SQL text must be the same for every row, which is what makes it
    one prepared statement. A batch method whose statement contains dynamic tags is a
    compile error.
