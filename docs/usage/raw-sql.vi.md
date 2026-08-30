# SQL thô và SqlFragment

`#{}` là một tham số bind. `${}` chèn thẳng chuỗi vào câu SQL, và đó chính là chỗ SQL
injection phát sinh. LarkBatis không cấm `${}`, vì sắp xếp theo cột do người dùng chọn
là một nhu cầu có thật. Nhưng nó bắt mọi chỗ chèn phải đi qua một kiểu mà trình biên dịch
kiểm tra được, và một cái tên mà bạn `grep` ra được.

## Quy tắc { #the-rule }

!!! failure "Một tham số `String` gắn vào `${}` là lỗi biên dịch"

    ```java
    @Select("SELECT id, name FROM users ORDER BY ${sort}")
    List<User> all(String sort);        // lỗi biên dịch
    ```

    Thông báo lỗi gọi tên tham số và liệt kê ba dạng được chấp nhận.

| Được chấp nhận cho `${}` | Vì sao nó an toàn |
|---|---|
| `SqlFragment` | Được dựng qua một factory đã kiểm tra giá trị, hoặc qua `unsafeRawSql`, điểm rà soát duy nhất |
| Kiểu giá trị đóng: `int`, `long`, `short`, `byte`, `boolean`, enum | Toàn bộ không gian giá trị của chúng vốn đã an toàn với SQL |
| `String` chú thích `@OrderBy(allowed = {...})` | Biên dịch thành một `switch` trên danh sách hằng |

## `@OrderBy`

Trường hợp phổ biến nhất, và cũng là trường hợp không đòi hỏi thủ tục gì ở chỗ gọi:

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY ${sort}")
List<User> all(@OrderBy(allowed = {"id", "name", "created_at"}) String sort);
```

Bộ sinh code phát ra một `switch` trên ba hằng đó. Một giá trị ngoài danh sách bị từ chối
bằng `LarkBatisRejectedException` nêu rõ giá trị đó và tập được phép. Giá trị ấy không
bao giờ chạm tới câu SQL.

## `SqlFragment`

Ba factory, và khác biệt giữa chúng chính là toàn bộ vấn đề:

```java
SqlFragment.allowed(value, "created_at", "name")   // (1)!
SqlFragment.identifier(value)                      // (2)!
SqlFragment.unsafeRawSql(value)                    // (3)!
```

1.  Một danh sách cho phép đóng. Mọi thứ khác đều ném `LarkBatisRejectedException`.
    **Hãy ưu tiên cái này.**
2.  Chấp nhận một định danh SQL thuần (chữ cái, chữ số, gạch dưới, có thể có dấu chấm
    phân định) và từ chối mọi thứ khác. Dành cho tên cột và tên bảng thực sự đến từ cấu
    hình.
3.  Chấp nhận bất cứ thứ gì. Điểm rà soát duy nhất cho câu SQL tuỳ ý trong toàn bộ
    codebase.

```java
@Select("SELECT id, name FROM users WHERE ${predicate} ORDER BY id")
List<User> where(SqlFragment predicate);
```

### Vì sao `unsafeRawSql` mang cái tên đó

Cái tên mang sẵn lời cảnh báo, vì đây là nơi duy nhất chuỗi tuỳ ý trở thành SQL. Rà soát
việc chèn SQL thô trong một codebase LarkBatis là:

```console
$ grep -rn 'unsafeRawSql' src/
```

MyBatis không có điểm hội tụ tương đương. `${}` rải rác khắp XML, thân của
`@SelectProvider` rải rác khắp Java, và muốn tìm cho đủ thì phải đọc từng mapper một.

## Theo dõi biến thể SQL { #tracking-sql-variants }

Statement cache, cả của driver lẫn của database, đều lấy **câu SQL** làm khoá. Một
fragment có tập giá trị không bị chặn sẽ làm chúng phình ra vô hạn, và bạn chỉ biết
chuyện đó qua một sự cố bộ nhớ hoặc độ trễ, chứ không phải qua một bug.

Có hai loại statement mà câu SQL không cố định từ lúc build: một chỗ chèn `${}`, và một
`<foreach>`, vì số phần tử cũng làm đổi câu SQL y hệt. Cả hai đều nhận thêm một lời gọi
được sinh ra:

```java
LarkBatisSql.trackVariants(STMT_findByIds, sql);
```

Nó đếm số câu SQL khác nhau cho mỗi statement. Vượt ngưỡng thì bạn nhận **một** dòng
log gọi tên statement, và bộ đếm ngừng giữ lại các văn bản.

```yaml title="application.yml"
larkbatis:
  max-sql-variants: 64                # mặc định
  fail-on-unbounded-fragment: false   # mặc định
```

Ngoài Spring thì vẫn là những thiết lập đó dưới dạng system property
(`-Dlarkbatis.maxSqlVariants=64`, `-Dlarkbatis.failOnUnboundedVariants=true`) hoặc các
phương thức tĩnh `LarkBatisSql.maxSqlVariants(int)` và
`LarkBatisSql.failOnUnboundedVariants(boolean)`.

!!! tip "Hãy bật `fail-on-unbounded-fragment` ở môi trường staging"

    Một hệ thống production không nên bắt đầu ném lỗi chỉ vì một xu hướng đáng ghi log,
    nên mặc định là cảnh báo. Một profile test hay staging có ném
    `LarkBatisUnboundedVariantsException` sẽ tìm ra cái fragment không bị chặn trước khi
    nó lên production.

`@PadPow2` là nửa còn lại của câu chuyện này cho `<foreach>`: nó chặn số biến thể bằng
cấu trúc thay vì chỉ báo cáo về chúng. Xem
[foreach và batch](foreach-and-batches.md#padpow2-bounding-the-sql-variants).

## `${}` trong select list

Một `${}` nằm trong select list nghĩa là bộ sinh code không phân tích được các cột, nên
riêng statement đó lùi về dùng row reader theo tên, với chỉ số lấy từ `ResultSetMetaData`
ở dòng đầu tiên. Vẫn đúng, chậm hơn ở mức đo được, và **được báo lúc build**, nên bạn
thấy được cái giá ngay lúc chấp nhận nó.

## Cửa thoát hiểm { #the-escape-hatch }

Đôi khi câu SQL thật sự phải được ráp bằng Java. Một phương thức `default` trên interface
mapper là chỗ dành cho việc đó, và nó giữ lại hai tính chất quan trọng:

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

1.  Một `StatementBinder`, tức một lambda trên `PreparedStatement`. Hãy bind các dấu `?`
    của bạn ở đây; ưu tiên cách này thay vì chèn giá trị thẳng vào câu SQL.
2.  Row reader **được sinh ra**. Không reflection, và kiểu kết quả vẫn được javac kiểm
    tra.

Các điểm vào:

| Phương thức | Trả về |
|---|---|
| `s.query(SqlFragment, StatementBinder, RowReader<T>)` | `List<T>` |
| `s.queryOne(SqlFragment, StatementBinder, RowReader<T>)` | `T` hoặc `null` |
| `s.queryStream(SqlFragment, StatementBinder, RowReader<T>)` | `Stream<T>`, người gọi đóng |
| `s.update(SqlFragment, StatementBinder)` | `int` |

Để ý xem chữ ký từ chối điều gì: không có phiên bản nạp chồng nhận `String`. Ngay cả ở
đây, câu SQL tuỳ ý vẫn phải đi qua đúng cái cổng đã được rà soát đó.

Mỗi lớp được dùng làm `resultType` của một statement đều có sẵn một reader. Một lớp *chỉ*
dùng ở đây thì chẳng có statement nào kích hoạt việc sinh reader, nên hãy đánh dấu nó
bằng [`@LarkBatisRow`](../features/annotations.md#larkbatisrow):

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

`READER` đọc **theo vị trí, theo thứ tự khai báo của lớp**, bởi lúc build không có select
list nào để đối chiếu thứ tự cả. Chỗ nào SQL ráp tay không bảo đảm được thứ tự đó thì
khớp theo tên:

```java
int[] c = DomainCountRow.columns(rs);   // một lần, từ ResultSetMetaData
DomainCount row = DomainCountRow.read(rs, c);
```
