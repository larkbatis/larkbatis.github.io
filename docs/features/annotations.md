# Annotations

Everything in `io.github.lightbatis.annotations`. All of them are `CLASS`-retention: they
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

A method may have **either** a statement annotation **or** an XML statement — both, or
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
| `keyColumn` | Column name(s) of the key, comma-separated. Strongly recommended — omitting it produces a **mandatory build warning** and falls back to `RETURN_GENERATED_KEYS`, which returns `ROWID` on Oracle and every column on PostgreSQL |

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
`LightBatisRejectedException` and never reaches the SQL text.

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
element — bounding SQL-text variants at log₂(n) instead of n. Hibernate calls the same
trick `in_clause_parameter_padding`.

On an interface it applies to every statement; on a method, to that one.

!!! warning "Enforced, not trusted"

    Repeating the last element is invisible only in an `IN` list. The generator requires
    the `<foreach>` body to be a single `#{}` bind and the statement not to be an
    `INSERT` — otherwise padding is a **compile error** rather than silently duplicated
    rows.

[Details](../usage/foreach-and-batches.md#padpow2-bounding-the-sql-variants)

---

## Declared but not yet implemented

These three ship in the annotations artifact and reserve their design, but the processor
does **not** read them as of `0.1.0-SNAPSHOT`. Applying one has no effect.

### `@Column`

```java
@Retention(CLASS) @Target({FIELD, METHOD})
public @interface Column { String value(); }
```

Intended to override the column a result property maps to, where the build-time
`snake_case` → `camelCase` convention is not enough.

**Today:** use a `<resultMap>`, or alias the column in the select list
(`SELECT usr_email AS email`).

### `@Handler`

```java
@Retention(CLASS) @Target({PARAMETER, FIELD, METHOD})
public @interface Handler { Class<?> value(); }
```

Intended to select a custom type handler for one parameter or one result property — named
explicitly, called directly from generated code, with no registry lookup and no discovery
scan. A mapper XML `typeHandler=` attribute is rejected with a message pointing at this
annotation.

**Today:** convert at the edge of the mapper, or use the
[escape hatch](../usage/raw-sql.md#the-escape-hatch), where the binder and the reader are
both yours.

### `@LightBatisRow`

```java
@Retention(CLASS) @Target(TYPE)
public @interface LightBatisRow { }
```

Intended to request a generated row reader for a class that never appears as a statement's
`resultType` — typically one used only by the escape hatch.

**Today:** give the class one statement that returns it, or write the `RowReader` lambda
by hand.
