# Generated Code

Generated code is a **feature**, not an implementation detail. It is meant to be opened,
read, and stepped through in a debugger — a stack trace should point at a real Java line
in your package, not at `MapperProxy.invoke → MapperMethod.execute → …`.

For a codebase with 300 mapper methods, that debuggability is worth more day to day than
a few microseconds per query.

## What gets emitted

| File | Cardinality | Contents |
|---|---|---|
| `UserMapper$$Impl` | one per mapper | The implementation. One method per statement |
| `UserRow` | one per result class | Three reads and a column resolver. Shared by every statement returning `User` |
| `LightBatisMappers` | one per compilation | Static factory over the closed set of mappers |
| `LightBatisMapperConfiguration` | one per compilation, if Spring is present | `@Bean` per mapper |

Everything lands in your own package, next to the interface. Under JPMS that means nothing
has to be exported for it.

## The mapper implementation

```java
@Generated("io.github.lightbatis.processor.LightBatisProcessor")
public final class UserMapper$$Impl implements UserMapper {

    private static final String SQL_findById =
            "SELECT id, name, email, created_at FROM users WHERE id = ?";   // (1)!
    private static final String[] KEYS_insert = { "id" };                   // (2)!

    private final LightBatisSession s;

    public UserMapper$$Impl(LightBatisSession s) {                          // (3)!
        this.s = s;
    }

    @Override
    public User findById(long id) {
        Connection c = s.conn();                                            // (4)!
        try (PreparedStatement ps = c.prepareStatement(SQL_findById)) {
            ps.setLong(1, id);                                              // (5)!
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? UserRow.read(rs) : null;
            }
        } catch (SQLException e) {
            throw s.translate(e, SQL_findById);                             // (6)!
        } finally {
            s.release(c);                                                   // (7)!
        }
    }
}
```

1.  Static SQL is a `static final String` — allocated once, interned, and the same object
    every call. `#{}` already became `?` at build time.
2.  Explicit key columns for `useGeneratedKeys`, so `prepareStatement(sql, String[])` can
    be used instead of the non-portable `RETURN_GENERATED_KEYS`.
3.  A public constructor taking the session. That is what makes it an ordinary Spring bean
    with no `FactoryBean` in sight.
4.  Borrowed, not opened. Under a transaction this is the transaction's connection.
5.  `setLong`, not `setObject` — chosen at build time from the parameter's declared type.
6.  Translation carries the SQL text into the exception.
7.  `release`, in `finally`. The connection is **not** in try-with-resources.

## Dynamic statements

Conditions are evaluated **once**, into locals, and the same locals drive both SQL
assembly and parameter binding:

```java
boolean c0 = q.getName() != null;
boolean c1 = q.getMinAge() != null;
StringBuilder sb = new StringBuilder(96);       // (1)!
sb.append("SELECT id, name, email, created_at FROM users");
if (c0 | c1) sb.append(" WHERE");               // (2)!
if (c0) sb.append(" name LIKE ?");
if (c1) sb.append(c0 ? " AND age >= ?" : " age >= ?");   // (3)!
sb.append(" ORDER BY id");
String sql = sb.toString();
Connection c = s.conn();
try (PreparedStatement ps = c.prepareStatement(sql)) {
    int i = 1;
    if (c0) ps.setString(i++, q.getName());     // (4)!
    if (c1) JdbcCodec.setInt(ps, i++, q.getMinAge());
    ...
```

1.  Capacity computed at build time from the longest possible text — no `StringBuilder`
    growth.
2.  `<where>` folded into a guarded literal. `|` rather than `||` because both operands are
    already-computed locals; there is nothing to short-circuit.
3.  The leading-`AND` rule, constant-folded into a ternary over known locals — not a
    runtime substring search of the assembled fragment.
4.  Binding walks the **same** conditions in the **same** order. That is why the SQL and
    the parameters can never disagree: there is no name-to-position map between them, just
    one shared set of booleans.

## Row readers

One class per result class, with three entry points:

```java
public final class UserRow {

    public static final RowReader<User> READER = UserRow::read;   // (1)!

    public static User read(ResultSet rs) throws SQLException {   // (2)!
        User u = new User();
        u.setId(rs.getLong(1));
        u.setName(rs.getString(2));
        u.setEmail(rs.getString(3));
        u.setCreatedAt(JdbcCodec.instant(rs, 4));
        return u;
    }

    public static User read(ResultSet rs, int[] c) throws SQLException {   // (3)!
        User u = new User();
        if (c[0] != 0) u.setId(rs.getLong(c[0]));
        ...
    }

    public static int[] columns(ResultSet rs) throws SQLException {        // (4)!
        ResultSetMetaData md = rs.getMetaData();
        int[] c = new int[4];
        for (int i = 1, n = md.getColumnCount(); i <= n; i++) {
            switch (md.getColumnLabel(i).replace("_", "").toLowerCase(Locale.ROOT)) {
                case "id" -> c[0] = i;
                case "name" -> c[1] = i;
                ...
            }
        }
        return c;
    }
}
```

1.  The escape hatch reuses this, so hand-assembled SQL still reads rows without
    reflection.
2.  **Positional read** — used when the generator parsed the select list. Every index is a
    literal.
3.  **Indexed read** — `c[k]` is the ResultSet position of property *k*, `0` meaning "not
    selected". A property whose column is absent stays unset rather than becoming null.
4.  **Column resolver** — runs once, on the first row, when the select list could not be
    parsed. Unmatched columns are ignored, matching MyBatis auto-mapping. The
    `replace("_","").toLowerCase()` is the `snake_case` convention, applied here for the
    same reason it is applied at build time elsewhere.

This three-entry shape is why `SELECT *` costs one metadata pass and then reads
positionally, rather than a name lookup per column per row.

## Result maps

A nested `<resultMap>` becomes a grouping loop, not a `CacheKey` map:

```java
long key = rs.getLong(1);
if (!has || key != lastKey) {          // new parent
    parent = new Team();
    ...
}
if (rs.getObject(3) != null) {         // LEFT JOIN miss
    Member m = new Member();
    ...
    parent.getMembers().add(m);
}
```

MyBatis does the same job by building a `CacheKey` per row: reflect over the id columns,
read each through a `TypeHandler`, hash, look the parent up in a map. Here the key is a
typed local compared with `!=`, so a `long` key costs no boxing per row. The price is the
[ordering requirement](../usage/result-maps.md#the-ordering-rule).

## The registry and the Spring configuration

```java
public final class LightBatisMappers {
    public static UserMapper userMapper(LightBatisSession s) {
        return new UserMapper$$Impl(s);
    }
}
```

```java
@Configuration(proxyBeanMethods = false)
public class LightBatisMapperConfiguration {
    @Bean
    public UserMapper userMapper(LightBatisSession s) {
        return new UserMapper$$Impl(s);
    }
}
```

Both are the same three lines twice, and that is the point: a mapper is a class with a
constructor, so registering one is ordinary. `proxyBeanMethods = false` avoids the runtime
CGLIB subclass Spring would otherwise build — the exact runtime bytecode generation this
project exists to remove.

## Reading the diff

Generated output is not free-form. Golden snapshots of it are committed to the core
repository, so any emitter change shows up as a reviewed diff:

```console
$ ./gradlew test -Pupdate-golden
$ git diff lightbatis-processor/src/test/resources/golden/
```

If a change to an emitter produces no golden diff, it changed nothing. If it produces one
nobody can explain, that is the review catching it.
