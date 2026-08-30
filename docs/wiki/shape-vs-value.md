# Shape vs Value

Every design decision in LightBatis follows from one cut. On one side: everything
derivable from the **shape** of a mapper, which stopped changing when you saved the file.
On the other: the **values** that flow through a call at runtime.

The shape side is resolved at build time. The value side is the only thing left.

## The closed list

This is the whole of what may be resolved at runtime. It is a closed list on purpose — an
open one would quietly grow back into an interpreter.

| Resolved at runtime | Why it has to be |
|---|---|
| Parameter **values** | They are the input |
| The **boolean result** of an `<if>` / `<when>` test | It depends on parameter values |
| The **size** of a `<foreach>` collection | It depends on parameter values |
| The **rows** in a `ResultSet` | The database produced them |
| The **actual column count**, when the generator could not parse the select list | `SELECT *` has no static answer |
| The **contents** of a `SqlFragment` | It is the deliberate escape hatch, and it is audited |
| `databaseId` | Chosen once at startup |

Everything else happens at build time. Not "usually", not "when possible" — everything.

## What that buys, item by item

| Decided at build time | What MyBatis does at runtime instead |
|---|---|
| Which `ps.setXxx` binds each parameter | `TypeHandlerRegistry` lookup by Java type and JDBC type |
| Which column index feeds each setter | Reflective `MetaObject.setValue(propertyName, value)` per column per row |
| Which setter that even is | `Reflector` builds a name → `Invoker` map per class |
| Whether `<where>` emits its keyword | A runtime scan of the assembled fragment for a leading `AND`/`OR` |
| What `<include refid>` expands to | Resolved from a `Configuration` map |
| The Java expression for each `test` | OGNL parses and evaluates against an `ObjectWrapper` |
| Which class implements the mapper | `Proxy.newProxyInstance` + `MapperMethod` dispatch |

## The consequences you actually feel

**Type errors move to compile time.** A `#{customerName}` that does not exist on the
parameter type is a build error naming the method. In MyBatis it is a runtime
`ReflectionException` on the unlucky code path.

**There is no metadata to write for native image.** No `Proxy`, no `Class.forName`, no
`setAccessible` — so nothing to declare. This is a *consequence* of the cut, not a feature
that was added.

**Reflection cannot be reintroduced accidentally.** There is no runtime that could do it.
A feature request that needs runtime type inspection has no place to put it, which is why
the [dropped feature list](../features/mybatis-differences.md) is what it is.

**Some MyBatis features become impossible rather than unimplemented.** That distinction
matters when reading the dropped list. `<discriminator>` chooses a result class from a
column value — the *shape* of the result depends on a runtime value, so it is on the wrong
side of the cut by construction. Lazy loading needs a proxy per result object. Plugins
hook a runtime pipeline that does not exist. None of these are "not yet".

## Where the cut is uncomfortable

Three places, and it is worth being honest that they are trade-offs rather than free wins.

**1 · `<foreach>` cardinality.** The number of placeholders genuinely is a runtime value,
so the SQL text is assembled at runtime for those statements. LightBatis compiles the loop
rather than interpreting a tree, but the text still varies — which is why those statements
get variant tracking and why `@PadPow2` exists.

**2 · `SELECT *`.** The column count is not knowable at build time. That one statement
falls back to name-based reads resolved from `ResultSetMetaData` on the first row. Correct,
slower, and reported at build time so it is a decision.

**3 · `${}`.** Sometimes an identifier really does come from configuration. Rather than
banning it, the cut is enforced at the type level: only `SqlFragment`, closed-value types,
or `@OrderBy(allowed = {...})` may be spliced, and arbitrary text has exactly one named
entry point.

## The test for any new feature

Before adding anything, the question is: *does this need a runtime value that is not on
the list?*

- **No** → it belongs at build time, and the design question is only what the generated
  code should look like.
- **Yes** → either the list grows, which requires a very good reason, or the feature is
  dropped with a compile error naming the replacement.

Read the [dropped feature list](../features/mybatis-differences.md) with that question in
hand and it stops looking arbitrary.
