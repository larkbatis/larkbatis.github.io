# Java Module System (JPMS)

Các artifact `larkbatis-annotations`, `larkbatis-runtime` và các thư viện Spring của LarkBatis được đóng gói dưới dạng **named module tường minh** (không phải automatic module), không gặp tình trạng split package.

| Artifact | Tên Module |
|---|---|
| `larkbatis-annotations` | `io.github.larkbatis.annotations` |
| `larkbatis-runtime` | `io.github.larkbatis.runtime` |
| `larkbatis-spring` | `io.github.larkbatis.spring` |
| `larkbatis-spring-boot-autoconfigure` | `io.github.larkbatis.spring.boot` |
| `larkbatis-spring-boot-starter` | `io.github.larkbatis.spring.boot.starter` |

`larkbatis-processor` chỉ chạy trong pha build và không xuất hiện trên runtime module path.

## Cấu hình `module-info.java`

```java title="module-info.java"
module com.example.app {
    requires io.github.larkbatis.runtime;             // (1)!
    requires static io.github.larkbatis.annotations;  // (2)!
    requires static java.compiler;                    // (3)!
}
```

1.  Cung cấp các class runtime mà code sinh ra cần dùng: `LarkBatisSession`, `JdbcCodec`, `RowReader`, `LarkBatisSql`.
2.  Annotations chỉ cần lúc biên dịch (retention `CLASS`).
3.  Annotation `@Generated` trong các file mã nguồn được sinh ra thuộc module `java.compiler`.

!!! failure "Lỗi: `package javax.annotation.processing is not visible`"

    Lỗi này xảy ra khi bạn quên khai báo `requires static java.compiler`. Hãy thêm chỉ thị này vào `module-info.java`.

## Những thứ bạn không cần cấu hình

- **Không cần `requires java.sql`**: `io.github.larkbatis.runtime` đã khai báo `requires transitive java.sql`, nên ứng dụng của bạn tự động nhìn thấy `Connection`, `ResultSet` và `PreparedStatement`.
- **Không cần `opens ...`**: LarkBatis hoàn toàn không dùng reflection lúc runtime, nên không cần mở package cho bất kỳ module nào.
- **Không cần `exports` mã nguồn sinh ra**: Code được sinh ra trong cùng package với mapper interface của bạn.

## Lưu ý về JDBC Driver

Một số JDBC driver (như H2) hoạt động dưới dạng automatic module và có thể yêu cầu thêm cấu hình phụ thuộc:

```java title="module-info.java"
module com.example.app {
    requires io.github.larkbatis.runtime;
    requires static io.github.larkbatis.annotations;
    requires static java.compiler;

    requires com.h2database;
    requires java.naming;     // Do JdbcDataSource của H2 implements javax.naming.Referenceable
}
```

## GraalVM Native Image

Tầng mapper của LarkBatis không sử dụng `Proxy.newProxyInstance()`, không dùng `Class.forName()` và không dùng `setAccessible()`. Do đó, bạn không cần khai báo reflection reachability metadata cho mappers khi biên dịch GraalVM native image.

!!! warning "Lưu ý kiểm thử thực tế"

    Mặc dù về mặt cấu trúc không có reflection, việc kiểm thử tích hợp đầy đủ quy trình build native image được lên kế hoạch trong mốc M5. Xem [Hiệu năng](../wiki/performance.md#native-image).

