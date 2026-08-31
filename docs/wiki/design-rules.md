# Design Red Lines

Nine rules that hold in every change to the project. They are listed here not as trivia
but because each one is load-bearing: relax it and something specific breaks.

---

### 1 · Shape vs value

Only these may be resolved at runtime: parameter values; `<if>`/`<when>` boolean results;
`<foreach>` collection size; ResultSet rows; the actual column count when the select list
could not be parsed; `SqlFragment` contents.

The rule as written also allows a `databaseId` chosen once at startup. Nothing implements
it — a `databaseId` attribute is a compile error — so the allowance is a reserved slot,
not a feature.

**If relaxed:** the list grows one plausible exception at a time until there is an
interpreter again. See [Shape vs Value](shape-vs-value.md).

---

### 2 · No runtime reflection

No `Proxy`, no `Class.forName` and no `setAccessible`, either in the runtime module or in
generated code. `larkbatis-runtime` keeps zero dependencies beyond JDBC.

**If relaxed:** GraalVM native image needs hand-written reachability metadata, which is
the single strongest reason the project exists.

---

### 3 · Build-only modules never reach the runtime classpath

`larkbatis-processor` and both build plugins are compile-time tools.

**If relaxed:** the generator becomes reachable at runtime, someone eventually calls it,
and rules 1 and 2 stop being checkable.

---

### 4 · The `${}` discipline

`${}` binds only to `SqlFragment`, closed-value types (`int`, `long`, `boolean`, enums), or
parameters annotated `@OrderBy(allowed = {...})`. A `String` signature is a **compile
error**. `SqlFragment.unsafeRawSql` is the single audit point for arbitrary SQL text, and
the manual escape hatch takes `SqlFragment` too, never `String`. Statements containing
`${}` get a generated `LarkBatisSql.trackVariants` call.

**If relaxed:** SQL injection review goes back to reading every mapper, and the one-`grep`
audit claim is gone.

---

### 5 · The expression grammar

`<if test>` accepts null checks, comparisons on statically-typed property paths,
`and`/`or`/`not`, `size()`/`length()`/`isEmpty()`, boolean-returning methods, and bare
booleans. MyBatis OGNL truthiness is deliberately not reproduced: `test="count"` and
`test="user"` are compile errors requiring `count != 0` / `user != null`.

**If relaxed:** OGNL comes back, and with it a runtime evaluator, a runtime type model,
and the ambiguity the grammar exists to reject.

---

### 6 · Row readers

Positional (`rs.getLong(1)`) when the generator can parse the select list; otherwise
name-based, with indexes resolved **once** from `ResultSetMetaData` on the first row. A
`${}` inside a select list downgrades that one statement to name-based, and the build says
so.

**If relaxed:** a name lookup per column per row, which is most of what was removed in the
first place.

---

### 7 · Spring: the connection contract

`LarkBatisSession.conn()` goes through `DataSourceUtils`, never
`dataSource.getConnection()`. Generated bodies must **not** put the `Connection` in
try-with-resources; they release via `s.release(c)` in `finally`. The generated
`@Configuration` uses `proxyBeanMethods = false`. Boot auto-config registers via
`META-INF/spring/…AutoConfiguration.imports`, not `spring.factories`.

**If relaxed:** `@Transactional` silently stops working: every mapper call opens its own
connection and commits independently, which looks fine until it does not.

---

### 8 · Generated code is a feature

Readable and breakpoint-able. One `$$Impl` per mapper, one row reader per result class,
`<if>` conditions evaluated once into locals (`boolean c0 = …`) reused for both SQL
assembly and parameter binding.

**If relaxed:** the debuggability argument goes away, and it is the benefit users report
valuing most day to day, above the microseconds.

---

### 9 · `useGeneratedKeys`

Always pass explicit key column names to `prepareStatement(sql, String[])`, because Oracle
returns `ROWID` and PostgreSQL returns all columns under `RETURN_GENERATED_KEYS`. Warn at
build time when `keyColumn` is missing. Verify the returned key count in batch mode.

**If relaxed:** code that works on H2 returns the wrong key in production, and a batch
insert silently leaves some rows with unset ids.

---

## How these are enforced

Not by convention:

- **`CompileFailTest`**: every "this is a compile error" promise has a test.
- **Golden snapshots**: generated output is committed and diffed, so shape rules (7, 8)
  cannot drift silently.
- **The hand-written emitter spec**: the target shape of generated code exists as
  compiling, tested Java that the emitters are measured against.
- **Differential tests**: generated SQL is compared against MyBatis's interpreted output
  for the same mapper, which is how rules 5 and 6 stay honest about semantics.
- **A dedicated code reviewer** for changes to the emitters and the runtime's public
  surface.

## The counterarguments, taken seriously

Four objections are worth answering directly:

| Objection | Answer |
|---|---|
| *"Micronaut Data, Quarkus Panache and jOOQ already exist."* | True, and that is the feasibility evidence. What none of them do is keep the MyBatis mapper model that thousands of codebases already run. The value is the migration path, not the idea |
| *"Build time will go up."* | Yes, and it is a real cost paid by developers daily, not by production. Mitigated by incremental processing. But it is moving the cost left, not deleting it |
| *"Changing SQL means rebuilding."* | The strongest objection, with no way around it. For teams used to editing XML and restarting, this is a genuine workflow change. The counter is that SQL with a type error already fails at runtime today; rebuilding trades that for javac catching it first |
| *"Requiring `SqlFragment` means touching every `${}` call site."* | True, and the cost is proportional to call sites rather than mappers. Mitigated by the scanner, which rewrites the mechanical cases. In exchange, that edit is the first time anyone looks at every raw-SQL splice in the codebase |

A fifth objection covers codegen bloating jars and IDEs: one impl and one reader per
mapper is a few thousand generated lines for 300 mapper methods, smaller than the 40,000
lines of framework it replaces.
