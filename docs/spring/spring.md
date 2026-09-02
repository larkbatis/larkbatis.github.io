# Spring Integration

To understand how LarkBatis integrates with Spring, it helps to see what `mybatis-spring` had to do. In standard MyBatis, `mybatis-spring` solved two distinct problems:

1. **Mappers are bare interfaces without concrete classes.** Spring cannot instantiate them on its own, requiring `@MapperScan` → `ClassPathMapperScanner` → `MapperFactoryBean` → `MapperProxy` dynamic JDK proxies.
2. **`SqlSession` must participate in `@Transactional`.** Solved via `SqlSessionTemplate`, `SqlSessionUtils`, and `SpringManagedTransaction`.

**In LarkBatis, Problem 1 doesn't exist.** `AccountMapper$$Impl` is a concrete Java class with a standard public constructor. The entire classpath scanner, dynamic proxy layer, and runtime bean definition post-processing disappear. They are replaced by a compile-time generated `@Configuration` with standard `@Bean` methods.

**Problem 2 is fully preserved**, and is the primary focus of our Spring integration.

## Modules

| Module | Role |
|---|---|
| `larkbatis-spring` | Provides `SpringLarkBatisSession`: delegates connections to `DataSourceUtils` and translates exceptions via `SQLExceptionTranslator` |
| `larkbatis-spring-boot-autoconfigure` | Auto-configuration: `LarkBatisAutoConfiguration`, properties, and `AutoConfiguration.imports` |
| `larkbatis-spring-boot-starter` | Dependency aggregator for Spring Boot applications |

## `SpringLarkBatisSession`

The core integration delegates connection acquisition to Spring:

```java
@Override
public Connection conn() {
    return DataSourceUtils.getConnection(dataSource);   // never calls dataSource.getConnection() directly
}
```

`DataSourceUtils` returns the active connection bound to the running `@Transactional` scope, or opens a new connection if called outside a transaction. `release()` is a no-op during active transactions and closes the connection only when running standalone. This is why generated mapper methods do not close connections directly. See [Transactions](../usage/transactions.md#why-generated-code-never-closes-the-connection).

`SpringLarkBatisSession` is stateless and thread-safe.

Exception translation uses Spring's `SQLExceptionTranslator` (`SQLExceptionSubclassTranslator` by default), mapping JDBC errors directly to Spring's `DataAccessException` tree (e.g. `DuplicateKeyException`).

## Feature Matrix

| Feature | Support | Notes |
|---|---|---|
| `@Transactional` on services | Supported | `DataSourceUtils` returns the transaction's bound connection |
| Propagation rules (`REQUIRES_NEW`, `NESTED`) | Supported | Handled entirely by Spring |
| `readOnly = true` | Supported | Applied by Spring directly to the connection |
| Standalone calls (no transaction) | Supported | Standard auto-commit per statement |
| `Stream<T>` returns | Supported | Stream holds connection until closed; no-op release inside transactions |
| Interop with `JdbcTemplate` / JPA | Supported | Shares identical `DataSourceTransactionManager` context |
| Spring AOP on mappers | Supported | Mappers are regular Spring beans |
| MyBatis `ExecutorType.BATCH` | Replaced | Batching is declared via [method signatures](../usage/foreach-and-batches.md#jdbc-batches) |
| MyBatis Interceptor plugins | Replaced | Replaced with explicit SQL, custom type handlers, or Spring AOP. [See recipes](../features/mybatis-differences.md#what-replaces-a-plugin) |


## Configuration Properties

```yaml
larkbatis:
  max-sql-variants: 64                # warning threshold for dynamic SQL variants
  fail-on-unbounded-fragment: false   # throw exception instead of warning
```

See [Raw SQL](../usage/raw-sql.md#tracking-sql-variants) for details on SQL variant tracking.

!!! note "SQL query logging"

    LarkBatis does not inject runtime logging branches into generated method bytecode. Configure query logging at the connection pool or driver level (`datasource-proxy`, p6spy).

## Advanced Configuration

| Requirement | Solution |
|---|---|
| Mappers in non-standard packages | Pass `-Alarkbatis.springConfigPackage=com.example.app` or use `@Import(LarkBatisMapperConfiguration.class)` |
| Declare mapper beans manually | Pass `-Alarkbatis.springConfig=false` to disable auto-generating `@Configuration` |
| Multiple `DataSource` configurations | Define a `SpringLarkBatisSession` per `DataSource` and declare mapper `@Bean` methods explicitly |

## Spring Boot 3 and Spring Boot 4 Compatibility

A single LarkBatis starter jar works on both Spring Boot 3 and Spring Boot 4.

Spring Boot 4 moved `DataSourceAutoConfiguration` into `spring-boot-jdbc` under a new package:

| Class | Boot 3 Package | Boot 4 Package |
|---|---|---|
| `DataSourceAutoConfiguration` | `org.springframework.boot.autoconfigure.jdbc` | `org.springframework.boot.jdbc.autoconfigure` |
| `@AutoConfiguration`, `@ConditionalOn*` | `org.springframework.boot.autoconfigure(.condition)` | Unchanged |
| `@ConfigurationProperties` | `org.springframework.boot.context.properties` | Unchanged |

`LarkBatisAutoConfiguration` orders itself using `afterName` listing **both** package names, ensuring correct ordering across both Spring Boot versions without class loading issues.

## Spring AOT and GraalVM Native Image

Generated mapper bean definitions like `@Bean AccountMapper accountMapper(LarkBatisSession s)` have static return types. Spring AOT processes them directly without needing runtime reflection metadata or proxy hints.

Additionally, generated `@Configuration` classes declare `proxyBeanMethods = false` to avoid generating runtime CGLIB subclasses.
