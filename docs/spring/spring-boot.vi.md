# Tích hợp với Spring Boot

Với LarkBatis, bạn không cần `@MapperScan`, không cần `SqlSessionFactoryBean`, và không cần `SqlSessionTemplate`. Mỗi mapper là một class Java cụ thể với constructor công khai, nên Spring quản lý chúng như các bean thông thường.

Processor tự động sinh ra class `@Configuration` chứa các phương thức `@Bean` tương ứng cho từng mapper, và Spring Boot Starter tự động cung cấp `LarkBatisSession`.

## 1. Cấu hình Dependencies

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

1.  Lưu tên tham số phương thức vào class file để các bản build incremental của Gradle không bị mất tên tham số `#{id}`.

Cùng một starter jar tương thích trên **cả Spring Boot 3 và Spring Boot 4**.

## 2. Định nghĩa Mapper Interface

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

## 3. Inject vào Spring Service

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

1.  Constructor injection tiêu chuẩn. Bean thực thi là `AccountMapper$$Impl`, được cấu hình trong class `LarkBatisMapperConfiguration` sinh ra tại base package.

Annotation `@Transactional` hoạt động mượt mà vì `SpringLarkBatisSession.conn()` gọi `DataSourceUtils.getConnection(dataSource)`, tự động liên kết với connection đang hoạt động của Spring Transaction Manager. Mọi cơ chế propagation (`REQUIRES_NEW`, `NESTED`), rollback rules và `readOnly = true` đều hoạt động tương tự như khi sử dụng `JdbcTemplate`.

## 4. Cấu hình

Khác với `mybatis-spring-boot-starter`, LarkBatis **không dùng** `application.yml` để trỏ đường dẫn file XML hay cấu hình MyBatis. Vì SQL được xử lý triệt để lúc biên dịch, Spring ở runtime hoàn toàn không biết đến sự tồn tại của mapper XML.

### Cấu hình Runtime (`application.yml`)
Bạn chỉ dùng file này để thiết lập các cờ giám sát runtime:

```yaml title="application.yml"
larkbatis:
  max-sql-variants: 64                # Ngưỡng cảnh báo số lượng biến thể SQL động
  fail-on-unbounded-fragment: false   # Ném exception thay vì log cảnh báo (khuyến khích bật trên staging)
```

Xem chi tiết tại [Cấu hình](../features/configuration.md).

### Cấu hình Build-time (XML Mapper)
Nếu file XML của bạn không nằm ở `src/main/resources` (mặc định), hoặc bạn cần bật các tính năng như `mapUnderscoreToCamelCase`, hãy khai báo trực tiếp vào build plugin:

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

1. LarkBatis mặc định đã quét `src/main/resources`. Bạn chỉ cần khai báo thuộc tính này nếu để XML ở thư mục khác.

## Mã nguồn Spring Configuration được sinh ra

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

1.  `proxyBeanMethods = false` ngăn chặn Spring tạo class CGLIB proxy lúc runtime.

## Tùy biến cấu hình nâng cao

| Nhu cầu | Giải pháp |
|---|---|
| Mapper nằm ngoài package quét mặc định | Thêm `-Alarkbatis.springConfigPackage=com.example.app` hoặc khai báo `@Import(LarkBatisMapperConfiguration.class)` |
| Tự định nghĩa các bean mapper thủ công | Thêm cờ `-Alarkbatis.springConfig=false` để tắt sinh `@Configuration` tự động |
| Sử dụng nhiều DataSource | Khai báo một `SpringLarkBatisSession` cho từng `DataSource` và tự viết các phương thức `@Bean` cho mapper tương ứng |

## Spring AOT và GraalVM Native Image

Phương thức `@Bean AccountMapper accountMapper(LarkBatisSession s)` có kiểu trả về tĩnh rõ ràng. Spring AOT phân tích và đăng ký bean trực tiếp mà không cần cấu hình reflection metadata hay JDK dynamic proxy hints.

Đọc tiếp: [Tích hợp Spring chi tiết](spring.md).

