# Dynamic SQL (SQL động)

Các thẻ `<if>`, `<choose>`, `<where>`, `<set>` và `<trim>` được hỗ trợ đầy đủ. Thay vì xây dựng và duyệt cây AST lúc runtime như MyBatis, LarkBatis phẳng hoá toàn bộ cấu trúc thẻ XML thành các biến điều kiện cục bộ (`condition locals`) và các lệnh nối chuỗi `StringBuilder` cố định.

## Cơ chế biên dịch mã nguồn

```xml title="UserSearchMapper.xml"
<select id="search" resultType="com.example.app.User">
  SELECT id, name, email, created_at FROM users
  <where>
    <if test="name != null">AND name LIKE #{name}</if>
    <if test="minAge != null">AND age &gt;= #{minAge}</if>
  </where>
  ORDER BY id
</select>
```

Mã nguồn Java sinh ra tương ứng:

```java title="UserSearchMapper$$Impl.java"
@Override
public List<User> search(UserQuery q) {
    boolean c0 = q.getName() != null;          // (1)!
    boolean c1 = q.getMinAge() != null;
    StringBuilder sb = new StringBuilder(96);  // (2)!
    sb.append("SELECT id, name, email, created_at FROM users");
    if (c0 | c1) {
        sb.append(" WHERE");                   // (3)!
    }
    if (c0) {
        sb.append(" name LIKE ?");
    }
    if (c1) {
        sb.append(c0 ? " AND age >= ?" : " age >= ?");   // (4)!
    }
    sb.append(" ORDER BY id");
    String sql = sb.toString();
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(sql)) {
        int i = 1;
        if (c0) {
            ps.setString(i++, q.getName());    // (5)!
        }
        if (c1) {
            JdbcCodec.setInt(ps, i++, q.getMinAge());
        }
        // ... đọc ResultSet
    }
}
```

1.  Mỗi biểu thức `test` được đánh giá **đúng một lần** vào biến boolean cục bộ. Biến này dùng chung cho cả khâu nối chuỗi SQL lẫn khâu bind tham số JDBC.
2.  Kích thước `StringBuilder` được tính toán trước từ lúc build.
3.  Thẻ `<where>` được biên dịch thành lệnh `if` thông thường, không quét chuỗi để xóa `AND`/`OR` lúc runtime.
4.  Tiền tố `AND`/`OR` được tối ưu thành toán tử ba ngôi (ternary operator) dựa trên các biến boolean.
5.  Khâu gán tham số `PreparedStatement` đi qua cùng thứ tự điều kiện, không cần bảng tra cứu động.

## `<if>`

```xml
<if test="email != null">AND email = #{email}</if>
```

Nối đoạn SQL khi điều kiện đúng. Hỗ trợ lồng nhau và đặt bên trong thẻ `<foreach>`.

## `<choose>`, `<when>`, `<otherwise>`

Tương đương câu lệnh `switch` / `if-else`:

```xml
<choose>
  <when test="status != null">AND status = #{status}</when>
  <otherwise>AND status = 'NEW'</otherwise>
</choose>
```

```java
boolean c0 = q.getStatus() != null;
boolean c1 = !c0;                       // <otherwise> là phủ định của nhánh trên
```

## `<where>` và `<set>`

`<where>` chỉ chèn từ khóa `WHERE` nếu có ít nhất một điều kiện con thỏa mãn, và tự động bỏ từ khóa `AND`/`OR` ở nhánh đầu tiên. `<set>` hoạt động tương tự với từ khóa `SET` và dấu phẩy ở cuối câu:

```xml
<update id="rename">
  UPDATE users
  <set>
    <if test="name != null">name = #{name},</if>
    <if test="email != null">email = #{email},</if>
  </set>
  WHERE id = #{id}
</update>
```

```java
if (c0 | c1) sb.append(" SET");
if (c0) sb.append(c1 ? " name = ?," : " name = ?");
if (c1) sb.append(" email = ?");
sb.append(" WHERE id = ?");
```

## `<trim>`

Hỗ trợ các thuộc tính hằng số (`prefix`, `suffix`, `prefixOverrides`, `suffixOverrides`) và được tối ưu hóa lúc compile.

## Ngữ pháp biểu thức `test` { #the-test-grammar }

Khác với MyBatis (dùng OGNL runtime), LarkBatis sử dụng ngữ pháp kiểm tra kiểu tĩnh:

| Biểu thức hỗ trợ | Ví dụ |
|---|---|
| Kiểm tra null | `name != null`, `probe.email == null` |
| So sánh giá trị | `age >= 18`, `status == 'NEW'`, `id != other.id` |
| Toán tử logic | `and`, `or`, `not`, dấu ngoặc `()` |
| Kiểm tra độ dài / collection | `ids.size() > 0`, `name.length() > 3`, `!ids.isEmpty()` |
| Phương thức trả về boolean | `user.isActive()` |
| Biến boolean | `active` (với `active` có kiểu `boolean` hoặc `Boolean`) |

Mọi biểu thức nằm ngoài danh sách trên sẽ **báo lỗi biên dịch**.

!!! failure "Không hỗ trợ truthiness kiểu OGNL"

    ```xml
    <if test="count">      <!-- Lỗi biên dịch -->
    <if test="user">       <!-- Lỗi biên dịch -->
    ```

    Trong LarkBatis, bạn phải viết rõ ràng: `count != 0`, `user != null`, hoặc `!list.isEmpty()`.

### Bảng so sánh xử lý giá trị null

| Biểu thức | LarkBatis | MyBatis / OGNL |
|---|---|---|
| `a == null` / `a != null` | Lan truyền null an toàn | Như nhau |
| `age <= 18` khi `age` là `null` | **`false`** | `true` (OGNL tự ép `null` thành 0) |
| `user.isActive()` khi `user` là `null` | **`false`** | Ném ngoại lệ `NullPointerException` |

## Quản lý Statement Cache cho Dynamic SQL

Mỗi tổ hợp điều kiện tạo ra một chuỗi SQL riêng biệt. Với *n* thẻ `<if>` độc lập, số lượng biến thể tối đa là 2ⁿ chuỗi. LarkBatis tự động theo dõi số lượng biến thể qua `LarkBatisSql.trackVariants()` để ngăn chặn tràn bộ nhớ cache. Xem [Raw SQL & An toàn](raw-sql.md#tracking-sql-variants).

