# Stream kết quả (Streaming)

Phương thức mapper có thể khai báo kiểu trả về `Stream<T>` thay vì `List<T>`. Dữ liệu được đọc tuần tự trực tiếp từ con trỏ `ResultSet` đang mở, giúp xử lý các tập dữ liệu lớn hàng triệu dòng mà không gây tràn bộ nhớ (Out Of Memory).

```java
@Select("SELECT id, name, email, created_at FROM users ORDER BY id")
Stream<User> streamAll();
```

```java
try (Stream<User> rows = mapper.streamAll()) {
    rows.filter(User::isActive).forEach(exporter::write);
}
```

## Bắt buộc sử dụng `try-with-resources`

!!! danger "Caller chịu trách nhiệm đóng Stream"

    Khi phương thức trả về `Stream<T>`, tài nguyên JDBC (`ResultSet`, `PreparedStatement`, `Connection`) tiếp tục tồn tại sau khi phương thức mapper kết thúc. Thao tác gọi `stream.close()` sẽ đóng toàn bộ các tài nguyên này và giải phóng connection.

    - **Nếu không đóng stream**: `Connection` sẽ bị chiếm dụng cho đến khi GC thu hồi đối tượng, gây rò rỉ connection pool nghiêm trọng.
    - Luôn bọc lời gọi `Stream` trong khối `try-with-resources`.

Mã nguồn Java sinh ra:

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
        return s.stream(c, ps, rs, OrderRow::read, SQL_streamByStatus);  // Chuyển giao tài nguyên cho Stream quản lý
    } catch (SQLException e) {
        throw s.streamFailed(c, ps, rs, SQL_streamByStatus, e);          // Đóng tài nguyên dở dang nếu có lỗi
    }
}
```

## Stream trong LarkBatis là tuần tự (Sequential)

`Stream` trả về luôn là tuần tự (sequential) và không hỗ trợ thực thi song song (`parallelStream`). Song song hoá một con trỏ JDBC bắt buộc phải nạp trước toàn bộ dữ liệu vào RAM, làm mất đi ý nghĩa tiết kiệm bộ nhớ của streaming.

## Bảng hỗ trợ Streaming

| Kiểu dữ liệu trả về | Trạng thái hỗ trợ | Cơ chế xử lý |
|---|---|---|
| `Stream<User>` (POJO) | Có | Đọc qua `RowReader` sinh sẵn |
| `Stream<String>`, `Stream<Long>` (Vô hướng) | Có | Đọc trực tiếp từ cột 1 |
| `SELECT *` | Có | Đọc vị trí từ `ResultSetMetaData` ở dòng đầu tiên |
| `<resultMap>` có association/collection | **Không** | Báo lỗi biên dịch (do quan hệ lồng nhau đòi hỏi phải nạp nhiều dòng để gom nhóm) |

## Streaming với Lối thoát thủ công (`s.queryStream()`)

`LarkBatisSession.queryStream` cho phép stream các câu SQL động phức tạp:

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

## Lưu ý về `fetchSize` của JDBC Driver

LarkBatis không tự động can thiệp vào `fetchSize` của JDBC connection. Để streaming dữ liệu lớn hiệu quả:
- **PostgreSQL**: Cần chạy bên trong một transaction (`@Transactional`) hoặc tắt auto-commit, và cấu hình `defaultRowFetchSize` trên DataSource.
- **MySQL**: Driver MySQL mặc định nạp toàn bộ ResultSet vào RAM; cần cấu hình `useCursorFetch=true` hoặc `defaultFetchSize` trong JDBC URL.

