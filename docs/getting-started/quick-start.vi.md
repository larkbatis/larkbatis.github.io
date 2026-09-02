# Hướng dẫn nhanh 5 phút

Chỉ mất khoảng 5 phút để xây dựng một mapper hoàn chỉnh từ đầu. Đây là ví dụ sử dụng JDBC thuần: không cần Spring, không cần file XML. Toàn bộ mã nguồn mẫu được lấy từ module `larkbatis-sample` trong repository.

## 1. Tạo Result Class

Một POJO Java tiêu chuẩn với constructor không tham số và các setter tương ứng:

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

Tên cột được tự động ánh xạ sang setter theo quy ước `snake_case` → `camelCase` lúc biên dịch (ví dụ cột `created_at` tự động gọi `setCreatedAt()`).

## 2. Khai báo Interface Mapper

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

Không bắt buộc phải thêm `@Mapper`: processor tự động nhận diện các interface có annotation `@Select`, `@Insert`, `@Update`, `@Delete`. Annotation `@Mapper` chỉ cần thiết khi bạn viết câu lệnh hoàn toàn trong [mapper XML](../usage/xml-mappers.md).

## 3. Biên dịch dự án

```console
$ ./gradlew compileJava
```

Trình biên dịch sẽ sinh ra 3 class Java trong cùng package với mapper của bạn:

| Class sinh ra | Vai trò |
|---|---|
| `UserMapper$$Impl` | Class triển khai cụ thể của mapper, chứa các lệnh gọi JDBC trực tiếp |
| `UserRow` | Chứa các phương thức tĩnh đọc `ResultSet` để ánh xạ dữ liệu thành đối tượng `User` |
| `LarkBatisMappers` | Factory tĩnh dùng để khởi tạo mapper instance |

Mã nguồn sinh ra là file Java thông thường, có thể đọc và đặt breakpoint debug trực tiếp. Xem [Mã nguồn sinh ra](../wiki/generated-code.md).

!!! tip "Nếu không thấy code được sinh ra"

    Kiểm tra xem `larkbatis-processor` đã được khai báo ở cấu hình `annotationProcessor` (Gradle) hay `<annotationProcessorPaths>` (Maven) chưa, và đảm bảo bạn đang biên dịch bằng `javac`. Xem [Khắc phục sự cố](../usage/troubleshooting.md).

## 4. Thực thi truy vấn

`LarkBatisSession` là đối tượng runtime duy nhất mà mapper cần: quản lý lấy/trả connection và dịch mã lỗi JDBC.

```java title="SampleApp.java"
package com.example.app;

import io.github.larkbatis.runtime.JdbcLarkBatisSession;
import io.github.larkbatis.runtime.LarkBatisTx;
import java.time.Instant;
import javax.sql.DataSource;

public class SampleApp {

    public static void main(String[] args) {
        DataSource ds = /* Khởi tạo HikariCP, H2 hoặc DataSource bất kỳ */;

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

        System.out.println(u.getId());              // ID tự động được gán nhờ useGeneratedKeys
        System.out.println(mapper.findById(u.getId()));
        System.out.println(mapper.countByName("A%"));
    }
}
```

`session.begin()` mở một scope transaction tương thích với `try`-with-resources. Lệnh `commit()` đóng vai trò bỏ phiếu (vote): commit vật lý xuống database chỉ diễn ra khi scope ngoài cùng kết thúc thành công. Xem [Transactions](../usage/transactions.md).

## 5. Xem mã nguồn được sinh ra

Bạn có thể mở trực tiếp file `UserMapper$$Impl.java` trong thư mục `build/` để kiểm tra:

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

```java title="UserRow.java"
public static User read(ResultSet rs) throws SQLException {
    User u = new User();
    u.setId(rs.getLong(1));
    u.setName(rs.getString(2));
    u.setEmail(rs.getString(3));
    u.setCreatedAt(JdbcCodec.instant(rs, 4));
    return u;
}
```

Mọi thứ—từ câu lệnh SQL, chỉ số cột trong `ResultSet`, cho đến kiểu dữ liệu tham số—đều được cố định sẵn từ lúc biên dịch.

!!! note "Lý do `Connection` không nằm trong `try`-with-resources"

    Việc đóng connection được uỷ quyền cho `s.release(c)`. Khi chạy trong một transaction (Spring `@Transactional` hoặc `LarkBatisTx`), connection thuộc sở hữu của transaction đó và không được tự ý đóng lại giữa chừng.

## Các chủ đề tiếp theo

- Xây dựng câu truy vấn điều kiện → [Dynamic SQL](../usage/dynamic-sql.md)
- Mệnh đề `WHERE id IN (...)` và batch insert → [foreach và Batching](../usage/foreach-and-batches.md)
- Join dữ liệu quan hệ 1-N → [Result Maps](../usage/result-maps.md)
- Truy vấn tập dữ liệu lớn qua con trỏ → [Streaming](../usage/streaming.md)
- Tích hợp Spring Boot → [Spring Boot](../spring/spring-boot.md)

