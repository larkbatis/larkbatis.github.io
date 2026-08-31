# Shape vs. Value

Every architectural decision in LarkBatis stems from a single design rule: separating the **static structure (shape)** of a query from the **dynamic values** passed at runtime.

The structure of a query—its SQL template, parameter types, column mappings, and target bean setters—is completely fixed the moment you write the code. Only dynamic values should be evaluated when the query executes.

## The Closed Runtime List

To prevent the gradual creep of runtime interpreters and reflection, LarkBatis strictly limits what may be evaluated at runtime to this closed list:

| Runtime Evaluation | Technical Reason |
|---|---|
| Method parameter **values** | Dynamic inputs provided by caller |
| Evaluated **boolean result** of `<if>` / `<when>` | Depends on runtime parameter values |
| Element **count** of `<foreach>` collections | Depends on collection size passed at runtime |
| Returned **data rows** from a `ResultSet` | Data returned by the database |
| Dynamic **column positions** for `SELECT *` | Only used when query columns cannot be parsed statically |
| Dynamic text in `SqlFragment` | Explicitly audited dynamic SQL fragments |

Everything else—parameter setter selection, property-to-column mappings, SQL inlining, and bean instantiation—is resolved at compile time during `javac`.

## What Compile-Time Resolution Replaces

| Compile-Time Resolution (LarkBatis) | Runtime Interpretation (MyBatis) |
|---|---|
| Hardcodes typed `ps.setXxx` calls | `TypeHandlerRegistry` map lookup per parameter |
| Hardcodes positional `rs.getXxx(index)` calls | Reflective `MetaObject.setValue()` per column per row |
| Hardcodes direct bean setter invocations | `Reflector` property name-to-method invocation lookup |
| Constant-folds `<where>` and `<set>` into booleans | Runtime substring scanning and string trimming |
| Inlines static `<include refid="...">` fragments | Runtime XML DOM tree node resolution |
| Compiles `<if test="...">` to plain Java booleans | Runtime OGNL expression parsing and reflection |
| Generates concrete `Mapper$$Impl` classes | `Proxy.newProxyInstance()` dynamic JDK proxies |

## Practical Architectural Benefits

- **Compile-Time Type Safety**: Referencing a non-existent parameter like `#{customerName}` fails compilation with a clear error pointing to the method. In standard MyBatis, this only fails at runtime when that specific query executes.
- **Zero GraalVM Native Image Metadata**: Without `Proxy`, `Class.forName()`, or `setAccessible()`, there is no reflection reachability configuration to write or maintain.
- **Guaranteed No-Reflection Architecture**: Because there is no runtime reflection engine, new features cannot accidentally introduce runtime reflection overhead.

## Where the Boundary Requires Trade-offs

Being honest about architectural trade-offs:

1. **`<foreach>` Parameter Counts**: Because collection size is only known at runtime, dynamic query strings must be assembled for `<foreach>` queries. LarkBatis compiles this into efficient loops and provides `@PadPow2` to bound statement cache variants.
2. **`SELECT *` Queries**: If column names cannot be parsed at compile time, LarkBatis resolves column indexes once from `ResultSetMetaData` on the first row, then reads subsequent rows positionally.
3. **Dynamic Identifiers via `${}`**: When table or column names must vary dynamically, LarkBatis enforces type-safe validation using `@OrderBy(allowed = {...})` or audited `SqlFragment` wrappers.

## The Guiding Rule for New Features

When evaluating any proposed feature, we ask a single question: *Does this feature require runtime information not on the closed list?*

- **If No**: It must be resolved at compile time.
- **If Yes**: The feature is either modeled as an explicit `SqlFragment` or rejected with a compile error pointing to a safer alternative.
