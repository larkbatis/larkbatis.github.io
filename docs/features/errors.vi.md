# Xử lý lỗi & Ngoại lệ

Hầu hết các lỗi tiềm ẩn lúc runtime trong MyBatis sẽ được LarkBatis phát hiện ngay từ pha biên dịch (`javac`).

## Lỗi lúc biên dịch (Compile-time Errors)

Mỗi lỗi compile đều nêu rõ class, phương thức mapper gây lỗi và thông báo hướng dẫn sửa:

| Lỗi compile | Cách khắc phục |
|---|---|
| Tên tham số trong `#{}` không tồn tại | Kiểm tra lại tên biến hoặc thêm `@Param`. Nếu tên biến bị đổi thành `arg0`, xem [Khắc phục sự cố](../usage/troubleshooting.md) |
| Gán trực tiếp biến `String` vào `${}` | Đổi kiểu sang `SqlFragment`, enum/primitive, hoặc gắn `@OrderBy(allowed = {...})` |
| `test="count"` (truthiness kiểu OGNL) | Đổi thành so sánh tường minh: `count != 0`, `user != null`, `!list.isEmpty()` |
| Biểu thức `test` ngoài ngữ pháp hỗ trợ | Viết lại biểu thức hoặc tính toán logic trong Java trước khi truyền vào mapper |
| Khai báo câu truy vấn ở cả annotation lẫn XML | Chọn một trong hai nơi để định nghĩa câu truy vấn |
| Tham số kiểu `Map` hoặc `Object` không định kiểu | Sử dụng parameter class cụ thể hoặc khai báo `@Param` cho từng tham số |
| Bật `useGeneratedKeys` nhưng thiếu `keyProperty` | Chỉ định tên thuộc tính POJO nhận giá trị khóa tự tăng |
| Số lượng `keyColumn` và `keyProperty` không khớp | Khai báo hai danh sách có cùng số lượng phần tử |
| Gắn `@PadPow2` trên câu lệnh `INSERT` | Gỡ bỏ `@PadPow2` (chỉ được dùng cho mệnh đề `WHERE ... IN`) |
| Batch insert chứa SQL động | Câu lệnh batch insert nhận `List<T>` bắt buộc phải có cấu trúc SQL cố định |
| Phương thức trả về `Stream<T>` trên `<resultMap>` join | Trả về `List<T>`, hoặc stream danh sách phẳng rồi tự gom nhóm trong Java |
| Result map lồng sâu hơn 1 cấp | Sử dụng join 1 cấp hoặc ghép dữ liệu trong tầng Service |
| Khai báo `select="..."` trong `<association>` / `<collection>` | Viết lại bằng câu lệnh `JOIN` tường minh |
| Cột `<id>` bị thiếu trong danh sách SELECT | Thêm cột khóa chính vào câu `SELECT` để thuật toán gom nhóm hoạt động |
| Result class thiếu constructor mặc định hoặc setter | Bổ sung constructor không tham số và setter (hoặc kiểm tra thứ tự nạp Lombok) |

## Cảnh báo lúc biên dịch (Compile-time Warnings)

| Cảnh báo | Tác động kỹ thuật |
|---|---|
| `useGeneratedKeys without keyColumn falls back to RETURN_GENERATED_KEYS` | Oracle trả về `ROWID`, PostgreSQL trả về toàn bộ dòng. Cần chỉ định rõ `keyColumn` để đảm bảo tương thích database |
| Fallback đọc theo tên cột | Xảy ra khi câu lệnh là `SELECT *` hoặc dùng `${}` trong SELECT. Code vẫn chạy đúng nhưng tốc độ đọc chậm hơn |
| Result map lồng nhau nhưng câu SQL thiếu `ORDER BY` | Thuật toán gom nhóm single-pass yêu cầu ResultSet phải được sắp xếp theo khóa của bảng cha |
| Khai báo `<result>` cho cột không tồn tại trong SELECT | Thuộc tính tương ứng trong Java Bean sẽ giữ giá trị mặc định (`null`/`0`) |

## Ngoại lệ lúc Runtime (Runtime Exceptions)

Tất cả ngoại lệ kế thừa từ unchecked exception `LarkBatisException` và cung cấp phương thức `sql()` để kiểm tra câu lệnh gây lỗi.

### `LarkBatisRejectedException`

Ném ra khi giá trị truyền vào `SqlFragment.allowed()` hoặc `@OrderBy` không nằm trong danh sách whitelist cho phép:

```text
Rejected SQL fragment value: "id; DROP TABLE users" (allowed: id, name, created_at)
```

### `LarkBatisEmptyForeachException`

Ném ra khi collection truyền vào thẻ `<foreach>` bị rỗng:

```text
<foreach collection="ids"> is empty in statement com.example.app.UserBatchMapper.findByIds;
wrap the loop in an <if> testing the collection if an empty one should drop the fragment instead
```

### `LarkBatisNoKeyException`

Ném ra khi câu lệnh bật `useGeneratedKeys` nhưng JDBC driver không trả về khóa chính nào sau khi thực thi `INSERT`.

### `LarkBatisKeyCountMismatchException`

Ném ra khi số lượng khóa chính trả về trong batch insert ít hơn số bản ghi được gửi đi:

```text
Statement com.example.app.OrderMapper.insertAll expected 500 generated keys but the driver returned 1
```

### `LarkBatisUnboundedVariantsException`

Ném ra khi số lượng biến thể prepared statement vượt quá ngưỡng `max-sql-variants` và ứng dụng đang bật `fail-on-unbounded-fragment: true`.

### `LarkBatisRollbackOnlyException`

Ném ra khi gọi `commit()` trên một transaction đã bị scope bên trong đánh dấu rollback.

## Tích hợp dịch mã lỗi trong Spring

Khi chạy trong Spring, `SpringLarkBatisSession` chuyển đổi lỗi JDBC thông qua `SQLExceptionTranslator` của Spring (`SQLExceptionSubclassTranslator`).

Các lỗi cơ sở dữ liệu sẽ tự động được chuyển đổi sang cây phân cấp `DataAccessException` tương ứng (ví dụ `DuplicateKeyException`, `CannotAcquireLockException`), đảm bảo tương thích trực tiếp với các annotation `@ExceptionHandler` và `@Retryable` hiện có trong dự án.

Các ngoại lệ riêng của LarkBatis (`LarkBatisRejectedException`, `LarkBatisEmptyForeachException`, v.v.) được chuyển tiếp trực tiếp mà không bị thay đổi.

