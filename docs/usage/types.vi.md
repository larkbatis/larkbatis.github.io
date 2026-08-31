# Kiểu dữ liệu & Type Handlers

Trong MyBatis, `TypeHandler` là một dynamic registry tra cứu lúc runtime theo cặp `(javaType, jdbcType)` qua reflection.

LarkBatis xác định toàn bộ các chuyển đổi kiểu dữ liệu lúc build và sinh lệnh gọi JDBC trực tiếp. Lúc runtime, hệ thống chỉ sử dụng `JdbcCodec` — class chứa các static helper xử lý null an toàn cho các kiểu primitive/wrapper và `java.time`.

## Các kiểu dữ liệu hỗ trợ sẵn

Ký hiệu `#{}` và các thuộc tính POJO kết quả hỗ trợ sẵn các kiểu dữ liệu sau:

| Kiểu Java | Đọc ResultSet | Ghi PreparedStatement |
|---|---|---|
| `String` | `rs.getString(i)` | `ps.setString(i, v)` |
| `long`, `int`, `short`, `byte`, `boolean`, `float`, `double` | `rs.getLong(i)` v.v. | `ps.setLong(i, v)` v.v. |
| `Long`, `Integer`, … (Wrapper) | `JdbcCodec.longOrNull(rs, i)` | `JdbcCodec.setLong(ps, i, v)` |
| `BigDecimal`, `BigInteger` | `rs.getBigDecimal(i)` | `ps.setBigDecimal(i, v)` |
| `byte[]` | `rs.getBytes(i)` | `ps.setBytes(i, v)` |
| `java.sql.Date`, `Time`, `Timestamp` | Trực tiếp JDBC | Trực tiếp JDBC |
| `Instant`, `LocalDate`, `LocalTime`, `LocalDateTime` | `JdbcCodec.instant(rs, i)` v.v. | `JdbcCodec.setInstant(ps, i, v)` v.v. |
| Mọi `enum` | `JdbcCodec.enumValue(...)` | `JdbcCodec.setEnum(ps, i, v)` |

### Cơ chế xử lý null cho kiểu Wrapper qua `JdbcCodec`

JDBC `rs.getLong(i)` mặc định trả về `0` khi giá trị trong database là `SQL NULL`. Các hàm helper trong `JdbcCodec` kiểm tra `rs.wasNull()` để trả về đúng `null`:

```java
public static Long longOrNull(ResultSet rs, int column) throws SQLException {
    long v = rs.getLong(column);
    return rs.wasNull() ? null : v;
}
```

Khi ghi dữ liệu, `JdbcCodec.setLong(ps, i, null)` sẽ tự động gọi `ps.setNull(i, Types.BIGINT)`.

## Enum

Enum được ánh xạ tự động theo tên chuỗi `name()` và hỗ trợ null an toàn:

```java
public enum Status { NEW, PAID, SHIPPED }
```

```java
@Select("SELECT id, status, total FROM orders WHERE status = #{status}")
List<Order> byStatus(Status status);
```

Vì Enum là **kiểu dữ liệu có tập giá trị đóng**, bạn có thể truyền biến Enum trực tiếp vào chuỗi `${}`. Xem [Raw SQL & An toàn](raw-sql.md#the-rule).

Nếu cần lưu Enum dưới dạng số thứ tự (ordinal) hoặc mã code database riêng, hãy tạo [TypeHandler tùy biến](#custom-type-handlers).

## `java.time`

Các kiểu `Instant`, `LocalDate`, `LocalTime`, `LocalDateTime` được chuyển đổi qua `java.sql.Timestamp` / `Date` / `Time`. `Instant` sử dụng `Timestamp.toInstant()` và `Timestamp.from(...)`, đảm bảo giá trị thời gian chuẩn UTC và không bị ảnh hưởng bởi múi giờ JVM.

## Ánh xạ tên cột (Column Naming) { #column-naming }

LarkBatis tự động ánh xạ cột sang setter theo quy ước `snake_case` → `camelCase` lúc build (`created_at` → `setCreatedAt`). Bạn có thể tắt quy ước này bằng `-Alarkbatis.mapUnderscoreToCamelCase=false`.

Nếu tên cột trong database khác biệt với thuộc tính Java:
1. Sử dụng thẻ `<resultMap>` trong XML:
   ```xml
   <resultMap id="userMap" type="com.example.app.User">
     <id     property="id"    column="id"/>
     <result property="email" column="usr_email"/>
   </resultMap>
   ```
2. Gắn annotation `@Column` trực tiếp trên field, setter hoặc getter:
   ```java
   public class User {
       @Column("usr_email")
       private String email;

       public void setEmail(String email) { this.email = email; }
   }
   ```

## TypeHandler tùy biến { #custom-type-handlers }

Đối với các kiểu dữ liệu phức tạp (ví dụ `Money`, JSON node, hoặc enum tùy biến), bạn implement interface `LarkBatisTypeHandler<T>`:

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

### Các nguyên tắc khi viết TypeHandler

1. **Stateless, public, concrete class với constructor mặc định không tham số**: Code sinh ra lưu handler trong một biến `static final` và tái sử dụng cho toàn bộ ứng dụng.
2. **Kiểu generic tham số hóa rõ ràng**: `LarkBatisTypeHandler<Money>` phải khớp chính xác với kiểu trường POJO.
3. **Tự xử lý null an toàn**: Handler tự kiểm tra `value == null` khi ghi (`write`) và kiểm tra `rs.wasNull()` khi đọc (`read`).

### Khai báo và sử dụng TypeHandler

- **Trên thuộc tính POJO hoặc tham số Mapper**:
  ```java
  public class Wallet {
      @Handler(MoneyHandler.class)
      private Money balance;
  }

  @Select("SELECT id FROM wallet WHERE balance >= #{floor}")
  List<Long> atLeast(@Handler(MoneyHandler.class) Money floor);
  ```

- **Trong Mapper XML**:
  ```xml
  <resultMap id="entry" type="com.example.Entry">
      <id property="id" column="id"/>
      <result property="amount" column="amount" typeHandler="com.example.MoneyHandler"/>
  </resultMap>
  ```

- **Toàn cục cho toàn bộ dự án**:
  ```
  -Alarkbatis.typeHandlers=com.example.Money:com.example.MoneyHandler
  ```

