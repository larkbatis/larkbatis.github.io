# Types and Handlers

The MyBatis `TypeHandler` layer is a runtime registry: for every parameter and every
column, look up a handler by Java type and JDBC type, then call it. LightBatis makes
that choice at build time and inlines the result. What is left at runtime is
`JdbcCodec` — a handful of static helpers for the types whose natural JDBC accessor is
primitive or needs a conversion.

## What binds without help

`#{}` and result properties handle these directly:

| Java type | Read | Write |
|---|---|---|
| `String` | `rs.getString(i)` | `ps.setString(i, v)` |
| `long`, `int`, `short`, `byte`, `boolean`, `float`, `double` | `rs.getLong(i)` etc. | `ps.setLong(i, v)` etc. |
| `Long`, `Integer`, … (wrappers) | `JdbcCodec.longOrNull(rs, i)` | `JdbcCodec.setLong(ps, i, v)` |
| `BigDecimal`, `BigInteger` | `rs.getBigDecimal(i)` | `ps.setBigDecimal(i, v)` |
| `byte[]` | `rs.getBytes(i)` | `ps.setBytes(i, v)` |
| `java.sql.Date`, `Time`, `Timestamp` | direct | direct |
| `Instant`, `LocalDate`, `LocalTime`, `LocalDateTime` | `JdbcCodec.instant(rs, i)` etc. | `JdbcCodec.setInstant(ps, i, v)` etc. |
| Any `enum` | `JdbcCodec.enumValue(...)` | `JdbcCodec.setEnum(ps, i, v)` |

### Why wrappers go through `JdbcCodec`

`rs.getLong(i)` returns `0` for a SQL `NULL`. The wrapper helpers do what you actually
meant:

```java
public static Long longOrNull(ResultSet rs, int column) throws SQLException {
    long v = rs.getLong(column);
    return rs.wasNull() ? null : v;
}
```

The choice between `rs.getLong(i)` and `JdbcCodec.longOrNull(rs, i)` is made at build
time from the property's declared type. A `long` property gets the primitive read; a
`Long` property gets the null-aware one. Declaring the property nullable is how you ask
for null handling — there is no separate setting.

On the write side, `JdbcCodec.setLong(ps, i, null)` calls `ps.setNull(i, Types.BIGINT)`
with the right SQL type, which some drivers require.

## Enums

Enums map to their `name()` by default, in both directions, with `null` handled:

```java
public enum Status { NEW, PAID, SHIPPED }
```

```java
@Select("SELECT id, status, total FROM orders WHERE status = #{status}")
List<Order> byStatus(Status status);
```

An enum is also a **closed-value type**, so it is one of the few things that may be bound
to `${}` — its entire value space is known at build time. See
[Raw SQL](raw-sql.md#the-rule).

An enum stored as an ordinal or a custom code needs a custom handler, which is
not yet implemented — see below.

## `java.time`

`Instant`, `LocalDate`, `LocalTime` and `LocalDateTime` convert through
`java.sql.Timestamp` / `Date` / `Time`, which is what MyBatis's handlers do as well.
`Instant` uses `Timestamp.toInstant()` and `Timestamp.from(...)`, so the value is
absolute and the JVM default time zone does not enter into it.

Zone-carrying types (`ZonedDateTime`, `OffsetDateTime`) are not built in — a column has
no zone to carry, so the conversion needs a decision that belongs to your application.
Store `Instant`, and convert at the edge of the mapper.

## Column naming

Columns find properties by `snake_case` → `camelCase`, applied at build time, always:
`created_at` → `setCreatedAt`. There is no `mapUnderscoreToCamelCase` switch to turn off,
because there is no runtime to switch it in.

Where the convention is not enough, a `<resultMap>` names the column explicitly:

```xml
<resultMap id="userMap" type="com.example.app.User">
  <id     property="id"    column="id"/>
  <result property="email" column="usr_email"/>
</resultMap>
```

!!! warning "`@Column` is declared but not yet implemented"

    `io.github.lightbatis.annotations.Column` ships in the annotations artifact and is the
    reserved mechanism for naming a column on the property itself. As of
    `0.1.0-SNAPSHOT` **the processor does not read it** — putting it on a property has no
    effect. Use a `<resultMap>`, or alias the column in the select list:

    ```sql
    SELECT usr_email AS email FROM users
    ```

    A codebase that relied on `mapUnderscoreToCamelCase` being *off* needs one of those
    two, and the [migration scanner](../features/migration.md) reports the case.

## Custom type handlers

!!! warning "`@Handler` is declared but not yet implemented"

    `io.github.lightbatis.annotations.Handler` ships in the annotations artifact and
    reserves the design: a handler class named **explicitly** on the parameter or the
    property, called directly from generated code, with no registry and no discovery
    scan. As of `0.1.0-SNAPSHOT` **the processor does not read it**, and a mapper XML
    `typeHandler=` attribute is rejected with a message pointing here.

    Until it lands, convert at the edges of the mapper: expose the column as a type from
    the table above and map it in your own code, or use the
    [escape hatch](raw-sql.md#the-escape-hatch), where the `StatementBinder` and the
    `RowReader` are both yours to write.

What will *not* change when it lands: there is no handler discovery. Being explicit is
the trade — you lose "declare it once and it applies everywhere", and you gain a
generated call site that javac type-checks and you can navigate to in the IDE.

## Result classes, once more

The contract is small enough to restate: **a no-arg constructor and setters**. No base
class, no annotation, no registration, no `<constructor>` mapping. A class with neither a
no-arg constructor nor setters is a build error naming the class — and if it carries
Lombok annotations, the message says so, because that is nearly always a processor
ordering problem rather than a missing accessor. See
[Troubleshooting](troubleshooting.md).
