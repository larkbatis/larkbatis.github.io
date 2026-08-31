# Generated Code

Generated code in LarkBatis is designed to be clean, readable, and easy to debug. When something goes wrong, you get a clean stack trace pointing directly to a line of Java code in your project package—not a deep labyrinth of dynamic proxy invocations like `MapperProxy.invoke() → MapperMethod.execute()`.

## Generated Artifacts

During compilation, LarkBatis generates four types of source files:

| Emitted Class | Scope | Purpose |
|---|---|---|
| `UserMapper$$Impl` | One per mapper interface | Concrete class implementing the mapper methods using direct JDBC calls |
| `UserRow` | One per result class | Static row reader methods shared by all queries returning `User` |
| `LarkBatisMappers` | One per compilation unit | Static factory registry for instantiating mappers |
| `LarkBatisMapperConfiguration` | One per compilation (if Spring is on classpath) | Spring `@Configuration` defining mapper `@Bean`s |

All generated files are placed in the same package as their corresponding mapper interface.

## Anatomy of a Generated Mapper

Here is what a generated `Mapper$$Impl` class looks like:

```java
@Generated("io.github.larkbatis.processor.LarkBatisProcessor")
public final class UserMapper$$Impl implements UserMapper {

    private static final String SQL_findById =
            "SELECT id, name, email, created_at FROM users WHERE id = ?";   // (1)!
    private static final String[] KEYS_insert = { "id" };                   // (2)!

    private final LarkBatisSession s;

    public UserMapper$$Impl(LarkBatisSession s) {                          // (3)!
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

1. **Static SQL constant**: Static queries are compiled into `static final String` constants. Parameter placeholders `#{}` are converted into JDBC `?` markers at compile time.
2. **Explicit generated keys**: Passes key column names directly to `prepareStatement(sql, String[])`.
3. **Public constructor**: Accepts `LarkBatisSession`, making mapper beans standard Spring components without requiring factory beans or dynamic proxies.
4. **Transaction-aware connection**: `s.conn()` checks out the connection from Spring's active `@Transactional` context or opens a standalone auto-commit connection.
5. **Typed parameter setters**: Calls `ps.setLong()` directly instead of reflecting or calling `setObject()`.
6. **Exception translation**: Automatically translates JDBC exceptions into Spring's exception hierarchy (or `LarkBatisException`).
7. **Connection release**: Released via `s.release(c)` in a `finally` block to preserve Spring transaction ownership.

## Anatomy of Dynamic SQL Statements

Dynamic SQL tags (`<if>`, `<where>`, `<choose>`) compile into boolean flags and a pre-sized `StringBuilder`:

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
    // ...
```

1. **Calculated buffer capacity**: Initial `StringBuilder` capacity is calculated at compile time based on the longest potential query string.
2. **Constant-folded `<where>` clause**: Replaces runtime string trimming with boolean checks (`c0 | c1`).
3. **Leading `AND`/`OR` handling**: Inlines prefix decisions using ternary conditions based on active flags.
4. **Synchronized parameter binding**: Uses the exact same boolean flags (`c0`, `c1`) to bind parameters, guaranteeing that bound parameters always match query placeholders.

## Anatomy of Generated Row Readers { #row-readers }

Each result bean gets a dedicated `RowReader` class with three read strategies:

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
        // ...
    }

    public static int[] columns(ResultSet rs) throws SQLException {        // (4)!
        ResultSetMetaData md = rs.getMetaData();
        int[] c = new int[4];
        for (int i = 1, n = md.getColumnCount(); i <= n; i++) {
            switch (md.getColumnLabel(i).replace("_", "").toLowerCase(Locale.ROOT)) {
                case "id" -> c[0] = i;
                case "name" -> c[1] = i;
                // ...
            }
        }
        return c;
    }
}
```

1. **Static `READER` constant**: Reusable functional interface instance used by escape-hatch dynamic queries.
2. **Positional reader**: Hardcoded column indexes for queries with parsed select lists (fastest path).
3. **Indexed reader**: Maps column positions dynamically when query column order cannot be determined at compile time.
4. **Column resolver**: Parses `ResultSetMetaData` once on the first result row, computing column index positions to avoid repeated string lookups on subsequent rows.

## Anatomy of Nested `<resultMap>` Join Mappings

Nested collections compile into single-pass grouping loops:

```java
long key = rs.getLong(1);
if (!has || key != lastKey) {          // new parent object
    parent = new Team();
    // populate parent properties...
}
if (rs.getObject(3) != null) {         // check for null child in LEFT JOIN
    Member m = new Member();
    // populate child properties...
    parent.getMembers().add(m);
}
```

This single-pass algorithm avoids allocating intermediate map lookup keys and boxing primitives. It requires queries to be sorted by parent key (`ORDER BY team.id`).

## Spring Configuration & Factory Registry

```java
public final class LarkBatisMappers {
    public static UserMapper userMapper(LarkBatisSession s) {
        return new UserMapper$$Impl(s);
    }
}

@Configuration(proxyBeanMethods = false)
public class LarkBatisMapperConfiguration {
    @Bean
    public UserMapper userMapper(LarkBatisSession s) {
        return new UserMapper$$Impl(s);
    }
}
```

Because mappers are standard classes with public constructors, Spring instantiates them as direct beans without runtime JDK dynamic proxies or CGLIB subclassing.
