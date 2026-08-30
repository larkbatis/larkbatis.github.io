# Spring Integration

Half of `mybatis-spring` evaporates here, and knowing *which* half explains the whole
integration. `mybatis-spring` exists to solve exactly two problems:

1. **A mapper is an interface with no implementation**, so Spring cannot create a bean for
   it. Solved with `@MapperScan` → `ClassPathMapperScanner` → `MapperFactoryBean` →
   `MapperProxy`.
2. **`SqlSession` must share its `Connection` with `@Transactional`.** Solved with
   `SqlSessionTemplate` + `SqlSessionUtils` + `SpringManagedTransaction`.

**Problem 1 is not a problem here.** `AccountMapper$$Impl` is a real class with a real
constructor, which is an ordinary bean. The scanner, the `FactoryBean` and the
`BeanDefinition` post-processing all disappear, replaced by a generated `@Configuration`
with one `@Bean` method per mapper.

**Problem 2 is untouched**, and it is very nearly the whole content of the integration.

## The modules

| Module | Role |
|---|---|
| `larkbatis-spring` | `SpringLarkBatisSession`: connections via `DataSourceUtils`, exception translation via `SQLExceptionTranslator` |
| `larkbatis-spring-boot-autoconfigure` | `LarkBatisAutoConfiguration`, `LarkBatisProperties`, the `AutoConfiguration.imports` entry |
| `larkbatis-spring-boot-starter` | Empty; dependencies only |

## `SpringLarkBatisSession`

The one rule the class exists to enforce:

```java
@Override
public Connection conn() {
    return DataSourceUtils.getConnection(dataSource);   // never dataSource.getConnection()
}
```

`DataSourceUtils` hands back the connection already bound to the running transaction, and
opens a fresh one only when there is none. `release()` does the reverse: a no-op inside a
transaction, a real close outside one. Generated bodies therefore keep the `Connection`
out of try-with-resources. See
[Why generated code never closes the Connection](transactions.md#why-generated-code-never-closes-the-connection).

The class holds no state beyond its two collaborators and is safe to share across
threads. One bean per `DataSource`.

Exception translation goes through Spring's `SQLExceptionTranslator`, defaulting to
`SQLExceptionSubclassTranslator` (Spring's own default since 6.0), which reads the
standard `SQLException` subclass tree and not a per-vendor error-code table. So your
existing `DuplicateKeyException` handlers keep working unchanged.

## What runs and what does not

| Scenario | | Why |
|---|---|---|
| `@Transactional` on a service, mapper called inside | works | `DataSourceUtils` returns the transaction's connection |
| `REQUIRES_NEW`, `NESTED`, rollback rules | works | Spring handles all of it |
| `readOnly = true` | works | Spring sets the flag on that connection |
| Mapper called outside any transaction | works | Auto-commit; `release` closes it immediately |
| A `Stream`-returning mapper method | works | The stream holds a pooled connection until closed; inside a transaction `release` is a no-op. `try (Stream<T> …)` either way |
| Sharing a transaction with `JdbcTemplate` or JPA | works | Same `DataSourceUtils`, same `DataSourceTransactionManager` |
| Spring AOP on a mapper bean | works | The mapper is a real bean |
| MyBatis `ExecutorType.BATCH` | absent | There is no executor. Batch is a [method signature](foreach-and-batches.md#jdbc-batches) |
| MyBatis plugins / interceptors | absent | Dropped; they hook a runtime pipeline that does not exist |

## Properties

```yaml
larkbatis:
  max-sql-variants: 64                # distinct SQL texts per statement before a warning
  fail-on-unbounded-fragment: false   # true = throw instead of one warning
```

Both are about the operational cost of `${}`: statement caches are keyed by SQL text, so
a fragment whose value set is not bounded grows them without limit. See
[Raw SQL](raw-sql.md#tracking-sql-variants).

!!! note "`log-sql` is not implemented"

    It appears in the design document's property list and is not implemented. Every
    generated body would have to carry a logging branch, and the generated shape has none.
    SQL logging belongs to the driver or the pool (`net.ttddyy:datasource-proxy`, p6spy)
    until there is a reason to change that.

## When the defaults do not fit

| Situation | What to do |
|---|---|
| Mappers outside the scanned packages | `-Alarkbatis.springConfigPackage=com.example.app`, or `@Import(LarkBatisMapperConfiguration.class)` |
| You want to declare the mapper beans yourself | `-Alarkbatis.springConfig=false` |
| More than one `DataSource` | Declare one `SpringLarkBatisSession` per `DataSource` and write the mapper `@Bean` methods yourself |

On multiple data sources: `@ConditionalOnSingleCandidate` makes the auto-configuration
back off entirely instead of guessing, and the generated `@Configuration` takes a single
`LarkBatisSession`, so mark one `@Primary` or suppress the generated class with the
option above. Per-mapper `DataSource` selection is **deferred**: no design without a real
service that needs it.

## Spring Boot 3 and Spring Boot 4

One jar works on both, and it took one decision to get there. Boot 4 moved
`DataSourceAutoConfiguration` out of `spring-boot-autoconfigure` into the new
`spring-boot-jdbc` module and renamed its package:

| | Boot 3 | Boot 4 |
|---|---|---|
| `DataSourceAutoConfiguration` | `org.springframework.boot.autoconfigure.jdbc` | `org.springframework.boot.jdbc.autoconfigure` |
| `@AutoConfiguration`, `@ConditionalOn*` | `org.springframework.boot.autoconfigure(.condition)` | unchanged |
| `@ConfigurationProperties` | `org.springframework.boot.context.properties` | unchanged |

So `LarkBatisAutoConfiguration` declares its ordering with `afterName` and lists **both**
package names.

!!! danger "Why this is not style"

    `after = DataSourceAutoConfiguration.class` compiled against Boot 3 cannot be resolved
    on Boot 4, and Spring's response is to drop the whole auto-configuration from the
    candidate list: no bean, no warning. Nothing goes wrong until something asks for a
    `LarkBatisSession` and the context fails to start.

    A name that matches nothing is simply ignored, which is what makes listing both safe.
    Verified by migrating a real Boot 4.1 service; a test asserts both names are still
    there, because "simplifying" it back to a class reference reintroduces a failure with
    no symptom.

## Spring AOT and native image

`@Bean AccountMapper accountMapper(LarkBatisSession s)` has a static return type, so AOT
treats it like any other bean: no `getObjectType()` at runtime, no proxy hint, no
`reflect-config.json` for the mapper layer. `MapperFactoryBean` is the opposite case: the
bean type is only known at runtime and what it returns is a JDK proxy.

`proxyBeanMethods = false` on the generated `@Configuration` is load-bearing, not style:
the default `true` makes Spring build a CGLIB subclass of that class at runtime, which is
exactly the runtime bytecode generation this project exists to remove.

## Registration

The auto-configuration registers through
`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`, not
`spring.factories`.
