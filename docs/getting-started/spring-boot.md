# Spring Boot Quick Start

There is no `@MapperScan`, no `SqlSessionFactoryBean` and no `SqlSessionTemplate`.
A mapper implementation is a real class with a real constructor, so it is an ordinary bean.
The processor emits a `@Configuration` with one `@Bean` method per mapper, and the
auto-configuration supplies the single `LarkBatisSession` those methods ask for.

## 1 · Dependencies

```kotlin title="build.gradle.kts"
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-jdbc")
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0")
    implementation("io.github.larkbatis:larkbatis-spring-boot-starter:0.1.0")
    annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")

    runtimeOnly("com.h2database:h2")
}

tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.add("-parameters")   // (1)!
}
```

1.  Keeps real parameter names in the class file, so `#{id}` still finds `id` on a Gradle
    incremental build. Without it the processor can see `arg0` instead and fail to resolve
    the bind. Spring Boot's own starter parent sets the same flag for its constructor
    binding, so this line is often already there.
    [Troubleshooting](../usage/troubleshooting.md#what-the-flag-actually-does) has the
    detail.

That is the whole setup. Works on **Spring Boot 3 and Spring Boot 4** from the same jar.

## 2 · A mapper

```java title="AccountMapper.java"
package com.example.app;

import io.github.larkbatis.annotations.Insert;
import io.github.larkbatis.annotations.Options;
import io.github.larkbatis.annotations.Select;
import io.github.larkbatis.annotations.Update;
import java.util.List;

public interface AccountMapper {

    @Select("SELECT id, owner, balance FROM account WHERE id = #{id}")
    Account findById(long id);

    @Select("SELECT id, owner, balance FROM account ORDER BY id")
    List<Account> findAll();

    @Insert("INSERT INTO account (owner, balance) VALUES (#{owner}, #{balance})")
    @Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
    int insert(Account a);

    @Update("UPDATE account SET balance = #{balance} WHERE id = #{id}")
    int updateBalance(Account a);
}
```

## 3 · Inject it

```java title="AccountService.java"
package com.example.app;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AccountService {

    private final AccountMapper accounts;

    public AccountService(AccountMapper accounts) {   // (1)!
        this.accounts = accounts;
    }

    @Transactional
    public void transfer(long from, long to, long amount) {
        Account a = accounts.findById(from);
        Account b = accounts.findById(to);
        a.setBalance(a.getBalance() - amount);
        b.setBalance(b.getBalance() + amount);
        accounts.updateBalance(a);
        accounts.updateBalance(b);
    }
}
```

1.  An ordinary constructor injection of an ordinary bean. The bean is
    `AccountMapper$$Impl`, declared by the generated `LarkBatisMapperConfiguration`,
    which lands in your base package so `@SpringBootApplication`'s default
    `@ComponentScan` picks it up.

`@Transactional` works because `SpringLarkBatisSession.conn()` goes through
`DataSourceUtils`, which returns the connection already bound to the running transaction.
Spring owns the transaction and LarkBatis only asks for a connection, so `REQUIRES_NEW`,
`NESTED`, rollback rules and `readOnly = true` all behave exactly as they do for
`JdbcTemplate`. Sharing one transaction with `JdbcTemplate` or JPA works for the same
reason. [Spring Integration](../usage/spring.md) has the connection contract in full.

## 4 · Configure (optional)

```yaml title="application.yml"
larkbatis:
  max-sql-variants: 64                # distinct SQL texts per statement before a warning
  fail-on-unbounded-fragment: false   # true = throw instead; useful in staging
```

Both settings are about the operational cost of `${}`: statement caches are keyed by SQL
text, so a fragment whose value set is not bounded grows them without limit. See
[Configuration](../features/configuration.md).

## What the processor generated

```java title="LarkBatisMapperConfiguration.java"
@Generated("io.github.larkbatis.processor.LarkBatisProcessor")
@Configuration(proxyBeanMethods = false)   // (1)!
public class LarkBatisMapperConfiguration {

    @Bean
    public AccountMapper accountMapper(LarkBatisSession s) {
        return new AccountMapper$$Impl(s);
    }
}
```

1.  Required, not cosmetic. Left at its default of `true`, Spring builds a CGLIB
    subclass of this class at runtime, which is precisely the runtime bytecode generation
    LarkBatis exists to remove.

## When the defaults do not fit

| Situation | What to do |
|---|---|
| Mappers outside the scanned packages | `-Alarkbatis.springConfigPackage=com.example.app`, or `@Import(LarkBatisMapperConfiguration.class)` |
| You want to declare the mapper beans yourself | `-Alarkbatis.springConfig=false` |
| More than one `DataSource` | Declare one `SpringLarkBatisSession` per `DataSource` and write the `@Bean` methods yourself. The auto-configuration is `@ConditionalOnSingleCandidate`, so it backs off rather than guessing. Mark one `DataSource` `@Primary`, or suppress the generated class |

Per-mapper `DataSource` selection is deferred until a real service needs it.

## Spring AOT and native image

`@Bean AccountMapper accountMapper(LarkBatisSession s)` has a static return type, so
Spring AOT treats it like any other bean: no `getObjectType()` at runtime, no proxy hint,
no `reflect-config.json` for the mapper layer. `MapperFactoryBean` is the opposite case,
where the bean type is only known at runtime and what it returns is a JDK proxy.

Read on: [Spring Integration](../usage/spring.md) covers the Boot 3 / Boot 4 story, what
runs and what does not, and the properties in detail.
