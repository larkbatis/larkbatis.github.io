# Khởi động nhanh

Chỉ mất 5 phút để thiết lập một mapper hoàn chỉnh từ project rỗng. Đây là luồng JDBC thuần tuý: không phụ thuộc Spring, không cần XML. Toàn bộ ví dụ dưới đây được trích từ module `larkbatis-sample` trong repository lõi.

## 1 · Result Class

Một Java bean chuẩn: chỉ cần constructor không tham số và các setter tương ứng. Không kế thừa class cha, không cần annotation hay implement interface nào.

```java title="User.java"
package com.example.app;

import java.time.Instant;

public class User {

    private long id;
    private String name;
    private String email;
    private Instant createdAt;

    public long getId() { return id; }
    public void setId(long id) { this.id = id; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
```

Tên cột được tự động ánh xạ sang property theo quy ước `snake_case` → `camelCase` ngay lúc build (ví dụ `created_at` ánh xạ vào `setCreatedAt`). Trường hợp tên cột khác biệt, bạn có thể đặt alias trong câu SELECT hoặc khai báo [`<resultMap>`](../usage/result-maps.md).

## 2 · Interface Mapper

```java title="UserMapper.java"
package com.example.app;

import io.github.larkbatis.annotations.Insert;
import io.github.larkbatis.annotations.Options;
import io.github.larkbatis.annotations.Param;
import io.github.larkbatis.annotations.Select;
import java.util.List;

public interface UserMapper {

    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);

    @Select("SELECT id, name, email, created_at FROM users ORDER BY id")
    List<User> findAll();

    @Select("SELECT COUNT(*) FROM users WHERE name LIKE #{pattern}")
    long countByName(@Param("pattern") String pattern);

    @Insert("INSERT INTO users (name, email, created_at) VALUES (#{name}, #{email}, #{createdAt})")
    @Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
    int insert(User u);
}
```

Không bắt buộc khai báo `@Mapper`: interface có chứa annotation statement sẽ được processor tự động nhận diện. Annotation `@Mapper` chỉ cần thiết khi toàn bộ statement được khai báo trong [mapper XML](../usage/xml-mappers.md).

## 3 · Biên dịch

```console
$ ./gradlew compileJava
```

Ba tệp Java được sinh ra trong cùng package với mapper của bạn:

| Tệp sinh ra | Ý nghĩa |
|---|---|
| `UserMapper$$Impl` | Class triển khai cụ thể bằng JDBC thuần; mỗi statement tương ứng một phương thức |
| `UserRow` | Row reader cho `User`: sinh riêng cho từng result class và dùng chung cho mọi statement trả về class đó |
| `LarkBatisMappers` | Static factory khởi tạo tất cả mapper trong lần biên dịch |

Các tệp sinh ra là mã nguồn Java thực thụ, được thiết kế rõ ràng để lập trình viên có thể đọc hiểu và debug trực tiếp. Xem [Code sinh ra](../wiki/generated-code.md).

!!! tip "Nếu không có file nào được sinh ra"

    Hãy kiểm tra xem `larkbatis-processor` đã được khai báo trong `annotationProcessor` hay chưa (không phải `implementation`), và đảm bảo bạn đang biên dịch bằng `javac`. Xem [Xử lý sự cố](../usage/troubleshooting.md).

## 4 · Khởi chạy ứng dụng

`LarkBatisSession` là cầu nối duy nhất mà mapper sinh ra cần tới: cung cấp kết nối `Connection`, giải phóng kết nối và dịch exception. Bản triển khai độc lập nhận trực tiếp một `DataSource`.

```java title="SampleApp.java"
package com.example.app;

import io.github.larkbatis.runtime.JdbcLarkBatisSession;
import io.github.larkbatis.runtime.LarkBatisTx;
import java.time.Instant;
import javax.sql.DataSource;

public class SampleApp {

    public static void main(String[] args) {
        DataSource ds = /* HikariCP, H2, hoặc DataSource bạn đang sử dụng */;

        JdbcLarkBatisSession session = new JdbcLarkBatisSession(ds);
        UserMapper mapper = LarkBatisMappers.userMapper(session);

        User u = new User();
        u.setName("Ada");
        u.setEmail("ada@example.com");
        u.setCreatedAt(Instant.now());

        try (LarkBatisTx tx = session.begin()) {
            mapper.insert(u);
            tx.commit();
        }

        System.out.println(u.getId());              // được gán tự động nhờ useGeneratedKeys
        System.out.println(mapper.findById(u.getId()));
        System.out.println(mapper.countByName("A%"));
    }
}
```

`session.begin()` mở một scope transaction tương thích với try-with-resources. Lệnh `commit()` đóng vai trò bỏ phiếu (vote): commit thực sự chỉ diễn ra khi scope ngoài cùng đóng lại. Rời khỏi bất kỳ scope nào mà không commit sẽ tự động chuyển toàn bộ transaction sang trạng thái rollback-only. Xem [Transaction](../usage/transactions.md).

## 5 · Đọc mã nguồn sinh ra

Mở tệp `UserMapper$$Impl.java` trong IDE. Câu SQL là một hằng số `static final String` với dấu `?` thay thế cho `#{}`. Các tham số được gán theo thứ tự tĩnh và dữ liệu dòng được đọc theo vị trí cột:

```java
private static final String SQL_findById =
        "SELECT id, name, email, created_at FROM users WHERE id = ?";

@Override
public User findById(long id) {
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(SQL_findById)) {
        ps.setLong(1, id);
        try (ResultSet rs = ps.executeQuery()) {
            return rs.next() ? UserRow.read(rs) : null;
        }
    } catch (SQLException e) {
        throw s.translate(e, SQL_findById);
    } finally {
        s.release(c);
    }
}
```

```java title="UserRow.java (trích đoạn)"
public static User read(ResultSet rs) throws SQLException {
    User u = new User();
    u.setId(rs.getLong(1));
    u.setName(rs.getString(2));
    u.setEmail(rs.getString(3));
    u.setCreatedAt(JdbcCodec.instant(rs, 4));
    return u;
}
```

Mọi chỉ số cột và phương thức setter đều được định hình tĩnh lúc build. Hoàn toàn không phát sinh thao tác inspect kiểu dữ liệu, resolve tên property hay tra cứu registry lúc runtime.

!!! note "Connection cố ý không đặt trong try-with-resources"

    Chỉ `s.release(c)` mới xác định được connection có được phép đóng hay không. Khi chạy trong transaction có quản lý (Spring hoặc LarkBatis), connection thuộc quyền kiểm soát của transaction và việc tự ý đóng kết nối là sai lầm. Cấu trúc này là một [lằn ranh thiết kế](../wiki/design-rules.md) cốt lõi.

## Bước tiếp theo

- Câu lệnh có điều kiện lọc tuỳ chọn → [SQL động](../usage/dynamic-sql.md)
- `WHERE id IN (...)` và batch insert → [foreach và batch](../usage/foreach-and-batches.md)
- Join bảng cha - con quan hệ 1-N → [Result map và join](../usage/result-maps.md)
- Tập kết quả lớn cần đọc con trỏ → [Stream kết quả](../usage/streaming.md)
- Sử dụng với Spring Boot → [Spring Boot](spring-boot.md)
