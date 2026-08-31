# Types and Handlers

In MyBatis, type handling happens through a runtime registry: every query parameter and column triggers a HashMap lookup matching the Java and JDBC types. LarkBatis makes that decision at compile time and emits direct Java method calls. At runtime, all that remains is `JdbcCodec`—a tiny set of static helpers handling primitive conversions and null checks.

## Built-in types

The following types bind out of the box with `#{}` and map directly to result properties:

| Java Type | Read Operation | Write Operation |
|---|---|---|
| `String` | `rs.getString(i)` | `ps.setString(i, v)` |
| `long`, `int`, `short`, `byte`, `boolean`, `float`, `double` | `rs.getLong(i)` etc. | `ps.setLong(i, v)` etc. |
| `Long`, `Integer`, `Boolean`, … (wrappers) | `JdbcCodec.longOrNull(rs, i)` | `JdbcCodec.setLong(ps, i, v)` |
| `BigDecimal`, `BigInteger` | `rs.getBigDecimal(i)` | `ps.setBigDecimal(i, v)` |
| `byte[]` | `rs.getBytes(i)` | `ps.setBytes(i, v)` |
| `java.sql.Date`, `Time`, `Timestamp` | Direct JDBC call | Direct JDBC call |
| `Instant`, `LocalDate`, `LocalTime`, `LocalDateTime` | `JdbcCodec.instant(rs, i)` etc. | `JdbcCodec.setInstant(ps, i, v)` etc. |
| Java `enum` types | `JdbcCodec.enumValue(...)` | `JdbcCodec.setEnum(ps, i, v)` |

### Why boxed primitives use `JdbcCodec`

In JDBC, `rs.getLong(i)` returns `0` for SQL `NULL`. The wrapper methods handle nulls correctly:

```java
public static Long longOrNull(ResultSet rs, int column) throws SQLException {
    long v = rs.getLong(column);
    return rs.wasNull() ? null : v;
}
```

The choice between `rs.getLong(i)` and `JdbcCodec.longOrNull(rs, i)` is made at compile time based on your property type: primitive `long` gets direct reading; boxed `Long` gets null-safe handling.

On write operations, `JdbcCodec.setLong(ps, i, null)` calls `ps.setNull(i, Types.BIGINT)` with the correct SQL type constant.

## Enums

Enums are mapped to/from `name()` by default, with null safety handled automatically:

```java
public enum Status { NEW, PAID, SHIPPED }
```

```java
@Select("SELECT id, status, total FROM orders WHERE status = #{status}")
List<Order> byStatus(Status status);
```

Enums are **closed-value types**, making them safe to splice into `${}` expressions because the compiler knows all possible values at build time. See [Raw SQL](raw-sql.md#the-rule).

If you store enums as integer ordinals or custom database codes, write a [custom type handler](#custom-type-handlers).

## `java.time`

`Instant`, `LocalDate`, `LocalTime`, and `LocalDateTime` convert via `java.sql.Timestamp`, `Date`, and `Time`. `Instant` uses `Timestamp.toInstant()` and `Timestamp.from(...)`, representing absolute UTC points without depending on the host machine's timezone.

Zone-aware types (`ZonedDateTime`, `OffsetDateTime`) are intentionally not built-in because standard database columns don't carry timezone metadata. We recommend storing `Instant` in the database and converting to specific time zones in your application layer.

## Column naming conventions

Columns map to properties using `snake_case` → `camelCase` at build time: `created_at` maps to `setCreatedAt`. This is enabled by default. To preserve legacy MyBatis behavior, pass `-Alarkbatis.mapUnderscoreToCamelCase=false`. See [Configuration](../features/configuration.md#column-naming).

To override mapping for specific properties, use a `<resultMap>`:

```xml
<resultMap id="userMap" type="com.example.app.User">
  <id     property="id"    column="id"/>
  <result property="email" column="usr_email"/>
</resultMap>
```

Or annotate the Java property directly using `@Column`:

```java
public class User {

    @Column("usr_email")
    private String email;

    public void setEmail(String email) { this.email = email; }
}
```

You can put `@Column` on the field, getter, or setter. See [`@Column`](../features/annotations.md#column).

## Custom type handlers

For domain types not listed above (e.g. `Money`, JSON wrappers, or custom enums), write a `LarkBatisTypeHandler`:

```java
public class MoneyHandler implements LarkBatisTypeHandler<Money> {

    @Override
    public Money read(ResultSet rs, int column) throws SQLException {
        long cents = rs.getLong(column);
        return rs.wasNull() ? null : new Money(cents);
    }

    @Override
    public void write(PreparedStatement ps, int index, Money value) throws SQLException {
        if (value == null) {
            ps.setNull(index, Types.BIGINT);
        } else {
            ps.setLong(index, value.cents());
        }
    }
}
```

Requirements checked at compile time:

- **Must be public, concrete, stateless, with a public no-arg constructor.** Generated code stores singletons in `static final` fields.
- **Type argument must match the target property type.**
- **Handler manages its own null handling.**

### Declaring type handlers

On a property (field, getter, or setter):

```java
public class Wallet {

    @Handler(MoneyHandler.class)
    private Money balance;
}
```

On a mapper method parameter:

```java
@Select("SELECT id FROM wallet WHERE balance >= #{floor}")
List<Long> atLeast(@Handler(MoneyHandler.class) Money floor);
```

Or in mapper XML:

```xml
<resultMap id="entry" type="com.example.Entry">
    <id property="id" column="id"/>
    <result property="amount" column="amount" typeHandler="com.example.MoneyHandler"/>
</resultMap>

<insert id="insert">
    INSERT INTO ledger (id, amount)
    VALUES (#{id}, #{amount, typeHandler=com.example.MoneyHandler})
</insert>
```

### Global type handlers

To register a type handler globally across your entire project, configure `-Alarkbatis.typeHandlers=com.example.Money:com.example.MoneyHandler` during compilation. See [Configuration](../features/configuration.md#type-handlers-for-a-whole-build).

## Result class contract

The contract is simple: **a public no-arg constructor and standard setters**. No annotations, base classes, or runtime registrations needed. If a class uses Lombok, ensure the annotation processor order is correct in your build file. See [Troubleshooting](troubleshooting.md).
