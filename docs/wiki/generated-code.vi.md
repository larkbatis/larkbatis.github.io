# Code sinh ra

Code sinh ra là một **tính năng**, không phải chi tiết triển khai nội bộ. Mã nguồn này được thiết kế để mở ra đọc và debug từng bước trong IDE. Một stack trace khi xảy ra lỗi phải trỏ chính xác đến dòng code Java trong package của ứng dụng, thay vì chuỗi gọi trừu tượng `MapperProxy.invoke → MapperMethod.execute → …`.

Đối với một codebase có 300 phương thức mapper, khả năng debug trực quan này mang lại giá trị thực tế hàng ngày lớn hơn nhiều so với việc tiết kiệm vài micro giây cho mỗi truy vấn.

## Các tệp được sinh ra

| Tệp | Số lượng | Nội dung |
|---|---|---|
| `UserMapper$$Impl` | 1 tệp cho mỗi mapper | Bản hiện thực cụ thể. Mỗi statement tương ứng một phương thức |
| `UserRow` | 1 tệp cho mỗi result class | Ba phương thức đọc dòng và một bộ resolve cột. Dùng chung cho mọi statement trả về `User` |
| `LarkBatisMappers` | 1 tệp cho mỗi lần biên dịch | Static factory bao bọc tập hợp các mapper |
| `LarkBatisMapperConfiguration` | 1 tệp cho mỗi lần biên dịch (khi có Spring) | Khai báo `@Bean` cho từng mapper |

Toàn bộ code sinh ra đều nằm trong cùng package với mapper interface. Khi sử dụng JPMS, không cần phải export package ra ngoài cho framework.

## Bản hiện thực Mapper

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

1.  SQL tĩnh là hằng số `static final String`, được cấp phát một lần duy nhất và tái sử dụng cho mọi lời gọi. Ký hiệu `#{}` đã được chuyển thành `?` ngay từ lúc build.
2.  Tên cột khoá tường minh cho `useGeneratedKeys`, cho phép gọi `prepareStatement(sql, String[])` thay vì dùng `RETURN_GENERATED_KEYS` vốn không đảm bảo tính di động giữa các hệ quản trị database.
3.  Constructor public nhận session làm tham số. Điều này giúp mapper trở thành một Spring bean thông thường mà không cần bất kỳ `FactoryBean` nào.
4.  Mượn connection từ session, không tự mở kết nối mới. Khi nằm trong transaction, connection này chính là kết nối của transaction hiện tại.
5.  Gọi trực tiếp `setLong` thay vì `setObject`, được chọn tĩnh từ lúc build dựa trên kiểu tham số khai báo.
6.  Bộ dịch ngoại lệ đính kèm chuỗi câu SQL vào exception.
7.  Giải phóng kết nối qua `release` trong khối `finally`. Connection **không** được đặt trong khối try-with-resources.

## Statement động

Các điều kiện được đánh giá **một lần duy nhất** vào các biến cục bộ, và chính các biến này điều khiển cả việc ghép chuỗi SQL lẫn việc gán tham số:

```java
boolean c0 = q.getName() != null;
boolean c1 = q.getMinAge() != null;
StringBuilder sb = new StringBuilder(96);       // (1)!
sb.append("SELECT id, name, email, created_at FROM users");
if (c0 | c1) sb.append(" WHERE");               // (2)!
if (c0) sb.append(" name LIKE ?");
if (c1) sb.append(c0 ? " AND age >= ?" : " age >= ?");   // (3)!
sb.append(" ORDER BY id");
String sql = sb.toString();
Connection c = s.conn();
try (PreparedStatement ps = c.prepareStatement(sql)) {
    int i = 1;
    if (c0) ps.setString(i++, q.getName());     // (4)!
    if (c1) JdbcCodec.setInt(ps, i++, q.getMinAge());
    ...
```

1.  Dung lượng của `StringBuilder` được tính toán từ lúc build dựa trên độ dài tối đa có thể có của câu SQL, tránh việc cấp phát lại bộ nhớ khi nối chuỗi.
2.  Thẻ `<where>` được chuyển thành lệnh nối chuỗi có điều kiện. Dùng toán tử `|` thay vì `||` vì cả hai toán hạng đều là biến cục bộ đã tính toán sẵn, không cần cơ chế ngắt sớm (short-circuit).
3.  Quy tắc xử lý từ khoá `AND` ở đầu mệnh đề được gập hằng số thành toán tử ba ngôi trên các biến cục bộ đã biết, không quét chuỗi lúc runtime.
4.  Quá trình gán tham số duyệt qua **cùng** các điều kiện theo **đúng** thứ tự đó. Nhờ vậy chuỗi SQL và tham số không bao giờ bị lệch nhau: không cần bảng tra cứu tên - vị trí, chỉ có một tập biến boolean dùng chung.

## Trình đọc dòng (Row Reader) { #row-readers }

Mỗi result class tương ứng với một class đọc dòng riêng biệt, cung cấp ba điểm vào:

```java
public final class UserRow {

    public static final RowReader<User> READER = UserRow::read;   // (1)!

    public static User read(ResultSet rs) throws SQLException {   // (2)!
        User u = new User();
        u.setId(rs.getLong(1));
        u.setName(rs.getString(2));
        u.setEmail(rs.getString(3));
        u.setCreatedAt(JdbcCodec.instant(rs, 4));
        return u;
    }

    public static User read(ResultSet rs, int[] c) throws SQLException {   // (3)!
        User u = new User();
        if (c[0] != 0) u.setId(rs.getLong(c[0]));
        ...
    }

    public static int[] columns(ResultSet rs) throws SQLException {        // (4)!
        ResultSetMetaData md = rs.getMetaData();
        int[] c = new int[4];
        for (int i = 1, n = md.getColumnCount(); i <= n; i++) {
            switch (md.getColumnLabel(i).replace("_", "").toLowerCase(Locale.ROOT)) {
                case "id" -> c[0] = i;
                case "name" -> c[1] = i;
                ...
            }
        }
        return c;
    }
}
```

1.  Lối thoát thủ công tái sử dụng hằng số này để đọc dữ liệu mà không cần reflection.
2.  **Đọc theo vị trí cố định**, áp dụng khi bộ sinh code phân tích được danh sách SELECT. Mọi chỉ số cột đều là hằng số.
3.  **Đọc theo mảng chỉ số**: `c[k]` là vị trí trong ResultSet của thuộc tính thứ *k*, với giá trị `0` nghĩa là "không được select". Thuộc tính không có cột tương ứng sẽ giữ giá trị mặc định, không bị gán null.
4.  **Bộ resolve cột**, chỉ chạy một lần duy nhất trên dòng đầu tiên khi danh sách SELECT không thể phân tích cú pháp tĩnh. Các cột không khớp sẽ được bỏ qua, tương thích với cơ chế auto-mapping của MyBatis. Lệnh `replace("_","").toLowerCase()` áp dụng quy ước `snake_case` thống nhất với pha build.

Cấu trúc ba điểm vào này giải thích vì sao câu lệnh `SELECT *` chỉ tốn một lần quét metadata ở dòng đầu tiên rồi sau đó đọc theo vị trí nhanh chóng, không tra cứu tên cột trên từng dòng.

## Result Map lồng nhau

Thẻ `<resultMap>` lồng nhau được biên dịch thành một vòng lặp gom nhóm, không dùng map `CacheKey`:

```java
long key = rs.getLong(1);
if (!has || key != lastKey) {          // doi tuong cha moi
    parent = new Team();
    ...
}
if (rs.getObject(3) != null) {         // dong LEFT JOIN co du lieu con
    Member m = new Member();
    ...
    parent.getMembers().add(m);
}
```

MyBatis thực hiện việc này bằng cách tạo một `CacheKey` cho mỗi dòng: dùng reflection quét các cột id, đọc giá trị qua `TypeHandler`, tính mã hash và tra cứu đối tượng cha trong một `Map`. Trong LarkBatis, khoá là biến cục bộ có kiểu tĩnh được so sánh trực tiếp bằng `!=`, do đó khoá kiểu `long` hoàn toàn không tốn chi phí boxing kiểu đối tượng. Đổi lại, câu truy vấn [bắt buộc phải có mệnh đề ORDER BY](../usage/result-maps.md#the-ordering-rule).

## Registry và Cấu hình Spring

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

Cả hai đều chỉ gồm vài dòng code đơn giản: mapper là một class Java thông thường có constructor, do đó việc khởi tạo và đăng ký bean diễn ra tự nhiên. Thuộc tính `proxyBeanMethods = false` giúp tránh việc Spring phải sinh CGLIB subclass lúc runtime, đúng với mục tiêu loại bỏ hoàn toàn việc sinh bytecode lúc chạy của dự án.

## Đọc và kiểm soát thay đổi (Golden Snapshot)

Code sinh ra không mang tính ngẫu nhiên. Các bản golden snapshot của code sinh ra được commit trực tiếp trong repository chính, vì vậy mọi thay đổi trong bộ sinh code đều hiển thị dưới dạng diff rõ ràng trong git:

```console
$ ./gradlew test -Pupdate-golden
$ git diff larkbatis-processor/src/test/resources/golden/
```

Nếu một thay đổi trong bộ sinh code không tạo ra diff nào trong thư mục golden, thay đổi đó không có tác dụng. Nếu tạo ra diff bất thường, quy trình code review sẽ phát hiện ngay lập tức.
