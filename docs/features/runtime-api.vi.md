# Runtime API

Toàn bộ các class và interface công khai trong package `io.github.larkbatis.runtime`. Thư viện runtime của LarkBatis có kích thước siêu nhẹ (~1.500 dòng code), không phụ thuộc bên ngoài ngoài JDBC thuần, và không sử dụng reflection.

## `LarkBatisSession`

Interface trung tâm quản lý vòng đời kết nối JDBC và dịch mã lỗi:

```java
public interface LarkBatisSession {

    Connection conn();                                    // (1)!
    void release(Connection c);                           // (2)!
    RuntimeException translate(SQLException e, String sql);

    // Lối thoát thủ công (Escape hatch)
    default <T> List<T>   query(SqlFragment, StatementBinder, RowReader<T>);
    default <T> T         queryOne(SqlFragment, StatementBinder, RowReader<T>);
    default <T> Stream<T> queryStream(SqlFragment, StatementBinder, RowReader<T>);
    default int           update(SqlFragment, StatementBinder);

    // Dành cho phương thức trả về Stream
    default <T> Stream<T> stream(Connection, PreparedStatement, ResultSet, RowReader<T>, String);
    default RuntimeException streamFailed(Connection, PreparedStatement, ResultSet, String, SQLException);
}
```

1.  Lấy một JDBC `Connection`. Nếu đang trong transaction, trả về connection của transaction đó; nếu không, mở một connection auto-commit.
2.  Giải phóng connection. Lệnh này không làm gì (no-op) nếu connection thuộc sở hữu của một transaction đang hoạt động.

Hai triển khai chính: `JdbcLarkBatisSession` (JDBC thuần) và `SpringLarkBatisSession` (tích hợp Spring qua `DataSourceUtils`).

## `JdbcLarkBatisSession`

```java
public JdbcLarkBatisSession(DataSource dataSource)

public LarkBatisTx begin()
public LarkBatisTx begin(boolean readOnly)
public boolean hasActiveTransaction()
```

## `LarkBatisTx`

Quản lý transaction độc lập qua scope `AutoCloseable`, áp dụng cơ chế vote-to-commit:

```java
try (LarkBatisTx tx = session.begin()) {
    mapper.insert(user);
    tx.commit();
}
```

| Phương thức | Ý nghĩa |
|---|---|
| `commit()` | Bỏ phiếu xác nhận commit. Commit vật lý xuống database chỉ xảy ra khi scope ngoài cùng đóng lại thành công |
| `rollbackOnly()` | Đánh dấu transaction ở trạng thái rollback-only |
| `close()` | Kết thúc scope. Nếu scope chưa được gọi `commit()`, toàn bộ transaction sẽ bị đánh dấu rollback |

Xem [Transactions](../usage/transactions.md).

## `SqlFragment`

Đối tượng đại diện cho các chuỗi SQL động an toàn:

```java
public static SqlFragment allowed(String value, String... allowed)   // (1)!
public static SqlFragment identifier(String value)                    // (2)!
public static SqlFragment unsafeRawSql(String value)                  // (3)!
public String text()
```

1.  Kiểm tra giá trị với danh sách whitelist định sẵn. Ném `LarkBatisRejectedException` nếu không khớp.
2.  Chỉ chấp nhận tên định danh hợp lệ (chữ cái, chữ số, dấu gạch dưới và dấu chấm).
3.  Nhận chuỗi bất kỳ. Đây là điểm duy nhất trong dự án cần kiểm toán bảo mật (`grep -rn unsafeRawSql`).

## `LarkBatisSql`

Class tiện ích chứa các phương thức tĩnh hỗ trợ mã nguồn sinh ra:

| Phương thức | Ý nghĩa |
|---|---|
| `trackVariants(statementId, sql)` | Đếm số lượng biến thể SQL động cho mỗi câu truy vấn |
| `maxSqlVariants(limit)` | Cấu hình ngưỡng cảnh báo số lượng biến thể SQL (mặc định 64) |
| `failOnUnboundedVariants(bool)` | Bật chế độ ném exception khi vượt ngưỡng biến thể |
| `padPow2(n)` | Đệm số lượng tham số lên lũy thừa của 2 gần nhất |
| `sum(updateCounts)` | Tính tổng số bản ghi bị ảnh hưởng từ mảng kết quả `executeBatch()` |

## `JdbcCodec`

Chứa các phương thức chuyển đổi dữ liệu JDBC có xử lý null an toàn cho kiểu primitive và `java.time`:

**Đọc dữ liệu:** `booleanOrNull`, `byteOrNull`, `shortOrNull`, `intOrNull`, `longOrNull`, `floatOrNull`, `doubleOrNull`, `instant`, `localDateTime`, `localDate`, `localTime`, `enumValue`.

**Ghi dữ liệu:** `setBoolean`, `setByte`, `setShort`, `setInt`, `setLong`, `setFloat`, `setDouble`, `setInstant`, `setLocalDateTime`, `setLocalDate`, `setLocalTime`, `setEnum`.

```java
public static Long longOrNull(ResultSet rs, int column) throws SQLException {
    long v = rs.getLong(column);
    return rs.wasNull() ? null : v;
}
```

## `RowReader<T>` và `StatementBinder`

```java
@FunctionalInterface public interface RowReader<T> { T read(ResultSet rs) throws SQLException; }
@FunctionalInterface public interface StatementBinder { void bind(PreparedStatement ps) throws SQLException; }
```

Mỗi class đọc dòng sinh ra đều có sẵn một hằng số `public static final RowReader<T> READER` để dùng cho các truy vấn động.

## Cây Exception

Tất cả ngoại lệ đều là unchecked exception kế thừa từ `LarkBatisException`:

| Ngoại lệ | Nguyên nhân phát sinh |
|---|---|
| `LarkBatisException` | Ngoại lệ gốc, bọc `SQLException` kèm câu SQL gây lỗi |
| `LarkBatisRejectedException` | Giá trị truyền vào `SqlFragment.allowed()` hoặc `@OrderBy` không nằm trong danh sách whitelist |
| `LarkBatisEmptyForeachException` | Collection truyền vào `<foreach>` rỗng |
| `LarkBatisNoKeyException` | Cấu hình `useGeneratedKeys` nhưng JDBC driver không trả về khóa chính nào |
| `LarkBatisKeyCountMismatchException` | Số lượng khóa chính trả về trong batch insert ít hơn số bản ghi được chèn |
| `LarkBatisUnboundedVariantsException` | Số lượng biến thể câu SQL vượt quá ngưỡng `max-sql-variants` khi bật chế độ nghiêm ngặt |
| `LarkBatisRollbackOnlyException` | Gọi `commit()` trên một transaction đã bị đánh dấu rollback |

Xem [Xử lý lỗi & Exception](errors.md).

