# Khởi động nhanh với Spring Boot

Không có `@MapperScan`, không `SqlSessionFactoryBean` và không `SqlSessionTemplate`.
Phần hiện thực của một mapper là một lớp thật với constructor thật, nên nó là một bean
bình thường. Processor phát ra một `@Configuration` với mỗi mapper một phương thức
`@Bean`, còn auto-configuration thì cung cấp cái `LarkBatisSession` duy nhất mà các
phương thức đó yêu cầu.

## 1 · Phụ thuộc

```kotlin title="build.gradle.kts"
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-jdbc")
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0-SNAPSHOT")
    implementation("io.github.larkbatis:larkbatis-spring-boot-starter:0.1.0-SNAPSHOT")
    annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0-SNAPSHOT")

    runtimeOnly("com.h2database:h2")
}

tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.add("-parameters")   // (1)!
}
```

1.  Giữ lại tên tham số thật trong file class, để `#{id}` vẫn tìm ra `id` ở một bản build
    incremental của Gradle. Thiếu nó, processor có thể chỉ thấy `arg0` và không xử lý được
    chỗ gắn tham số. Starter parent của chính Spring Boot cũng đặt đúng cờ này cho phần
    constructor binding, nên dòng này thường đã có sẵn.
    [Xử lý sự cố](../usage/troubleshooting.md#what-the-flag-actually-does) có phần chi tiết.

Chỉ có vậy. Cùng một jar chạy được trên **cả Spring Boot 3 lẫn Spring Boot 4**.

## 2 · Một mapper

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

## 3 · Inject nó vào

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

1.  Một lần inject qua constructor bình thường cho một bean bình thường. Bean đó là
    `AccountMapper$$Impl`, được khai báo bởi lớp `LarkBatisMapperConfiguration` sinh ra,
    lớp này nằm trong base package của bạn nên `@ComponentScan` mặc định của
    `@SpringBootApplication` nhặt được nó.

`@Transactional` hoạt động vì `SpringLarkBatisSession.conn()` đi qua
`DataSourceUtils`, và hàm đó trả về đúng connection đã được gắn vào transaction đang
chạy. `REQUIRES_NEW`, `NESTED`, các quy tắc rollback và `readOnly = true` đều hành xử y
hệt như với `JdbcTemplate`: Spring sở hữu transaction, LarkBatis chỉ đi xin một
connection. Chia sẻ chung một transaction với `JdbcTemplate` hay JPA cũng hoạt động vì
đúng lý do đó.

## 4 · Cấu hình (tuỳ chọn)

```yaml title="application.yml"
larkbatis:
  max-sql-variants: 64                # số câu SQL khác nhau cho mỗi statement trước khi cảnh báo
  fail-on-unbounded-fragment: false   # true = ném lỗi luôn; hữu ích ở môi trường staging
```

Cả hai thiết lập đều xoay quanh cái giá vận hành của `${}`: statement cache được đánh
khoá bằng chính câu SQL, nên một fragment mà tập giá trị không bị chặn sẽ làm cache
phình ra vô hạn. Xem [Cấu hình](../features/configuration.md).

## Processor đã sinh ra cái gì

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

1.  Đây là bắt buộc, không phải cho đẹp. Giá trị mặc định `true` khiến Spring dựng một
    lớp con CGLIB của lớp này lúc chạy, đúng thứ sinh bytecode lúc chạy mà
    LarkBatis sinh ra để loại bỏ.

## Khi mặc định không vừa

| Tình huống | Làm gì |
|---|---|
| Mapper nằm ngoài các package được quét | `-Alarkbatis.springConfigPackage=com.example.app`, hoặc `@Import(LarkBatisMapperConfiguration.class)` |
| Bạn muốn tự khai báo các bean mapper | `-Alarkbatis.springConfig=false` |
| Có nhiều hơn một `DataSource` | Khai báo mỗi `DataSource` một `SpringLarkBatisSession` và tự viết các phương thức `@Bean`. Auto-configuration mang `@ConditionalOnSingleCandidate`, nên nó lùi lại chứ không đoán mò. Hãy đánh dấu một `DataSource` là `@Primary`, hoặc tắt lớp được sinh ra |

Việc chọn `DataSource` theo từng mapper được cố ý để lại: chưa thiết kế khi chưa có một
service thật cần đến nó.

## Spring AOT và native image

`@Bean AccountMapper accountMapper(LarkBatisSession s)` có kiểu trả về tĩnh, nên Spring
AOT đối xử với nó như mọi bean khác: không cần `getObjectType()` lúc chạy, không hint
proxy, không `reflect-config.json` cho tầng mapper. `MapperFactoryBean` là trường hợp
ngược lại: kiểu của bean chỉ biết được lúc chạy, và thứ nó trả về là một JDK proxy.

Đọc tiếp: [Tích hợp Spring](../usage/spring.md) nói về câu chuyện Boot 3 / Boot 4, cái
gì chạy và cái gì không, cùng chi tiết các property.
