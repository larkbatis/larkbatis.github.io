# Danh mục Annotations

Tất cả annotations của LarkBatis nằm trong package `io.github.larkbatis.annotations`. Toàn bộ đều có phạm vi `@Retention(CLASS)`: chỉ phục vụ quá trình biên dịch (`javac`) và không tồn tại lúc runtime. Khi sử dụng JPMS, bạn chỉ cần khai báo `requires static io.github.larkbatis.annotations;`.

## Annotations cho Statement

### `@Select`, `@Insert`, `@Update`, `@Delete`

```java
@Retention(CLASS) @Target(METHOD)
public @interface Select { String[] value(); }
```

Nhận mảng `String[]` chứa câu lệnh SQL (tự động nối các phần tử bằng một dấu cách đơn).

```java
@Select({
    "SELECT id, name, email, created_at",
    "FROM users",
    "WHERE email = #{email}"
})
User findByEmail(String email);
```

Mỗi phương thức mapper chỉ được định nghĩa **hoặc** bằng annotation **hoặc** trong file XML. Nếu khai báo cả hai hoặc không khai báo ở đâu, trình biên dịch sẽ báo lỗi.

---

## `@Mapper`

```java
@Retention(CLASS) @Target(TYPE)
public @interface Mapper { }
```

Đánh dấu interface có statement được định nghĩa trong mapper XML. Thuộc tính `namespace` trong file XML bắt buộc phải khớp với FQN của interface.

Các mapper chỉ dùng annotation **không bắt buộc** phải có `@Mapper`. Annotation này cần thiết để processor nhận biết các interface chỉ khai báo truy vấn qua XML.

---

## `@Param`

```java
@Retention(CLASS) @Target(PARAMETER)
public @interface Param { String value(); }
```

Đặt tên tham số tường minh để đối chiếu trong `#{}`. Bắt buộc khi phương thức có nhiều tham số nếu dự án không bật cờ biên dịch `-parameters`.

```java
@Select("SELECT id, name FROM users WHERE name LIKE #{pattern} AND id > #{after}")
List<User> page(@Param("pattern") String pattern, @Param("after") long after);
```

---

## `@Options`

```java
@Retention(CLASS) @Target(METHOD)
public @interface Options {
    boolean useGeneratedKeys() default false;
    String keyProperty() default "";
    String keyColumn() default "";
}
```

Cấu hình tự động lấy khóa chính tự tăng sau câu lệnh `INSERT`.

| Thuộc tính | Ý nghĩa |
|---|---|
| `useGeneratedKeys` | Bật tính năng lấy Generated Keys từ JDBC driver |
| `keyProperty` | Tên thuộc tính trong Java Bean nhận giá trị khóa chính (bắt buộc khi bật `useGeneratedKeys`) |
| `keyColumn` | Tên cột khóa chính trong database. Khuyến nghị luôn khai báo rõ ràng để đảm bảo tương thích đa cơ sở dữ liệu (PostgreSQL, Oracle, v.v.). Xem [Generated Keys](../usage/generated-keys.md) |

```java
@Insert("INSERT INTO users (name, email) VALUES (#{name}, #{email})")
@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
int insert(User u);
```

---

## `@OrderBy`

```java
@Retention(CLASS) @Target(PARAMETER)
public @interface OrderBy { String[] allowed(); }
```

Cho phép truyền tham số `String` an toàn vào `${}` bằng cách kiểm tra giá trị runtime với danh sách whitelist định sẵn. Nếu giá trị không khớp, hệ thống ném `LarkBatisRejectedException` và chặn đứng trước khi SQL được thực thi.

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY ${sort}")
List<User> all(@OrderBy(allowed = {"id", "name", "created_at"}) String sort);
```

Xem [Raw SQL & An toàn](../usage/raw-sql.md).

---

## `@PadPow2`

```java
@Retention(CLASS) @Target({TYPE, METHOD})
public @interface PadPow2 { }
```

Tự động đệm (pad) số lượng phần tử giữ chỗ trong `<foreach>` lên lũy thừa của 2 gần nhất bằng cách lặp lại phần tử cuối cùng. Giúp database tái sử dụng statement execution plan trong cache hiệu quả hơn.

Có thể đặt trên interface (áp dụng toàn bộ mapper) hoặc trên từng phương thức cụ thể.

!!! warning "Chỉ áp dụng cho mệnh đề `IN`"

    Việc lặp lại phần tử chỉ an toàn trong mệnh đề `WHERE ... IN (...)`. Bộ sinh code cấm dùng `@PadPow2` trong câu lệnh `INSERT` và sẽ báo lỗi compile nếu phát hiện.

Xem [foreach & Batching](../usage/foreach-and-batches.md#padpow2-bounding-the-sql-variants).

---

## `@Column`

```java
@Retention(CLASS) @Target({FIELD, METHOD})
public @interface Column { String value(); }
```

Chỉ định tên cột trong database cho một trường POJO khi tên cột không thể ánh xạ tự động theo quy tắc `snake_case` → `camelCase`.

```java
public class Contact {

    @Column("contact_id")
    private long id;
    private String email;
    private String phone;

    @Column("usr_email")
    public void setEmail(String email) { this.email = email; }

    @Column("mobile")
    public String getPhone() { return phone; }
}
```

Có thể gắn trên **field, setter hoặc getter**. Khai báo trùng lặp hoặc mâu thuẫn tên cột sẽ báo lỗi compile ngay lúc build.

---

## `@LarkBatisRow`

```java
@Retention(CLASS) @Target(TYPE)
public @interface LarkBatisRow { }
```

Yêu cầu processor sinh `RowReader` cho một POJO class không xuất hiện trong kiểu trả về của mapper nào (thường dùng cho các câu truy vấn động ad-hoc qua [lối thoát thủ công `session.query()`](../usage/raw-sql.md#the-escape-hatch)).

```java
@LarkBatisRow
public class DomainCount {
    private String domain;
    private long total;
}
```

```java
default List<DomainCount> countByDomain(LarkBatisSession s, int minimum) {
    return s.query(
            SqlFragment.unsafeRawSql("SELECT domain, COUNT(*) FROM users GROUP BY domain HAVING COUNT(*) >= ?"),
            ps -> ps.setInt(1, minimum),
            DomainCountRow.READER);   // Sinh ra tự động nhờ @LarkBatisRow
}
```

---

## `@Handler`

```java
@Retention(CLASS) @Target({PARAMETER, FIELD, METHOD})
public @interface Handler { Class<?> value(); }
```

Chỉ định rõ `LarkBatisTypeHandler` tùy biến dùng cho một tham số hoặc một trường thuộc tính. Mã nguồn sinh ra sẽ gọi trực tiếp handler này mà không cần tra cứu runtime registry.

```java
public class Wallet {

    @Handler(MoneyHandler.class)
    private Money balance;
}

@Select("SELECT id FROM wallet WHERE balance >= #{floor}")
List<Long> atLeast(@Handler(MoneyHandler.class) Money floor);
```

Xem [Kiểu dữ liệu & Type Handlers](../usage/types.md#custom-type-handlers).

