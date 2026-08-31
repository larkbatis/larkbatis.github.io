# Result Maps and Joins

A `<resultMap>` explicitly maps SQL columns to Java properties and can populate **one** nested `<association>` (a 1-to-1 child object) or `<collection>` (a `List`) from a SQL join query.

```xml
<resultMap id="teamWithMembers" type="com.example.app.Team">
  <id     property="id"   column="t_id"/>
  <result property="name" column="t_name"/>
  <collection property="members" ofType="com.example.app.Member">
    <id     property="id"     column="m_id"/>
    <result property="name"   column="m_name"/>
    <result property="jersey" column="m_jersey"/>
  </collection>
</resultMap>

<select id="findAllWithMembers" resultMap="teamWithMembers">
  SELECT t.id AS t_id, t.name AS t_name,
         m.id AS m_id, m.name AS m_name, m.jersey AS m_jersey
  FROM team t LEFT JOIN member m ON m.team_id = t.id
  ORDER BY t.id, m.jersey
</select>
```

`<association>` works the exact same way for single child relationships:

```xml
<resultMap id="teamWithCoach" type="com.example.app.Team">
  <id     property="id"   column="t_id"/>
  <result property="name" column="t_name"/>
  <association property="coach" javaType="com.example.app.Coach">
    <id     property="id"   column="c_id"/>
    <result property="name" column="c_name"/>
  </association>
</resultMap>
```

## What it compiles to

A generated loop instantiates a new parent object whenever the parent `<id>` column value changes. It ignores child properties when the child `<id>` is `NULL` (a `LEFT JOIN` miss):

```java
List<Team> out = new ArrayList<>();
Team parent = null;
long lastKey = 0;
boolean has = false;
while (rs.next()) {
    long key = rs.getLong(1);
    if (!has || key != lastKey) {          // (1)!
        parent = new Team();
        parent.setId(key);
        parent.setName(rs.getString(2));
        parent.setMembers(new ArrayList<>());
        out.add(parent);
        lastKey = key;
        has = true;
    }
    if (rs.getObject(3) != null) {         // (2)!
        Member m = new Member();
        m.setId(rs.getLong(3));
        m.setName(rs.getString(4));
        m.setJersey(rs.getInt(5));
        parent.getMembers().add(m);
    }
}
```

1.  MyBatis manages join grouping by creating a `CacheKey` per row: reflecting over ID columns, converting them via `TypeHandler`s, hashing, and performing HashMap lookups. LarkBatis compares typed primitives directly using `!=`, avoiding object allocations and boxing entirely.
2.  Handles `LEFT JOIN` misses. Without this check, unmatched parent rows would create child instances filled with `null`s.

## The ordering rule

!!! warning "The query ResultSet MUST be ordered by parent ID"

    This is the trade-off for zero heap allocations: rows must group parent keys sequentially. If rows for a given parent ID appear out of order later in the ResultSet, a duplicate parent instance will be created rather than merged into the previous one.

    ```sql
    ORDER BY t.id, m.jersey   -- parent key must be ordered first
    ```

    Queries using nested result maps without an `ORDER BY` clause will produce a build warning.

## No implicit auto-mapping in `<resultMap>`

A `<resultMap>` maps **only the columns you explicitly declare**. There is no implicit runtime column guessing:

- A `<result>` mapping referencing a column missing from the `SELECT` list produces a **build warning**, leaving that property unset.
- An `<id>` mapping referencing a missing column causes a **compile error** because the loop requires it for row grouping.

If you want automatic camelCase property mapping based on column names, use `resultType` instead. Use `resultType` for standard convention mapping and `<resultMap>` when you need explicit column-to-property control or SQL join mapping.

## Column indexes

When the `SELECT` list can be parsed, column indexes are hardcoded as static constants. If the query uses `SELECT *` or dynamic column splices, a lightweight resolver determines column positions once on the first row and reads by index thereafter.

## Intentional limitations { #narrowed-on-purpose }

The following features produce explicit **compile errors** with recommended alternatives:

| Unsupported Feature | Recommended Alternative |
|---|---|
| Nesting deeper than 1 level, or multiple collections | Use a single SQL join, or query relationships separately |
| `select=` on `<association>` / `<collection>` | Write a SQL join (nested `select=` causes N+1 queries) |
| Nested `resultMap=` references | Declare child `<id>`/`<result>` mappings inline |
| `columnPrefix` attribute | Alias child columns in the `SELECT` query |
| `extends` attribute | Declare property mappings explicitly |
| `<constructor>` results | Provide a standard no-arg constructor and setters |
| `<discriminator>` tags | Split into separate queries with distinct return types |
| `autoMapping="true"` | Declare mappings explicitly or use `resultType` |
| Type aliases in `type`/`javaType`/`ofType` | Use fully-qualified class names |

For multi-level hierarchies, execute two targeted queries and assemble the object graph in Java. It uses the same number of database round trips and keeps your assembly logic clear and testable.

## Streams and nested result maps

Returning a `Stream<T>` with a nested `<resultMap>` is a **compile error**. Because parent objects span multiple rows in a join ResultSet, a parent is only complete when the next parent ID is encountered. Streaming one row at a time would require buffering the entire ResultSet in memory, defeating the purpose of streaming. See [Streaming Results](streaming.md).
