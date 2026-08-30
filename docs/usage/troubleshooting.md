# Troubleshooting

## Nothing was generated

Check, in this order:

1. **Is the processor on the right configuration?** `annotationProcessor` in Gradle,
   `annotationProcessorPaths` in Maven — not `implementation` / `<dependencies>`.
2. **Are you compiling with javac?** ECJ / the Eclipse batch compiler is not supported.
   The processor relies on javac behaviour: declaration order of elements, and
   multi-round resolution of generated types.
3. **Does the interface have a statement annotation or `@Mapper`?** Those are the only
   trigger types. An XML-only interface without `@Mapper` never reaches a processing
   round.
4. **JDK 23+ with `addProcessorPath=false`?** javac no longer discovers processors from
   the compile classpath, and `-Alightbatis.mapperDir` does not count as asking for
   annotation processing. Add the processor to `annotationProcessorPaths` or set
   `<proc>full</proc>`.

## `#{id}` does not resolve — parameters are called `arg0`, `arg1`

```text
error: no parameter or property named 'id' in findById(long)
```

A Gradle **incremental** build re-runs aggregating processors over unchanged mappers from
their **class files**, where parameter names survive only if the class was compiled with
`-parameters`. Clean builds read the AST and work; the next incremental one does not.
This is a documented Gradle limitation, not a LightBatis bug.

=== "Fix 1 — compile with `-parameters`"

    ```kotlin
    tasks.withType<JavaCompile>().configureEach {
        options.compilerArgs.add("-parameters")
    }
    ```

=== "Fix 2 — name every parameter"

    ```java
    User findById(@Param("id") long id);
    ```

## `Lombok has not run yet` / result class has no accessors

Lombok writes its getters and setters into the AST when **its** processor runs, and javac
runs discovered processors in classpath order. Declared first, LightBatis sees a result
class with no accessors at all.

```kotlin
annotationProcessor("org.projectlombok:lombok")
annotationProcessor("io.github.lightbatis:lightbatis-processor:0.1.0-SNAPSHOT")  // after
```

The error message says so when it spots a Lombok annotation on the class, but the fix is
that one line of ordering.

## Editing mapper XML changes nothing

The processor reads mapper XML with plain `java.io`, outside the compiler's `Filer`, so
the build tool has to be told those files are compile inputs.

- **Using a [build plugin](../getting-started/build-plugins.md)?** Gradle registers the
  files as `compileJava` inputs; Maven's `lightbatis:refresh` goal touches the mapper
  interface source whose XML content hash changed. Both should just work.
- **Maven, but nothing happens?** You almost certainly omitted
  `<extensions>true</extensions>`, which fails **silently**. Run `mvn lightbatis:check`.
- **Passing `-Alightbatis.mapperDir` by hand?** Then nothing registered the inputs. Run
  `clean` after an XML-only edit.

Also check that the file's root element is `<mapper>` — anything else in the directory is
ignored by design — and that its `namespace` names an interface **in the same module**.
A cross-module namespace is skipped with a build warning.

## `package javax.annotation.processing is not visible`

A modular consumer needs `requires static java.compiler`, because every emitted source
carries `@Generated`. The error points at the *generated* file, which is what makes it
confusing. See [Java Modules](../getting-started/jpms.md).

## `useGeneratedKeys without keyColumn falls back to RETURN_GENERATED_KEYS`

A mandatory build warning, and one worth treating as an error: Oracle returns `ROWID` and
PostgreSQL returns every column under that flag. Name the key column explicitly. See
[Generated Keys](generated-keys.md).

## `LightBatisEmptyForeachException` at runtime

A `<foreach>` collection was empty. If the fragment should simply disappear for an empty
collection — MyBatis's behaviour — say so:

```xml
<if test="ids != null and !ids.isEmpty()">
  AND id IN <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
</if>
```

See [foreach and Batches](foreach-and-batches.md#empty-collections).

## `test="count"` is a compile error

OGNL truthiness is deliberately not reproduced. Write `count != 0`, `user != null`, or
`!list.isEmpty()`. See [the test grammar](dynamic-sql.md#the-test-grammar).

## A `String` parameter bound to `${}` is a compile error

By design. Use `@OrderBy(allowed = {...})`, a `SqlFragment`, or a closed-value type. See
[Raw SQL](raw-sql.md).

## `LightBatisRollbackOnlyException` on commit

An inner transaction scope left without voting, poisoning the transaction, and the outer
scope then tried to commit. The exception is preferable to a silent rollback that looks
like success. See [Transactions](transactions.md).

## `LightBatisUnboundedVariantsException`

You set `fail-on-unbounded-fragment: true` (good, in staging) and a statement produced
more than `max-sql-variants` distinct SQL texts. Find the unbounded `${}` or the
`<foreach>` and either close the value set with `SqlFragment.allowed(...)` / `@OrderBy`,
or bound the cardinality with `@PadPow2`. See
[Tracking SQL variants](raw-sql.md#tracking-sql-variants).

## A statement fell back to name-based row reads

Reported at build time. It means the select list could not be parsed — `SELECT *`, a
`${}` splice in the select list, or an unaliased expression like `1 + 1`. The statement is
correct and measurably slower. Alias the expression, or spell out the columns, if you
want positional reads back.

## Generated code does not close the Connection

That is correct, and the emitter tests assert it. Only `s.release(c)` knows whether the
connection belongs to a running transaction. See
[Transactions](transactions.md#why-generated-code-never-closes-the-connection).
