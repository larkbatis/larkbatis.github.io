---
hide:
  - navigation
---

# LarkBatis

**An ahead-of-time MyBatis.** The SQL text, the parameter positions, the type-handler
choices, the column-to-setter mapping, the dynamic-SQL tree: everything derivable from the
*shape* of a mapper is resolved at build time by a code generator. What ships at runtime is
generated plain-Java mapper implementations plus a thin JDBC layer, roughly 1,500 lines with
no dependencies beyond JDBC, no reflection, no proxies and no OGNL.

You keep the MyBatis programming model you already have: mapper interfaces, `#{}`
parameters, mapper XML, `<if>`/`<where>`/`<foreach>`, `<resultMap>`. What you lose is the
interpreter underneath it.

```java
public interface UserMapper {

    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);
}
```

The build emits `UserMapper$$Impl`, and it is code you can read and set a breakpoint in:

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

    Install the annotations, the runtime and the annotation processor, then write your
    first mapper.

-   :material-book-open-variant: **[Usage](usage/index.md)**

    Mapper interfaces, mapper XML, dynamic SQL, `<foreach>`, result maps, generated
    keys, streams, transactions.

-   :material-sitemap: **[Wiki](wiki/index.md)**

    How the two-phase architecture works, what the generated code looks like, and why
    each design line is drawn where it is.

-   :material-checkbox-multiple-marked: **[Features](features/index.md)**

    The support matrix: what LarkBatis does, what it narrows, and what it drops on
    purpose.

</div>

## Why

MyBatis resolves a mapper call at runtime. Every query goes through a JDK proxy, an OGNL
evaluation of every `<if test>`, and a `TypeHandler` lookup per parameter. Then comes the
expensive part: one reflective `setValue` per column per row, each allocating a
`PropertyTokenizer` and an `Object[]` before it reaches what is really a `putfield`.

None of that depends on the values. It depends on the *shape* of the mapper, which is fixed
the moment you save the file. LarkBatis resolves the shape once, at build time, and emits
the JDBC calls directly.

| | MyBatis | LarkBatis |
|---|---|---|
| Lines on the runtime classpath | ~40,000 | ~1,500 |
| Runtime dependencies | ognl, javassist | none beyond JDBC |
| Reflection on the hot query path | 4 groups of call sites | none |
| Reflective operations per row | 1 per column | none |
| Hand-written `native-image` metadata | required | none needed[^1] |
| Wrong parameter type caught at | runtime | compile time |
| Auditing raw SQL splices | read every mapper | one `grep` for `unsafeRawSql` |

[^1]: Structural: there is no reflection to declare. A native-image build has not been run
    yet; see [Performance](wiki/performance.md#native-image).

The performance case is real but narrow, and it is worth being blunt about where it
applies. Measured against MyBatis 3.5.19 on JDK 21, reading 10,000 rows of 12 columns goes
from **3.38 ms and 10.2 MB of allocation to 0.54 ms and 1.88 MB**. Per row, 338 ns and
1,018 B become 54 ns and 188 B. Cold start to the first row drops from 61.8 ms to 6.3 ms.

The other half was measured over a real socket rather than assumed. A `findById` returning
one row costs **94.2 µs on MyBatis and 89.2 µs on LarkBatis**: five percent, over loopback
TCP, which is the cheapest round trip there is. A real database only shrinks the
difference. **LarkBatis pays for reporting queries, exports, batches and list screens. It
changes almost nothing for single-record lookups.** [Performance](wiki/performance.md) has
the full tables, the method, and the two places the design's predictions turned out wrong.

## What it costs

Three honest trade-offs, in the order teams actually hit them:

1. **Changing SQL means rebuilding.** If your workflow is "edit mapper XML, restart", this
   is a real change to how you work. What you get back is javac catching the type errors
   that used to surface as a runtime exception.
2. **Build time moves left.** Generation is not free. Developers pay for it on every build
   instead of production paying on every query.
3. **`${}` call sites have to change.** A `String` parameter bound to `${}` is a compile
   error. It becomes a [`SqlFragment`](usage/raw-sql.md), a closed-value type, or an
   `@OrderBy(allowed = {...})` switch. That migration is the first time anyone actually
   looks at every raw-SQL splice in the codebase.

## Status

`0.1.0-SNAPSHOT`, and not yet published to Maven Central. Milestones M1 through M4 are
implemented: the runtime core, the annotation processor, mapper XML with dynamic tags,
`<foreach>` and batches, one-level join result maps, `Stream` returns, transactions, both
build plugins, JPMS descriptors and the Spring integration. M5 has landed the
[benchmark suite](wiki/performance.md) and the [migration scanner](features/migration.md).
The native-image smoke test is still not run, for want of a GraalVM install. See the
[Roadmap](features/roadmap.md).
