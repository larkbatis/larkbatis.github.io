# Java Modules (JPMS)

`lightbatis-annotations` and `lightbatis-runtime` ship **real named modules**, not
automatic ones, and so do the three Spring artifacts. Generated mapper code is usable
from a modular consumer, and the module path stays free of split packages. This is a
design requirement of the project, not a nice-to-have.

| Artifact | Module name |
|---|---|
| `lightbatis-annotations` | `io.github.lightbatis.annotations` |
| `lightbatis-runtime` | `io.github.lightbatis.runtime` |
| `lightbatis-spring` | `io.github.lightbatis.spring` |
| `lightbatis-spring-boot-autoconfigure` | `io.github.lightbatis.spring.boot` |
| `lightbatis-spring-boot-starter` | `io.github.lightbatis.spring.boot.starter` |

`lightbatis-processor` is build-only and never appears on a module path.

## The consumer descriptor

Three directives, and the third is the one that surprises people:

```java title="module-info.java"
module com.example.app {
    requires io.github.lightbatis.runtime;             // (1)!
    requires static io.github.lightbatis.annotations;  // (2)!
    requires static java.compiler;                     // (3)!
}
```

1.  What the generated bodies actually call: `LightBatisSession`, `JdbcCodec`,
    `RowReader`, `LightBatisSql`.
2.  Every mapper annotation is `CLASS`-retention, so this is a compile-time-only edge.
3.  Every emitted source carries `@javax.annotation.processing.Generated`, which lives in
    `java.compiler`. `SOURCE` retention makes it `static`.

!!! failure "`package javax.annotation.processing is not visible`"

    This is what you get without `requires static java.compiler`, and the error points at
    the **generated** file, which is why it is confusing the first time. Add the
    directive.

## What you do *not* need

- **`requires java.sql`** — `io.github.lightbatis.runtime` requires it *transitively*,
  because its own API hands you `Connection`, `ResultSet` and `PreparedStatement`. A
  module that reads the runtime can already name those types.
- **`opens`, anywhere** — neither LightBatis module ever needs it. There is no reflection
  to open anything for.
- **an `exports` for generated code** — it lands in your own package, alongside the
  mapper interface it implements.

## Your JDBC driver may need directives of its own

That is the driver's business, not the mapper layer's, but it will land in your
`module-info.java`. H2 is the common example:

```java
module com.example.app {
    requires io.github.lightbatis.runtime;
    requires static io.github.lightbatis.annotations;
    requires static java.compiler;

    // automatic module, named from the jar manifest — re-check with
    // `jar --describe-module` after an upgrade
    requires com.h2database;

    // H2's JdbcDataSource implements javax.naming.Referenceable, and an automatic
    // module cannot declare its own requires, so the consumer reads java.naming for it.
    requires java.naming;
}
```

An automatic module cannot declare `requires` of its own, so anything it needs and the
platform does not give it by default becomes the consumer's problem. Run
`jar --describe-module` against a driver jar after every upgrade — an automatic module's
name comes from the manifest and can change.

## Native image

There is nothing for the mapper layer to declare. No `Proxy.newProxyInstance`, no
`Class.forName`, no `setAccessible` anywhere in the runtime or in generated code, so
there is no reachability metadata to write. Your JDBC driver may still ship or need its
own — that is a driver concern.

!!! warning "Not yet verified by a real build"

    That claim is structural — you can check it by reading the code — but a native-image
    build has **not been run yet**; it is open M5 work. Treat it as a well-founded
    expectation rather than a result. See [Performance](../wiki/performance.md#native-image).

The `lightbatis-sample` module of the core repository is a working modular consumer, and
is the intended subject of that smoke test.
