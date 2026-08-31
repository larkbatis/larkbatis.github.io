# Java Modules (JPMS)

`larkbatis-annotations` and `larkbatis-runtime` ship as **real named modules**, not automatic ones (and so do the Spring artifacts). Generated mapper code works cleanly in modular applications without split packages. We treat JPMS support as a hard requirement, not an afterthought.

| Artifact | Module name |
|---|---|
| `larkbatis-annotations` | `io.github.larkbatis.annotations` |
| `larkbatis-runtime` | `io.github.larkbatis.runtime` |
| `larkbatis-spring` | `io.github.larkbatis.spring` |
| `larkbatis-spring-boot-autoconfigure` | `io.github.larkbatis.spring.boot` |
| `larkbatis-spring-boot-starter` | `io.github.larkbatis.spring.boot.starter` |

`larkbatis-processor` is build-only and never belongs on a module path.

## The consumer descriptor

Here are the module directives you need (the third one usually catches people off guard):

```java title="module-info.java"
module com.example.app {
    requires io.github.larkbatis.runtime;             // (1)!
    requires static io.github.larkbatis.annotations;  // (2)!
    requires static java.compiler;                     // (3)!
}
```

1.  Runtime types called by generated code: `LarkBatisSession`, `JdbcCodec`, `RowReader`, `LarkBatisSql`.
2.  Mapper annotations have `CLASS` retention, so this is compile-time only (`requires static`).
3.  Generated files include `@javax.annotation.processing.Generated` from the `java.compiler` module.

!!! failure "`package javax.annotation.processing is not visible`"

    If you omit `requires static java.compiler`, javac throws this error pointing at the generated source file. Adding the directive fixes it.

## What you do *not* need

- **`requires java.sql`.** `io.github.larkbatis.runtime` requires `java.sql` *transitively* because its API exposes `Connection`, `ResultSet`, and `PreparedStatement`. Any module requiring LarkBatis gets `java.sql` automatically.
- **`opens` directives.** LarkBatis uses zero reflection, so you never need to open packages.
- **`exports` for generated code.** Generated files are placed in your own packages alongside your mapper interfaces.

## JDBC driver module requirements

Your JDBC driver might require its own module directives in `module-info.java`. H2 is a common example:

```java
module com.example.app {
    requires io.github.larkbatis.runtime;
    requires static io.github.larkbatis.annotations;
    requires static java.compiler;

    // automatic module named from jar manifest
    requires com.h2database;

    // H2's JdbcDataSource implements javax.naming.Referenceable,
    // so consumer modules need java.naming
    requires java.naming;
}
```

Because automatic modules cannot declare their own dependencies, transitive requirements fall to the application's `module-info.java`. You can check a driver jar's module name anytime using `jar --describe-module`.

## Native image

There's nothing you need to configure for the mapper layer. No dynamic proxies, no `Class.forName`, and no `setAccessible` calls anywhere in the runtime or generated code. That means zero reflection metadata to maintain for your mappers (though your JDBC driver may still need its own driver-specific configuration).

!!! warning "Pending real-world verification"

    This claim is structural: you can verify there is no reflection by inspecting the generated code. However, a native-image smoke test build is still scheduled for milestone M5. Treat this as an expectation based on code inspection rather than an executed benchmark. See [Performance](../wiki/performance.md#native-image).

The `larkbatis-sample` module in the core repository is a fully configured modular consumer used to verify module compatibility.
