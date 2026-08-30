# Usage

Everything you write in LarkBatis is one of two things: a **mapper interface** whose
methods carry statement annotations, or a mapper interface marked `@Mapper` whose
statements live in **mapper XML**. Both compile to the same generated implementation.
They are two frontends onto one intermediate representation, not two code paths.

## The shape of a project

```text
src/main/java/com/example/app/
    User.java                 # result class: no-arg constructor, setters
    UserMapper.java           # annotation statements
    UserSearchMapper.java     # @Mapper — statements in XML
src/main/resources/mappers/
    UserSearchMapper.xml      # namespace = com.example.app.UserSearchMapper
```

At build time the processor emits, into the same package:

```text
UserMapper$$Impl.java              one per mapper
UserSearchMapper$$Impl.java
UserRow.java                       one per result class
LarkBatisMappers.java             one per compilation
LarkBatisMapperConfiguration.java one, if Spring is on the build classpath
```

## Pages in this section

<div class="grid cards" markdown>

-   **[Mapper Interfaces](mappers.md)**

    Statement annotations, `#{}` parameters, `@Param`, result classes and how columns
    find their setters.

-   **[Mapper XML](xml-mappers.md)**

    `@Mapper`, namespaces, statement ids, `<sql>`/`<include>`, and how a statement is
    resolved per method.

-   **[Dynamic SQL](dynamic-sql.md)**

    `<if>`, `<choose>`, `<where>`, `<set>`, `<trim>`, and the narrow `test` grammar that
    replaces OGNL.

-   **[foreach and Batches](foreach-and-batches.md)**

    `IN` lists, multi-row `VALUES`, nested loops, `addBatch()` inserts and `@PadPow2`.

-   **[Result Maps and Joins](result-maps.md)**

    `<resultMap>`, one level of `<association>` / `<collection>`, and the ordering rule
    that makes it work.

-   **[Generated Keys](generated-keys.md)**

    `useGeneratedKeys`, why `keyColumn` matters, and key counting in batch mode.

-   **[Streaming Results](streaming.md)**

    `Stream<T>` returns over an open cursor, and who owns the resources.

-   **[Transactions](transactions.md)**

    `LarkBatisTx` vote-to-commit semantics, nesting, and `@Transactional`.

-   **[Raw SQL and SqlFragment](raw-sql.md)**

    The `${}` discipline, `@OrderBy`, the escape hatch, and SQL-variant tracking.

-   **[Types and Handlers](types.md)**

    What `#{}` binds without help, `JdbcCodec`, `@Column`, `@Handler`, enums and
    `java.time`.

-   **[Spring Integration](spring.md)**

    What `mybatis-spring` does that LarkBatis does not need, and what it still does.

-   **[Troubleshooting](troubleshooting.md)**

    Nothing generated, `arg0` parameter names, Lombok ordering, XML not picked up.

</div>

## Two rules that explain most surprises

**1 · If it can be decided at build time, it is.** Column indexes, type-handler choices,
`<trim>` prefixes, `<include>` bodies, whether a comparison is on a `long` or a `String`:
none of it is inspected at runtime. A mistake in any of them surfaces as a compile error
naming the mapper method, not as a stack trace.

**2 · If it cannot, it must be explicit.** The list of things resolved at runtime is short
and closed: parameter values, the boolean results of `<if>`/`<when>` tests, the size of a
`<foreach>` collection, the rows in a `ResultSet`, the actual column count when the select
list could not be parsed, and the contents of a `SqlFragment`. Anything not on that list
has to be spelled out in the mapper signature, which is why binding a `String` to `${}`
fails the build instead of passing quietly.

The full statement of that boundary is in the wiki:
[Shape vs Value](../wiki/shape-vs-value.md).
