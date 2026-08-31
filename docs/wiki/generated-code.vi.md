# Mã nguồn sinh ra (Generated Code)

Mã nguồn Java sinh ra bởi LarkBatis được thiết kế để đọc và debug trực tiếp trong IDE. Khi xảy ra lỗi hoặc ngoại lệ, stack trace sẽ trỏ chính xác đến từng dòng code Java cụ thể trong package của dự án, thay vì chuỗi gọi trừu tượng qua reflection như `MapperProxy.invoke → MapperMethod.execute`.

## Danh sách các file sinh ra

| File | Số lượng | Vai trò |
|---|---|---|
| `UserMapper$$Impl` | 1 file cho mỗi mapper | Triển khai JDBC cụ thể của interface mapper |
| `UserRow` | 1 file cho mỗi result class | Class đọc dòng từ `ResultSet`, dùng chung cho mọi truy vấn trả về `User` |
| `LarkBatisMappers` | 1 file cho toàn bộ lần compile | Static factory khởi tạo các instance mapper |
| `LarkBatisMapperConfiguration` | 1 file cho toàn bộ lần compile (khi có Spring) | Khai báo các `@Bean` mapper |

Mã nguồn sinh ra nằm trong cùng package với mapper interface.

## Chi tiết Mapper Implementation (`UserMapper$$Impl`)

```java
@Generated("io.github.larkbatis.processor.LarkBatisProcessor")
public final class UserMapper$$Impl implements UserMapper {

    private static final String SQL_findById =
            "SELECT id, name, email, created_at FROM users WHERE id = ?";   // (1)!
    private static final String[] KEYS_insert = { "id" };                   // (2)!

    private final LarkBatisSession s;

    public UserMapper$$Impl(LarkBatisSession s) {                          // (3)!
        this.s = s;
    }

    @Override
    public User findById(long id) {
        Connection c = s.conn();                                            // (4)!
        try (PreparedStatement ps = c.prepareStatement(SQL_findById)) {
            ps.setLong(1, id);                                              // (5)!
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? UserRow.read(rs) : null;
            }
        } catch (SQLException e) {
            throw s.translate(e, SQL_findById);                             // (6)!
        } finally {
            s.release(c);                                                   // (7)!
        }
    }
}
```

1. Chuỗi SQL tĩnh được lưu dưới dạng `static final String`, tạo một lần duy nhất. Cú pháp `#{}` đã được chuyển thành dấu `?` trong pha compile.
2. Tên cột Generated Keys tường minh cho `prepareStatement(sql, String[])`.
3. Constructor public nhận `LarkBatisSession`, giúp Spring khởi tạo mapper như một Spring Bean thông thường.
4. Mượn connection từ session (tham gia vào transaction nếu có).
5. Gọi trực tiếp `ps.setLong()` theo kiểu tĩnh, không qua `setObject()` hay reflection.
6. Dịch mã lỗi JDBC và đính kèm chuỗi SQL vào exception.
7. Giải phóng connection trong khối `finally` qua `s.release(c)` (không bọc connection trong try-with-resources).

## Xử lý Dynamic SQL

Các điều kiện được tính toán một lần vào các biến cục bộ (boolean locals) và điều khiển đồng thời việc ghép chuỗi SQL lẫn bind tham số:

```java
boolean c0 = q.getName() != null;
boolean c1 = q.getMinAge() != null;
StringBuilder sb = new StringBuilder(96);       // (1)! Pre-sized StringBuilder
sb.append("SELECT id, name, email, created_at FROM users");
if (c0 | c1) sb.append(" WHERE");               // (2)!
if (c0) sb.append(" name LIKE ?");
if (c1) sb.append(c0 ? " AND age >= ?" : " age >= ?");   // (3)!
sb.append(" ORDER BY id");
String sql = sb.toString();

Connection c = s.conn();
try (PreparedStatement ps = c.prepareStatement(sql)) {
    int i = 1;
    if (c0) ps.setString(i++, q.getName());     // (4)! Bind tham số cùng thứ tự điều kiện
    if (c1) JdbcCodec.setInt(ps, i++, q.getMinAge());
    // ...
```

1. Dung lượng `StringBuilder` được tính toán trước từ lúc build, tránh cấp phát lại bộ nhớ khi ghép chuỗi.
2. Thẻ `<where>` được chuyển thành lệnh `append(" WHERE")` có điều kiện.
3. Loại bỏ tiền tố `AND` bằng toán tử ba ngôi trên các biến boolean, không cắt chuỗi lúc runtime.
4. Quá trình gán tham số duyệt qua cùng các biến điều kiện, đảm bảo số lượng và thứ tự dấu `?` luôn khớp tuyệt đối.

## Row Reader (`UserRow`) { #row-readers }

```java
public final class UserRow {

    public static final RowReader<User> READER = UserRow::read;

    // 1. Đọc theo vị trí cột cố định (tối ưu nhất, dùng khi biết trước danh sách SELECT)
    public static User read(ResultSet rs) throws SQLException {
        User u = new User();
        u.setId(rs.getLong(1));
        u.setName(rs.getString(2));
        u.setEmail(rs.getString(3));
        u.setCreatedAt(JdbcCodec.instant(rs, 4));
        return u;
    }

    // 2. Đọc theo mảng chỉ số cột (dùng khi SELECT * hoặc fallback)
    public static User read(ResultSet rs, int[] c) throws SQLException {
        User u = new User();
        if (c[0] != 0) u.setId(rs.getLong(c[0]));
        if (c[1] != 0) u.setName(rs.getString(c[1]));
        // ...
        return u;
    }

    // 3. Quét metadata lấy chỉ số cột một lần duy nhất ở dòng đầu tiên
    public static int[] columns(ResultSet rs) throws SQLException {
        ResultSetMetaData md = rs.getMetaData();
        int[] c = new int[4];
        for (int i = 1, n = md.getColumnCount(); i <= n; i++) {
            switch (md.getColumnLabel(i).replace("_", "").toLowerCase(Locale.ROOT)) {
                case "id" -> c[0] = i;
                case "name" -> c[1] = i;
                // ...
            }
        }
        return c;
    }
}
```

## Nested ResultMap (Single-Pass Grouping)

Các quan hệ 1-N trong `<resultMap>` được biên dịch thành vòng lặp gom nhóm trực tiếp:

```java
long key = rs.getLong(1);
if (!has || key != lastKey) {          // Bắt đầu một đối tượng cha mới
    parent = new Team();
    // ...
}
if (rs.getObject(3) != null) {         // Dòng chứa dữ liệu con từ LEFT JOIN
    Member m = new Member();
    // ...
    parent.getMembers().add(m);
}
```

Khóa cha được so sánh trực tiếp qua biến primitive/object mà không cần khởi tạo `CacheKey` hay tra cứu `HashMap`. Cơ chế này yêu cầu câu truy vấn phải có mệnh đề `ORDER BY` theo khóa của bảng cha.

## Registry & Spring Configuration

```java
public final class LarkBatisMappers {
    public static UserMapper userMapper(LarkBatisSession s) {
        return new UserMapper$$Impl(s);
    }
}
```

```java
@Configuration(proxyBeanMethods = false)
public class LarkBatisMapperConfiguration {
    @Bean
    public UserMapper userMapper(LarkBatisSession s) {
        return new UserMapper$$Impl(s);
    }
}
```

`proxyBeanMethods = false` đảm bảo Spring không tạo CGLIB subclass lúc runtime.

