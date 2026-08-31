# Mapper Interfaces

A mapper is just a plain Java interface. You don't need base interfaces, special marker annotations on methods beyond statement annotations, or runtime proxies. The compiler generates `final class UserMapper$$Impl implements UserMapper` with a public constructor accepting a `LarkBatisSession`.

## Statement annotations

| Annotation | Statement |
|---|---|
| `@Select` | `SELECT` |
| `@Insert` | `INSERT` |
| `@Update` | `UPDATE` |
| `@Delete` | `DELETE` |

Each takes `String[]`, so long SQL statements can be split cleanly across multiple lines and are joined with a single space:

```java
@Select({
    "SELECT id, name, email, created_at",
    "FROM users",
    "WHERE email = #{email}"
})
User findByEmail(String email);
```

Any interface containing statement annotations is discovered automatically. You only need [`@Mapper`](../features/annotations.md#mapper) if the interface statements live entirely in [mapper XML](xml-mappers.md).

## Parameters and `#{}`

`#{name}` becomes a `?` in the prepared statement and an indexed `ps.setXxx` call in generated code. How `name` is resolved depends on your method signature:

=== "Single parameter"

    The name matches the parameter name or a property path on the parameter object:

    ```java
    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);

    @Insert("INSERT INTO users (name, email) VALUES (#{name}, #{email})")
    int insert(User u);          // #{name} -> u.getName()
    ```

=== "Multiple parameters"

    Parameters need names for SQL binding—either from compiled parameter names or `@Param`:

    ```java
    @Select("SELECT id, name FROM users WHERE name LIKE #{pattern} AND id > #{after}")
    List<User> page(@Param("pattern") String pattern, @Param("after") long after);
    ```

=== "Property paths"

    Dotted paths navigate getters and are strictly type-checked at build time:

    ```java
    @Select("SELECT id FROM users WHERE email = #{probe.email}")
    List<User> byProbe(@Param("probe") User probe);
    ```

!!! warning "Compile with `-parameters` or use `@Param`"

    Gradle incremental builds can pass compiled class files to the processor where parameter names are stripped unless compiled with `-parameters`. Without it, parameters appear as `arg0`, `arg1`, breaking `#{id}` resolution. See [Troubleshooting](troubleshooting.md).

Unresolvable parameter names trigger a **compile error** showing the method and invalid expression. Untyped `Map` or `Object` parameters are not supported because the compiler requires concrete types to generate parameter bindings.

## Return types

| Signature | Generated method body |
|---|---|
| `User findById(long)` | `rs.next() ? UserRow.read(rs) : null` |
| `List<User> findAll()` | `while (rs.next()) out.add(UserRow.read(rs))` |
| `Stream<User> streamAll()` | Returns cursor stream; caller closes it. See [Streaming](streaming.md) |
| `long countByName(String)` | Reads column 1 directly as `long` |
| `int insert(User)` | `ps.executeUpdate()` |
| `void delete(long)` | `ps.executeUpdate()` (result discarded) |

Scalar queries read column 1 directly without allocating bean objects or row readers:

```java
@Select("SELECT COUNT(*) FROM users WHERE name LIKE #{pattern}")
long countByName(@Param("pattern") String pattern);
```

## Result classes

A result class needs a no-arg constructor and standard getters/setters:

```java
public class User {
    private long id;
    private String name;
    private Instant createdAt;
    // standard getters and setters
}
```

Columns are mapped to properties using `snake_case` → `camelCase` **at build time**: `created_at` maps to `setCreatedAt`. This is enabled by default. To preserve legacy MyBatis behavior (where underscore mapping was off by default), pass `-Alarkbatis.mapUnderscoreToCamelCase=false`. See [Configuration](../features/configuration.md#column-naming).

To override mapping for specific columns, use [`@Column`](../features/annotations.md#column) on the field/getter/setter, alias the column in your SQL, or define a [`<resultMap>`](result-maps.md). See [Types and Handlers](types.md#column-naming).

### Positional vs Name-Based Reads

When the generator can parse your select list, column indexes are hardcoded as constants:

```java
u.setId(rs.getLong(1));
u.setName(rs.getString(2));
```

If the generator cannot parse the select list, that statement falls back to a name-based reader. It resolves column indexes from `ResultSetMetaData` **once on the first row** and reads by index for the rest. Three things trigger this fallback: `SELECT *`, a `${}` splice in the select list, or an unaliased expression. The fallback is fully correct but slightly slower, and javac outputs a build note when it happens. See [Generated Code](../wiki/generated-code.md#row-readers).

!!! note "`@LarkBatisRow`"

    If a class is never used as a statement's `resultType` (for example, ad-hoc queries run via the [escape hatch](raw-sql.md#the-escape-hatch)), annotate it with [`@LarkBatisRow`](../features/annotations.md#larkbatisrow) to generate a row reader for it.

## Default methods

`default` methods on mapper interfaces remain intact and are inherited by generated implementation classes. This is the recommended place for hand-assembled dynamic queries:

```java
default List<User> recent(LarkBatisSession s, int limit) {
    return s.query(
            SqlFragment.unsafeRawSql(
                    "SELECT id, name, email, created_at FROM users"
                            + " ORDER BY created_at DESC LIMIT " + limit),
            ps -> { },
            UserRow.READER);
}
```

Notice that row reading remains completely type-safe: rows are read by the generated `UserRow.READER` with zero reflection. See [Raw SQL and SqlFragment](raw-sql.md).

## The generated registry

Every mapper in a compilation module is registered in a static `LarkBatisMappers` factory:

```java
UserMapper mapper = LarkBatisMappers.userMapper(session);
```

`LarkBatisMappers` is a static factory over a fixed set of mappers known at compile time. In Spring applications, you don't need to call this directly because the generated `@Configuration` exposes each mapper as a Spring bean automatically.

By default, the registry is generated in the common package prefix of all mappers. You can customize this with `-Alarkbatis.registryPackage=com.example.app`.
