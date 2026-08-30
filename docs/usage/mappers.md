# Mapper Interfaces

A mapper is an ordinary Java interface. There is no base type, no marker on the methods
beyond the statement annotation, and no runtime proxy — the build emits a
`final class UserMapper$$Impl implements UserMapper` with a public constructor taking a
`LightBatisSession`.

## Statement annotations

| Annotation | Statement |
|---|---|
| `@Select` | `SELECT` |
| `@Insert` | `INSERT` |
| `@Update` | `UPDATE` |
| `@Delete` | `DELETE` |

Each takes `String[]`, so a long statement can be written as several lines that are
joined with a single space:

```java
@Select({
    "SELECT id, name, email, created_at",
    "FROM users",
    "WHERE email = #{email}"
})
User findByEmail(String email);
```

An interface carrying at least one statement annotation is discovered on its own. Add
[`@Mapper`](../features/annotations.md#mapper) only when the statements live in
[XML](xml-mappers.md).

## Parameters and `#{}`

`#{name}` becomes a `?` in the prepared statement and a `ps.setXxx` call at the matching
position. What `name` resolves against depends on the method signature:

=== "One parameter"

    The name is the parameter name, or a property path into it.

    ```java
    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);

    @Insert("INSERT INTO users (name, email) VALUES (#{name}, #{email})")
    int insert(User u);          // #{name} -> u.getName()
    ```

=== "Several parameters"

    Every parameter needs a name the SQL can use — the declared name, or `@Param`.

    ```java
    @Select("SELECT id, name FROM users WHERE name LIKE #{pattern} AND id > #{after}")
    List<User> page(@Param("pattern") String pattern, @Param("after") long after);
    ```

=== "Property paths"

    Dotted paths walk getters, and are resolved and type-checked at build time.

    ```java
    @Select("SELECT id FROM users WHERE email = #{probe.email}")
    List<User> byProbe(@Param("probe") User probe);
    ```

!!! warning "Name your parameters, or compile with `-parameters`"

    Gradle's incremental compilation can re-run the processor against **class files**,
    where parameter names survive only if the class was compiled with `-parameters`.
    Without either, `#{id}` has nothing to resolve against. See
    [Troubleshooting](troubleshooting.md).

A name that does not resolve is a **compile error** naming the method and the offending
expression. There is no `Map` or `Object` parameter: there would be no type to resolve
`#{}` against, and the whole point is that there always is one.

## Return types

| Signature | Generated body |
|---|---|
| `User findById(long)` | `rs.next() ? UserRow.read(rs) : null` |
| `List<User> findAll()` | `while (rs.next()) out.add(UserRow.read(rs))` |
| `Stream<User> streamAll()` | An open cursor — the caller closes it. See [Streaming](streaming.md) |
| `long countByName(String)` | Column 1, read as a `long` |
| `int insert(User)` | `ps.executeUpdate()` |
| `void delete(long)` | `ps.executeUpdate()`, result discarded |

Scalar results read column 1 directly, with no bean and no reader:

```java
@Select("SELECT COUNT(*) FROM users WHERE name LIKE #{pattern}")
long countByName(@Param("pattern") String pattern);
```

## Result classes

A result class needs a no-arg constructor and setters. That is the whole contract — no
annotations, no interface, no registration.

```java
public class User {
    private long id;
    private String name;
    private Instant createdAt;
    // getters and setters
}
```

Columns find properties by `snake_case` → `camelCase`, **applied at build time,
always**: `created_at` → `setCreatedAt`. There is no `mapUnderscoreToCamelCase` switch,
because there is no runtime to switch it in.

Where the convention is not enough, alias the column in the select list or declare a
[`<resultMap>`](result-maps.md). The `@Column` annotation ships in the annotations
artifact for this purpose but is **not yet read by the processor** — see
[Types and Handlers](types.md#column-naming).

### Positional or name-based reads

When the generator can parse the select list, column indexes are constants:

```java
u.setId(rs.getLong(1));
u.setName(rs.getString(2));
```

When it cannot — `SELECT *`, a `${}` splice inside the select list, an unaliased
expression — that one statement falls back to a name-based reader that resolves indexes
from `ResultSetMetaData` **once, on the first row**, and then reads positionally for the
rest. It is correct and measurably slower, and the build tells you which statement it
happened to. See [Generated Code](../wiki/generated-code.md#row-readers).

!!! note "`@LightBatisRow`"

    The annotations artifact declares `@LightBatisRow` to request a row reader for a
    class that never appears as a statement's `resultType` — one used only by the
    [escape hatch](raw-sql.md#the-escape-hatch). As of `0.1.0-SNAPSHOT` **the processor
    does not read it**. Until it lands, give the class one statement that returns it, or
    write the `RowReader` lambda by hand.

## Default methods

A `default` method on a mapper interface is left alone: it is compiled into the
interface like any other, and the generated implementation inherits it. This is where
hand-assembled SQL lives:

```java
default List<User> recent(LightBatisSession s, int limit) {
    return s.query(
            SqlFragment.unsafeRawSql(
                    "SELECT id, name, email, created_at FROM users"
                            + " ORDER BY created_at DESC LIMIT " + limit),
            ps -> { },
            UserRow.READER);
}
```

Note what stays type-safe even here: the rows are read by the **generated** `UserRow`
reader, so there is still no reflection and the result type is still checked by javac.
See [Raw SQL and SqlFragment](raw-sql.md).

## The generated registry

Every mapper in the compilation appears in one `LightBatisMappers` class:

```java
UserMapper mapper = LightBatisMappers.userMapper(session);
```

It is a static factory over a closed set known at compile time — there is no
`addMapper()` and no runtime registration, because there is nothing to register. Under
Spring you never touch it: the generated `@Configuration` declares the same
constructors as beans.

By default the registry lands in the common package prefix of all mappers; override with
`-Alightbatis.registryPackage=com.example.app`.
