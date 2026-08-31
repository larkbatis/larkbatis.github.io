# API Runtime

Toàn bộ các interface và class trong package `io.github.larkbatis.runtime`. Không có bất kỳ dependency nào ngoài JDBC thuần, không kiểm tra kiểu bằng reflection, không resolve tên động và không tra cứu registry lúc runtime. Mọi thứ đã được xử lý xong từ pha build.

## `LarkBatisSession`

Cung cấp toàn bộ môi trường thực thi mà mapper sinh ra cần tới.

```java
public interface LarkBatisSession {

    Connection conn();                                    // (1)!
    void release(Connection c);                           // (2)!
    RuntimeException translate(SQLException e, String sql);

    // loi thoat thu cong (escape hatch)
    default <T> List<T>   query(SqlFragment, StatementBinder, RowReader<T>);
    default <T> T         queryOne(SqlFragment, StatementBinder, RowReader<T>);
    default <T> Stream<T> queryStream(SqlFragment, StatementBinder, RowReader<T>);
    default int           update(SqlFragment, StatementBinder);

    // dung cho phuong thuc sinh san tra ve Stream
    default <T> Stream<T> stream(Connection, PreparedStatement, ResultSet, RowReader<T>, String);
    default RuntimeException streamFailed(Connection, PreparedStatement, ResultSet, String, SQLException);
}
```

1.  Mượn một connection. Khi ở trong scope transaction đang hoạt động, hàm trả về chính connection của transaction đó; ngược lại trả về một connection auto-commit mới.
2.  Trả lại connection đã mượn qua `conn()`. Hàm này là no-op (không làm gì) nếu connection thuộc về transaction đang hoạt động; đóng connection thật nếu ở ngoài transaction.

Hai bản hiện thực chính: `JdbcLarkBatisSession` (dùng độc lập với JDBC) và `SpringLarkBatisSession` (nằm trong `larkbatis-spring`).

Các chữ ký của lối thoát thủ công không có bất kỳ overload nào nhận kiểu `String`. Mọi chuỗi SQL tuỳ ý chỉ được phép đưa vào thông qua `SqlFragment`.

## `JdbcLarkBatisSession`

```java
public JdbcLarkBatisSession(DataSource dataSource)

public LarkBatisTx begin()
public LarkBatisTx begin(boolean readOnly)
public boolean hasActiveTransaction()
```

## `LarkBatisTx`

Đại diện cho programmatic transaction scope (`AutoCloseable`), quản lý transaction boundary theo cơ chế vote-to-commit.

```java
try (LarkBatisTx tx = session.begin()) {
    mapper.insert(user);
    tx.commit();
}
```

| Phương thức | Ý nghĩa |
|---|---|
| `commit()` | **Bỏ phiếu** (vote) để commit. Lệnh commit thực sự chỉ diễn ra khi scope ngoài cùng đóng lại. Ném `LarkBatisRollbackOnlyException` nếu một scope bên trong đã đánh dấu hỏng transaction |
| `rollbackOnly()` | Đánh dấu tường minh transaction ở trạng thái rollback-only |
| `close()` | Rời khỏi scope mà chưa gọi commit sẽ tự động đánh dấu toàn bộ transaction ở trạng thái rollback-only |

Các scope có thể lồng nhau: lệnh `begin()` ở scope bên trong sẽ tham gia vào transaction bên ngoài, và chỉ lệnh close của scope ngoài cùng mới tác động trực tiếp đến connection. [Chi tiết](../usage/transactions.md)

## `SqlFragment`

Cổng kiểm soát duy nhất cho phép đưa các đoạn câu SQL tuỳ biến vào câu truy vấn.

```java
public static SqlFragment allowed(String value, String... allowed)   // (1)!
public static SqlFragment identifier(String value)                    // (2)!
public static SqlFragment unsafeRawSql(String value)                  // (3)!
public String text()
```

1.  Kiểm tra theo danh sách cho phép (allow-list) cố định. Bất kỳ giá trị nào ngoài danh sách sẽ ném `LarkBatisRejectedException`. **Khuyến nghị luôn ưu tiên dùng phương thức này.**
2.  Định danh SQL chuẩn: chữ cái, chữ số, dấu gạch dưới, hỗ trợ tiền tố chấm (dấu chấm).
3.  Nhận chuỗi bất kỳ. Đây là điểm duy nhất cần kiểm toán bảo mật trong toàn dự án: `grep -rn unsafeRawSql src/`.

## `LarkBatisSql`

Các hàm tiện ích tĩnh (static helper) được code sinh ra gọi tới.

| Phương thức | Ý nghĩa |
|---|---|
| `trackVariants(String statementId, String sql)` | Đếm số lượng biến thể câu SQL riêng biệt cho mỗi statement. Được sinh ra cho mọi statement có nội dung SQL không cố định lúc build |
| `maxSqlVariants(int limit)` | Ngưỡng giới hạn biến thể. Mặc định là **64**, hoặc cấu hình qua `-Dlarkbatis.maxSqlVariants` |
| `failOnUnboundedVariants(boolean)` | Ném exception thay vì chỉ ghi log cảnh báo khi vượt ngưỡng. Mặc định `false`, hoặc cấu hình qua `-Dlarkbatis.failOnUnboundedVariants` |
| `padPow2(int n)` | Làm tròn số lượng tham số lên luỹ thừa của 2 gần nhất, phục vụ `@PadPow2` |
| `sum(int[] updateCounts)` | Tính tổng số dòng bị ảnh hưởng từ mảng kết quả của `executeBatch()` |

## `JdbcCodec`

Tập hợp các helper đọc/ghi dữ liệu có xử lý null an toàn, là phần còn lại sau khi đã inline toàn bộ tầng `TypeHandler`. *Việc lựa chọn* hàm helper nào được quyết định từ lúc build; runtime chỉ thực thi việc chuyển đổi giá trị.

**Đọc dữ liệu:** `booleanOrNull`, `byteOrNull`, `shortOrNull`, `intOrNull`, `longOrNull`, `floatOrNull`, `doubleOrNull`, `instant`, `localDateTime`, `localDate`, `localTime`, `enumValue`.

**Ghi dữ liệu:** `setBoolean`, `setByte`, `setShort`, `setInt`, `setLong`, `setFloat`, `setDouble`, `setInstant`, `setLocalDateTime`, `setLocalDate`, `setLocalTime`, `setEnum`.

```java
public static Long longOrNull(ResultSet rs, int column) throws SQLException {
    long v = rs.getLong(column);
    return rs.wasNull() ? null : v;   // rs.getLong tra ve 0 khi gia tri la SQL NULL
}
```

Những kiểu dữ liệu mà phương thức của JDBC đã chuẩn xác sẵn (`String`, `BigDecimal`, `byte[]`, `java.sql.Timestamp`) được gọi trực tiếp và không cần đi qua helper này.

## `RowReader<T>` và `StatementBinder`

```java
@FunctionalInterface public interface RowReader<T> { T read(ResultSet rs) throws SQLException; }
@FunctionalInterface public interface StatementBinder { void bind(PreparedStatement ps) throws SQLException; }
```

Mỗi class đọc dòng sinh ra đều cung cấp sẵn hằng số `public static final RowReader<T> READER`. Nhờ đó, lối thoát thủ công có thể tái sử dụng trực tiếp reader sinh sẵn mà không cần reflection.

## Phân cấp ngoại lệ (Exceptions)

Tất cả đều là unchecked exception, kế thừa từ `LarkBatisException` và mang theo nội dung câu SQL tương ứng (hoặc mã giả định như `tx:commit`) qua phương thức `sql()`.

| Ngoại lệ | Điều kiện phát sinh |
|---|---|
| `LarkBatisException` | Ngoại lệ gốc, bọc một `SQLException` kèm câu SQL gây lỗi |
| `LarkBatisRejectedException` | Giá trị đưa vào factory của `SqlFragment` hoặc câu lệnh switch `@OrderBy` bị từ chối; giá trị này chưa từng lọt vào chuỗi SQL |
| `LarkBatisEmptyForeachException` | Collection trong thẻ `<foreach>` rỗng; nêu rõ tên statement và tên tham số |
| `LarkBatisNoKeyException` | Statement yêu cầu Generated Keys nhưng JDBC driver không trả về khoá nào |
| `LarkBatisKeyCountMismatchException` | Thao tác batch insert nhận được số lượng Generated Keys ít hơn số dòng dữ liệu |
| `LarkBatisUnboundedVariantsException` | Statement vượt quá ngưỡng `max-sql-variants` và ứng dụng đang bật chế độ ném lỗi thay vì chỉ cảnh báo |
| `LarkBatisRollbackOnlyException` | Gọi `commit()` trên một transaction đã bị scope bên trong đánh dấu rollback |

Khi chạy dưới môi trường Spring, phương thức `translate` sẽ chuyển đổi lỗi thành cây phân cấp `DataAccessException` của Spring. Lỗi vi phạm ràng buộc khoá duy nhất (unique constraint) sẽ xuất hiện dưới dạng `DuplicateKeyException`, hoàn toàn tương thích với `JdbcTemplate`. [Chi tiết](errors.md)
