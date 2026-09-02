# Quick Start

Here is how to go from an empty project to a working mapper in five minutes using plain JDBC—no Spring, no XML. Everything here comes straight from the `larkbatis-sample` module in the core repository.

## 1 · A result class

An ordinary Java bean with a no-arg constructor and standard getters/setters. No base class, no special annotations, and no interfaces to implement:

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

Column names map to properties using `snake_case` → `camelCase`, and this happens **at build time**, every time. `created_at` matches `setCreatedAt`. If that convention doesn't fit, alias the column in your SQL or define a [`<resultMap>`](../usage/result-maps.md).

## 2 · A mapper interface

```java title="UserMapper.java"
package com.example.app;

import io.github.larkbatis.annotations.Insert;
import io.github.larkbatis.annotations.Options;
import io.github.larkbatis.annotations.Param;
import io.github.larkbatis.annotations.Select;
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

You don't need a `@Mapper` annotation here: the processor picks up any interface with statement annotations on its own. `@Mapper` is only needed when an interface has all its statements in [mapper XML](../usage/xml-mappers.md), since javac wouldn't otherwise pass it to the processor.

## 3 · Compile

```console
$ ./gradlew compileJava
```

Three source files are generated next to your code in the same package:

| Generated | What it is |
|---|---|
| `UserMapper$$Impl` | The implementation. Plain JDBC, one method per statement |
| `UserRow` | Row reader for `User`. One per result class, shared by every query returning it |
| `LarkBatisMappers` | Static factory for all mappers in the compilation |

These are real Java source files, and stepping through them in your IDE is encouraged. See [Generated Code](../wiki/generated-code.md).

!!! tip "If nothing is generated"

    Check that `larkbatis-processor` is configured under `annotationProcessor` (not `implementation`), and make sure you are compiling with javac. See [Troubleshooting](../usage/troubleshooting.md).

## 4 · Wire it up and run

`LarkBatisSession` is the only dependency a generated mapper needs: it borrows a `Connection`, returns it, and translates SQLExceptions. The standalone version takes a `DataSource`:

```java title="SampleApp.java"
package com.example.app;

import io.github.larkbatis.runtime.JdbcLarkBatisSession;
import io.github.larkbatis.runtime.LarkBatisTx;
import java.time.Instant;
import javax.sql.DataSource;

public class SampleApp {

    public static void main(String[] args) {
        DataSource ds = /* HikariCP, H2, or whatever pool you use */;

        JdbcLarkBatisSession session = new JdbcLarkBatisSession(ds);
        UserMapper mapper = LarkBatisMappers.userMapper(session);

        User u = new User();
        u.setName("Ada");
        u.setEmail("ada@example.com");
        u.setCreatedAt(Instant.now());

        try (LarkBatisTx tx = session.begin()) {
            mapper.insert(u);
            tx.commit();
        }

        System.out.println(u.getId());              // populated by useGeneratedKeys
        System.out.println(mapper.findById(u.getId()));
        System.out.println(mapper.countByName("A%"));
    }
}
```

`session.begin()` opens a transaction scope designed for try-with-resources. Calling `commit()` is a **vote**: the real commit happens when the outermost block closes. If any scope exits without voting to commit, the whole transaction rolls back. See [Transactions](../usage/transactions.md).

## 5 · Inspect what was generated

Open `UserMapper$$Impl.java` in your IDE. The SQL statement is a `static final String` where `#{}` has been replaced with `?`, parameters are bound by index, and rows are read positionally because the generator parsed the column list:

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

Every column index and getter/setter call was determined at build time. Nothing here inspects types at runtime, resolves property names, or looks up registries.

!!! note "Why Connection is not in try-with-resources"

    Only `s.release(c)` knows whether the connection can actually be closed. If you're inside an active transaction (Spring or LarkBatis), the connection belongs to that transaction and closing it would break it. See [Transactions](../usage/transactions.md#why-generated-code-never-closes-the-connection) for details.

## Next steps

- Statements with optional filters → [Dynamic SQL](../usage/dynamic-sql.md)
- `WHERE id IN (...)` and batch inserts → [foreach and Batches](../usage/foreach-and-batches.md)
- Joining parent and child entities → [Result Maps and Joins](../usage/result-maps.md)
- Large result sets without memory bloat → [Streaming Results](../usage/streaming.md)
- Using Spring Boot instead of `main()` → [Spring Boot](../spring/spring-boot.md)
