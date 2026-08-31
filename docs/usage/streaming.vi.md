# Stream kết quả

Phương thức mapper có thể khai báo kiểu trả về `Stream<T>` thay vì `List<T>`. Dữ liệu được đọc tuần tự từng dòng từ con trỏ `ResultSet` đang mở, giúp xử lý các tập dữ liệu lớn mà không gây tràn bộ nhớ (Out Of Memory).

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY id")
Stream<User> streamAll();
```

```java
try (Stream<User> rows = mapper.streamAll()) {
    rows.filter(User::isActive).forEach(exporter::write);
}
```

## Trách nhiệm đóng tài nguyên thuộc về phía gọi

!!! danger "Bắt buộc sử dụng try-with-resources khi gọi Stream"

    Đây là trường hợp duy nhất mà tài nguyên JDBC sống lâu hơn chính phương thức mapper mở chúng, do đó thân phương thức sinh ra **không thể có khối `finally` đóng kết nối**. Việc đóng stream (`close()`) chính là thao tác đóng `ResultSet`, `PreparedStatement` và giải phóng `Connection`.

    - **Ngoài transaction**: nếu không đóng stream, `Connection` sẽ bị giữ vô thời hạn cho đến khi GC thu hồi đối tượng. Đây là lỗi rò rỉ connection pool nghiêm trọng.
    - **Trong transaction**: connection được quản lý bởi transaction, nhưng stream vẫn giữ statement và con trỏ mở cho đến khi hoàn tất.

Mã nguồn sinh ra thể hiện rõ quyền sở hữu tài nguyên này:

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

1.  Chuyển giao toàn bộ ba tài nguyên cho stream; stream sẽ đóng tất cả khi gọi `close()`.
2.  Khối catch xử lý các lỗi xảy ra *trước khi* khởi tạo stream thành công: dọn dẹp các tài nguyên đã mở dở dang và đính kèm lỗi dọn dẹp vào ngoại lệ chính (suppressed exception).

## Vì sao Stream trong LarkBatis là tuần tự (sequential)

Stream trả về luôn là tuần tự và không hỗ trợ tách nhánh (`spliterator` không song song). Song song hoá một con trỏ JDBC bắt buộc phải nạp trước toàn bộ dữ liệu vào RAM — điều đi ngược lại mục đích tiết kiệm bộ nhớ của `Stream`. Nếu cần xử lý song song, hãy đọc dữ liệu theo từng batch có kích thước giới hạn rồi xử lý song song trên từng batch đó.

## Khả năng hỗ trợ stream

| Kiểu dữ liệu | Hỗ trợ | Cơ chế xử lý |
|---|---|---|
| `Stream<User>` trên một bean | Có | Sử dụng row reader sinh sẵn |
| `Stream<String>`, `Stream<Long>` (vô hướng) | Có | Đọc trực tiếp cột 1, không cần bean hay reader |
| `SELECT *` | Có | Đọc vị trí từ `ResultSetMetaData` ở dòng đầu tiên |
| `<resultMap>` lồng nhau | **Không** | Lỗi biên dịch |

Đối tượng cha trong result map lồng nhau trải dài trên nhiều dòng và chỉ hoàn chỉnh khi dòng của đối tượng cha kế tiếp xuất hiện. Xử lý điều này trên con trỏ đọc tuần tự buộc phải đệm dữ liệu vào bộ nhớ. Với dữ liệu lồng nhau, hãy stream các dòng phẳng rồi tự gom nhóm, hoặc dùng `List` nếu kích thước dữ liệu cho phép.

## Lối thoát thủ công cũng hỗ trợ stream

`LarkBatisSession.queryStream` là phiên bản stream tương ứng của `query`:

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

Quy tắc đóng tài nguyên không đổi: bên gọi bắt buộc phải đóng stream trong try-with-resources. Xem [SQL thô](raw-sql.md#the-escape-hatch).

## Sử dụng trong Spring

`@Transactional` và `Stream` hoạt động hoàn toàn tương thích với nhau:

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
