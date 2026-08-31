# Annotations

Everything in `io.github.larkbatis.annotations`. All of them are `CLASS`-retention: they
exist for the compiler and never appear at runtime, which is why a modular consumer
declares the artifact `requires static`.

## Statement annotations

### `@Select` `@Insert` `@Update` `@Delete`

```java
@Retention(CLASS) @Target(METHOD)
public @interface Select { String[] value(); }
```

`String[]`, joined with a single space. Applied to a mapper method.

```java
@Select({
    "SELECT id, name, email, created_at",
    "FROM users",
    "WHERE email = #{email}"
})
User findByEmail(String email);
```

A method may have **either** a statement annotation **or** an XML statement. Both, or
neither, is a compile error.

---

## `@Mapper`

```java
@Retention(CLASS) @Target(TYPE)
public @interface Mapper { }
```

Marks an interface whose statements (or some of them) live in mapper XML. The XML file's
`<mapper namespace="…">` must be this interface's fully-qualified name, and each statement
`id` must match a method name.

Purely annotation-based mappers do **not** need it: the marker exists so the processor can
see XML-only interfaces at all, which would otherwise never reach a processing round.

---

## `@Param`

```java
@Retention(CLASS) @Target(PARAMETER)
public @interface Param { String value(); }
```

Names a parameter for `#{}` resolution. Required when a method has several parameters,
and a reliable substitute for compiling with `-parameters`.

```java
@Select("SELECT id, name FROM users WHERE name LIKE #{pattern} AND id > #{after}")
List<User> page(@Param("pattern") String pattern, @Param("after") long after);
```

---

## `@Options`

```java
@Retention(CLASS) @Target(METHOD)
public @interface Options {
    boolean useGeneratedKeys() default false;
    String keyProperty() default "";
    String keyColumn() default "";
}
```

Only the generated-keys subset of the MyBatis annotation is supported.

| Attribute | |
|---|---|
| `useGeneratedKeys` | Ask the driver for generated keys after an `INSERT` |
| `keyProperty` | Property (or `param.property`) the key is assigned to. **Required** when `useGeneratedKeys` is set; a wrong name is a compile error. Comma-separated for composite keys |
| `keyColumn` | Column name(s) of the key, comma-separated. Strongly recommended: omitting it produces a **mandatory build warning** and falls back to the non-portable `RETURN_GENERATED_KEYS`. See [Generated Keys](../usage/generated-keys.md) |

If both are comma-separated, the two lists must be the same length.

```java
@Insert("INSERT INTO users (name, email) VALUES (#{name}, #{email})")
@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
int insert(User u);
```

[Details](../usage/generated-keys.md)

---

## `@OrderBy`

```java
@Retention(CLASS) @Target(PARAMETER)
public @interface OrderBy { String[] allowed(); }
```

Permits a `String` parameter to be bound to `${}`, by compiling it to a `switch` over the
literal allow-list. A value outside the list is rejected at runtime with
`LarkBatisRejectedException` and never reaches the SQL text.

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY ${sort}")
List<User> all(@OrderBy(allowed = {"id", "name", "created_at"}) String sort);
```

Without it, a `String` parameter bound to `${}` is a compile error.
[Details](../usage/raw-sql.md)

---

## `@PadPow2`

```java
@Retention(CLASS) @Target({TYPE, METHOD})
public @interface PadPow2 { }
```

Pads a `<foreach>` placeholder count up to the next power of two, repeating the last
element, which bounds SQL-text variants at log₂(n) instead of n. Hibernate calls the same
trick `in_clause_parameter_padding`.

On an interface it applies to every statement; on a method, to that one.

!!! warning "Enforced, not trusted"

    Repeating the last element is invisible only in an `IN` list. The generator requires
    the `<foreach>` body to be a single `#{}` bind and the statement not to be an
    `INSERT`. Outside those limits padding is a **compile error**, never silently
    duplicated rows.

[Details](../usage/foreach-and-batches.md#padpow2-bounding-the-sql-variants)

---

## `@Column`

```java
@Retention(CLASS) @Target({FIELD, METHOD})
public @interface Column { String value(); }
```

Names the column a result property reads from, where the build-time `snake_case` →
`camelCase` convention is not enough: a legacy name the property should not be bent to,
or one that has no relation to the property name at all.

```java
public class Contact {

    @Column("contact_id")
    private long id;
    private String email;
    private String phone;

    @Column("usr_email")
    public void setEmail(String email) { this.email = email; }

    @Column("mobile")
    public String getPhone() { return phone; }

    // ...
}
```

Read on the **field, the setter and the getter**: the annotation targets `FIELD` and
`METHOD` both, and the site you pick is the site that is read. Two of them naming
different columns for one property is a compile error, because there is no correct way to
pick between them.

The name replaces the property name everywhere a column is matched: the positional reader
when the select list parses, and the name-based `switch` when it does not. Matching stays
case-insensitive, and underscores are ignored on both sides by default, so
`@Column("usr_email")` also matches a `USR_EMAIL` or `usrEmail` label. Under
[`-Alarkbatis.mapUnderscoreToCamelCase=false`](configuration.md#column-naming) the
underscores are significant: the same annotation then matches `USR_EMAIL` but not
`usrEmail`, which is also what makes `@Column` the way to keep one column mapped in a
build that turned the convention off.

!!! warning "One column, one property"

    Two properties resolving to the same column is a compile error naming both, and that
    includes a `@Column` colliding with another property's own name. The generated
    reader switches on that name, so there is no reading that could be right.

A `<resultMap>` still wins where it applies: it names columns per statement, which is
more specific than a class-wide default.

---

## `@LarkBatisRow`

```java
@Retention(CLASS) @Target(TYPE)
public @interface LarkBatisRow { }
```

Asks for a generated row reader for a class that never appears as a statement's
`resultType`: the shape of an ad-hoc query, read only by the
[escape hatch](../usage/raw-sql.md#the-escape-hatch).

```java
@LarkBatisRow
public class DomainCount {
    private String domain;
    private long total;
    // no-arg constructor + setters, as for any result class
}
```

```java
default List<DomainCount> countByDomain(LarkBatisSession s, int minimum) {
    return s.query(
            SqlFragment.unsafeRawSql("SELECT ... GROUP BY domain HAVING COUNT(*) >= ?"),
            ps -> ps.setInt(1, minimum),
            DomainCountRow.READER);   // generated because of the annotation
}
```

The same reasoning keeps `s.query(...)` taking a `RowReader<T>` instead of a `Class<T>`.
A `Class` there would have to be inspected at runtime to find setters, costing the
no-reflection property the whole design rests on. The reader is generated, so javac
checks the result type and there is nothing to discover at startup.

The class has the same contract as any result class: no-arg constructor and setters. Its
**declaration order is the canonical column order** of `READER`, there being no select
list to take an order from. Hand-assembled SQL either selects the columns in that order,
or reads through `DomainCountRow.columns(rs)` and `DomainCountRow.read(rs, c)`, which
match on name.

Marking a class that a statement already returns is harmless: one reader is generated
either way.

---

## `@Handler`

```java
@Retention(CLASS) @Target({PARAMETER, FIELD, METHOD})
public @interface Handler { Class<?> value(); }
```

Names the `LarkBatisTypeHandler` that moves one parameter or one result property: named
explicitly, called directly from generated code, with no registry lookup and no discovery
scan. It also lifts the [type whitelist](../usage/types.md) for the value it moves, which
is usually the reason to reach for it.

For a type that always moves the same way, registering it once for the whole build with
[`-Alarkbatis.typeHandlers`](configuration.md#type-handlers-for-a-whole-build) says the
same thing without an annotation per site. This annotation still wins wherever it
appears.

```java
public class Wallet {

    @Handler(MoneyHandler.class)
    private Money balance;
}

@Select("SELECT id FROM wallet WHERE balance >= #{floor}")
List<Long> atLeast(@Handler(MoneyHandler.class) Money floor);
```

Read on the **field, the setter and the getter**, as `@Column` is, and two of them naming
different handlers is a compile error. A mapper XML `typeHandler=` attribute names the
same thing and is read the same way; the two must agree.

The handler class has to be public and concrete, with a public no-argument constructor,
and stateless, because one instance is shared. See
[custom type handlers](../usage/types.md#custom-type-handlers) for the full contract.

!!! note "Why `Class<?>` and not `Class<? extends LarkBatisTypeHandler<?>>`"

    Bounding it would make `larkbatis-annotations` depend on `larkbatis-runtime`, and
    that artifact has no dependencies, which is what lets you declare it
    `requires static`. The processor makes the check javac would have made, and gets to
    say *why* a handler was rejected while it is at it.
