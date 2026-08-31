# Tích hợp Spring

Khối lượng cấu hình phức tạp của `mybatis-spring` được giản lược tối đa trong LarkBatis. `mybatis-spring` vốn cần giải quyết hai bài toán:

1. **Interface mapper không có phần hiện thực**, khiến Spring không thể trực tiếp khởi tạo bean. Phải giải quyết qua `@MapperScan` → `ClassPathMapperScanner` → `MapperFactoryBean` → `MapperProxy`.
2. **`SqlSession` phải dùng chung `Connection` với `@Transactional`.** Phải giải quyết qua `SqlSessionTemplate` → `SqlSessionUtils` → `SpringManagedTransaction`.

**Bài toán 1 không còn tồn tại trong LarkBatis.** `AccountMapper$$Impl` là một class Java thông thường với constructor nhận `LarkBatisSession`, đóng vai trò như một Spring bean tiêu chuẩn. Toàn bộ cơ chế quét class, `FactoryBean` và xử lý `BeanDefinition` được thay thế bằng class `@Configuration` sinh sẵn với mỗi mapper là một phương thức `@Bean`.

**Bài toán 2 được giải quyết gọn gàng**, và đó là nội dung chính của tầng tích hợp Spring.

## Các module

| Module | Vai trò |
|---|---|
| `larkbatis-spring` | `SpringLarkBatisSession`: lấy connection qua `DataSourceUtils`, dịch ngoại lệ qua `SQLExceptionTranslator` |
| `larkbatis-spring-boot-autoconfigure` | `LarkBatisAutoConfiguration`, `LarkBatisProperties`, khai báo trong `AutoConfiguration.imports` |
| `larkbatis-spring-boot-starter` | Starter module quản lý dependency |

## `SpringLarkBatisSession`

Quy tắc lấy kết nối duy nhất mà class này thực thi:

```java
@Override
public Connection conn() {
    return DataSourceUtils.getConnection(dataSource);   // không bao giờ gọi trực tiếp dataSource.getConnection()
}
```

`DataSourceUtils` trả về đúng connection đang gắn với transaction Spring hiện tại và chỉ mở kết nối mới khi chưa có transaction nào. `release()` đóng vai trò ngược lại: là no-op khi ở trong transaction, và đóng kết nối thực sự khi ở ngoài transaction. Vì vậy các thân phương thức sinh ra luôn giữ `Connection` nằm ngoài khối try-with-resources. Xem [Vì sao code sinh ra không bao giờ đóng Connection](transactions.md#why-generated-code-never-closes-the-connection).

`SpringLarkBatisSession` là thread-safe và được đăng ký như một Spring bean duy nhất cho mỗi `DataSource`.

Việc dịch exception sử dụng `SQLExceptionTranslator` của Spring (mặc định là `SQLExceptionSubclassTranslator` từ Spring 6.0). Nhờ vậy, các exception nghiệp vụ như `DuplicateKeyException` hay `DataIntegrityViolationException` được ném ra nhất quán, giúp các `@ExceptionHandler` sẵn có của bạn hoạt động trơn tru.

## Khả năng tương thích tính năng

| Tình huống | Kết quả | Cơ chế hoạt động |
|---|---|---|
| `@Transactional` trên service | Hoạt động | `DataSourceUtils` trả về connection của transaction hiện tại |
| `REQUIRES_NEW`, `NESTED`, rollback rules | Hoạt động | Spring Transaction Manager xử lý toàn diện |
| `readOnly = true` | Hoạt động | Spring đặt cờ readOnly lên Connection |
| Mapper gọi ngoài transaction | Hoạt động | Chế độ auto-commit; `release` đóng kết nối ngay lập tức |
| Phương thức mapper trả về `Stream` | Hoạt động | Stream giữ connection cho tới khi đóng; trong transaction `release` là no-op; luôn dùng `try (Stream<T> …)` |
| Chia sẻ transaction với `JdbcTemplate` hoặc JPA | Hoạt động | Dùng chung `DataSourceUtils` và cùng một `PlatformTransactionManager` |
| Spring AOP trên bean mapper | Hoạt động | Mapper là Spring bean thông thường |
| `ExecutorType.BATCH` của MyBatis | Không có | Thay bằng [chữ ký phương thức batch](foreach-and-batches.md#jdbc-batches) |
| Plugin / interceptor của MyBatis | Không có | Đã lược bỏ; thay thế bằng Spring AOP trên bean mapper hoặc DataSource proxy. Xem [Công thức thay thế plugin](../features/mybatis-differences.md#what-replaces-a-plugin) |

## Cấu hình thuộc tính

```yaml
larkbatis:
  max-sql-variants: 64                # số câu SQL khác nhau cho mỗi statement trước khi cảnh báo
  fail-on-unbounded-fragment: false   # true = ném lỗi thay vì chỉ cảnh báo
```

Cả hai thuộc tính này giúp kiểm soát statement cache tránh bị phình to do `${}` hoặc `<foreach>`. Xem [SQL thô](raw-sql.md#tracking-sql-variants).

!!! note "Chưa hỗ trợ `log-sql` trực tiếp"

    Để ghi log SQL, hãy sử dụng giải pháp ở tầng DataSource hoặc Connection Pool (như `net.ttddyy:datasource-proxy`, p6spy). Điều này giúp thân phương thức sinh ra không phải gánh thêm rẽ nhánh ghi log không cần thiết.

## Tuỳ biến nâng cao

| Tình huống | Hướng xử lý |
|---|---|
| Mapper nằm ngoài package quét mặc định | `-Alarkbatis.springConfigPackage=com.example.app`, hoặc `@Import(LarkBatisMapperConfiguration.class)` |
| Tự khai báo bean mapper thủ công | `-Alarkbatis.springConfig=false` |
| Sử dụng nhiều `DataSource` | Khai báo mỗi `DataSource` một bean `SpringLarkBatisSession` và tự viết các phương thức `@Bean` khởi tạo mapper |

Khi có nhiều `DataSource`, `@ConditionalOnSingleCandidate` sẽ tự động tắt auto-configuration để tránh cấu hình nhầm lẫn. Bạn chỉ cần đánh dấu một DataSource là `@Primary` hoặc tự định nghĩa bean mapper tương ứng.

## Spring Boot 3 và Spring Boot 4

Một jar chạy trên cả hai, và điều đó đến từ một quyết định có chủ ý. Boot 4 đã dời
`DataSourceAutoConfiguration` khỏi `spring-boot-autoconfigure` sang module mới
`spring-boot-jdbc` và đổi tên package của nó:

| | Boot 3 | Boot 4 |
|---|---|---|
| `DataSourceAutoConfiguration` | `org.springframework.boot.autoconfigure.jdbc` | `org.springframework.boot.jdbc.autoconfigure` |
| `@AutoConfiguration`, `@ConditionalOn*` | `org.springframework.boot.autoconfigure(.condition)` | không đổi |
| `@ConfigurationProperties` | `org.springframework.boot.context.properties` | không đổi |

Vậy nên `LarkBatisAutoConfiguration` khai báo thứ tự bằng `afterName` và liệt kê **cả
hai** tên package.

!!! danger "Vì sao đây không phải chuyện thẩm mỹ"

    `after = DataSourceAutoConfiguration.class` biên dịch với Boot 3 sẽ không resolve được
    trên Boot 4, và phản ứng của Spring là loại luôn cả cái auto-configuration đó ra khỏi
    danh sách ứng viên: không bean, không cảnh báo. Chẳng có gì sai cho tới khi có
    thứ gì đó đi hỏi một `LarkBatisSession` và context không khởi động nổi.

    Một cái tên không khớp với gì cả thì đơn giản là bị bỏ qua, và chính điều đó khiến
    việc liệt kê cả hai là an toàn. Đã kiểm chứng bằng cách chuyển một service Boot 4.1
    thật; có một bài test khẳng định cả hai cái tên vẫn còn đó, bởi vì "đơn giản hoá" nó
    về lại một tham chiếu lớp sẽ tái tạo một lỗi không hề có triệu chứng.

## Spring AOT và native image

`@Bean AccountMapper accountMapper(LarkBatisSession s)` có kiểu trả về tĩnh, nên AOT đối
xử với nó như mọi bean khác: không `getObjectType()` lúc chạy, không hint proxy, không
`reflect-config.json` cho tầng mapper. `MapperFactoryBean` là trường hợp ngược lại:
kiểu của bean chỉ biết được lúc chạy và thứ nó trả về là một JDK proxy.

`proxyBeanMethods = false` trên `@Configuration` sinh ra là bắt buộc, không phải cho đẹp:
giá trị mặc định `true` khiến Spring dựng một lớp con CGLIB của lớp đó lúc chạy, đúng là thứ
sinh bytecode lúc chạy mà dự án này sinh ra để loại bỏ.

## Đăng ký

Auto-configuration đăng ký qua
`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`, không
phải `spring.factories`.
