# SQL thô và SqlFragment

Ký hiệu `#{}` biểu thị tham số bind (Prepared Statement). Ký hiệu `${}` chèn trực tiếp chuỗi vào câu SQL — nơi tiềm ẩn nguy cơ SQL Injection. LarkBatis không cấm `${}` vì các yêu cầu như sắp xếp động (`ORDER BY`) theo lựa chọn của người dùng là nhu cầu thực tế, nhưng bắt buộc mọi điểm chèn phải được kiểm soát kiểu tĩnh và có thể kiểm toán dễ dàng.

## Quy tắc bắt buộc { #the-rule }

!!! failure "Tham số `String` thô gắn vào `${}` là lỗi biên dịch"

    ```java
    @Select("SELECT id, name FROM users ORDER BY ${sort}")
    List<User> all(String sort);        // lỗi biên dịch
    ```

    Thông báo lỗi sẽ nêu rõ tên tham số và liệt kê ba dạng kiểu dữ liệu hợp lệ được chấp nhận.

| Kiểu dữ liệu hợp lệ cho `${}` | Cơ chế bảo đảm an toàn |
|---|---|
| `SqlFragment` | Khởi tạo qua static factory đã whitelist giá trị, hoặc qua `unsafeRawSql` (điểm kiểm toán duy nhất) |
| Kiểu dữ liệu tập giá trị đóng: `int`, `long`, `short`, `byte`, `boolean`, enum | Toàn bộ không gian giá trị vốn dĩ an toàn trong cú pháp SQL |
| `String` kèm annotation `@OrderBy(allowed = {...})` | Biên dịch thành cấu trúc `switch` trên danh sách hằng số an toàn |

## `@OrderBy`

Giải pháp thuận tiện nhất cho việc sắp xếp động mà không đòi hỏi xử lý phức tạp ở phía gọi:

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY ${sort}")
List<User> all(@OrderBy(allowed = {"id", "name", "created_at"}) String sort);
```

Bộ sinh code phát ra một `switch` trên ba hằng số này. Giá trị nằm ngoài danh sách sẽ bị từ chối bằng ngoại lệ `LarkBatisRejectedException` nêu rõ giá trị vi phạm và tập hợp hợp lệ. Giá trị không an toàn sẽ không bao giờ chạm tới câu SQL gửi xuống database.

## `SqlFragment`

Ba phương thức khởi tạo tĩnh thể hiện ba mức độ kiểm soát khác nhau:

```java
SqlFragment.allowed(value, "created_at", "name")   // (1)!
SqlFragment.identifier(value)                      // (2)!
SqlFragment.unsafeRawSql(value)                    // (3)!
```

1.  Danh sách whitelist đóng. Mọi giá trị khác đều ném `LarkBatisRejectedException`. **Khuyến nghị ưu tiên sử dụng phương thức này.**
2.  Chỉ chấp nhận định danh SQL thuần (chữ cái, chữ số, dấu gạch dưới, dấu chấm phân cách) và từ chối mọi ký tự đặc biệt khác. Phù hợp cho tên bảng hoặc tên cột cấu hình động.
3.  Chấp nhận chuỗi bất kỳ. Đây là điểm kiểm toán duy nhất cho câu SQL tuỳ biến trong toàn bộ dự án.

```java
@Select("SELECT id, name FROM users WHERE ${predicate} ORDER BY id")
List<User> where(SqlFragment predicate);
```

### Vì sao phương thức mang tên `unsafeRawSql`

Tên gọi `unsafeRawSql` mang tính cảnh báo chủ đích. Để kiểm toán toàn bộ các điểm chèn SQL thô trong một dự án LarkBatis, bạn chỉ cần chạy:

```console
$ grep -rn 'unsafeRawSql' src/
```

Trong MyBatis, bạn không có điểm quy tụ tương đương: ký hiệu `${}` rải rác trong file XML và các chuỗi SQL trong `@SelectProvider` phân tán khắp nơi, buộc phải rà soát thủ công từng file.

## Theo dõi biến thể SQL { #tracking-sql-variants }

Statement cache của JDBC driver và database lấy **chuỗi SQL** làm khoá. Một fragment có tập giá trị không giới hạn sẽ làm bộ nhớ cache này phình to liên tục mà không thể phát hiện qua unit test.

Hai loại statement có câu SQL không cố định từ lúc build gồm: điểm chèn `${}` và `<foreach>` có số phần tử thay đổi. Cả hai đều được tự động bổ sung lệnh theo dõi:

```java
LarkBatisSql.trackVariants(STMT_findByIds, sql);
```

Hệ thống đếm số biến thể SQL khác nhau cho mỗi statement. Khi vượt ngưỡng, hệ thống sẽ ghi **một** dòng log cảnh báo chỉ rõ tên statement và dừng lưu thêm chuỗi SQL mới vào bộ nhớ.

```yaml title="application.yml"
larkbatis:
  max-sql-variants: 64                # mặc định
  fail-on-unbounded-fragment: false   # mặc định
```

Ngoài Spring thì vẫn là những thiết lập đó dưới dạng system property (`-Dlarkbatis.maxSqlVariants=64`, `-Dlarkbatis.failOnUnboundedVariants=true`) hoặc các phương thức tĩnh `LarkBatisSql.maxSqlVariants(int)` và `LarkBatisSql.failOnUnboundedVariants(boolean)`.

!!! tip "Hãy bật `fail-on-unbounded-fragment` ở môi trường staging"

    Một hệ thống production không nên ném lỗi chỉ vì xu hướng phân mảnh SQL, nên mặc định là cảnh báo. Bật `fail-on-unbounded-fragment` trên staging sẽ giúp phát hiện sớm các fragment có tập giá trị không bị giới hạn trước khi triển khai lên production.

`@PadPow2` là giải pháp hữu hiệu cho `<foreach>`: chặn số biến thể bằng cấu trúc thay vì chỉ cảnh báo. Xem [foreach và batch](foreach-and-batches.md#padpow2-bounding-the-sql-variants).

## `${}` trong select list

Một `${}` nằm trong select list đồng nghĩa bộ sinh code không thể phân tích cú pháp tĩnh danh sách cột, do đó statement đó sẽ sử dụng cơ chế fallback: đọc theo tên cột từ `ResultSetMetaData` ở dòng đầu tiên. Xem [Đọc theo vị trí hay theo tên](mappers.md#positional-or-name-based-reads).

## Lối thoát thủ công (Escape Hatch) { #the-escape-hatch }

Khi cần thực thi câu SQL ráp tay trong Java, phương thức `default` trên interface mapper là vị trí lý tưởng:

```java
default List<User> recent(LarkBatisSession s, int limit) {
    return s.query(
            SqlFragment.unsafeRawSql(
                    "SELECT id, name, email, created_at FROM users"
                            + " ORDER BY created_at DESC LIMIT " + limit),
            ps -> { },                 // (1)!
            UserRow.READER);           // (2)!
}
```

1.  Một `StatementBinder` (lambda trên `PreparedStatement`). Hãy bind các dấu `?` tại đây thay vì nối trực tiếp giá trị vào chuỗi SQL.
2.  Row reader **được sinh sẵn**. Không reflection, và kiểu kết quả luôn được javac kiểm tra kiểu tĩnh.

Các phương thức thực thi SQL thô:

| Phương thức | Trả về |
|---|---|
| `s.query(SqlFragment, StatementBinder, RowReader<T>)` | `List<T>` |
| `s.queryOne(SqlFragment, StatementBinder, RowReader<T>)` | `T` hoặc `null` |
| `s.queryStream(SqlFragment, StatementBinder, RowReader<T>)` | `Stream<T>`, người gọi đóng |
| `s.update(SqlFragment, StatementBinder)` | `int` |

Không có phương thức overload nào nhận `String` thuần: mọi câu SQL tuỳ biến bắt buộc phải đi qua cổng `SqlFragment` đã được rà soát.

Nếu một class chỉ dùng ở đây mà không xuất hiện làm `resultType` của statement nào, hãy đánh dấu bằng [`@LarkBatisRow`](../features/annotations.md#larkbatisrow):

```java
@LarkBatisRow
public class DomainCount {
    private String domain;
    private long total;
    // constructor không tham số + các setter
}
```

```java
default List<DomainCount> countByDomain(LarkBatisSession s, int minimum) {
    return s.query(
            SqlFragment.unsafeRawSql("SELECT domain, COUNT(*) AS total FROM contacts"
                    + " GROUP BY domain HAVING COUNT(*) >= ?"),
            ps -> ps.setInt(1, minimum),
            DomainCountRow.READER);
}
```

`READER` đọc **theo vị trí dựa trên thứ tự khai báo field trong class**. Trường hợp SQL ráp tay không đảm bảo thứ tự đó, bạn có thể đọc theo tên:

```java
int[] c = DomainCountRow.columns(rs);   // lấy một lần từ ResultSetMetaData
DomainCount row = DomainCountRow.read(rs, c);
```
