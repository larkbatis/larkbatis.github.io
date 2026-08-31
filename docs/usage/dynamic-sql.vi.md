# SQL động

Các thẻ `<if>`, `<choose>`, `<where>`, `<set>` và `<trim>` đều được hỗ trợ đầy đủ, nhưng không thẻ nào tồn tại dưới dạng cây AST lúc runtime. Bộ sinh code chuyển đổi cấu trúc XML thành các biến boolean điều kiện cục bộ và các lệnh nối chuỗi `StringBuilder` tối ưu. Yếu tố duy nhất được đánh giá lúc chạy là các biểu thức `test`, mỗi biểu thức đúng một lần.

## Cơ chế biên dịch

```xml
<select id="search" resultType="com.example.app.User">
  SELECT id, name, email, created_at FROM users
  <where>
    <if test="name != null">AND name LIKE #{name}</if>
    <if test="minAge != null">AND age &gt;= #{minAge}</if>
  </where>
  ORDER BY id
</select>
```

```java
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
        // ... đọc các dòng
    }
}
```

1.  Mỗi biểu thức `test` được đánh giá **đúng một lần** vào một biến cục bộ. Biến này điều khiển đồng thời cả việc ghép SQL lẫn việc gán tham số, đảm bảo hai bên luôn đồng bộ tuyệt đối.
2.  Dung lượng của `StringBuilder` được tính toán từ lúc build dựa trên chiều dài tối đa của câu SQL.
3.  Thẻ `<where>` được chuyển thành câu lệnh nối chuỗi có điều kiện, không quét chuỗi lúc runtime để tìm từ khoá `AND`/`OR`.
4.  Quy tắc xử lý từ khoá `AND`/`OR` ở đầu mệnh đề được gập hằng số thành toán tử ba ngôi trên các biến boolean đã tính sẵn.
5.  Quá trình gán tham số đi qua cùng các điều kiện theo đúng thứ tự đó, không cần bảng tra cứu trung gian.

## `<if>`

```xml
<if test="email != null">AND email = #{email}</if>
```

Nội dung bên trong được nối vào câu lệnh khi điều kiện đúng. Hỗ trợ lồng nhau, đặt ngang hàng, hoặc đặt bên trong thẻ `<foreach>`.

## `<choose>` / `<when>` / `<otherwise>`

Đúng một nhánh được chọn, và tính loại trừ lẫn nhau được biên dịch thẳng vào mã nguồn:

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

`<where>` chỉ phát sinh từ khoá nếu phần thân có nội dung, và tự động loại bỏ `AND`/`OR` đứng đầu của nhánh đầu tiên được chọn. `<set>` hoạt động tương tự với từ khoá `SET` và dấu phẩy ở cuối:

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

Bộ sinh code xác định chính xác nhánh nào là nhánh cuối cùng của từng tổ hợp điều kiện để chỉ phát dấu phẩy khi chắc chắn còn nhánh phía sau, không cần thao tác cắt chuỗi lúc runtime.

## `<trim>`

Được hỗ trợ với **thuộc tính hằng** (`prefix`, `suffix`, `prefixOverrides`, `suffixOverrides`) và được xử lý gập hằng số lúc build. `<where>` và `<set>` thực chất là các dạng đặc biệt của `<trim>` với thuộc tính cố định.

## Ngữ pháp `test` { #the-test-grammar }

Đây là điểm khác biệt có chủ ý lớn nhất với MyBatis. Thuộc tính `test` **không** sử dụng OGNL, mà sử dụng một ngữ pháp biểu thức thu hẹp được kiểm tra kiểu tĩnh dựa trên các tham số của phương thức mapper:

| Biểu thức được chấp nhận | Ví dụ |
|---|---|
| Kiểm tra null | `name != null`, `probe.email == null` |
| So sánh trên property có kiểu | `age >= 18`, `status == 'NEW'`, `id != other.id` |
| Toán tử boolean | `and`, `or`, `not`, dấu ngoặc đơn |
| Kích thước và kiểm tra rỗng | `ids.size() > 0`, `name.length() > 3`, `!ids.isEmpty()` |
| Phương thức trả về boolean | `user.isActive()` |
| Biến boolean thuần | `active` (với điều kiện `active` là property `boolean`/`Boolean`) |

Mọi biểu thức nằm ngoài danh sách trên đều là **lỗi biên dịch nêu rõ token gây lỗi**.

!!! failure "Không tái tạo cơ chế truthiness kiểu OGNL"

    ```xml
    <if test="count">      <!-- lỗi biên dịch -->
    <if test="user">       <!-- lỗi biên dịch -->
    ```

    MyBatis coi giá trị khác null, khác 0, khác rỗng là true. LarkBatis yêu cầu viết tường minh: `count != 0`, `user != null`, hoặc `!list.isEmpty()`.

    Đây là sự khắt khe có chủ đích: biểu thức `test="count"` trong MyBatis gây nhập nhằng giữa "count khác null" và "count khác 0", và hai trường hợp này có ý nghĩa nghiệp vụ hoàn toàn khác nhau.

### Quy tắc xử lý null cố định

Ngữ pháp của LarkBatis không tự động ép kiểu. Các quy tắc được xác định nhất quán:

| Biểu thức | LarkBatis | MyBatis / OGNL |
|---|---|---|
| `a == null` / `a != null` | Lan truyền null an toàn qua các thuộc tính con | Như nhau |
| `age <= 18` khi `age` là null | **`false`** (bất kỳ toán hạng nào là null làm phép so sánh thành false) | `true` (null bị ép kiểu thành 0) |
| `a != b` | Tương đương `!(a == b)` | Như nhau |
| `user.isActive()` khi `user` là null | **`false`** | Ném ngoại lệ |

Dòng thứ hai là điểm cần lưu ý nhất khi migration: phép so sánh `null <= 18` âm thầm mang giá trị true trong MyBatis sẽ trở thành **false** trong LarkBatis. [Trình quét mã cũ](../features/migration.md) sẽ tự động gắn cờ các biểu thức này.

## SQL động và statement cache

Statement có nội dung SQL phụ thuộc vào điều kiện runtime sẽ sinh ra nhiều chuỗi SQL khác nhau. Với *n* thẻ `<if>` độc lập, số biến thể tối đa là 2ⁿ chuỗi (đã biết trước lúc build). Những statement chứa `${}` hoặc `<foreach>` có số phần tử thay đổi sẽ được chèn thêm lệnh `LarkBatisSql.trackVariants`. Xem [SQL thô](raw-sql.md#tracking-sql-variants).

## Kiểm chứng đối chiếu với MyBatis

Repository lõi tích hợp sẵn harness kiểm thử vi sai: cùng một mapper được chạy qua cả hai luồng (thông dịch của MyBatis và code sinh sẵn của LarkBatis) trên cùng một `DataSource` ghi nhận dữ liệu, sau đó so sánh từng câu SQL và từng tham số được bind. Quá trình quét toàn bộ kho mapper XML mẫu của MyBatis đảm bảo độ bao phủ thực tế của ngữ pháp.
