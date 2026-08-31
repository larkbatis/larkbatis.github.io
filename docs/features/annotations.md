# Annotations

Here is the complete reference for annotations in `io.github.larkbatis.annotations`. All annotations use `CLASS` retention: they are read by the compiler during build time and discarded from bytecode at runtime. Modular projects can declare them via `requires static io.github.larkbatis.annotations;`.

## Statement Annotations

### `@Select`, `@Insert`, `@Update`, `@Delete`

```java
@Retention(CLASS) @Target(METHOD)
public @interface Select { String[] value(); }
```

Accepts `String[]` (lines are joined with a single space). Applied directly to mapper methods:

```java
@Select({
    "SELECT id, name, email, created_at",
    "FROM users",
    "WHERE email = #{email}"
})
User findByEmail(String email);
```

Each method must define its SQL using **either** an annotation **or** XML. Having both or neither is a compile error.

---

## `@Mapper`

```java
@Retention(CLASS) @Target(TYPE)
public @interface Mapper { }
```

Marks an interface whose statements are defined in mapper XML. The XML file's `namespace` must match the interface's fully-qualified class name, and statement `id`s must match method names.

Purely annotation-based mappers do **not** need `@Mapper`: javac discovers them automatically from their `@Select`/`@Insert` annotations.

---

## `@Param`

```java
@Retention(CLASS) @Target(PARAMETER)
public @interface Param { String value(); }
```

Names a method parameter for `#{}` binding. Required when a method has multiple parameters unless compiled with the javac `-parameters` flag.

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

Configures primary key retrieval after an `INSERT` statement:

| Attribute | Description |
|---|---|
| `useGeneratedKeys` | Set to `true` to retrieve database-generated keys |
| `keyProperty` | Target property on parameter object (e.g. `"id"` or `"user.id"`). **Required** when `useGeneratedKeys` is `true` |
| `keyColumn` | Database column name(s). Strongly recommended for consistent driver behavior. See [Generated Keys](../usage/generated-keys.md) |

For composite keys, provide matching comma-separated lists:

```java
@Insert("INSERT INTO users (name, email) VALUES (#{name}, #{email})")
@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
int insert(User u);
```

---

## `@OrderBy`

```java
@Retention(CLASS) @Target(PARAMETER)
public @interface OrderBy { String[] allowed(); }
```

Allows a `String` parameter to be safely spliced into dynamic `${}` SQL clauses by validating it against a static whitelist at runtime via a generated `switch` statement. Inputs outside the allowed list throw `LarkBatisRejectedException`.

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY ${sort}")
List<User> all(@OrderBy(allowed = {"id", "name", "created_at"}) String sort);
```

Without `@OrderBy`, binding a plain `String` to `${}` fails compilation. See [Raw SQL](../usage/raw-sql.md).

---

## `@PadPow2`

```java
@Retention(CLASS) @Target({TYPE, METHOD})
public @interface PadPow2 { }
```

Rounds `<foreach>` placeholder counts in `IN` clauses up to the next power of two by repeating the last element, bounding dynamic SQL statement variants to $\log_2(N)$ instead of $N$.

Can be applied at the interface level or on individual methods:

```java
@PadPow2
List<User> findByIdsPadded(List<Long> ids);
```

!!! warning "Restricted to `IN` clauses"

    Repeating parameters is only valid when duplicate elements don't affect query semantics. The compiler enforces that `@PadPow2` is only used on `SELECT`/`UPDATE`/`DELETE` statements with simple single-item `#{}` binds, and rejects its use on `INSERT` queries.

---

## `@Column`

```java
@Retention(CLASS) @Target({FIELD, METHOD})
public @interface Column { String value(); }
```

Overrides the default `snake_case` → `camelCase` column mapping for a specific field or accessor:

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
}
```

Can be placed on fields, getters, or setters. (Placing conflicting `@Column` names on the same property is a compile error).

---

## `@LarkBatisRow`

```java
@Retention(CLASS) @Target(TYPE)
public @interface LarkBatisRow { }
```

Generates a static `RowReader` for classes used exclusively in custom escape-hatch queries rather than standard mapper return types:

```java
@LarkBatisRow
public class DomainCount {
    private String domain;
    private long total;
    // standard getters and setters
}
```

```java
default List<DomainCount> countByDomain(LarkBatisSession s, int minimum) {
    return s.query(
            SqlFragment.unsafeRawSql("SELECT ... GROUP BY domain HAVING COUNT(*) >= ?"),
            ps -> ps.setInt(1, minimum),
            DomainCountRow.READER);   // generated via @LarkBatisRow
}
```

---

## `@Handler`

```java
@Retention(CLASS) @Target({PARAMETER, FIELD, METHOD})
public @interface Handler { Class<?> value(); }
```

Specifies a custom `LarkBatisTypeHandler` for a specific parameter, field, getter, or setter. Generated code calls the handler directly without runtime registry lookups.

```java
public class Wallet {

    @Handler(MoneyHandler.class)
    private Money balance;
}

@Select("SELECT id FROM wallet WHERE balance >= #{floor}")
List<Long> atLeast(@Handler(MoneyHandler.class) Money floor);
```

See [Custom Type Handlers](../usage/types.md#custom-type-handlers) for implementation details.
