# Types and Handlers

The MyBatis `TypeHandler` layer is a runtime registry: for every parameter and every
column, look up a handler by Java type and JDBC type, then call it. LarkBatis makes
that choice at build time and inlines the result. What is left at runtime is
`JdbcCodec`, a handful of static helpers for the types whose natural JDBC accessor is
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
for null handling. No separate setting exists.

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
to `${}`, because its entire value space is known at build time. See
[Raw SQL](raw-sql.md#the-rule).

An enum stored as an ordinal or a custom code needs a [custom handler](#custom-type-handlers).

## `java.time`

`Instant`, `LocalDate`, `LocalTime` and `LocalDateTime` convert through
`java.sql.Timestamp` / `Date` / `Time`, which is what MyBatis's handlers do as well.
`Instant` uses `Timestamp.toInstant()` and `Timestamp.from(...)`, so the value is
absolute and the JVM default time zone does not enter into it.

Zone-carrying types (`ZonedDateTime`, `OffsetDateTime`) are not built in. A column has no
zone to carry, so the conversion needs a decision that belongs to your application.
Store `Instant`, and convert at the edge of the mapper.

## Column naming

Columns find properties by `snake_case` → `camelCase`, applied at build time:
`created_at` → `setCreatedAt`. It is on by default — MyBatis defaults it off — and
`-Alarkbatis.mapUnderscoreToCamelCase=false` carries that default across. The choice is
baked into the generated reader; there is no runtime setting either way. See
[Configuration](../features/configuration.md#column-naming).

Where the convention is not enough, a `<resultMap>` names the column explicitly:

```xml
<resultMap id="userMap" type="com.example.app.User">
  <id     property="id"    column="id"/>
  <result property="email" column="usr_email"/>
</resultMap>
```

Or `@Column` names it on the property itself, once, for every statement:

```java
public class User {

    @Column("usr_email")
    private String email;

    public void setEmail(String email) { this.email = email; }
}
```

The annotation is read on the **field, the setter or the getter**, whichever site you
put it on. Two of them naming different columns for one property is a compile error, and
so is two properties landing on the same column. See
[`@Column`](../features/annotations.md#column).

A codebase that relied on `mapUnderscoreToCamelCase` being *off* either carries the
setting across or gives the affected columns `@Column` or a `<resultMap>`; the
[migration scanner](../features/migration.md) reports the case either way.

## Custom type handlers

Types the table above does not cover (your own `Money`, a JSON column, an enum stored as
an ordinal) move through a handler you write:

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

Three rules, all checked during `javac`:

- **Public, concrete, public no-arg constructor, and stateless.** Generated code holds
  one instance in a `static final` field and shares it. A handler that needs
  construction arguments is a handler that is not stateless; use the
  [escape hatch](raw-sql.md#the-escape-hatch) instead.
- **The type argument is the value's own type**, not a supertype. `read` has to return
  something the setter accepts.
- **The handler owns `null`** in both directions. There is no `jdbcType` to fall back
  on, so a handler that wants `setNull` calls it itself.

### Naming it

Three sites, all read at build time.

On the property, meaning the field, the setter or the getter, as with `@Column`:

```java
public class Wallet {

    @Handler(MoneyHandler.class)
    private Money balance;
}
```

On a mapper parameter:

```java
@Select("SELECT id FROM wallet WHERE balance >= #{floor}")
List<Long> atLeast(@Handler(MoneyHandler.class) Money floor);
```

Or in mapper XML, which is the form a migrated MyBatis mapper already carries, where the
bean needs no annotation at all:

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

A handler also lifts the type whitelist for the value it moves: `Money` is not in the
table above, and these compile anyway.

### What is still not there

**No discovery.** No `@MappedTypes` scan, no package scan, no `(Type, JdbcType)` lookup.
"Declare it once and it applies everywhere" is available, but written out rather than
found: `-Alarkbatis.typeHandlers=com.example.Money:com.example.MoneyHandler` registers a
default handler per Java type for the whole build, checked during `javac`. See
[Configuration](../features/configuration.md#type-handlers-for-a-whole-build). What you
get either way is a generated call site that javac type-checks and you can navigate to in
the IDE.

**One reading per result class.** One row reader is generated per class, so a property
has one handler. Two statements naming different handlers for the same property is a
build error, because two readings would mean two result classes.

**Not on a mapper method.** `@Handler` on the method itself is rejected: a scalar result
reads column 1 and has no property to hang a handler on. Return a bean, or use the
escape hatch.

## Result classes, once more

The contract is small enough to restate: **a no-arg constructor and setters**. No base
class, no annotation, no registration, no `<constructor>` mapping. A class with neither a
no-arg constructor nor setters is a build error naming the class. If it carries Lombok
annotations, the message says so, because the cause is nearly always processor ordering
and not a missing accessor. See
[Troubleshooting](troubleshooting.md).
