# Tích hợp Spring

Một nửa `mybatis-spring` bốc hơi ở đây, và biết *nửa nào* thì hiểu được toàn bộ phần tích
hợp. `mybatis-spring` tồn tại để giải đúng hai bài toán:

1. **Một mapper là interface không có phần hiện thực**, nên Spring không tạo bean cho nó
   được. Giải bằng `@MapperScan` → `ClassPathMapperScanner` → `MapperFactoryBean` →
   `MapperProxy`.
2. **`SqlSession` phải dùng chung `Connection` với `@Transactional`.** Giải bằng
   `SqlSessionTemplate` + `SqlSessionUtils` + `SpringManagedTransaction`.

**Bài toán 1 ở đây không còn là bài toán.** `AccountMapper$$Impl` là một lớp thật với
constructor thật, tức là một bean bình thường. Bộ quét, `FactoryBean` và phần hậu xử lý
`BeanDefinition` đều biến mất, thay bằng một `@Configuration` được sinh ra với mỗi mapper
một phương thức `@Bean`.

**Bài toán 2 thì không đụng tới**, và nó gần như là toàn bộ nội dung của phần tích hợp.

## Các module

| Module | Vai trò |
|---|---|
| `larkbatis-spring` | `SpringLarkBatisSession`: connection qua `DataSourceUtils`, dịch exception qua `SQLExceptionTranslator` |
| `larkbatis-spring-boot-autoconfigure` | `LarkBatisAutoConfiguration`, `LarkBatisProperties`, mục trong `AutoConfiguration.imports` |
| `larkbatis-spring-boot-starter` | Rỗng; chỉ có phụ thuộc |

## `SpringLarkBatisSession`

Quy tắc duy nhất mà lớp này sinh ra để cưỡng chế:

```java
@Override
public Connection conn() {
    return DataSourceUtils.getConnection(dataSource);   // không bao giờ dataSource.getConnection()
}
```

`DataSourceUtils` trả về đúng connection đã gắn vào transaction đang chạy, và chỉ mở một
connection mới khi chưa có cái nào. `release()` làm ngược lại: lệnh rỗng khi ở
trong transaction, một lần đóng thật khi ở ngoài. Vì vậy các thân phương thức sinh ra giữ
`Connection` nằm ngoài try-with-resources. Xem
[Vì sao code sinh ra không bao giờ đóng Connection](transactions.md#why-generated-code-never-closes-the-connection).

Lớp này không giữ trạng thái gì ngoài hai cộng tác viên của nó và dùng chung giữa các
luồng được. Mỗi `DataSource` một bean.

Việc dịch exception đi qua `SQLExceptionTranslator` của Spring, mặc định là
`SQLExceptionSubclassTranslator` (cũng là mặc định của chính Spring từ 6.0). Bộ dịch này
đọc cây lớp con `SQLException` chuẩn chứ không dùng bảng mã lỗi riêng theo từng hãng. Nhờ
vậy các handler `DuplicateKeyException` sẵn có của bạn vẫn chạy nguyên.

## Cái gì chạy và cái gì không

| Tình huống | | Vì sao |
|---|---|---|
| `@Transactional` trên service, mapper được gọi bên trong | chạy | `DataSourceUtils` trả về connection của transaction |
| `REQUIRES_NEW`, `NESTED`, các quy tắc rollback | chạy | Spring lo hết |
| `readOnly = true` | chạy | Spring đặt cờ đó lên connection |
| Mapper được gọi ngoài mọi transaction | chạy | Auto-commit; `release` đóng nó ngay |
| Phương thức mapper trả về `Stream` | chạy | Stream giữ một connection của pool cho tới khi đóng; trong transaction thì `release` là lệnh rỗng. Dùng `try (Stream<T> …)` trong mọi trường hợp |
| Chia sẻ transaction với `JdbcTemplate` hoặc JPA | chạy | Cùng `DataSourceUtils`, cùng `DataSourceTransactionManager` |
| Spring AOP trên một bean mapper | chạy | Mapper là một bean thật |
| `ExecutorType.BATCH` của MyBatis | không có | Làm gì có executor. Batch là một [chữ ký phương thức](foreach-and-batches.md#jdbc-batches) |
| Plugin / interceptor của MyBatis | không có | Bỏ theo thiết kế |

## Các property

```yaml
larkbatis:
  max-sql-variants: 64                # số câu SQL khác nhau cho mỗi statement trước khi cảnh báo
  fail-on-unbounded-fragment: false   # true = ném lỗi thay vì một cảnh báo
```

Cả hai đều xoay quanh cái giá vận hành của `${}`: statement cache được đánh khoá bằng văn
bản SQL, nên một fragment có tập giá trị không bị chặn sẽ làm chúng phình ra vô hạn. Xem
[SQL thô](raw-sql.md#tracking-sql-variants).

!!! note "`log-sql` chưa được hiện thực"

    Nó xuất hiện trong danh sách property của tài liệu thiết kế nhưng không được hiện
    thực. Mọi thân phương thức sinh ra sẽ phải mang thêm một nhánh ghi log, mà hình dạng
    sinh ra thì không có nhánh nào như vậy. Việc ghi log SQL thuộc về driver hoặc pool
    (`net.ttddyy:datasource-proxy`, p6spy) cho tới khi có lý do đổi điều đó.

## Khi mặc định không vừa

| Tình huống | Làm gì |
|---|---|
| Mapper nằm ngoài các package được quét | `-Alarkbatis.springConfigPackage=com.example.app`, hoặc `@Import(LarkBatisMapperConfiguration.class)` |
| Bạn muốn tự khai báo các bean mapper | `-Alarkbatis.springConfig=false` |
| Có nhiều hơn một `DataSource` | Khai báo mỗi `DataSource` một `SpringLarkBatisSession` rồi tự viết các phương thức `@Bean` cho mapper |

Về chuyện nhiều data source: `@ConditionalOnSingleCandidate` khiến auto-configuration lùi
hẳn lại thay vì đoán mò, còn `@Configuration` sinh ra thì nhận đúng một
`LarkBatisSession`, nên hãy đánh dấu một cái là `@Primary`, hoặc tắt lớp sinh ra bằng
tuỳ chọn ở trên. Việc chọn `DataSource` theo từng mapper được **để lại**: chưa thiết kế
khi chưa có một service thật cần đến nó.

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
