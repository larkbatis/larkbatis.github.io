# Raw SQL & An toàn

Cú pháp `#{}` biểu thị tham số bind (`PreparedStatement`), trong khi `${}` biểu thị việc chèn trực tiếp chuỗi vào câu lệnh SQL — nguyên nhân hàng đầu gây lỗi bảo mật SQL Injection.

LarkBatis không cấm `${}` vì các trường hợp như sắp xếp động (`ORDER BY`) là nhu cầu thực tế. Tuy nhiên, LarkBatis bắt buộc mọi điểm chèn `${}` phải được kiểm soát kiểu tĩnh an toàn.

## Nguyên tắc kiểu dữ liệu cho `${}` { #the-rule }

!!! failure "Cấm gán trực tiếp tham số `String` không kiểm soát vào `${}`"

    ```java
    @Select("SELECT id, name FROM users ORDER BY ${sort}")
    List<User> all(String sort);        // Lỗi biên dịch javac
    ```

| Kiểu dữ liệu hợp lệ cho `${}` | Cơ chế bảo đảm an toàn |
|---|---|
| `SqlFragment` | Khởi tạo qua static factory đã whitelist giá trị, hoặc qua `unsafeRawSql` (điểm kiểm toán duy nhất) |
| Kiểu tập giá trị đóng (`int`, `long`, `boolean`, `enum`) | Toàn bộ không gian giá trị đều an toàn về mặt cú pháp SQL |
| `String` có gắn `@OrderBy(allowed = {...})` | Biên dịch thành câu lệnh `switch` kiểm tra whitelist trước khi thực thi |

## `@OrderBy`

Giải pháp sắp xếp động an toàn và tiện lợi:

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY ${sort}")
List<User> all(@OrderBy(allowed = {"id", "name", "created_at"}) String sort);
```

Processor sẽ sinh câu lệnh `switch` kiểm tra giá trị tham số `sort`. Nếu giá trị truyền vào không nằm trong whitelist, hệ thống lập tức ném ngoại lệ `LarkBatisRejectedException` và ngăn chặn SQL độc hại gửi xuống database.

## `SqlFragment`

Đối tượng đại diện cho chuỗi SQL tùy biến với 3 mức độ bảo mật:

```java
SqlFragment.allowed(value, "created_at", "name")   // (1)! Whitelist đóng (Khuyến nghị dùng)
SqlFragment.identifier(value)                      // (2)! Chỉ cho phép định danh SQL chuẩn
SqlFragment.unsafeRawSql(value)                    // (3)! Chuỗi SQL thô (Điểm cần kiểm toán bảo mật)
```

Sử dụng trong Mapper interface:

```java
@Select("SELECT id, name FROM users WHERE ${predicate} ORDER BY id")
List<User> where(SqlFragment predicate);
```

### Kiểm toán bảo mật với `unsafeRawSql`

Tất cả các điểm ghép chuỗi SQL thô trong toàn bộ dự án đều tập trung vào phương thức `unsafeRawSql`. Bạn có thể kiểm toán toàn bộ codebase chỉ bằng một lệnh grep:

```console
$ grep -rn 'unsafeRawSql' src/
```

## Theo dõi biến thể SQL (Tracking SQL Variants) { #tracking-sql-variants }

Prepared statement cache của JDBC driver định danh câu truy vấn theo **chuỗi SQL**. Nếu một câu SQL động chứa `${}` hoặc `<foreach>` sinh ra vô số chuỗi khác nhau, statement cache sẽ bị phình to liên tục.

LarkBatis tự động chèn lệnh theo dõi biến thể:

```java
LarkBatisSql.trackVariants(STMT_findByIds, sql);
```

Khi số lượng biến thể vượt quá ngưỡng (mặc định 64), hệ thống sẽ ghi log cảnh báo.

```yaml title="application.yml"
larkbatis:
  max-sql-variants: 64                # Ngưỡng số lượng chuỗi SQL tối đa
  fail-on-unbounded-fragment: false   # Ném exception nếu vượt ngưỡng (nên bật trên Staging)
```

## Lối thoát thủ công (`s.query()`) { #the-escape-hatch }

Khi cần thực thi các câu SQL động phức tạp được ghép trong mã Java, hãy viết phương thức `default` trên mapper interface và sử dụng `s.query()`:

```java
default List<User> recent(LarkBatisSession s, int limit) {
    return s.query(
            SqlFragment.unsafeRawSql(
                    "SELECT id, name, email, created_at FROM users"
                            + " ORDER BY created_at DESC LIMIT " + limit),
            ps -> { },                 // StatementBinder: bind tham số nếu có
            UserRow.READER);           // Tái sử dụng UserRow.READER sinh sẵn không cần reflection
}
```

Các phương thức thực thi thủ công:

| Phương thức | Kết quả trả về |
|---|---|
| `s.query(SqlFragment, StatementBinder, RowReader<T>)` | `List<T>` |
| `s.queryOne(SqlFragment, StatementBinder, RowReader<T>)` | `T` hoặc `null` |
| `s.queryStream(SqlFragment, StatementBinder, RowReader<T>)` | `Stream<T>` (người gọi có trách nhiệm đóng stream) |
| `s.update(SqlFragment, StatementBinder)` | `int` (số dòng bị ảnh hưởng) |

Nếu một class POJO chỉ dùng cho các truy vấn thủ công ad-hoc, hãy gắn `@LarkBatisRow` để processor sinh `RowReader`:

```java
@LarkBatisRow
public class DomainCount {
    private String domain;
    private long total;
}
```

