# Khởi động nhanh

Năm phút từ một project rỗng tới một mapper chạy được. Đây là đường JDBC thuần: không
Spring, không XML. Mọi thứ ở đây lấy từ module `larkbatis-sample` của repository lõi,
cũng chính là đối tượng của bài kiểm tra native-image.

## 1 · Một lớp kết quả

Một Java bean bình thường: constructor không tham số và các setter. Không có lớp cha,
không annotation, và không interface nào phải hiện thực.

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

Tên cột được ánh xạ sang property theo quy ước `snake_case` → `camelCase`, luôn luôn áp
dụng **lúc build**. `created_at` tìm ra `setCreatedAt`. Chỗ nào quy ước đó không đủ thì
đặt alias cho cột trong select list hoặc khai báo một
[`<resultMap>`](../usage/result-maps.md).

## 2 · Một interface mapper

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

Không cần đánh dấu `@Mapper`: một interface có annotation statement thì processor tự tìm
ra. Cái đánh dấu đó tồn tại cho những interface mà toàn bộ statement nằm trong
[mapper XML](../usage/xml-mappers.md), vì nếu không thì chúng chẳng bao giờ lọt vào một
vòng xử lý nào.

## 3 · Biên dịch

```console
$ ./gradlew compileJava
```

Ba file xuất hiện ngay cạnh mã nguồn của bạn, trong cùng package:

| File sinh ra | Là gì |
|---|---|
| `UserMapper$$Impl` | Phần hiện thực. JDBC thuần, mỗi statement một phương thức |
| `UserRow` | Row reader cho `User`. Mỗi lớp kết quả một cái, dùng chung cho mọi statement trả về nó |
| `LarkBatisMappers` | Factory tĩnh cho mọi mapper trong lần biên dịch |

Chúng là file mã nguồn thật, và việc đọc chúng là một phần của thiết kế. Xem
[Code sinh ra](../wiki/generated-code.md).

!!! tip "Nếu chẳng có gì được sinh ra"

    Kiểm tra xem `larkbatis-processor` có nằm ở `annotationProcessor` không (chứ không
    phải `implementation`), và bạn có đang biên dịch bằng javac không. Xem
    [Xử lý sự cố](../usage/troubleshooting.md).

## 4 · Ráp lại và chạy

`LarkBatisSession` là thứ duy nhất một mapper sinh ra cần tới: một cách mượn
`Connection`, một cách trả nó lại, và việc dịch exception. Bản hiện thực độc lập nhận
vào một `DataSource`.

```java title="SampleApp.java"
package com.example.app;

import io.github.larkbatis.runtime.JdbcLarkBatisSession;
import io.github.larkbatis.runtime.LarkBatisTx;
import java.time.Instant;
import javax.sql.DataSource;

public class SampleApp {

    public static void main(String[] args) {
        DataSource ds = /* HikariCP, H2, bất cứ thứ gì bạn đang dùng */;

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

        System.out.println(u.getId());              // được điền nhờ useGeneratedKeys
        System.out.println(mapper.findById(u.getId()));
        System.out.println(mapper.countByName("A%"));
    }
}
```

`session.begin()` mở một phạm vi transaction dành cho try-with-resources. `commit()` là
một lá **phiếu**: việc commit thật sự chỉ xảy ra khi phạm vi ngoài cùng đóng lại, và rời
khỏi bất kỳ phạm vi nào mà không bỏ phiếu sẽ đánh dấu cả transaction là chỉ-rollback.
Xem [Transaction](../usage/transactions.md).

## 5 · Đọc thứ vừa được sinh ra

Mở `UserMapper$$Impl.java` trong IDE. Câu SQL là một `static final String` với dấu `?`
ở chỗ trước kia là `#{}`, các tham số được gắn theo thứ tự, và dòng dữ liệu được đọc
theo vị trí vì bộ sinh code phân tích được select list:

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

```java title="UserRow.java (trích)"
public static User read(ResultSet rs) throws SQLException {
    User u = new User();
    u.setId(rs.getLong(1));
    u.setName(rs.getString(2));
    u.setEmail(rs.getString(3));
    u.setCreatedAt(JdbcCodec.instant(rs, 4));
    return u;
}
```

Mọi chỉ số cột và mọi accessor đều đã được chọn lúc build. Không có chỗ nào ở đây đi soi
kiểu, resolve tên property hay tra một registry nào cả.

!!! note "Connection cố ý không nằm trong try-with-resources"

    Chỉ `s.release(c)` mới biết được connection đó có thực sự được phép đóng hay không.
    Dưới một transaction có quản lý (của Spring hoặc của chính LarkBatis), nó thuộc về
    transaction và đóng nó là sai. Hình dạng này là một
    [lằn ranh thiết kế](../wiki/design-rules.md), không phải sơ suất.

## Đi tiếp từ đâu

- Statement có bộ lọc tuỳ chọn → [SQL động](../usage/dynamic-sql.md)
- `WHERE id IN (...)` và insert theo batch → [foreach và batch](../usage/foreach-and-batches.md)
- Join cha với con → [Result map và join](../usage/result-maps.md)
- Tập kết quả quá lớn để nhét vào `List` → [Stream kết quả](../usage/streaming.md)
- Dùng Spring Boot thay cho `main()` → [Spring Boot](spring-boot.md)
