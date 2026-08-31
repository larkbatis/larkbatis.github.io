# Tích hợp Spring Boot

Tích hợp Spring trong LarkBatis được thiết kế tối giản:
- Không dùng dynamic proxy runtime (`MapperProxy`).
- Không cần `@MapperScan` hay `MapperFactoryBean`.
- Processor tự động sinh class `@Configuration(proxyBeanMethods = false)` với các phương thức `@Bean` khởi tạo mapper trực tiếp.
- `SpringLarkBatisSession` quản lý kết nối an toàn qua `DataSourceUtils`.

## Các Artifact tích hợp

| Artifact | Nhiệm vụ |
|---|---|
| `larkbatis-spring` | `SpringLarkBatisSession`: lấy kết nối qua `DataSourceUtils`, dịch mã lỗi qua `SQLExceptionTranslator` |
| `larkbatis-spring-boot-autoconfigure` | `LarkBatisAutoConfiguration`, `LarkBatisProperties` |
| `larkbatis-spring-boot-starter` | Starter quản lý dependency tiện lợi |

## `SpringLarkBatisSession`

Class này đảm bảo mọi thao tác JDBC đều tham gia đúng transaction context của Spring:

```java
@Override
public Connection conn() {
    return DataSourceUtils.getConnection(dataSource);   // Không gọi trực tiếp dataSource.getConnection()
}
```

- **Trong Transaction**: `DataSourceUtils` trả về kết nối hiện tại của transaction; lệnh `release()` là no-op.
- **Ngoài Transaction**: Chế độ auto-commit; lệnh `release()` lập tức hoàn trả kết nối về Connection Pool.

Dịch mã lỗi cơ sở dữ liệu sử dụng `SQLExceptionTranslator` của Spring (mặc định là `SQLExceptionSubclassTranslator` từ Spring 6.0), chuyển đổi `SQLException` thành `DataAccessException` tương ứng (`DuplicateKeyException`, v.v.).

## Bảng tương thích tính năng

| Tính năng | Trạng thái | Cơ chế |
|---|---|---|
| `@Transactional` trên Service | Hoạt động | `DataSourceUtils` trả về connection của transaction hiện tại |
| `REQUIRES_NEW`, `NESTED`, rollback rules | Hoạt động | Do Spring PlatformTransactionManager quản lý |
| `readOnly = true` | Hoạt động | Tự động đặt cờ read-only trên JDBC Connection |
| Mapper gọi ngoài transaction | Hoạt động | Chế độ auto-commit, tự động đóng kết nối khi hoàn tất |
| Phương thức trả về `Stream<T>` | Hoạt động | Luôn bọc lời gọi trong `try (Stream<T> ...)` để giải phóng connection |
| Dùng chung transaction với `JdbcTemplate` | Hoạt động | Cùng truy cập connection qua `DataSourceUtils` |
| Spring AOP trên Mapper Bean | Hoạt động | Mapper là Spring Bean tiêu chuẩn |

## Tương thích Spring Boot 3 và Spring Boot 4

LarkBatis hỗ trợ đồng thời cả Spring Boot 3 và Spring Boot 4 trong cùng một file jar. `LarkBatisAutoConfiguration` sử dụng `afterName` để khai báo thứ tự sau `DataSourceAutoConfiguration` ở cả 2 tên package cũ và mới (`org.springframework.boot.autoconfigure.jdbc` và `org.springframework.boot.jdbc.autoconfigure`).

## Spring AOT và GraalVM Native Image

Phương thức `@Bean AccountMapper accountMapper(LarkBatisSession s)` có kiểu trả về tĩnh cụ thể. Spring AOT đối xử với nó như một bean thông thường: không cần JDK dynamic proxy, không cần reflection metadata cho interface mapper.

Class `@Configuration(proxyBeanMethods = false)` sinh sẵn đảm bảo Spring không tạo CGLIB subclass lúc runtime.

