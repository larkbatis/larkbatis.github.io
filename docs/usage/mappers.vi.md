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
không annotation, không interface, không đăng ký.

```java
public class User {
    private long id;
    private String name;
    private Instant createdAt;
    // getter và setter
}
```

Cột tìm ra property theo `snake_case` → `camelCase`, **áp dụng lúc build**:
`created_at` → `setCreatedAt`. Mặc định là bật — MyBatis thì mặc định tắt — và
`-Alarkbatis.mapUnderscoreToCamelCase=false` mang mặc định của MyBatis sang. Lựa chọn
này được nướng thẳng vào reader sinh ra; không có tuỳ chọn runtime nào cho cả hai chiều.
Xem [Cấu hình](../features/configuration.md#column-naming).

Chỗ nào quy ước đó không đủ thì đặt tên cột ngay trên property bằng
[`@Column`](../features/annotations.md#column) trên field, setter hoặc getter, hoặc đặt
alias cho cột trong select list, hoặc khai báo một
[`<resultMap>`](result-maps.md). Xem [Kiểu dữ liệu và handler](types.md#column-naming).

### Đọc theo vị trí hay theo tên { #positional-or-name-based-reads }

Khi bộ sinh code phân tích được select list, chỉ số cột là hằng số:

```java
u.setId(rs.getLong(1));
u.setName(rs.getString(2));
```

Khi không phân tích được, riêng statement đó lùi về dùng reader theo tên: reader này lấy
chỉ số từ `ResultSetMetaData` **một lần duy nhất, ở dòng đầu tiên**, rồi đọc theo vị trí
cho phần còn lại. Có ba thứ làm nó không phân tích được: `SELECT *`, một chỗ chèn `${}`
nằm trong select list, và một biểu thức không đặt alias. Cách lùi này vẫn đúng, chậm hơn
ở mức đo được, và bản build sẽ cho bạn biết statement nào rơi vào trường hợp đó. Xem
[Code sinh ra](../wiki/generated-code.md#row-readers).

!!! note "`@LarkBatisRow`"

    Một lớp không bao giờ xuất hiện làm `resultType` của statement nào, chẳng hạn lớp
    chỉ dùng bởi [cửa thoát hiểm](raw-sql.md#the-escape-hatch), thì không có gì kích hoạt
    việc sinh reader cho nó. Đánh dấu nó bằng
    [`@LarkBatisRow`](../features/annotations.md#larkbatisrow) là có reader. Thứ tự
    khai báo của lớp chính là thứ tự cột chuẩn, bởi ở đây không có select list nào để
    lấy thứ tự ra cả.

## Phương thức `default`

Một phương thức `default` trên interface mapper được để yên: nó được biên dịch vào
interface như mọi phương thức khác, và lớp hiện thực sinh ra thừa kế nó. Đây là chỗ để
SQL ráp tay:

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

Để ý xem thứ gì vẫn an toàn kiểu ngay cả ở đây: các dòng vẫn được đọc bởi reader
`UserRow` **được sinh ra**, nên vẫn không có reflection nào và kiểu kết quả vẫn được
javac kiểm tra. Xem [SQL thô và SqlFragment](raw-sql.md).

## Registry sinh ra

Mọi mapper trong lần biên dịch đều xuất hiện trong một lớp `LarkBatisMappers` duy nhất:

```java
UserMapper mapper = LarkBatisMappers.userMapper(session);
```

`LarkBatisMappers` là một factory tĩnh trên một tập đóng đã biết lúc biên dịch. Không có
`addMapper()` và không có đăng ký lúc chạy, bởi vì chẳng có gì để đăng ký. Dưới Spring bạn
không bao giờ động tới nó: lớp `@Configuration` sinh ra khai báo chính những constructor đó
thành bean.

Mặc định registry rơi vào tiền tố package chung của tất cả mapper; ghi đè bằng
`-Alarkbatis.registryPackage=com.example.app`.
