# Mapper Interfaces

Mapper trong LarkBatis là một Java interface thông thường. Không cần kế thừa interface cha, không cần bọc dynamic proxy lúc runtime.

Khi biên dịch, processor sinh ra class `final class UserMapper$$Impl implements UserMapper` với constructor công khai nhận `LarkBatisSession`.

## Annotations Statement

| Annotation | Loại Statement |
|---|---|
| `@Select` | `SELECT` |
| `@Insert` | `INSERT` |
| `@Update` | `UPDATE` |
| `@Delete` | `DELETE` |

Nhận mảng `String[]`, các dòng được tự động ghép nối bằng một dấu cách đơn:

```java
@Select({
    "SELECT id, name, email, created_at",
    "FROM users",
    "WHERE email = #{email}"
})
User findByEmail(String email);
```

Mapper interface chứa ít nhất một statement annotation sẽ được processor tự động nhận diện. Bạn chỉ cần thêm [`@Mapper`](../features/annotations.md#mapper) khi toàn bộ statement nằm trong [file XML](xml-mappers.md).

## Liên kết tham số qua `#{}`

Cú pháp `#{name}` được chuyển đổi thành ký tự giữ chỗ `?` trong JDBC `PreparedStatement` và sinh lệnh `ps.setXxx` tương ứng:

=== "Phương thức 1 tham số"

    Tham số là kiểu nguyên thủy, wrapper hoặc một Java Bean chứa getter:

    ```java
    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);

    @Insert("INSERT INTO users (name, email) VALUES (#{name}, #{email})")
    int insert(User u);          // #{name} -> u.getName()
    ```

=== "Phương thức nhiều tham số"

    Mỗi tham số cần có tên đối chiếu (tên biến trong code hoặc đặt qua `@Param`):

    ```java
    @Select("SELECT id, name FROM users WHERE name LIKE #{pattern} AND id > #{after}")
    List<User> page(@Param("pattern") String pattern, @Param("after") long after);
    ```

=== "Đường dẫn thuộc tính lồng nhau (Dot notation)"

    Truy cập getter lồng nhau và được kiểm tra kiểu tĩnh lúc build:

    ```java
    @Select("SELECT id FROM users WHERE email = #{probe.email}")
    List<User> byProbe(@Param("probe") User probe);
    ```

!!! warning "Lưu ý về cờ `-parameters`"

    Gradle incremental build có thể chạy processor trên file `.class`. Hãy bật cờ `-parameters` trong cấu hình biên dịch hoặc khai báo `@Param` để tránh việc tên tham số bị đổi thành `arg0`.

Tên tham số không tồn tại sẽ **báo lỗi biên dịch ngay lập tức**. Không hỗ trợ kiểu `Map` hoặc `Object` không định kiểu.

## Các kiểu trả về hỗ trợ

| Chữ ký phương thức | Mã nguồn sinh ra |
|---|---|
| `User findById(long)` | `rs.next() ? UserRow.read(rs) : null` |
| `List<User> findAll()` | Đọc tuần tự toàn bộ ResultSet vào danh sách `List` |
| `Stream<User> streamAll()` | Trả về con trỏ mở `Stream<User>` (caller chịu trách nhiệm đóng stream). Xem [Streaming](streaming.md) |
| `long countByName(String)` | Đọc trực tiếp giá trị kiểu `long` từ cột 1 |
| `int insert(User)` | `ps.executeUpdate()` trả về số dòng bị ảnh hưởng |
| `void delete(long)` | `ps.executeUpdate()` bỏ qua kết quả |

## Định nghĩa POJO Result Class

POJO kết quả chỉ cần constructor không tham số và các hàm getter/setter tương ứng:

```java
public class User {
    private long id;
    private String name;
    private Instant createdAt;

    // Getters and Setters
}
```

Tên cột được tự động ánh xạ sang setter theo quy tắc `snake_case` → `camelCase` lúc biên dịch (ví dụ cột `created_at` tự động gọi `setCreatedAt()`).

Nếu tên cột không thể tự khớp, bạn có thể:
1. Đặt alias trong câu SQL: `SELECT user_name AS name ...`
2. Gắn [`@Column("user_name")`](../features/annotations.md#column) trên field hoặc getter/setter.
3. Khai báo [`<resultMap>`](result-maps.md).

### Đọc dữ liệu: Vị trí cột vs. Tên cột { #positional-or-name-based-reads }

- **Đọc theo vị trí cột (Positional read)**: Khi câu `SELECT` liệt kê danh sách cột rõ ràng, processor sinh các lệnh đọc trực tiếp theo index tĩnh (`rs.getLong(1)`, `rs.getString(2)`).
- **Fallback đọc theo tên cột (Name-based fallback)**: Khi câu lệnh là `SELECT *` hoặc chứa chuỗi `${}` trong select list, processor giải quyết index cột từ `ResultSetMetaData` **một lần duy nhất ở dòng đầu tiên**, các dòng tiếp theo vẫn đọc theo vị trí.

## Phương thức `default` trong Mapper

Bạn có thể viết các phương thức `default` trực tiếp trong mapper interface để thực hiện truy vấn tùy biến hoặc nghiệp vụ bổ sung:

```java
default List<User> recent(LarkBatisSession s, int limit) {
    return s.query(
            SqlFragment.unsafeRawSql(
                    "SELECT id, name, email, created_at FROM users"
                            + " ORDER BY created_at DESC LIMIT " + limit),
            ps -> { },
            UserRow.READER);   // Tái sử dụng UserRow.READER sinh sẵn không cần reflection
}
```

## Factory Registry `LarkBatisMappers`

Tất cả các mapper được tổng hợp trong class factory tĩnh `LarkBatisMappers`:

```java
UserMapper mapper = LarkBatisMappers.userMapper(session);
```

Khi tích hợp Spring Boot, class `@Configuration` sinh ra sẽ tự động inject các mapper bean mà bạn không cần gọi factory này thủ công.

