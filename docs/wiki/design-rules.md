# Design Rules & Constraints

Here are the nine non-negotiable architectural rules that govern LarkBatis. Each rule exists for a specific technical reason: relaxing any of them breaks core guarantees.

---

### 1. Strict Shape vs. Value Separation

Only dynamic values are resolved at runtime: parameter arguments, evaluated `<if>` booleans, collection sizes in `<foreach>`, result rows, and `SqlFragment` contents. All structural decisions (query templates, parameter setters, column readers, type conversions) must be resolved at compile time.

**Why this matters**: Relaxing this boundary reintroduces runtime interpreters and reflection, destroying compile-time safety and GraalVM compatibility. See [Shape vs Value](shape-vs-value.md).

---

### 2. Zero Runtime Reflection

No `java.lang.reflect.Proxy`, no `Class.forName()`, and no `setAccessible()` in either `larkbatis-runtime` or generated code. `larkbatis-runtime` has zero dependencies beyond standard JDBC.

**Why this matters**: Eliminates the need for reflection configuration files in GraalVM native image builds and removes proxy invocation overhead.

---

### 3. Build Modules Never Leak to Runtime

`larkbatis-processor` and build plugins are strictly compile-time dependencies and must never be placed on an application's runtime classpath.

**Why this matters**: Prevents accidental runtime code generation or reliance on build-time AST manipulation at runtime.

---

### 4. Strict `${}` Dynamic SQL Discipline

`${}` parameter interpolation is strictly limited to `SqlFragment`, closed-value types (`int`, `long`, enums), or parameters annotated with `@OrderBy(allowed = {...})`. Binding a raw `String` parameter to `${}` is a **compile error**. Arbitrary dynamic SQL requires explicit `SqlFragment.unsafeRawSql(...)` wrapping, creating a single audit point searchable via `grep`.

**Why this matters**: Prevents SQL injection vulnerabilities by design and eliminates the need to manually audit every mapper query.

---

### 5. Type-Checked Test Grammar

`<if test="...">` conditions support null checks, statically-typed property comparisons, boolean methods, and logical operators (`and`, `or`, `not`). OGNL truthiness is deliberately rejected: `test="count"` and `test="user"` are compile errors requiring explicit comparisons like `count != 0` or `user != null`.

**Why this matters**: Replaces fragile runtime OGNL reflection with compile-time type verification.

---

### 6. Fast Positional Row Readers

When the compiler can parse a statement's `SELECT` column list, it hardcodes positional reads (`rs.getLong(1)`). If the query uses `SELECT *` or dynamic column splices, it falls back to name-based reads resolved once via `ResultSetMetaData` on the first row.

**Why this matters**: Avoids redundant string column name lookups for every single row and column.

---

### 7. Explicit Spring Connection Management

`LarkBatisSession.conn()` delegates connection checkout to Spring's `DataSourceUtils.getConnection(dataSource)`. Generated mapper methods never close connections directly in `try`-with-resources; they release connections via `s.release(c)` in a `finally` block.

**Why this matters**: Prevents breaking `@Transactional` boundaries. Generated mappers share the active transaction's connection without prematurely closing it.

---

### 8. Readable Generated Code

Generated code must be clean, readable, and easy to debug with breakpoints. `<if>` condition results are stored in local booleans (`boolean c0 = ...`) reused across both SQL string assembly and parameter binding loops.

**Why this matters**: Developers can step through generated mapper code in an IDE debugger just like hand-written JDBC.

---

### 9. Explicit Generated Key Columns

Always pass explicit column names to `prepareStatement(sql, String[])`. Omitting `keyColumn` triggers a compile warning because falling back to `RETURN_GENERATED_KEYS` behaves inconsistently across database drivers (Oracle returns `ROWID`, PostgreSQL returns all columns). Batch inserts must verify that returned key counts match inserted row counts.

**Why this matters**: Prevents silent data corruption and missing IDs when switching between database engines.

---

## Honest Answers to Common Objections

| Objection | Direct Answer |
|---|---|
| *"Tools like jOOQ, Micronaut Data, and Quarkus Panache already exist."* | Those tools require rewriting your queries into proprietary DSLs or method naming conventions. LarkBatis preserves your existing MyBatis XML mappers, SQL snippets, and dynamic tags without requiring an expensive rewrite. |
| *"Annotation processing increases compile times."* | Annotation processing moves interpretation cost from runtime startup to build time. Incremental compilation in Gradle and Maven ensures that only modified mappers are recompiled during daily development. |
| *"Modifying XML requires recompiling the project."* | In standard MyBatis, XML typos or type mismatches crash at runtime when queries are executed. LarkBatis catches these errors during compilation before your code even reaches a test environment. |
| *"Requiring `SqlFragment` forces touching raw `${}` call sites."* | Auditing raw string interpolation is the primary way to prevent SQL injection. The `larkbatis-scan` migration tool automatically flags or converts safe patterns. |
