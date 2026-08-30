# Result Maps and Joins

A `<resultMap>` declares the column each property comes from, and may fill **one** nested
`<association>` (a single child object) or `<collection>` (a `List`) from the same join.

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

An `<association>` works the same way for a single child:

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

A loop that starts a new parent where the `<id>` column changes, and skips the child when
its `<id>` column is `NULL` — a `LEFT JOIN` miss:

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

1.  MyBatis does this job by building a `CacheKey` per row: reflect over the id columns,
    read each through a `TypeHandler`, hash, look the parent up in a map. Here the key is
    a typed local compared with `!=` — a `long` key costs no boxing per row.
2.  The `LEFT JOIN` miss test. Without it, an unmatched parent would gain a child of all
    nulls.

## The ordering rule

!!! warning "The ResultSet must be ordered by the parent key"

    That is the price of not keeping a map. Rows that revisit a key **after another
    parent's rows** produce a second parent object instead of merging into the first.

    ```sql
    ORDER BY t.id, m.jersey   -- parent key first
    ```

    A statement using a nested result map with **no `ORDER BY` at all** gets a build-time
    note. A wrong `ORDER BY` cannot be detected at build time — that one is on you.

## No auto-mapping

A result map maps **exactly what it declares**. There is no `autoMapping` and no implicit
column matching inside a `<resultMap>`.

- A `<result>` whose column is missing from the select list is a **build warning**, and
  leaves that property unset.
- An `<id>` whose column is missing is a **build error** — that column is what the loop
  reads.

If you want columns matched to property names by convention, use `resultType` instead.
That path *does* apply `snake_case` → `camelCase`, at build time. The two are different
tools: `resultType` for "map what matches", `resultMap` for "map what I say".

## Column positions

When the select list parses, positions are constants. When it does not — `SELECT *`, a
`${}` splice, an unaliased expression like `1 + 1` — that statement gets its own
generated resolver that reads `ResultSetMetaData` once on the first row and matches the
column names the map declared. Correct either way; the build tells you which happened.

## Narrowed on purpose

Each of these is a **compile error naming the replacement**:

| Not supported | Instead |
|---|---|
| More than one level of nesting, or two nested mappings in one map | One join, one grouping key |
| `select=` on `<association>` / `<collection>` (nested select) | Write the join — the nested select *is* the N+1 it avoids |
| `resultMap=` inside a nested mapping | Spell the child's `<id>`/`<result>` out, which keeps the one-level limit visible |
| `columnPrefix` | Alias the child columns in the select list |
| `extends` | Spell the mappings out |
| `<constructor>` | Result classes are built with a no-arg constructor and setters |
| `<discriminator>` | Separate statements with separate result types |
| `autoMapping` | Declare the mappings, or use `resultType` |
| `<id column="x"/>` with no `property` | Map the key to a property and mark that `<id>` |
| A type alias in `type` / `ofType` / `javaType` | The fully-qualified class name |

Deeper object graphs are assembled in Java from two statements. That is not a workaround
for a missing feature — it is the same number of round trips, with the assembly visible
in code you can read.

## `Stream` and nested result maps

A `Stream` return over a nested `<resultMap>` is a **compile error**. A parent spans
several rows, so it is only complete once the next parent starts; answering that from a
one-row-at-a-time cursor means buffering the whole result, which is exactly what the
`Stream` return was chosen to avoid. See [Streaming Results](streaming.md).
