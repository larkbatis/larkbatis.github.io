# Interface mapper

Một mapper là một interface Java bình thường. Không có kiểu cha, không có đánh dấu nào
trên phương thức ngoài chính annotation statement, và không có proxy lúc chạy. Bản build
phát ra một `final class UserMapper$$Impl implements UserMapper` với constructor public
nhận vào một `LarkBatisSession`.

## Annotation statement

| Annotation | Statement |
|---|---|
| `@Select` | `SELECT` |
| `@Insert` | `INSERT` |
| `@Update` | `UPDATE` |
| `@Delete` | `DELETE` |

Mỗi cái nhận `String[]`, nên một statement dài có thể viết thành nhiều dòng rồi được nối
lại bằng một dấu cách:

```java
@Select({
    "SELECT id, name, email, created_at",
    "FROM users",
    "WHERE email = #{email}"
})
User findByEmail(String email);
```

Một interface mang ít nhất một annotation statement thì tự nó được tìm ra. Chỉ thêm
[`@Mapper`](../features/annotations.md#mapper) khi statement nằm trong [XML](xml-mappers.md).

## Tham số và `#{}`

`#{name}` trở thành một dấu `?` trong prepared statement và một lời gọi `ps.setXxx` ở
đúng vị trí tương ứng. Việc `name` đối chiếu với cái gì thì phụ thuộc vào chữ ký phương
thức:

=== "Một tham số"

    Tên chính là tên tham số, hoặc một đường dẫn property đi vào bên trong nó.

    ```java
    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);

    @Insert("INSERT INTO users (name, email) VALUES (#{name}, #{email})")
    int insert(User u);          // #{name} -> u.getName()
    ```

=== "Nhiều tham số"

    Mỗi tham số cần một cái tên mà SQL dùng được: tên khai báo, hoặc `@Param`.

    ```java
    @Select("SELECT id, name FROM users WHERE name LIKE #{pattern} AND id > #{after}")
    List<User> page(@Param("pattern") String pattern, @Param("after") long after);
    ```

=== "Đường dẫn property"

    Đường dẫn có dấu chấm sẽ đi qua các getter, được resolve và kiểm tra kiểu ngay lúc
    build.

    ```java
    @Select("SELECT id FROM users WHERE email = #{probe.email}")
    List<User> byProbe(@Param("probe") User probe);
    ```

!!! warning "Hãy đặt tên tham số, hoặc biên dịch kèm `-parameters`"

    Biên dịch incremental của Gradle có thể chạy lại processor trên **file class**, nơi
    tên tham số chỉ sống sót nếu lớp đó được biên dịch với `-parameters`. Thiếu cả hai
    thì `#{id}` chẳng còn gì để đối chiếu. Xem [Xử lý sự cố](troubleshooting.md).

Một cái tên không resolve được là **lỗi biên dịch**, nêu rõ tên phương thức và biểu thức
có vấn đề. Không có tham số kiểu `Map` hay `Object`: khi đó sẽ chẳng có kiểu nào để
đối chiếu `#{}` cả, mà toàn bộ ý đồ ở đây là lúc nào cũng phải có một kiểu như vậy.

## Kiểu trả về

| Chữ ký | Thân sinh ra |
|---|---|
| `User findById(long)` | `rs.next() ? UserRow.read(rs) : null` |
| `List<User> findAll()` | `while (rs.next()) out.add(UserRow.read(rs))` |
| `Stream<User> streamAll()` | Một con trỏ đang mở; người gọi phải đóng. Xem [Stream](streaming.md) |
| `long countByName(String)` | Cột 1, đọc dưới dạng `long` |
| `int insert(User)` | `ps.executeUpdate()` |
| `void delete(long)` | `ps.executeUpdate()`, bỏ kết quả |

Kết quả vô hướng đọc thẳng cột 1, không cần bean, không cần reader:

```java
@Select("SELECT COUNT(*) FROM users WHERE name LIKE #{pattern}")
long countByName(@Param("pattern") String pattern);
```

## Lớp kết quả

Một lớp kết quả cần constructor không tham số và các setter, ngoài ra không cần gì thêm:

```java
public class User {
    private long id;
    private String name;
    private Instant createdAt;
    // getter và setter
}
```

Tên cột được tự động ánh xạ sang property theo quy ước `snake_case` → `camelCase` **trực tiếp lúc build** (ví dụ `created_at` → `setCreatedAt`). Quy ước này mặc định được bật trong LarkBatis (trong khi MyBatis mặc định tắt). Nếu cần giữ nguyên hành vi của MyBatis, bạn có thể truyền cờ `-Alarkbatis.mapUnderscoreToCamelCase=false`. Ánh xạ này được biên dịch thẳng vào row reader sinh sẵn; hoàn toàn không có tuỳ chọn tra cứu lúc runtime. Xem [Cấu hình](../features/configuration.md#column-naming).

Trường hợp tên cột khác biệt hoặc quy ước trên không đáp ứng được, bạn có thể dùng [`@Column`](../features/annotations.md#column) đặt trực tiếp trên field, setter hoặc getter, hoặc đặt alias cho cột trong câu SELECT, hoặc khai báo [`<resultMap>`](result-maps.md). Xem [Kiểu dữ liệu và handler](types.md#column-naming).

### Đọc theo vị trí hay theo tên { #positional-or-name-based-reads }

Khi bộ sinh code phân tích được danh sách SELECT, chỉ số cột sẽ là các hằng số tĩnh:

```java
u.setId(rs.getLong(1));
u.setName(rs.getString(2));
```

Khi không thể phân tích cú pháp tĩnh danh sách SELECT (do `SELECT *`, chèn `${}` trong select list, hoặc biểu thức tính toán không đặt alias), statement đó sẽ sử dụng cơ chế fallback: đọc vị trí cột từ `ResultSetMetaData` **đúng một lần duy nhất ở dòng đầu tiên**, sau đó tiếp tục đọc dữ liệu theo vị trí cho các dòng còn lại. Cơ chế này đảm bảo tính chính xác và trình biên dịch sẽ thông báo rõ statement nào rơi vào trường hợp fallback. Xem [Code sinh ra](../wiki/generated-code.md#row-readers).

!!! note "`@LarkBatisRow`"

    Với những class không bao giờ xuất hiện làm `resultType` của statement nào (chẳng hạn class chỉ dùng cho [lối thoát thủ công](raw-sql.md#the-escape-hatch)), bạn hãy đánh dấu class đó bằng [`@LarkBatisRow`](../features/annotations.md#larkbatisrow) để kích hoạt sinh row reader. Thứ tự khai báo field trong class chính là thứ tự cột chuẩn.

## Phương thức `default`

Phương thức `default` trên interface mapper được giữ nguyên: javac biên dịch trực tiếp vào interface và class `$$Impl` sinh ra sẽ kế thừa phương thức đó. Đây là vị trí lý tưởng để viết các truy vấn SQL tuỳ biến:

```java
default List<User> recent(LarkBatisSession s, int limit) {
    return s.query(
            SqlFragment.unsafeRawSql(
                    "SELECT id, name, email, created_at FROM users"
                            + " ORDER BY created_at DESC LIMIT " + limit),
            ps -> { },
            UserRow.READER);
}
```

Các dòng dữ liệu vẫn được đọc an toàn qua `UserRow.READER` sinh sẵn: hoàn toàn không sử dụng reflection và kiểu kết quả luôn được javac kiểm tra kiểu tĩnh. Xem [SQL thô và SqlFragment](raw-sql.md).

## Registry sinh ra

Tất cả các mapper trong một lần biên dịch đều được tập hợp trong class static factory `LarkBatisMappers`:

```java
UserMapper mapper = LarkBatisMappers.userMapper(session);
```

`LarkBatisMappers` là một static factory cho tập hợp mapper cố định đã biết lúc compile. Không có phương thức `addMapper()` động lúc runtime vì mọi mapper đều đã được xác định trước. Khi dùng Spring Boot, bạn không cần gọi trực tiếp class này vì class `@Configuration` sinh ra sẽ tự động đăng ký các bean tương ứng.

Mặc định, registry nằm tại package prefix chung của các mapper; bạn có thể ghi đè vị trí này bằng cờ `-Alarkbatis.registryPackage=com.example.app`.
