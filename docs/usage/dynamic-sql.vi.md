# SQL động

`<if>`, `<choose>`, `<where>`, `<set>` và `<trim>` đều chạy được, và không cái nào sống
sót tới lúc chạy dưới dạng một cây. Bộ sinh code gấp cấu trúc thẻ thành các biến điều kiện
cục bộ và những lệnh nối chỉ chạy khi điều kiện đúng; thứ duy nhất được đánh giá lúc chạy là
mỗi biểu thức `test`, đúng một lần.

## Nó biên dịch thành cái gì

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

1.  Mỗi `test` được đánh giá **một lần**, vào một biến cục bộ. Chính biến đó điều khiển
    cả việc ráp SQL lẫn việc gắn tham số, nên hai bên không bao giờ lệch nhau được.
2.  Sức chứa được tính lúc build từ đoạn văn bản dài nhất có thể.
3.  `<where>` trở thành một hằng chỉ nối khi điều kiện đúng, chứ không phải một lần quét
    chuỗi lúc chạy để tìm `AND`/`OR` đứng đầu.
4.  Đây là quy tắc liên từ đứng đầu của `<where>`, đã được gấp thành hằng: nhánh đầu
    tiên được chọn thì không phát `AND`. Nó là một biểu thức ba ngôi trên các biến đã tính
    sẵn, không phải một phép tìm chuỗi con.
5.  Việc gắn tham số đi qua đúng những điều kiện đó theo đúng thứ tự đó. Không có bảng
    tra tên tham số nào chen vào giữa.

## `<if>`

```xml
<if test="email != null">AND email = #{email}</if>
```

Mọi thứ bên trong được nối vào khi điều kiện đúng. Lồng nhau chạy được; các thẻ ngang
hàng chạy được; một `<if>` nằm trong thân `<foreach>` cũng chạy được.

## `<choose>` / `<when>` / `<otherwise>`

Đúng một nhánh được chọn, và tính loại trừ lẫn nhau được biên dịch sẵn vào code:

```xml
<choose>
  <when test="status != null">AND status = #{status}</when>
  <otherwise>AND status = 'NEW'</otherwise>
</choose>
```

```java
boolean c0 = q.getStatus() != null;
boolean c1 = !c0;                       // <otherwise> là phủ định của phép tuyển
```

## `<where>` và `<set>`

`<where>` chỉ phát ra từ khoá nếu phần thân có đóng góp gì đó, và cắt bỏ `AND`/`OR` đứng
đầu của nhánh nào được chọn trước. `<set>` làm y hệt với `SET` và dấu phẩy cuối:

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

Để ý là không hề có việc cắt dấu phẩy cuối lúc chạy: bộ sinh code biết với mỗi tổ hợp
thì nhánh nào là nhánh cuối, và chỉ phát dấu phẩy ở chỗ chắc chắn còn nhánh phía sau.

## `<trim>`

Được hỗ trợ với **thuộc tính hằng** (`prefix`, `suffix`, `prefixOverrides`,
`suffixOverrides`), và chúng được gấp thành hằng lúc build. Chính điều đó khiến `<where>`
và `<set>` biên dịch ra đúng đoạn code ở trên; chúng là `<trim>` với thuộc tính cố định.

## Ngữ pháp `test` { #the-test-grammar }

Đây là chỗ duy nhất LarkBatis cố ý từ chối tương thích với MyBatis. `test` **không**
phải OGNL. Nó là một ngữ pháp hẹp, được kiểm tra kiểu dựa trên các tham số của phương
thức mapper:

| Được chấp nhận | Ví dụ |
|---|---|
| Kiểm tra null | `name != null`, `probe.email == null` |
| So sánh trên đường dẫn property có kiểu | `age >= 18`, `status == 'NEW'`, `id != other.id` |
| Toán tử boolean | `and`, `or`, `not`, dấu ngoặc |
| Kích thước và rỗng | `ids.size() > 0`, `name.length() > 3`, `!ids.isEmpty()` |
| Phương thức trả về boolean | `user.isActive()` |
| Boolean trần | `active`, với điều kiện `active` thực sự là property `boolean`/`Boolean` |

Mọi thứ khác đều là **lỗi biên dịch, nêu rõ token có vấn đề**.

!!! failure "Không tái tạo tính đúng-sai kiểu OGNL"

    ```xml
    <if test="count">      <!-- lỗi biên dịch -->
    <if test="user">       <!-- lỗi biên dịch -->
    ```

    MyBatis coi một giá trị khác null, khác 0, khác rỗng là đúng. LarkBatis từ chối
    đoán xem bạn định nói cái nào. Hãy viết `count != 0`, `user != null`, hoặc
    `!list.isEmpty()`.

    Đây không phải sự khó tính: `test="count"` trong một codebase MyBatis thực sự nhập
    nhằng giữa "count đã được gán" và "count khác 0", và hai cái đó khác nhau đúng ở chỗ
    quan trọng nhất.

### Ngữ nghĩa null, cố định và có ghi lại

OGNL thì ép kiểu; ngữ pháp này thì không. Các quy tắc được phát biểu một lần và đúng ở
mọi nơi:

| Biểu thức | LarkBatis | MyBatis / OGNL |
|---|---|---|
| `a == null` / `a != null` | Lan truyền null qua mọi bước tham chiếu của đường dẫn, giống cách điều hướng an toàn null của OGNL | Như nhau |
| `age <= 18` khi `age` là null | **`false`**, vì một giá trị null ở bất kỳ đâu trong hai toán hạng đều làm phép so sánh thành sai | `true`, null bị ép thành 0 |
| `a != b` | Đúng bằng `!(a == b)` | Như nhau |
| `user.isActive()` khi `user` là null | **`false`** | Ném exception |

Dòng thứ hai là dòng cần kiểm khi chuyển đổi. Một phép `null <= 18` vốn âm thầm mang
nghĩa "đúng" trong MyBatis thì ở đây thành "sai", và đó là một khác biệt cố ý:
null-là-số-không cũng chính là kiểu nhập nhằng mà ngữ pháp này đã từ chối ở chuyện
đúng-sai. [Trình quét mã cũ](../features/migration.md) đánh dấu những test mà nó không
tự quyết được.

## SQL động và statement cache

Một statement có câu SQL phụ thuộc vào điều kiện lúc chạy thì sinh ra nhiều hơn một chuỗi
SQL. Số đó vẫn bị chặn: với *n* thẻ `<if>` độc lập thì trần là 2ⁿ chuỗi, biết trước từ lúc
build. Thứ *không* bị chặn là một chỗ chèn `${}` hoặc một `<foreach>` có số phần tử thay
đổi, nên những statement đó nhận thêm một lời gọi `LarkBatisSql.trackVariants`. Xem [SQL
thô](raw-sql.md#tracking-sql-variants).

## Kiểm chứng đối chiếu với MyBatis

Repository lõi có sẵn một bộ khung kiểm thử vi sai: cùng một mapper được chạy qua đường
thông dịch của MyBatis và qua code sinh ra, đối diện một `DataSource` ghi lại mọi thứ,
rồi câu SQL và các tham số bind được đem so sánh. Ngoài ra còn một lượt quét toàn
bộ kho mapper XML trong cây mã nguồn MyBatis, và đó là cách độ phủ của ngữ pháp được đo
đạc chứ không phải phỏng đoán.
