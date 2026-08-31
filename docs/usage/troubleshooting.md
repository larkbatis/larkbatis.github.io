# Troubleshooting

## Nothing is generated during build

Check the following in order:

1. **Is the processor on the correct configuration?** Use `annotationProcessor` in Gradle, or `<annotationProcessorPaths>` in Maven (not `implementation` or standard `<dependencies>`).
2. **Are you compiling with standard javac?** ECJ / Eclipse batch compiler is not supported because the processor relies on javac's AST element ordering and multi-round type resolution.
3. **Does the interface have statement annotations or `@Mapper`?** Purely XML-based mappers must have `@Mapper` on the interface so javac knows to pass them to the processor.
4. **Running JDK 23+ with `addProcessorPath=false`?** javac on JDK 23+ no longer discovers processors from the compilation classpath automatically. Add the processor to `<annotationProcessorPaths>` or pass `<proc>full</proc>`.

## `#{id}` does not resolve, or parameters are named `arg0`, `arg1`

```text
error: no parameter or property named 'id' in findById(long)
```

In Gradle, incremental compilation can invoke annotation processors over existing class files where parameter names were stripped (unless compiled with `-parameters`). Clean builds succeed because they parse Java source files directly, but subsequent incremental builds fail.

### How to fix it

=== "Option 1: Compile with `-parameters` (Recommended)"

    ```kotlin title="build.gradle.kts"
    tasks.withType<JavaCompile>().configureEach {
        options.compilerArgs.add("-parameters")
    }
    ```

    In Maven, set `<parameters>true</parameters>` in `maven-compiler-plugin`.

=== "Option 2: Annotate parameters with `@Param`"

    ```java
    User findById(@Param("id") long id);
    ```

    `@Param` embeds the parameter name directly into annotation metadata, surviving bytecode compilation regardless of compiler flags.

## Lombok conflicts / "Result class has no accessors"

Lombok generates getters and setters in the AST during compilation. Because javac runs processors in the order they appear on the classpath, placing LarkBatis before Lombok means LarkBatis sees classes without getters/setters.

Always declare Lombok first:

```kotlin
annotationProcessor("org.projectlombok:lombok")
annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")  // must be after Lombok
```

## Editing mapper XML does not trigger recompilation

Annotation processors cannot easily track resource file edits automatically, which is why build plugins are used:

- **Using a [build plugin](../getting-started/build-plugins.md)?** Gradle registers XML files as compilation inputs; Maven's `larkbatis:refresh` goal touches mapper interfaces when XML changes.
- **Maven plugin not running?** Ensure you added `<extensions>true</extensions>` to `larkbatis-maven-plugin`. Without this, Maven silently ignores build extensions. Run `mvn larkbatis:check` to verify.
- **Passing `-Alarkbatis.mapperDir` manually?** Run `./gradlew clean` or `mvn clean` after editing XML files.

Also verify that XML root tags are `<mapper>` and that the `namespace` matches an interface in the **same compilation module**.

## `package javax.annotation.processing is not visible`

In modular JPMS projects, add `requires static java.compiler;` to your `module-info.java` because generated code includes `@Generated` annotations. See [Java Modules](../getting-started/jpms.md).

## `useGeneratedKeys without keyColumn falls back to RETURN_GENERATED_KEYS`

Always specify `keyColumn` when using `useGeneratedKeys = true`. `RETURN_GENERATED_KEYS` returns `ROWID` on Oracle and all columns on PostgreSQL. Specifying `keyColumn = "id"` guarantees consistent cross-database behavior. See [Generated Keys](generated-keys.md).

## `LarkBatisEmptyForeachException` at runtime

An empty collection was passed to a `<foreach>` block. In MyBatis, an empty collection generates malformed SQL that crashes at the database. In LarkBatis, it throws an informative exception immediately.

To skip the SQL fragment when a list is empty, wrap it in an `<if>` tag:

```xml
<if test="ids != null and !ids.isEmpty()">
  AND id IN <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
</if>
```

## `test="count"` causes a compile error

LarkBatis intentionally rejects OGNL truthiness. Write explicit comparisons: `count != 0`, `user != null`, or `!list.isEmpty()`. See [Dynamic SQL](dynamic-sql.md#the-test-grammar).

## `String` parameter bound to `${}` causes a compile error

Direct string splicing into `${}` is prohibited to prevent SQL injection vulnerabilities. Use `@OrderBy(allowed = {...})`, `SqlFragment`, or closed-value types (enums/integers). See [Raw SQL](raw-sql.md).

## `LarkBatisRollbackOnlyException` on commit

An inner transaction scope exited with an error or without voting to commit, poisoning the transaction. When the outer transaction scope attempted to commit, it threw `LarkBatisRollbackOnlyException` to avoid silent data loss. See [Transactions](transactions.md).

## `LarkBatisUnboundedVariantsException`

If `fail-on-unbounded-fragment: true` is enabled and a statement exceeds `max-sql-variants`, it throws this exception. Use `SqlFragment.allowed(...)`, `@OrderBy`, or `@PadPow2` to bound dynamic SQL variants. See [Raw SQL](raw-sql.md#tracking-sql-variants).

## Statement fell back to name-based row reads

If javac cannot parse a statement's `SELECT` column list (e.g. `SELECT *` or `${}` inside the column list), it falls back to reading columns by name via `ResultSetMetaData` on the first row. While fully functional, it is slightly slower than indexed reads. Provide explicit column names and aliases to restore fast indexed reading.
