# Hướng dẫn sử dụng

Trong LarkBatis, bạn định nghĩa các câu truy vấn qua **mapper interface** (sử dụng annotation như `@Select`, `@Insert`...) hoặc **mapper XML** (đánh dấu interface với `@Mapper`). Cả hai cách đều được processor biên dịch thành cùng một lớp Java triển khai JDBC trực tiếp.

## Cấu trúc thư mục dự án

```text
src/main/java/com/example/app/
    User.java                 # POJO kết quả: constructor không tham số, các setter
    UserMapper.java           # Mapper interface sử dụng annotation
    UserSearchMapper.java     # Mapper interface sử dụng XML (gắn @Mapper)
src/main/resources/mappers/
    UserSearchMapper.xml      # namespace = com.example.app.UserSearchMapper
```

Khi biên dịch (`./gradlew compileJava` hoặc `mvn compile`), processor sinh ra các file Java trong cùng package:

```text
UserMapper$$Impl.java              # Lớp triển khai JDBC cho từng mapper interface
UserSearchMapper$$Impl.java
UserRow.java                       # Lớp đọc ResultSet cho từng POJO kết quả
LarkBatisMappers.java             # Factory khởi tạo các mapper
LarkBatisMapperConfiguration.java # Class @Configuration cho Spring (nếu có spring-context)
```

## Mục lục hướng dẫn

<div class="grid cards" markdown>

-   **[Mapper Interfaces](mappers.md)**

    Annotations truy vấn, liên kết tham số `#{}` / `${}`, `@Param`, POJO result classes và cơ chế ánh xạ cột sang setter.

-   **[Mapper XML](xml-mappers.md)**

    Khai báo `@Mapper`, cấu hình namespace, statement id, inlining `<sql>` / `<include>` và quy tắc ánh xạ phương thức.

-   **[Dynamic SQL](dynamic-sql.md)**

    Các thẻ `<if>`, `<choose>`, `<where>`, `<set>`, `<trim>` và ngữ pháp kiểm tra kiểu tĩnh an toàn.

-   **[foreach & Batching](foreach-and-batches.md)**

    Mệnh đề `WHERE IN`, `VALUES` nhiều dòng, JDBC batch `addBatch()`, tối ưu cache với `@PadPow2`.

-   **[Result Maps](result-maps.md)**

    Cấu hình `<resultMap>`, join 1 cấp (`<association>` / `<collection>`) và thuật toán gom nhóm single-pass.

-   **[Generated Keys](generated-keys.md)**

    Cấu hình `useGeneratedKeys`, tầm quan trọng của `keyColumn` và lấy khóa tự tăng trong batch insert.

-   **[Streaming](streaming.md)**

    Truy vấn tập dữ liệu lớn qua `Stream<T>` kết nối trực tiếp con trỏ database và quản lý tài nguyên an toàn.

-   **[Transactions](transactions.md)**

    Quản lý transaction độc lập qua `LarkBatisTx`, cơ chế vote-to-commit và tích hợp Spring `@Transactional`.

-   **[Raw SQL & An toàn](raw-sql.md)**

    Kỷ luật an toàn khi dùng `${}`, `@OrderBy`, lối thoát thủ công `SqlFragment` và theo dõi biến thể prepared statement.

-   **[Kiểu dữ liệu & Type Handlers](types.md)**

    Hệ thống kiểu dữ liệu hỗ trợ sẵn, `JdbcCodec`, `@Column`, custom `LarkBatisTypeHandler`, enum và `java.time`.

-   **[Tích hợp Spring](spring.md)**

    Cơ chế hoạt động của Spring Boot Starter, tương thích Spring Boot 3 & 4 và quản lý transaction qua `DataSourceUtils`.

-   **[Khắc phục sự cố](troubleshooting.md)**

    Chẩn đoán các lỗi thường gặp: processor không sinh code, lỗi tham số `arg0`, thứ tự nạp Lombok.

</div>

## Hai nguyên tắc thiết kế cốt lõi

1. **Giải quyết mọi thứ có thể lúc biên dịch**: Chỉ số cột trong `ResultSet`, lựa chọn setter, chuỗi SQL tĩnh, inlining `<include>` đều được chốt cố định lúc build. Mọi sai sót về kiểu dữ liệu hay cú pháp đều trở thành lỗi biên dịch `javac`.
2. **Kiểm soát chặt chẽ các giá trị runtime**: Danh sách các thành phần được đánh giá lúc runtime là cố định và đóng (tham số đầu vào, kết quả boolean của `<if>`, kích thước collection trong `<foreach>`, dữ liệu trả về từ database). Mọi chuỗi động ngoài danh sách này bắt buộc phải được bọc qua `SqlFragment` hoặc `@OrderBy`. Xem chi tiết tại [Shape vs. Value](../wiki/shape-vs-value.md).

