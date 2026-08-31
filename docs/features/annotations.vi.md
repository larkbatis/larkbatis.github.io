# Annotation

Toàn bộ các annotation thuộc package `io.github.larkbatis.annotations`. Tất cả đều có phạm vi `@Retention(CLASS)`: chúng chỉ phục vụ cho trình biên dịch và không bao giờ tồn tại lúc runtime. Đó là lý do khi dùng Java module (JPMS), bạn chỉ cần khai báo `requires static`.

## Annotation cho statement

### `@Select` `@Insert` `@Update` `@Delete`

```java
@Retention(CLASS) @Target(METHOD)
public @interface Select { String[] value(); }
```

Nhận một mảng `String[]`, các chuỗi được nối với nhau bằng một dấu cách đơn. Được áp dụng trên phương thức của mapper interface.

```java
@Select({
    "SELECT id, name, email, created_at",
    "FROM users",
    "WHERE email = #{email}"
})
User findByEmail(String email);
```

Mỗi phương thức chỉ được phép khai báo **hoặc** bằng annotation **hoặc** bằng XML. Nếu khai báo cả hai, hoặc không khai báo cái nào, trình biên dịch sẽ báo lỗi.

---

## `@Mapper`

```java
@Retention(CLASS) @Target(TYPE)
public @interface Mapper { }
```

Đánh dấu interface có statement (toàn bộ hoặc một phần) được định nghĩa trong mapper XML. Thuộc tính `<mapper namespace="…">` của tệp XML bắt buộc phải là tên đầy đủ (FQN) của interface này, và thuộc tính `id` của mỗi statement phải khớp với tên phương thức tương ứng.

Các mapper chỉ dùng annotation **không bắt buộc** phải có `@Mapper`: annotation này tồn tại nhằm giúp annotation processor phát hiện được các interface chỉ dùng XML, vốn dĩ không có annotation nào trên phương thức để kích hoạt lượt xử lý.

---

## `@Param`

```java
@Retention(CLASS) @Target(PARAMETER)
public @interface Param { String value(); }
```

Đặt tên rõ ràng cho tham số để resolve trong `#{}`. Bắt buộc sử dụng khi phương thức có nhiều tham số, và là giải pháp thay thế an toàn khi dự án không bật cờ biên dịch `-parameters`.

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

Chỉ hỗ trợ tập thuộc tính phục vụ lấy khoá tự sinh (generated keys) của MyBatis.

| Thuộc tính | Ý nghĩa |
|---|---|
| `useGeneratedKeys` | Yêu cầu JDBC driver trả về khoá tự sinh sau câu lệnh `INSERT` |
| `keyProperty` | Tên thuộc tính (hoặc `param.property`) nhận giá trị khoá được sinh. **Bắt buộc** khi bật `useGeneratedKeys`; đặt sai tên sẽ báo lỗi biên dịch. Dùng dấu phẩy để phân tách khoá tổng hợp |
| `keyColumn` | Tên cột chứa khoá trong database, phân tách bằng dấu phẩy. Khuyến nghị luôn khai báo: nếu bỏ trống, trình biên dịch sẽ phát **cảnh báo bắt buộc** và fallback về `RETURN_GENERATED_KEYS` vốn không đảm bảo tính di động giữa các hệ quản trị database. Xem [Khoá tự sinh](../usage/generated-keys.md) |

Nếu cả hai thuộc tính đều chứa danh sách phân tách bằng dấu phẩy, hai danh sách phải có cùng số lượng phần tử.

```java
@Insert("INSERT INTO users (name, email) VALUES (#{name}, #{email})")
@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
int insert(User u);
```

[Chi tiết](../usage/generated-keys.md)

---

## `@OrderBy`

```java
@Retention(CLASS) @Target(PARAMETER)
public @interface OrderBy { String[] allowed(); }
```

Cho phép tham số kiểu `String` được chèn vào `${}`, bằng cách biên dịch thành câu lệnh `switch` kiểm tra trên danh sách giá trị cho phép (allow-list). Giá trị nằm ngoài danh sách sẽ bị từ chối lúc runtime với ngoại lệ `LarkBatisRejectedException` và tuyệt đối không bao giờ lọt vào chuỗi SQL.

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY ${sort}")
List<User> all(@OrderBy(allowed = {"id", "name", "created_at"}) String sort);
```

Nếu không có annotation này, tham số `String` gắn vào `${}` sẽ gây lỗi biên dịch.
[Chi tiết](../usage/raw-sql.md)

---

## `@PadPow2`

```java
@Retention(CLASS) @Target({TYPE, METHOD})
public @interface PadPow2 { }
```

Bổ sung (pad) số lượng phần tử giữ chỗ trong `<foreach>` lên luỹ thừa của 2 gần nhất bằng cách lặp lại phần tử cuối cùng. Kỹ thuật này giới hạn số biến thể câu SQL ở mức log₂(n) thay vì n, giúp database tái sử dụng execution plan trong cache. Trong Hibernate, kỹ thuật tương đương có tên là `in_clause_parameter_padding`.

Khi đặt trên interface, quy tắc áp dụng cho mọi statement bên trong; khi đặt trên phương thức, quy tắc chỉ áp dụng cho phương thức đó.

!!! warning "Quy tắc bắt buộc, không phụ thuộc vào suy đoán"

    Việc lặp lại phần tử cuối cùng chỉ an toàn tuyệt đối trong mệnh đề `IN`. Bộ sinh code yêu cầu phần thân của `<foreach>` chỉ được chứa duy nhất một liên kết `#{}` và câu lệnh không phải là `INSERT`. Nằm ngoài các giới hạn này, việc pad sẽ **báo lỗi biên dịch**, tránh tuyệt đối nguy cơ chèn trùng lặp dữ liệu trong im lặng.

[Chi tiết](../usage/foreach-and-batches.md#padpow2-bounding-the-sql-variants)

---

## `@Column`

```java
@Retention(CLASS) @Target({FIELD, METHOD})
public @interface Column { String value(); }
```

Chỉ định tên cột mà một thuộc tính kết quả sẽ đọc, áp dụng trong trường hợp quy ước chuyển đổi `snake_case` → `camelCase` lúc build không đáp ứng được: tên cột legacy không muốn đổi tên field Java, hoặc tên cột hoàn toàn khác với tên thuộc tính.

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

    // ...
}
```

Được đọc trên cả **field, setter và getter**: annotation hỗ trợ cả `FIELD` và `METHOD`, bạn khai báo ở đâu thì processor sẽ đọc ở đó. Khai báo hai vị trí khác nhau trỏ về hai cột khác nhau cho cùng một thuộc tính sẽ báo lỗi biên dịch, vì không có cách nào xác định vị trí nào là chính xác.

Tên chỉ định này thay thế tên thuộc tính ở mọi nơi khớp cột: trình đọc theo vị trí cột khi phân tích được câu SELECT, và câu lệnh `switch` theo tên khi không phân tích được. Việc so khớp không phân biệt hoa thường, và dấu gạch dưới mặc định được bỏ qua ở cả hai phía, do đó `@Column("usr_email")` cũng khớp với nhãn cột `USR_EMAIL` hoặc `usrEmail`. Nếu tắt cờ [`-Alarkbatis.mapUnderscoreToCamelCase=false`](configuration.md#column-naming), dấu gạch dưới sẽ có ý nghĩa phân biệt: annotation khi đó khớp `USR_EMAIL` nhưng không khớp `usrEmail`.

!!! warning "Một cột chỉ ánh xạ vào một thuộc tính"

    Hai thuộc tính cùng ánh xạ vào một cột là lỗi biên dịch và thông báo lỗi sẽ nêu rõ tên cả hai thuộc tính. Lỗi này bao gồm cả trường hợp một thuộc tính dùng `@Column` trùng tên với một thuộc tính khác. Bộ đọc sinh sẵn dùng câu lệnh switch trên tên cột, nên không thể có cách ánh xạ nào đúng nếu bị trùng lặp.

Thẻ `<resultMap>` luôn có độ ưu tiên cao nhất nếu được sử dụng: cấu hình trong XML định nghĩa ánh xạ cho từng statement cụ thể, chi tiết hơn cấu hình mặc định trên class.

---

## `@LarkBatisRow`

```java
@Retention(CLASS) @Target(TYPE)
public @interface LarkBatisRow { }
```

Yêu cầu sinh row reader cho một class không bao giờ xuất hiện làm `resultType` của statement nào: thường là cấu trúc dữ liệu của các truy vấn ad-hoc, chỉ được đọc qua [lối thoát thủ công](../usage/raw-sql.md#the-escape-hatch).

```java
@LarkBatisRow
public class DomainCount {
    private String domain;
    private long total;
    // constructor khong tham so + setter, tuong tu moi class ket qua
}
```

```java
default List<DomainCount> countByDomain(LarkBatisSession s, int minimum) {
    return s.query(
            SqlFragment.unsafeRawSql("SELECT ... GROUP BY domain HAVING COUNT(*) >= ?"),
            ps -> ps.setInt(1, minimum),
            DomainCountRow.READER);   // duoc sinh ra nho co annotation
}
```

Lý do `s.query(...)` nhận một `RowReader<T>` thay vì nhận `Class<T>`: nếu nhận `Class`, runtime buộc phải dùng reflection để tìm setter lúc chạy, làm mất đi đặc tính không dùng reflection của toàn bộ thiết kế. Nhờ reader được sinh sẵn, javac kiểm tra kiểu kết quả ngay lúc compile và không cần dò tìm gì khi ứng dụng khởi động.

Class áp dụng annotation này tuân thủ đúng quy ước của result class: constructor không tham số và các setter. **Thứ tự khai báo field trong class chính là thứ tự cột chuẩn** của `READER`, do không có câu SELECT tĩnh nào để xác định thứ tự. Câu SQL tự lắp ghép phải SELECT các cột theo đúng thứ tự đó, hoặc đọc thông qua `DomainCountRow.columns(rs)` và `DomainCountRow.read(rs, c)` để so khớp theo tên cột.

Đánh dấu annotation này lên một class đã được một statement trả về hoàn toàn không gây lỗi: processor chỉ sinh ra duy nhất một reader.

---

## `@Handler`

```java
@Retention(CLASS) @Target({PARAMETER, FIELD, METHOD})
public @interface Handler { Class<?> value(); }
```

Chỉ định rõ `LarkBatisTypeHandler` dùng để chuyển đổi một tham số hoặc một thuộc tính kết quả: gọi trực tiếp từ code sinh ra, không cần tra cứu registry và không quét classpath. Annotation này cũng gỡ bỏ giới hạn [danh sách kiểu dữ liệu mặc định](../usage/types.md) cho giá trị tương ứng.

Với kiểu dữ liệu luôn chuyển đổi theo một cách cố định trong toàn bộ dự án, bạn có thể đăng ký một lần qua cờ [`-Alarkbatis.typeHandlers`](configuration.md#type-handlers-for-a-whole-build) thay vì phải gắn annotation ở từng chỗ. Tuy nhiên, `@Handler` tại vị trí cụ thể luôn có độ ưu tiên cao nhất.

```java
public class Wallet {

    @Handler(MoneyHandler.class)
    private Money balance;
}

@Select("SELECT id FROM wallet WHERE balance >= #{floor}")
List<Long> atLeast(@Handler(MoneyHandler.class) Money floor);
```

Được đọc trên **field, setter và getter**, tương tự như `@Column`. Khai báo hai handler khác nhau trên cùng một thuộc tính sẽ gây lỗi biên dịch. Thuộc tính `typeHandler=` trong mapper XML có ý nghĩa tương đương và tuân thủ cùng quy tắc này.

Class handler phải là public, cụ thể (concrete), có constructor public không tham số, và là stateless (không lưu trạng thái) vì chỉ một instance duy nhất được dùng chung. Xem [type handler tuỳ biến](../usage/types.md#custom-type-handlers) để nắm đầy đủ quy chuẩn.

!!! note "Tại sao dùng `Class<?>` thay vì `Class<? extends LarkBatisTypeHandler<?>>`"

    Nếu ràng buộc kiểu chặt chẽ trong annotation, artifact `larkbatis-annotations` sẽ bị phụ thuộc vào `larkbatis-runtime`. Việc không phụ thuộc dependency nào giúp bạn có thể khai báo `larkbatis-annotations` với phạm vi `requires static`. Processor sẽ thực hiện toàn bộ các bước kiểm tra kiểu thay cho javac và đưa ra thông báo lỗi chi tiết nếu handler không hợp lệ.
