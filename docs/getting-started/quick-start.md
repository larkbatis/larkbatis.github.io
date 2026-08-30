# Quick Start

Five minutes from an empty project to a working mapper. This is the plain-JDBC path —
no Spring, no XML. Everything here comes from the `lightbatis-sample` module of the
core repository, which is also the native-image smoke-test subject.

## 1 · A result class

An ordinary Java bean: a no-arg constructor and setters. There is no base class, no
annotation, and no interface to implement.

```java title="User.java"
package com.example.app;

import java.time.Instant;

public class User {

    private long id;
    private String name;
    private String email;
    private Instant createdAt;

    public long getId() { return id; }
    public void setId(long id) { this.id = id; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
```

Column names map to properties with `snake_case` → `camelCase` applied **at build
time**, always. `created_at` finds `setCreatedAt`. Where that convention is not enough, alias the
column in the select list or declare a [`<resultMap>`](../usage/result-maps.md).

## 2 · A mapper interface

```java title="UserMapper.java"
package com.example.app;

import io.github.lightbatis.annotations.Insert;
import io.github.lightbatis.annotations.Options;
import io.github.lightbatis.annotations.Param;
import io.github.lightbatis.annotations.Select;
import java.util.List;

public interface UserMapper {

    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);

    @Select("SELECT id, name, email, created_at FROM users ORDER BY id")
    List<User> findAll();

    @Select("SELECT COUNT(*) FROM users WHERE name LIKE #{pattern}")
    long countByName(@Param("pattern") String pattern);

    @Insert("INSERT INTO users (name, email, created_at) VALUES (#{name}, #{email}, #{createdAt})")
    @Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
    int insert(User u);
}
```

No `@Mapper` marker is needed: an interface with statement annotations is found by the
processor on its own. The marker exists for interfaces whose statements live entirely in
[mapper XML](../usage/xml-mappers.md), which would otherwise never reach a processing
round.

## 3 · Compile

```console
$ ./gradlew compileJava
```

Three files appear next to your sources, in the same package:

| Generated | What it is |
|---|---|
| `UserMapper$$Impl` | The implementation. Plain JDBC, one method per statement |
| `UserRow` | The row reader for `User`. One per result class, shared by every statement returning it |
| `LightBatisMappers` | A static factory for every mapper in the compilation |

They are real source files, and reading them is part of the design — see
[Generated Code](../wiki/generated-code.md).

!!! tip "If nothing is generated"

    Check that `lightbatis-processor` is on `annotationProcessor` (not `implementation`),
    and that you are compiling with javac. See [Troubleshooting](../usage/troubleshooting.md).

## 4 · Wire it up and run

`LightBatisSession` is the only thing a generated mapper needs: a way to borrow a
`Connection`, a way to give it back, and exception translation. The standalone
implementation takes a `DataSource`.

```java title="SampleApp.java"
package com.example.app;

import io.github.lightbatis.runtime.JdbcLightBatisSession;
import io.github.lightbatis.runtime.LightBatisTx;
import java.time.Instant;
import javax.sql.DataSource;

public class SampleApp {

    public static void main(String[] args) {
        DataSource ds = /* HikariCP, H2, whatever you already use */;

        JdbcLightBatisSession session = new JdbcLightBatisSession(ds);
        UserMapper mapper = LightBatisMappers.userMapper(session);

        User u = new User();
        u.setName("Ada");
        u.setEmail("ada@example.com");
        u.setCreatedAt(Instant.now());

        try (LightBatisTx tx = session.begin()) {
            mapper.insert(u);
            tx.commit();
        }

        System.out.println(u.getId());              // filled in by useGeneratedKeys
        System.out.println(mapper.findById(u.getId()));
        System.out.println(mapper.countByName("A%"));
    }
}
```

`session.begin()` opens a transaction scope meant for try-with-resources. `commit()` is
a **vote**: the actual commit happens when the outermost scope closes, and leaving any
scope without voting marks the whole transaction rollback-only. See
[Transactions](../usage/transactions.md).

## 5 · Read what was generated

Open `UserMapper$$Impl.java` in your IDE. The SQL is a `static final String` with `?`
where `#{}` was, the parameters are bound in order, and the row is read positionally
because the generator could parse the select list:

```java
private static final String SQL_findById =
        "SELECT id, name, email, created_at FROM users WHERE id = ?";

@Override
public User findById(long id) {
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(SQL_findById)) {
        ps.setLong(1, id);
        try (ResultSet rs = ps.executeQuery()) {
            return rs.next() ? UserRow.read(rs) : null;
        }
    } catch (SQLException e) {
        throw s.translate(e, SQL_findById);
    } finally {
        s.release(c);
    }
}
```

```java title="UserRow.java (excerpt)"
public static User read(ResultSet rs) throws SQLException {
    User u = new User();
    u.setId(rs.getLong(1));
    u.setName(rs.getString(2));
    u.setEmail(rs.getString(3));
    u.setCreatedAt(JdbcCodec.instant(rs, 4));
    return u;
}
```

Every column index and every accessor was chosen at build time. Nothing here inspects a
type, resolves a property name or consults a registry.

!!! note "The Connection is not in try-with-resources — on purpose"

    Only `s.release(c)` knows whether the connection may really be closed. Under a
    managed transaction (Spring's or LightBatis's own) it belongs to the transaction and
    closing it would be wrong. This shape is a
    [design red line](../wiki/design-rules.md), not an oversight.

## Where to go next

- Statements with optional filters → [Dynamic SQL](../usage/dynamic-sql.md)
- `WHERE id IN (...)` and batch inserts → [foreach and Batches](../usage/foreach-and-batches.md)
- Joining a parent and its children → [Result Maps and Joins](../usage/result-maps.md)
- A result set too big for a `List` → [Streaming Results](../usage/streaming.md)
- Spring Boot instead of `main()` → [Spring Boot](spring-boot.md)
