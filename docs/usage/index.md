# Usage

In LarkBatis, you write SQL mappers in one of two ways: a **mapper interface** with statement annotations, or an interface marked `@Mapper` whose statements live in **mapper XML**. Both compile to identical Java implementations. They are simply two ways to feed the same compiler pipeline.

## Project Structure

```text
src/main/java/com/example/app/
    User.java                 # result class: standard no-arg constructor + getters/setters
    UserMapper.java           # annotation-based mapper
    UserSearchMapper.java     # @Mapper — statements defined in XML
src/main/resources/mappers/
    UserSearchMapper.xml      # namespace = com.example.app.UserSearchMapper
```

During compilation, the processor generates the following classes in the same package:

```text
UserMapper$$Impl.java              one per mapper interface
UserSearchMapper$$Impl.java
UserRow.java                       one per result class (shared across mappers)
LarkBatisMappers.java             one per compilation module (static factory)
LarkBatisMapperConfiguration.java generated when Spring is on the classpath
```

## Documentation Sections

<div class="grid cards" markdown>

-   **[Mapper Interfaces](mappers.md)**

    Statement annotations, `#{}` parameters, `@Param`, result classes, and automatic column-to-setter mapping.

-   **[Mapper XML](xml-mappers.md)**

    `@Mapper`, namespaces, statement IDs, `<sql>`/`<include>`, and statement resolution.

-   **[Dynamic SQL](dynamic-sql.md)**

    `<if>`, `<choose>`, `<where>`, `<set>`, `<trim>`, and the type-checked `test` grammar.

-   **[foreach and Batches](foreach-and-batches.md)**

    `IN` lists, multi-row `VALUES`, nested loops, JDBC `addBatch()` inserts, and `@PadPow2`.

-   **[Result Maps and Joins](result-maps.md)**

    `<resultMap>`, 1-level `<association>` / `<collection>` joins, and parent-key ordering rules.

-   **[Generated Keys](generated-keys.md)**

    `useGeneratedKeys`, why naming `keyColumn` matters, and batch key handling.

-   **[Streaming Results](streaming.md)**

    `Stream<T>` returns over open database cursors, and resource lifecycle management.

-   **[Transactions](transactions.md)**

    `LarkBatisTx` vote-to-commit scopes, nesting, and Spring `@Transactional` integration.

-   **[Raw SQL and SqlFragment](raw-sql.md)**

    Safe `${}` usage, `@OrderBy` allowlists, manual escape hatches, and SQL-variant tracking.

-   **[Types and Handlers](types.md)**

    Default `#{}` mappings, `JdbcCodec`, `@Column`, `@Handler`, enums, and `java.time` support.

-   **[Spring Integration](../spring/spring.md)**

    How LarkBatis integrates with Spring Boot without proxies or runtime scanning.

-   **[Troubleshooting](troubleshooting.md)**

    Common build issues: missing generated files, `arg0` parameter names, and Lombok processor ordering.

</div>

## Two guiding design rules

**1. If something can be decided at build time, it is.** Column indexes, type handler choices, `<trim>` prefixes, `<include>` inlining, and type comparisons: none of this is inspected at runtime. Any mistakes fail the build with a clear error pointing to the exact mapper method.

**2. If something cannot be decided at build time, it must be explicit.** The list of runtime operations is strictly limited: parameter values, boolean evaluation of `<if>`/`<when>` tests, `<foreach>` collection sizes, reading `ResultSet` rows, and `SqlFragment` contents. Anything beyond this must be declared explicitly in the method signature (which is why passing a raw `String` to `${}` fails compilation).

See [Shape vs Value](../wiki/shape-vs-value.md) for the full architectural breakdown.
