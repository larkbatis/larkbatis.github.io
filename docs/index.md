---
hide:
  - navigation
---

# LarkBatis

# LarkBatis

**An ahead-of-time MyBatis.** SQL text, parameter positions, type handlers, column-to-setter mappings, and dynamic SQL trees: everything about a mapper's *shape* is resolved at build time. What ships at runtime is plain generated Java mapper code plus a thin JDBC layer—roughly 1,500 lines with zero extra dependencies, no reflection, no proxies, and no OGNL.

You keep the MyBatis programming model you already know: mapper interfaces, `#{}` parameters, mapper XML, `<if>`/`<where>`/`<foreach>`, and `<resultMap>`. What you lose is the runtime interpreter underneath.

```java
public interface UserMapper {

    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);
}
```

The build emits `UserMapper$$Impl`, and it's plain Java you can read, debug, and set breakpoints in:

```java
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

<div class="grid cards" markdown>

-   :material-rocket-launch: **[Getting Started](getting-started/index.md)**

    Add the dependencies, configure the annotation processor, and write your first mapper.

-   :material-book-open-variant: **[Usage](usage/index.md)**

    Mapper interfaces, mapper XML, dynamic SQL, `<foreach>`, result maps, generated keys, streams, and transactions.

-   :material-sitemap: **[Wiki](wiki/index.md)**

    How the two-phase build works, what the generated code looks like, and why we drew each architectural line where we did.

-   :material-checkbox-multiple-marked: **[Features](features/index.md)**

    Support matrix: what LarkBatis supports, what it restricts, and what it drops on purpose.

</div>

## Why

MyBatis resolves mapper calls at runtime. Every query goes through a JDK dynamic proxy, evaluates OGNL for each `<if test>`, and looks up a `TypeHandler` for every parameter. Then comes the expensive part: reflective `setValue` calls for each column in every row, allocating a `PropertyTokenizer` and an `Object[]` before finally doing what is fundamentally a `putfield`.

None of that actually depends on runtime values. It depends on the *shape* of the mapper, which is fixed the moment you write the code. LarkBatis resolves that shape once at compile time and emits direct JDBC calls.

| | MyBatis | LarkBatis |
|---|---|---|
| Lines on runtime classpath | ~40,000 | ~1,500 |
| Runtime dependencies | ognl, javassist | None beyond JDBC |
| Reflection on hot query path | 4 groups of call sites | None |
| Reflective operations per row | 1 per column | None |
| Hand-written `native-image` metadata | Required | None needed[^1] |
| Parameter type mismatches caught at | Runtime | Compile time |
| Auditing raw SQL splices | Read every mapper | A single `grep` for `unsafeRawSql` |

[^1]: Structural: there is no reflection to declare. An actual native-image build has not been run yet; see [Performance](wiki/performance.md#native-image).

Let's be upfront about performance: the gains are real, but they apply where you have rows to process. Measured against MyBatis 3.5.19 on JDK 21, reading 10,000 rows with 12 columns drops from **3.38 ms and 10.2 MB of allocations to 0.54 ms and 1.88 MB**. Per row, that's 338 ns and 1,018 B down to 54 ns and 188 B. Cold start to first row drops from 61.8 ms to 6.3 ms.

We also measured over a real network socket. A single-row `findById` lookup costs **94.2 µs on MyBatis and 89.2 µs on LarkBatis**—about a 5% difference over loopback TCP (the fastest round trip there is). Over a real network to a remote database, that difference shrinks even further. **LarkBatis pays off on reporting queries, data exports, batches, and list views. It won't noticeably speed up single-record lookups.** See [Performance](wiki/performance.md) for full benchmarks and methodology.

## Honest Trade-offs

Here are the three real trade-offs you'll hit:

1. **Changing SQL requires recompilation.** If your current workflow relies on editing mapper XML and immediately restarting without compiling, this changes how you work. In return, javac catches SQL type errors before they reach production.
2. **Build times increase slightly.** Code generation isn't free. You pay that small compile-time cost up front instead of paying reflection overhead on every query in production.
3. **`${}` call sites need updates.** Binding a raw `String` parameter to `${}` is a compile error. You'll need to wrap it in [`SqlFragment`](usage/raw-sql.md), use an enum/closed-value type, or add an `@OrderBy(allowed = {...})` allowlist. Migrating these is usually the first time a team actually audits every dynamic SQL splice in their codebase.


