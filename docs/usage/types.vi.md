# Kiểu dữ liệu và handler

Tầng `TypeHandler` của MyBatis là một registry lúc chạy: với mỗi tham số và mỗi cột, tra
một handler theo kiểu Java và kiểu JDBC, rồi gọi nó. LarkBatis đưa ra lựa chọn đó ngay
lúc build rồi chèn thẳng kết quả vào code sinh ra. Còn lại lúc chạy là `JdbcCodec`, một
nhúm hàm tĩnh cho những kiểu mà accessor JDBC tự nhiên của chúng là kiểu nguyên thuỷ hoặc
cần một phép chuyển đổi.

## Những gì gắn được mà không cần trợ giúp

`#{}` và các property kết quả xử lý trực tiếp những kiểu sau:

| Kiểu Java | Đọc | Ghi |
|---|---|---|
| `String` | `rs.getString(i)` | `ps.setString(i, v)` |
| `long`, `int`, `short`, `byte`, `boolean`, `float`, `double` | `rs.getLong(i)` v.v. | `ps.setLong(i, v)` v.v. |
| `Long`, `Integer`, … (kiểu bọc) | `JdbcCodec.longOrNull(rs, i)` | `JdbcCodec.setLong(ps, i, v)` |
| `BigDecimal`, `BigInteger` | `rs.getBigDecimal(i)` | `ps.setBigDecimal(i, v)` |
| `byte[]` | `rs.getBytes(i)` | `ps.setBytes(i, v)` |
| `java.sql.Date`, `Time`, `Timestamp` | trực tiếp | trực tiếp |
| `Instant`, `LocalDate`, `LocalTime`, `LocalDateTime` | `JdbcCodec.instant(rs, i)` v.v. | `JdbcCodec.setInstant(ps, i, v)` v.v. |
| Mọi `enum` | `JdbcCodec.enumValue(...)` | `JdbcCodec.setEnum(ps, i, v)` |

### Vì sao các kiểu bọc phải đi qua `JdbcCodec`

`rs.getLong(i)` trả về `0` cho một `NULL` của SQL. Các hàm trợ giúp cho kiểu bọc làm đúng
điều bạn thật sự muốn:

```java
public static Long longOrNull(ResultSet rs, int column) throws SQLException {
    long v = rs.getLong(column);
    return rs.wasNull() ? null : v;
}
```

Việc chọn giữa `rs.getLong(i)` và `JdbcCodec.longOrNull(rs, i)` được quyết lúc build từ
kiểu khai báo của property. Property kiểu `long` nhận phép đọc nguyên thuỷ; property kiểu
`Long` nhận phép đọc có nhận biết null. Khai báo property cho phép null chính là cách bạn
yêu cầu xử lý null. Không có thiết lập riêng nào cả.

Ở phía ghi, `JdbcCodec.setLong(ps, i, null)` gọi `ps.setNull(i, Types.BIGINT)` với đúng
kiểu SQL, điều mà một số driver bắt buộc phải có.

## Enum

Enum ánh xạ theo `name()` của nó mặc định, theo cả hai chiều, và có xử lý `null`:

```java
public enum Status { NEW, PAID, SHIPPED }
```

```java
@Select("SELECT id, status, total FROM orders WHERE status = #{status}")
List<Order> byStatus(Status status);
```

Enum cũng là một **kiểu giá trị đóng**, nên nó là một trong số ít thứ được phép bind vào
`${}`, vì toàn bộ không gian giá trị của nó đã biết từ lúc build. Xem
[SQL thô](raw-sql.md#the-rule).

Một enum lưu dưới dạng ordinal hoặc một mã tuỳ biến thì cần
[handler riêng](#custom-type-handlers).

## `java.time`

`Instant`, `LocalDate`, `LocalTime` và `LocalDateTime` chuyển đổi qua
`java.sql.Timestamp` / `Date` / `Time`, đúng như các handler của MyBatis vẫn làm.
`Instant` dùng `Timestamp.toInstant()` và `Timestamp.from(...)`, nên giá trị là tuyệt đối
và múi giờ mặc định của JVM không xen vào.

Các kiểu mang theo múi giờ (`ZonedDateTime`, `OffsetDateTime`) không được dựng sẵn. Một
cột thì chẳng có múi giờ nào để mang, nên phép chuyển đổi cần một quyết định vốn thuộc về
ứng dụng của bạn. Hãy lưu `Instant`, và chuyển đổi ở rìa của mapper.

## Đặt tên cột { #column-naming }

Cột tìm ra property theo `snake_case` → `camelCase`, áp dụng lúc build, luôn luôn:
`created_at` → `setCreatedAt`. Không có tuỳ chọn `mapUnderscoreToCamelCase` nào để tắt
đi, bởi vì chẳng có runtime nào để mà tắt nó trong đó.

Chỗ nào quy ước không đủ thì một `<resultMap>` gọi tên cột tường minh:

```xml
<resultMap id="userMap" type="com.example.app.User">
  <id     property="id"    column="id"/>
  <result property="email" column="usr_email"/>
</resultMap>
```

Hoặc `@Column` đặt tên cột ngay trên property, một lần, dùng cho mọi statement:

```java
public class User {

    @Column("usr_email")
    private String email;

    public void setEmail(String email) { this.email = email; }
}
```

Annotation này được đọc trên **field, setter hoặc getter**, đặt ở đâu cũng được. Hai
trong số đó ghi hai tên cột khác nhau cho cùng một property là lỗi biên dịch, và hai
property rơi vào cùng một cột cũng vậy. Xem
[`@Column`](../features/annotations.md#column).

Một codebase từng dựa vào việc `mapUnderscoreToCamelCase` bị *tắt* sẽ cần `@Column` hoặc
`<resultMap>`, và [trình quét mã cũ](../features/migration.md) có báo cáo trường hợp này.

## Type handler tuỳ biến { #custom-type-handlers }

Những kiểu không có trong bảng trên (`Money` của riêng bạn, một cột JSON, một enum lưu
dạng ordinal) đi qua handler do bạn viết:

```java
public class MoneyHandler implements LarkBatisTypeHandler<Money> {

    @Override
    public Money read(ResultSet rs, int column) throws SQLException {
        long cents = rs.getLong(column);
        return rs.wasNull() ? null : new Money(cents);
    }

    @Override
    public void write(PreparedStatement ps, int index, Money value) throws SQLException {
        if (value == null) {
            ps.setNull(index, Types.BIGINT);
        } else {
            ps.setLong(index, value.cents());
        }
    }
}
```

Ba quy tắc, tất cả đều được kiểm lúc `javac` chạy:

- **Public, concrete, có constructor public không tham số, và stateless.** Code sinh ra
  giữ đúng một instance trong field `static final` rồi dùng chung. Một handler cần tham
  số khởi tạo cũng là một handler không stateless; trường hợp đó hãy dùng
  [cửa thoát hiểm](raw-sql.md#the-escape-hatch).
- **Type argument phải đúng kiểu của giá trị**, không phải một supertype. `read` phải trả
  về thứ mà setter nhận được.
- **Handler tự lo `null`** ở cả hai chiều. Không có `jdbcType` nào để lùi về, nên handler
  nào muốn `setNull` thì tự gọi.

### Gọi tên nó ở đâu

Ba chỗ, cả ba đều được đọc lúc build.

Trên property, tức field, setter hoặc getter, giống `@Column`:

```java
public class Wallet {

    @Handler(MoneyHandler.class)
    private Money balance;
}
```

Trên tham số của mapper:

```java
@Select("SELECT id FROM wallet WHERE balance >= #{floor}")
List<Long> atLeast(@Handler(MoneyHandler.class) Money floor);
```

Hoặc trong mapper XML, đây chính là dạng mà một mapper MyBatis cũ đã có sẵn, nên bean
không cần thêm annotation nào:

```xml
<resultMap id="entry" type="com.example.Entry">
    <id property="id" column="id"/>
    <result property="amount" column="amount" typeHandler="com.example.MoneyHandler"/>
</resultMap>

<insert id="insert">
    INSERT INTO ledger (id, amount)
    VALUES (#{id}, #{amount, typeHandler=com.example.MoneyHandler})
</insert>
```

Handler cũng mở khoá danh sách kiểu cho giá trị nó chuyển: `Money` không có trong bảng
trên, mà những đoạn trên vẫn biên dịch được.

### Những gì vẫn không có

**Không tự tìm handler.** Không có registry `<typeHandlers>`, không quét `@MappedTypes`,
không tra `(Type, JdbcType)`. Tường minh là cái giá phải trả: bạn mất đi "khai báo một
lần rồi áp dụng khắp nơi", và bạn được một chỗ gọi sinh ra mà javac kiểm tra kiểu được,
còn IDE thì nhảy tới được.

**Một cách đọc cho mỗi lớp kết quả.** Mỗi lớp chỉ sinh một row reader, nên mỗi property
chỉ có một handler. Hai statement gọi tên hai handler khác nhau cho cùng một property là
lỗi biên dịch, vì muốn hai cách đọc thì phải có hai lớp kết quả.

**Không đặt trên method của mapper.** `@Handler` ngay trên method bị từ chối: kết quả
scalar đọc cột 1 và không có property nào để gắn handler vào. Hãy trả về một bean, hoặc
dùng cửa thoát hiểm.

## Lớp kết quả, nói lại lần nữa

Giao kèo đủ ngắn để nhắc lại: **một constructor không tham số và các setter**. Không lớp
cha, không annotation, không đăng ký, không ánh xạ `<constructor>`. Một lớp không có cả
constructor không tham số lẫn setter là lỗi build nêu tên lớp đó. Nếu nó mang annotation
của Lombok, thông báo sẽ nói rõ, bởi nguyên nhân gần như lúc nào cũng là thứ tự processor
chứ không phải thiếu accessor. Xem [Xử lý sự cố](troubleshooting.md).
