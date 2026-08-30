# Architecture

Two phases and one intermediate representation. Everything in the build phase is thrown
away before the application runs; everything in the runtime phase is code you can read.

```mermaid
flowchart LR
    subgraph build["Build time — nothing ships"]
        A["Mapper interface<br/>@Select / @Insert"] --> F
        B["Mapper XML<br/>&lt;select&gt; &lt;if&gt; &lt;foreach&gt;"] --> F
        F["Frontend<br/>parse · type-check · fold"] --> IR["MapperModel<br/>(IR)"]
        IR --> E["Emitters<br/>JavaPoet"]
    end
    subgraph run["Runtime — ~1,500 lines, zero deps"]
        E --> G1["UserMapper$$Impl"]
        E --> G2["UserRow"]
        E --> G3["LarkBatisMappers"]
        E --> G4["LarkBatisMapperConfiguration"]
        G1 --> RT["larkbatis-runtime<br/>LarkBatisSession · JdbcCodec · SqlFragment"]
        RT --> JDBC[("JDBC driver")]
    end
```

## The repositories

Four independent repositories, because they have different lifecycles and different
answers to "does this reach an application's runtime classpath".

| Repository | Modules | Scope |
|---|---|---|
| `larkbatis` | `larkbatis-annotations` | runtime: annotations only, no logic |
| | `larkbatis-runtime` | runtime: zero dependencies beyond JDBC |
| | `larkbatis-processor` | **build-only**: the generator |
| `larkbatis-gradle-plugin` | | build-only: plugin id `io.github.larkbatis` |
| `larkbatis-maven-plugin` | | build-only: same job for Maven |
| `larkbatis-spring` | `larkbatis-spring`, `-spring-boot-autoconfigure`, `-spring-boot-starter` | runtime: transactions, Boot auto-config |

The rule that keeps this honest: **build-only modules must never leak onto an
application's runtime classpath.** The generator is a compile-time tool; if it can be
reached at runtime, someone will eventually reach for it, and the design's central claim
stops being checkable.

## The build phase

### Frontend

Two frontends, one output. The annotation path runs as a plain
`javax.annotation.processing.Processor`. The XML path parses mapper files handed to it as
directory paths by the build plugin. Both produce the same IR. One set of emitters, one
set of semantics, and no second code path to drift.

The frontend does all the work that "resolving the shape" means:

- parse the SQL text, turning `#{}` into positional binds and `${}` into checked splices
- resolve every `#{}` name against the method's parameter types, walking property paths
- parse the select list, when it parses, to fix column positions
- choose the read and write helper for every value from its declared Java type
- compile every `<if test>` into a Java boolean expression, or reject it
- constant-fold `<where>`, `<set>`, `<trim>` into guarded literal appends
- inline `<sql>`/`<include>`
- lower `<foreach>` into a placeholder loop and a binding loop

Anything it cannot decide is a compile error naming the mapper method, never a runtime
fallback.

### The IR

`MapperModel` is the boundary. It carries statements, parameters, result shapes, dynamic
nodes, key models and reader access strategies, and its shape follows neither frontend.
Golden snapshots of the IR are part of the test suite, so a frontend change that alters
meaning shows up as an IR diff before it becomes a generated-code diff.

### Emitters

JavaPoet, one emitter per artefact:

| Emitter | Output |
|---|---|
| `MapperImplEmitter` | `UserMapper$$Impl`, one per mapper |
| `RowReaderEmitter` | `UserRow`, one per result class |
| `RegistryEmitter` | `LarkBatisMappers`, one per compilation |
| `SpringConfigurationEmitter` | `LarkBatisMapperConfiguration`, when spring-context is on the build classpath |

The registry emitter is why the processor is **aggregating**: it needs every mapper in the
compilation to write one complete registry. The same requirement is what breaks Maven
builds under `useIncrementalCompilation=false`, where recompiling only stale sources would
regenerate the registry from a partial view.

## The runtime phase

`larkbatis-runtime` is small enough to list:

| Type | Job |
|---|---|
| `LarkBatisSession` | Borrow a `Connection`, give it back, translate exceptions. The whole environment a generated mapper needs |
| `JdbcLarkBatisSession` | The standalone implementation, plus `LarkBatisTx` |
| `SpringLarkBatisSession` | The Spring one: `DataSourceUtils` instead of `dataSource.getConnection()` |
| `JdbcCodec` | Null-aware and converting read/write helpers. The inlined remains of the `TypeHandler` layer |
| `SqlFragment` | The one gate arbitrary SQL text passes through |
| `LarkBatisSql` | Static helpers referenced by generated code: `trackVariants`, `padPow2`, `sum` |
| `RowReader`, `StatementBinder` | Two functional interfaces the escape hatch takes |
| `ResultSetStream` | Cursor-backed `Stream` with resource ownership |
| `LarkBatisException` + subclasses | The unchecked exception tree |

Nothing in that list inspects a type, resolves a name, or consults a registry. That all
happened at build time.

## Why a build-tool plugin exists at all

The processor cannot reach mapper XML through `Filer.getResource`, so it takes a directory
path as an option and something has to supply that path. Both build plugins exist for that
one job. Neither generates code; all generation stays inside javac.
[Build Plugins](../getting-started/build-plugins.md) has the full reasoning.

## Verification strategy

Three layers, because "the generated code compiles" proves very little:

1. **A hand-written emitter spec.** Before the emitters existed, the target shape of
   generated code was written out by hand as compiling, tested Java. The emitters are
   measured against it.
2. **Golden snapshots.** Generated output for a corpus of mappers is committed and
   diffed. An intended emitter change is a reviewed diff, not an invisible one.
3. **Differential tests.** The same mapper runs through MyBatis's interpreted path and
   through the generated code against a recording `DataSource`; the SQL text and the
   parameter bindings are compared. A sweep over the mapper XML corpus in the MyBatis
   source tree is how the expression grammar's real-world coverage was measured rather
   than guessed.

Plus a `CompileFailTest` for every "this is a compile error" promise the documentation
makes, including the ones on this site.
