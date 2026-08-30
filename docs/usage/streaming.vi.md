# Stream kết quả

Một phương thức mapper có thể trả về `Stream<T>` thay cho `List<T>`. Khi đó các dòng đến
lần lượt từng dòng một từ một con trỏ đang mở, và đó chính là mục đích: một tập kết quả
quá lớn để giữ trong bộ nhớ sẽ không bao giờ trở thành một danh sách.

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY id")
Stream<User> streamAll();
```

```java
try (Stream<User> rows = mapper.streamAll()) {
    rows.filter(User::isActive).forEach(exporter::write);
}
```

## Người gọi sở hữu tài nguyên

!!! danger "`try`-with-resources ở đây không phải tuỳ chọn"

    Đây là hình dạng sinh ra duy nhất mà tài nguyên JDBC sống lâu hơn chính phương thức
    đã mở chúng, nên thân sinh ra **không có `finally`**. Đóng stream chính là thứ đóng
    `ResultSet` và `PreparedStatement` rồi trả `Connection` về.

    - **Ngoài transaction**, một stream không bao giờ được đóng sẽ giữ một `Connection`
      của pool chừng nào nó còn với tới được. Đó là rò rỉ pool.
    - **Trong transaction**, connection vẫn thuộc về transaction, còn stream giữ
      statement và con trỏ cho tới khi nó kết thúc.

Thân sinh ra làm cho quyền sở hữu đó hiện rõ:

```java
@Override
public Stream<Order> streamByStatus(Status status) {
    Connection c = s.conn();
    PreparedStatement ps = null;
    ResultSet rs = null;
    try {
        ps = c.prepareStatement(SQL_streamByStatus);
        JdbcCodec.setEnum(ps, 1, status);
        rs = ps.executeQuery();
        return s.stream(c, ps, rs, OrderRow::read, SQL_streamByStatus);  // (1)!
    } catch (SQLException e) {
        throw s.streamFailed(c, ps, rs, SQL_streamByStatus, e);          // (2)!
    }
}
```

1.  Trao cả ba tài nguyên cho stream, và stream sẽ nhả chúng ra khi `close()`.
2.  Nhánh xử lý lỗi, tức bất cứ thứ gì ném lỗi *trước khi* stream tồn tại, sẽ tự tay gỡ
    lại toàn bộ, với lỗi dọn dẹp được nén vào lỗi thật chứ không thay thế nó.

## Vì sao stream là tuần tự

Stream trả về là tuần tự và không tách nhánh được. Song song hoá một con trỏ nghĩa là
đọc trước vào bộ nhớ, mà đó đúng là thứ kiểu trả về `Stream` được chọn để tránh. Nếu bạn
muốn song song, hãy gom một khúc có giới hạn rồi song song hoá khúc đó.

## Những gì stream được

| | |
|---|---|
| `Stream<User>` trên một bean | Được, dùng row reader sinh ra |
| `Stream<String>`, `Stream<Long>` (vô hướng) | Được, đọc cột 1, không bean, không reader |
| `SELECT *` | Được, chỉ số lấy từ `ResultSetMetaData` trước dòng đầu tiên |
| Một `<resultMap>` lồng nhau | **Lỗi biên dịch** |

Mục cuối đáng để hiểu hơn là để lách. Một đối tượng cha trải trên nhiều dòng, nên nó chỉ
hoàn chỉnh khi đối tượng cha *tiếp theo* bắt đầu. Trả lời điều đó từ một con trỏ
đọc-từng-dòng nghĩa là phải đệm, và như vậy là mất hết ý nghĩa. Hãy stream các dòng
phẳng rồi tự gom nhóm, hoặc dùng `List` và chấp nhận tốn bộ nhớ.

## Cửa thoát hiểm cũng stream được

`LarkBatisSession.queryStream` là bản stream tương ứng của `query`:

```java
default Stream<User> streamRecent(LarkBatisSession s, int limit) {
    return s.queryStream(
            SqlFragment.unsafeRawSql(
                    "SELECT id, name, email, created_at FROM users"
                            + " ORDER BY created_at DESC LIMIT " + limit),
            ps -> { },
            UserRow.READER);
}
```

Cùng một quy tắc sở hữu: người gọi phải đóng. Xem [SQL thô](raw-sql.md#the-escape-hatch).

## Dưới Spring

`@Transactional` và stream đi cùng nhau được, quy tắc sở hữu không đổi:

```java
@Transactional(readOnly = true)
public void export(Writer out) {
    try (Stream<User> rows = users.streamAll()) {
        rows.forEach(u -> write(out, u));
    }
}
```

Trong transaction, `release` là lệnh rỗng và transaction giữ connection; ngoài
transaction, đóng stream sẽ trả nó về pool. `try`-with-resources đúng trong cả hai
trường hợp, và đó là lý do quy tắc được phát biểu là "luôn luôn" chứ không phải "đôi
khi".

## Fetch size

LarkBatis không tự đặt `setFetchSize` giúp bạn: giá trị đúng phụ thuộc vào driver và
vào truy vấn, và một số driver (đặc biệt là PostgreSQL) còn đòi phải tắt auto-commit thì
con trỏ mới thật sự stream thay vì nạp hết ra. Nếu bạn đang stream một kết quả lớn, hãy
đặt nó trên connection hoặc trên pool, hoặc đọc bên trong một transaction.
