# Dynamic SQL

`<if>`, `<choose>`, `<where>`, `<set>` and `<trim>` all work, and none of them survives
to runtime as a tree. The generator folds the tag structure into condition locals and
guarded appends; the only thing evaluated at runtime is each `test` expression, once.

## What it compiles to

```xml
<select id="search" resultType="com.example.app.User">
  SELECT id, name, email, created_at FROM users
  <where>
    <if test="name != null">AND name LIKE #{name}</if>
    <if test="minAge != null">AND age &gt;= #{minAge}</if>
  </where>
  ORDER BY id
</select>
```

```java
@Override
public List<User> search(UserQuery q) {
    boolean c0 = q.getName() != null;          // (1)!
    boolean c1 = q.getMinAge() != null;
    StringBuilder sb = new StringBuilder(96);  // (2)!
    sb.append("SELECT id, name, email, created_at FROM users");
    if (c0 | c1) {
        sb.append(" WHERE");                   // (3)!
    }
    if (c0) {
        sb.append(" name LIKE ?");
    }
    if (c1) {
        sb.append(c0 ? " AND age >= ?" : " age >= ?");   // (4)!
    }
    sb.append(" ORDER BY id");
    String sql = sb.toString();
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(sql)) {
        int i = 1;
        if (c0) {
            ps.setString(i++, q.getName());    // (5)!
        }
        if (c1) {
            JdbcCodec.setInt(ps, i++, q.getMinAge());
        }
        // ... read rows
    }
}
```

1.  Each `test` is evaluated **once**, into a local. The same local drives both SQL
    assembly and parameter binding, so the two can never disagree.
2.  The capacity is computed at build time from the longest possible text.
3.  `<where>` becomes a guarded literal, not a runtime string scan for a leading
    `AND`/`OR`.
4.  This is the `<where>` leading-conjunction rule, constant-folded: the first branch
    that fires emits no `AND`. It is a ternary over already-computed locals, not a
    substring search.
5.  Binding walks the same conditions in the same order. There is no parameter-name map
    in between.

## `<if>`

```xml
<if test="email != null">AND email = #{email}</if>
```

Anything inside is appended when the condition holds. Nesting works; siblings work; an
`<if>` inside a `<foreach>` body works.

## `<choose>` / `<when>` / `<otherwise>`

Exactly one branch fires, and the mutual exclusion is compiled in:

```xml
<choose>
  <when test="status != null">AND status = #{status}</when>
  <otherwise>AND status = 'NEW'</otherwise>
</choose>
```

```java
boolean c0 = q.getStatus() != null;
boolean c1 = !c0;                       // <otherwise> is the negation of the disjunction
```

## `<where>` and `<set>`

`<where>` emits the keyword only if the body contributed something, and strips the
leading `AND`/`OR` of whichever branch fired first. `<set>` does the same for `SET` and
a trailing comma:

```xml
<update id="rename">
  UPDATE users
  <set>
    <if test="name != null">name = #{name},</if>
    <if test="email != null">email = #{email},</if>
  </set>
  WHERE id = #{id}
</update>
```

```java
if (c0 | c1) sb.append(" SET");
if (c0) sb.append(c1 ? " name = ?," : " name = ?");
if (c1) sb.append(" email = ?");
sb.append(" WHERE id = ?");
```

Notice there is no trailing-comma trimming at runtime: the generator knows which branch
is last for each combination and emits the comma only where a later branch will follow.

## `<trim>`

Supported with **literal attributes** (`prefix`, `suffix`, `prefixOverrides`,
`suffixOverrides`), which are constant-folded at build time. That is what makes `<where>`
and `<set>` compile to the code above; they are `<trim>` with fixed attributes.

## The `test` grammar

Compatibility with MyBatis stops here, and only here. `test` is **not** OGNL. It is a narrow
grammar, type-checked against the mapper method's parameters:

| Accepted | Example |
|---|---|
| Null checks | `name != null`, `probe.email == null` |
| Comparisons on typed property paths | `age >= 18`, `status == 'NEW'`, `id != other.id` |
| Boolean operators | `and`, `or`, `not`, parentheses |
| Size and emptiness | `ids.size() > 0`, `name.length() > 3`, `!ids.isEmpty()` |
| Boolean-returning methods | `user.isActive()` |
| Bare booleans | `active`, where `active` really is a `boolean`/`Boolean` property |

Anything else is a **compile error naming the offending token**.

!!! failure "OGNL truthiness is not reproduced"

    ```xml
    <if test="count">      <!-- compile error -->
    <if test="user">       <!-- compile error -->
    ```

    MyBatis treats a non-null, non-zero, non-empty value as true. LarkBatis refuses to
    guess which of those you meant. Write `count != 0`, `user != null`, or
    `!list.isEmpty()`.

    This is not pedantry: `test="count"` in a MyBatis codebase is genuinely ambiguous
    between "count is set" and "count is non-zero", and the two differ exactly where it
    matters.

### Null semantics, fixed and documented

OGNL coerces; the grammar does not. The rules are stated once and hold everywhere:

| Expression | LarkBatis | MyBatis / OGNL |
|---|---|---|
| `a == null` / `a != null` | Null-propagating over every reference step of the path, same as OGNL's null-safe navigation | Same |
| `age <= 18` when `age` is null | **`false`**, because a null anywhere along either operand makes the comparison false | `true`, null coerces to zero |
| `a != b` | Exactly `!(a == b)` | Same |
| `user.isActive()` when `user` is null | **`false`** | Throws |

The second row is the one to check when migrating. A `null <= 18` that silently meant
"true" in MyBatis becomes "false" here, and that is a deliberate divergence: null-as-zero
is the same ambiguity the grammar rejects for truthiness. The
[migration scanner](../features/migration.md) flags the tests it cannot decide.

## Dynamic SQL and statement caches

A statement whose text depends on runtime conditions produces more than one SQL string.
The count is bounded: with *n* independent `<if>`s the ceiling is 2ⁿ texts, known at
build time. What is *not* bounded is a `${}` splice or a `<foreach>` whose cardinality
varies, so those statements get a `LarkBatisSql.trackVariants` call. See
[Raw SQL](raw-sql.md#tracking-sql-variants).

## Verifying against MyBatis

The core repository carries a differential test harness: the same mapper is run through
MyBatis's interpreted path and through the generated code against a recording
`DataSource`, and the resulting SQL text and parameter bindings are compared. There is
also a sweep over the mapper XML corpus in the MyBatis source tree, which is how the
grammar's coverage was measured, not guessed.
