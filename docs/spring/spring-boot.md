# Spring Boot Quick Start

You don't need `@MapperScan`, `SqlSessionFactoryBean`, or `SqlSessionTemplate`. Since generated mapper implementations are real classes with standard constructors, they are just normal Spring beans. The processor emits a `@Configuration` class with one `@Bean` method per mapper, and auto-configuration provides the shared `LarkBatisSession`.

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

1.  Preserves parameter names in bytecode so `#{id}` can find `id` during Gradle incremental builds. Without this, javac passes `arg0` to the processor instead. Spring Boot's starter parent already turns this on for constructor binding, so you might already have it. See [Troubleshooting](../usage/troubleshooting.md#what-the-flag-actually-does).

That's the entire setup. It works on **Spring Boot 3 and Spring Boot 4** from the same jar.

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

1.  Standard constructor injection of a normal bean. The bean is `AccountMapper$$Impl`, declared by the generated `LarkBatisMapperConfiguration` in your base package (which `@SpringBootApplication`'s default `@ComponentScan` picks up automatically).

`@Transactional` works out of the box because `SpringLarkBatisSession.conn()` delegates to `DataSourceUtils`, which returns the connection already participating in the active transaction. Spring manages the transaction while LarkBatis simply borrows the connection. That means `REQUIRES_NEW`, `NESTED`, custom rollback rules, and `readOnly = true` behave exactly as they do with `JdbcTemplate`. Sharing transactions with `JdbcTemplate` or JPA works for the same reason. See [Spring Integration](spring.md) for details.

## 4 · Configuration

Unlike `mybatis-spring-boot-starter`, LarkBatis **does not use** `application.yml` for mapper locations or MyBatis settings. Because SQL is resolved at compile time, Spring never sees your XML files.

### Runtime properties (`application.yml`)
You only configure runtime monitoring here:

```yaml title="application.yml"
larkbatis:
  max-sql-variants: 64                # distinct SQL strings per statement before warning
  fail-on-unbounded-fragment: false   # throw exception instead of warning
```

Both settings help monitor the operational cost of `${}`. See [Configuration](../features/configuration.md) for details.

### Build-time properties (XML & Settings)
If you need to change where XML mappers are loaded from, or if you need to set global MyBatis options (like `mapUnderscoreToCamelCase`), you configure the build plugin instead:

=== "Gradle (`build.gradle.kts`)"
    ```kotlin
    larkbatis {
        mapperDir = layout.projectDirectory.dir("src/main/resources/mapper") // (1)!
        mapUnderscoreToCamelCase = true
    }
    ```

=== "Maven (`pom.xml`)"
    ```xml
    <configuration>
      <mapperDir>src/main/resources/mapper</mapperDir> <!-- 1 -->
      <mapUnderscoreToCamelCase>true</mapUnderscoreToCamelCase>
    </configuration>
    ```

1. LarkBatis already defaults to `src/main/resources`. You only need to set this if your XML files are somewhere else.

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

1.  This is required, not cosmetic. If left at the default `true`, Spring creates a CGLIB subclass at runtime—which is the exact kind of runtime bytecode generation LarkBatis is built to eliminate.

## Customizing defaults

| Scenario | What to do |
|---|---|
| Mappers outside scanned packages | `-Alarkbatis.springConfigPackage=com.example.app`, or `@Import(LarkBatisMapperConfiguration.class)` |
| Declare mapper beans manually | `-Alarkbatis.springConfig=false` |
| Multiple `DataSource` beans | Define a `SpringLarkBatisSession` per `DataSource` and write mapper `@Bean` definitions manually. Auto-configuration uses `@ConditionalOnSingleCandidate` and backs off when multiple datasources exist without a `@Primary` bean |

## Spring AOT and native image

Because `@Bean AccountMapper accountMapper(LarkBatisSession s)` has a static return type, Spring AOT treats it like any standard bean: no runtime `getObjectType()` inspection, no proxy hints, and no `reflect-config.json` needed for the mapper layer.

See [Spring Integration](spring.md) for full details on Spring Boot 3 / 4 support and available properties.
