# Kiểu dữ liệu và handler

Tầng `TypeHandler` của MyBatis vận hành như một registry động lúc runtime: với mỗi tham số và mỗi cột, hệ thống tra cứu handler theo cặp (javaType, jdbcType) và gọi qua reflection. LarkBatis định hình toàn bộ các ánh xạ này từ lúc build và phát ra trực tiếp các lệnh gọi tương ứng. Khi chạy, runtime chỉ sử dụng `JdbcCodec` — tập hợp các static helper xử lý null an toàn cho các kiểu dữ liệu cơ bản hoặc cần chuyển đổi.

## Các kiểu dữ liệu hỗ trợ sẵn

Ký hiệu `#{}` và các property kết quả hỗ trợ trực tiếp các kiểu sau:

| Kiểu Java | Đọc dữ liệu | Ghi dữ liệu |
|---|---|---|
| `String` | `rs.getString(i)` | `ps.setString(i, v)` |
| `long`, `int`, `short`, `byte`, `boolean`, `float`, `double` | `rs.getLong(i)` v.v. | `ps.setLong(i, v)` v.v. |
| `Long`, `Integer`, … (kiểu wrapper) | `JdbcCodec.longOrNull(rs, i)` | `JdbcCodec.setLong(ps, i, v)` |
| `BigDecimal`, `BigInteger` | `rs.getBigDecimal(i)` | `ps.setBigDecimal(i, v)` |
| `byte[]` | `rs.getBytes(i)` | `ps.setBytes(i, v)` |
| `java.sql.Date`, `Time`, `Timestamp` | trực tiếp qua JDBC | trực tiếp qua JDBC |
| `Instant`, `LocalDate`, `LocalTime`, `LocalDateTime` | `JdbcCodec.instant(rs, i)` v.v. | `JdbcCodec.setInstant(ps, i, v)` v.v. |
| Mọi `enum` | `JdbcCodec.enumValue(...)` | `JdbcCodec.setEnum(ps, i, v)` |

### Cơ chế xử lý null của kiểu wrapper qua `JdbcCodec`

`rs.getLong(i)` mặc định trả về `0` cho giá trị `NULL` trong database. Các hàm helper cho kiểu wrapper đảm bảo trả về đúng `null`:

```java
public static Long longOrNull(ResultSet rs, int column) throws SQLException {
    long v = rs.getLong(column);
    return rs.wasNull() ? null : v;
}
```

Việc chọn giữa `rs.getLong(i)` và `JdbcCodec.longOrNull(rs, i)` được quyết định tĩnh lúc build dựa trên kiểu khai báo của property: kiểu `long` nguyên thuỷ dùng đọc trực tiếp, kiểu `Long` wrapper dùng helper nhận biết null.

Khi ghi dữ liệu, `JdbcCodec.setLong(ps, i, null)` sẽ gọi `ps.setNull(i, Types.BIGINT)` với đúng kiểu SQL tương ứng.

## Enum

Enum được ánh xạ theo `name()` mặc định cho cả hai chiều và hỗ trợ an toàn `null`:

```java
public enum Status { NEW, PAID, SHIPPED }
```

```java
@Select("SELECT id, status, total FROM orders WHERE status = #{status}")
List<Order> byStatus(Status status);
```

Enum là một **kiểu dữ liệu có tập giá trị đóng**, do đó nó được phép bind trực tiếp vào `${}` vì toàn bộ không gian giá trị đã biết trước lúc build. Xem [SQL thô](raw-sql.md#the-rule).

Nếu cần lưu enum dưới dạng số thứ tự (ordinal) hoặc mã tuỳ biến, bạn cần khai báo [type handler riêng](#custom-type-handlers).

## `java.time`

`Instant`, `LocalDate`, `LocalTime` và `LocalDateTime` được chuyển đổi qua `java.sql.Timestamp` / `Date` / `Time`. `Instant` sử dụng `Timestamp.toInstant()` và `Timestamp.from(...)`, đảm bảo giá trị là tuyệt đối và không bị ảnh hưởng bởi múi giờ mặc định của JVM.

Các kiểu dữ liệu kèm múi giờ (`ZonedDateTime`, `OffsetDateTime`) không được tích hợp sẵn vì cột database chuẩn không lưu thông tin timezone. Khuyến nghị lưu trữ `Instant` (UTC) và chuyển đổi timezone ở tầng service.

## Đặt tên cột { #column-naming }

Tên cột được tự động ánh xạ sang property theo quy ước `snake_case` → `camelCase` lúc build (`created_at` → `setCreatedAt`). Mặc định được bật; bạn có thể dùng `-Alarkbatis.mapUnderscoreToCamelCase=false` để tắt. Xem [Cấu hình](../features/configuration.md#column-naming).

Khi cần ánh xạ tuỳ biến, bạn có thể dùng `<resultMap>`:

```xml
<resultMap id="userMap" type="com.example.app.User">
  <id     property="id"    column="id"/>
  <result property="email" column="usr_email"/>
</resultMap>
```

Hoặc sử dụng `@Column` trực tiếp trên property:

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

Một codebase từng dựa vào việc `mapUnderscoreToCamelCase` bị *tắt* thì hoặc mang luôn
tuỳ chọn đó sang, hoặc gắn `@Column` / `<resultMap>` cho những cột bị ảnh hưởng; dù chọn
cách nào thì [trình quét mã cũ](../features/migration.md) cũng báo cáo trường hợp này.

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

**Không tự tìm handler.** Không quét `@MappedTypes`, không quét package, không tra
`(Type, JdbcType)`. "Khai báo một lần rồi áp dụng khắp nơi" thì vẫn có, nhưng phải viết
ra chứ không được dò tìm: `-Alarkbatis.typeHandlers=com.example.Money:com.example.MoneyHandler`
đăng ký handler mặc định theo kiểu Java cho cả build, kiểm tra ngay lúc `javac`. Xem
[Cấu hình](../features/configuration.md#type-handlers-for-a-whole-build). Đằng nào bạn
cũng được một chỗ gọi sinh ra mà javac kiểm tra kiểu được, còn IDE thì nhảy tới được.

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
