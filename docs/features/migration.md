# Migrating from MyBatis

The migration path is the point of the project, and it is what LarkBatis has that Micronaut
Data and jOOQ do not. So the tooling for it is treated as being as important as the
generator itself.

## Start with a scan

`larkbatis-scan` points at an existing MyBatis codebase and prints what migrating it
would cost, with file and line numbers. It compiles nothing and resolves no dependencies,
so it runs against a checkout of a service nobody has built yet, which is when the
question "would this even work for us" actually gets asked.

```console
$ ./gradlew :larkbatis-scanner:installDist
$ ./build/install/larkbatis-scanner/bin/larkbatis-scan /path/to/legacy-service
```

```text
larkbatis-scan — what would it cost to move this codebase to LarkBatis

usage: larkbatis-scan [options] <path>...

  --summary            counts only, no per-line detail
  --min=LEVEL          detail level: BLOCKER, EDIT, REVIEW, INFO (default REVIEW)
  --limit=N            most findings listed per file (default 40)
  --out=FILE           also write the report to FILE
  --fail-on-blocker    exit 1 when anything is blocked on a dropped feature
```

Nothing is rewritten. The report is the deliverable, and the edits are yours to make.

### It uses the real frontend

The scanner depends on `larkbatis-processor` and runs **the same grammar checker and the
same XML parser** the build will run. So a scan report cannot drift away from what
actually compiles. Line positions are found by text scanning, because no parser returns a
trustworthy position for a `${}` in the middle of a text node.

### Four severities

Ordered by how much human judgement a finding needs, because the first question about a
300-mapper codebase is not "how many problems" but "how many do I have to think about".

| | Meaning |
|---|---|
| **BLOCKER** | No LarkBatis equivalent; the design dropped it. The mapper changes |
| **EDIT** | A rewrite with a known shape. The tool can say exactly what to write |
| **REVIEW** | Supported, but only after someone decides how |
| **INFO** | Compiles as-is; worth knowing before it surprises someone |

### The unit of the answer is the statement

Not the file, and not the finding. One `<bind>` in a 90-statement mapper must not condemn
the other 89, and "1,113 findings" is not something anyone can act on. A sentence like
*"N of M statements compile unchanged"* is what decides a migration proposal.

The report also prints **concentration**, not just counts: how many files the findings
live in, and the five files holding the most. In the MyBatis source tree's own mapper
corpus, 1,003 of 1,006 grammar rejections are in three files, and 1,000 of those in a
single generated fixture. Without an "in N files" column that reads as a codebase-wide
wall when it is nothing of the kind.

## What the scanner looks for

| Finding | Severity | Fix |
|---|---|---|
| `${}` splice | EDIT | Declare the parameter as `SqlFragment`, a closed-value type, or `@OrderBy(allowed={...})`. A `String` at the call site becomes `SqlFragment.identifier(x)` |
| `${}` inside a select list | REVIEW | That statement falls back to name-based row reads. Decide whether the column list can be made static |
| `test=` outside the grammar | EDIT | Rewrite it, or move the decision into Java |
| OGNL truthiness (`test="count"`) | EDIT | `count != 0`, `user != null`, `list.isEmpty()` |
| `Map` or `Object` parameter | BLOCKER | A parameter object, or `@Param` arguments |
| `@SelectProvider` family | BLOCKER | Move the SQL into the mapper, or use the escape hatch |
| Plugin / interceptor | BLOCKER | Paging, auditing and soft-delete plugins become explicit SQL or a decorator |
| Lazy loading | BLOCKER | Fetch eagerly with a join, or split into two statements |
| Nested `select=` in a result mapping | BLOCKER | Express it as a join |
| Result map nested deeper than one level | BLOCKER | Assemble in Java from two statements |
| Result map `extends` | BLOCKER | Write the mappings out |
| `<discriminator>` | BLOCKER | Separate statements with separate result types |
| `<constructor>` result | BLOCKER | No-arg constructor and setters |
| `<bind>` | BLOCKER | Compute in Java, pass as a parameter |
| `<parameterMap>` | BLOCKER | `#{}` with typed parameters |
| Second-level cache | BLOCKER | Cache above the mapper, where invalidation is visible |
| `RowBounds` | BLOCKER | `LIMIT` / `OFFSET` as real parameters |
| `statementType` other than `PREPARED` | BLOCKER | Stored-procedure calls go through the escape hatch |
| `objectFactory` / `objectWrapperFactory` | BLOCKER | Hooks into a reflection layer that is gone |
| `<include>` with a computed `refid` | BLOCKER | `refid` must be literal |
| `<selectKey>` | REVIEW | `useGeneratedKeys` with explicit `keyProperty`/`keyColumn`, or a statement of its own |
| Custom `TypeHandler` | REVIEW | Mapper XML `typeHandler=` is read as-is; rewrite the handler class against `LarkBatisTypeHandler` |
| `<script>` in an annotation | REVIEW | Read, but the same grammar rules apply, so check the tests it contains |
| Direct `SqlSession` use | REVIEW | Call the mapper, or use `session.query(SqlFragment, binder, GeneratedRow.READER)` |
| `mapUnderscoreToCamelCase` is off | REVIEW | LarkBatis applies it at build time, always. Affected columns need `@Column` on the property, or a `<resultMap>` |
| More than one environment / `DataSource` | REVIEW | One `DataSource` per build for now |
| `<foreach>` | INFO | Supported; counted because it is what makes a statement's SQL-variant count grow |
| Dynamic statement | INFO | Compiles to boolean locals and a `StringBuilder` |

## A suggested order

1. **Scan, and read the concentration column first.** If the blockers live in three files,
   the answer to "can we do this" is different from what the raw count suggests.
2. **Start with one mapper, not one module.** A mapper is the unit that compiles.
3. **Fix processor ordering before anything else** if the project uses Lombok: declare
   `larkbatis-processor` *after* it. This is the single most common first-day failure,
   and it presents as "the result class has no accessors", which sounds like a different
   problem entirely.
4. **Do the `${}` call sites next.** They are EDIT-severity and mechanical, and finishing
   them is the first time anyone has looked at every raw-SQL splice in the codebase.
5. **Then the `test=` expressions.** Mostly truthiness: `count` → `count != 0`. Check the
   [null-comparison divergence](mybatis-differences.md#behavioural-divergences-to-check-when-migrating)
   while you are in there, because that one does not produce a compile error.
6. **Leave the blockers for a design conversation.** Each has a named replacement, but the
   replacement is a decision, not a rewrite.
7. **Run your existing test suite.** That is the real acceptance criterion.

## Field notes

A trial migration of a real internal service was run on a copy as an exit
criterion, and its whole test suite passed. Two defects surfaced that no unit test had
found: the **Lombok processor-ordering** problem, and the **Spring Boot 4
auto-configuration** package rename, the latter being a failure with no symptom until the
context refuses to start. Both are now fixed and both are covered by tests.

What has *not* been completed is the other half of that criterion: running the migrated
service in a real environment for a week.

## What will change in your workflow

Three things, and it is better to agree on them before starting than to discover them:

- **Editing SQL means rebuilding.** For a team used to editing mapper XML and restarting,
  this is a genuine change. What you get back is javac catching the type errors that used
  to surface at runtime.
- **Build time goes up.** Real, and paid by developers daily instead of by production per
  query. It is moving the cost left, not deleting it.
- **`${}` call sites change.** Proportional to call sites, not to mappers. The scanner
  handles the mechanical shape of the edit.

For the honest version of what you get in return, see
[Performance](../wiki/performance.md), particularly the part about single-record lookups.
