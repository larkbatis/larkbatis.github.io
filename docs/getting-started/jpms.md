# Java Modules (JPMS)

`larkbatis-annotations` and `larkbatis-runtime` ship **real named modules**, not
automatic ones, and so do the three Spring artifacts. Generated mapper code is usable from
a modular consumer, and the module path stays free of split packages. The project treats
this as a requirement, not a nice-to-have.

| Artifact | Module name |
|---|---|
| `larkbatis-annotations` | `io.github.larkbatis.annotations` |
| `larkbatis-runtime` | `io.github.larkbatis.runtime` |
| `larkbatis-spring` | `io.github.larkbatis.spring` |
| `larkbatis-spring-boot-autoconfigure` | `io.github.larkbatis.spring.boot` |
| `larkbatis-spring-boot-starter` | `io.github.larkbatis.spring.boot.starter` |

`larkbatis-processor` is build-only and never appears on a module path.

## The consumer descriptor

Three directives. The third is the one that surprises people:

```java title="module-info.java"
module com.example.app {
    requires io.github.larkbatis.runtime;             // (1)!
    requires static io.github.larkbatis.annotations;  // (2)!
    requires static java.compiler;                     // (3)!
}
```

1.  What the generated bodies actually call: `LarkBatisSession`, `JdbcCodec`,
    `RowReader`, `LarkBatisSql`.
2.  Every mapper annotation is `CLASS`-retention, so this is a compile-time-only edge.
3.  Every emitted source carries `@javax.annotation.processing.Generated`, which lives in
    `java.compiler`. `SOURCE` retention makes it `static`.

!!! failure "`package javax.annotation.processing is not visible`"

    This is what you get without `requires static java.compiler`, and the error points at
    the **generated** file, which is why it is confusing the first time. Add the
    directive.

## What you do *not* need

- **`requires java.sql`.** `io.github.larkbatis.runtime` requires it *transitively*,
  because its own API hands you `Connection`, `ResultSet` and `PreparedStatement`. A
  module that reads the runtime can already name those types.
- **`opens`, anywhere.** Neither LarkBatis module ever needs it. There is no reflection
  to open anything for.
- **an `exports` for generated code.** It lands in your own package, alongside the mapper
  interface it implements.

## Your JDBC driver may need directives of its own

That is the driver's business, not the mapper layer's, but it will land in your
`module-info.java`. H2 is the common example:

```java
module com.example.app {
    requires io.github.larkbatis.runtime;
    requires static io.github.larkbatis.annotations;
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
`jar --describe-module` against a driver jar after every upgrade: an automatic module's
name comes from the manifest and can change.

## Native image

There is nothing for the mapper layer to declare. No `Proxy.newProxyInstance`, no
`Class.forName`, no `setAccessible` anywhere in the runtime or in generated code, so there
is no reachability metadata to write. Your JDBC driver may still ship or need its own,
which is a driver concern.

!!! warning "Not yet verified by a real build"

    The claim is structural, and you can check it by reading the code. But a native-image
    build has **not been run yet**; it is open M5 work. Treat it as a well-founded
    expectation rather than a result. See [Performance](../wiki/performance.md#native-image).

The `larkbatis-sample` module of the core repository is a working modular consumer, and
is the intended subject of that smoke test.
