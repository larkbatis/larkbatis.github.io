# Lỗi và Chẩn đoán

Hầu hết các lỗi xảy ra lúc runtime trong ứng dụng MyBatis sẽ được phát hiện ngay lúc build trong ứng dụng LarkBatis. Tài liệu này được phân chia theo hai mốc thời gian đó.

## Lỗi lúc build (Build-time errors)

Mỗi lỗi biên dịch đều nêu rõ phương thức mapper gây lỗi và giải pháp thay thế tương ứng. Tất cả đều có test tự động trong lớp `CompileFailTest` của processor để đảm bảo các ràng buộc luôn được thực thi nghiêm ngặt.

| Lỗi | Cách khắc phục |
|---|---|
| Tên trong `#{}` không khớp với kiểu tham số | Kiểm tra lại tên hoặc thêm `@Param`. Nếu tên tham số bị đổi thành `arg0`, xem [Xử lý sự cố](../usage/troubleshooting.md) |
| Tham số kiểu `String` gắn trực tiếp vào `${}` | Dùng `SqlFragment`, kiểu tập giá trị đóng, hoặc `@OrderBy(allowed = {...})` |
| `test="count"`, kiểm tra truthiness theo kiểu OGNL | Đổi thành `count != 0`. Tương tự: `user != null`, `!list.isEmpty()` |
| Biểu thức `test=` nằm ngoài ngữ pháp được hỗ trợ | Viết lại biểu thức hoặc tính toán logic trong Java rồi truyền kết quả vào |
| Phương thức khai báo cả annotation lẫn XML, hoặc không khai báo cái nào | Chọn một trong hai hình thức |
| Tham số kiểu `Map` hoặc `Object` | Dùng parameter object hoặc các tham số `@Param` cụ thể |
| Khai báo `useGeneratedKeys` nhưng thiếu `keyProperty` | Chỉ định rõ thuộc tính nhận giá trị khoá |
| Số lượng trong `keyColumn` và `keyProperty` không khớp nhau | Khai báo hai danh sách có cùng số lượng phần tử |
| Gắn `@PadPow2` trên `<foreach>` không phải danh sách `IN` đơn, hoặc gắn trên lệnh `INSERT` | Gỡ bỏ annotation; việc pad trong các trường hợp này sẽ làm nhân bản dòng dữ liệu |
| Phương thức batch chứa SQL động | Chuỗi SQL của câu lệnh batch phải cố định cho mọi dòng dữ liệu |
| Trả về kiểu `Stream` trên một `<resultMap>` lồng nhau | Dùng `List`, hoặc stream các dòng phẳng rồi tự gom nhóm |
| Result map lồng nhau nhiều hơn một cấp, hoặc chứa hai ánh xạ lồng nhau trong một map | Chỉ dùng một phép join, một khoá gom nhóm |
| Khai báo `select=` trên `<association>`/`<collection>` | Viết tường minh bằng câu lệnh join |
| Khai báo `resultMap=`, `columnPrefix`, `extends`, `<constructor>`, `<discriminator>`, `autoMapping` trong result map | Xem [Result Map](../usage/result-maps.md#narrowed-on-purpose) |
| Cột `<id>` bị thiếu trong danh sách SELECT | Cột này là điều kiện bắt buộc để vòng lặp gom nhóm hoạt động |
| Dùng type alias trong `type` / `ofType` / `javaType` | Dùng tên class đầy đủ (FQN) |
| Khai báo `refid` động trên thẻ `<include>` | `refid` được inline lúc build nên bắt buộc phải là hằng số cố định |
| Result class thiếu constructor không tham số hoặc thiếu setter | Bổ sung đầy đủ. Nếu class dùng Lombok, thông báo lỗi sẽ nêu rõ nguyên nhân do [thứ tự nạp annotation processor](../usage/troubleshooting.md) |

## Cảnh báo lúc build (Build-time warnings)

Những cảnh báo này nên được xử lý nghiêm túc như lỗi trong quá trình code review.

| Cảnh báo | Tác động kỹ thuật |
|---|---|
| `useGeneratedKeys without keyColumn falls back to RETURN_GENERATED_KEYS` | Oracle trả về `ROWID`, PostgreSQL trả về tất cả các cột. Code chạy được trên H2 nhưng sẽ lỗi trên production |
| Statement phải fallback về đọc dòng theo tên cột | Không phân tích được danh sách SELECT: `SELECT *`, chèn `${}`, hoặc biểu thức không có alias. Code vẫn chạy đúng nhưng tốc độ đọc chậm hơn |
| Statement dùng result map lồng nhau nhưng không có `ORDER BY` | Vòng lặp gom nhóm yêu cầu ResultSet phải được sắp xếp theo khoá của bảng cha |
| Cột trong thẻ `<result>` không có trong danh sách SELECT | Thuộc tính tương ứng sẽ giữ giá trị mặc định |
| Thuộc tính `namespace` trong mapper XML trỏ tới interface ở module khác | Tệp XML đó sẽ bị bỏ qua |

## Ngoại lệ lúc Runtime

Tất cả đều là unchecked exception, kế thừa từ `LarkBatisException` và mang theo nội dung câu SQL qua phương thức `sql()`.

### `LarkBatisRejectedException`

Giá trị đưa vào factory của `SqlFragment` hoặc câu lệnh switch `@OrderBy` bị từ chối. **Giá trị này chưa từng lọt vào câu SQL.** Ngoại lệ này là minh chứng cho thấy cơ chế kiểm soát `${}` đang hoạt động hiệu quả, không phải lỗi của hệ thống.

```text
Rejected SQL fragment value: "id; DROP TABLE users" (allowed: id, name, created_at)
```

### `LarkBatisEmptyForeachException`

```text
<foreach collection="ids"> is empty in statement com.example.app.UserBatchMapper.findByIds;
wrap the loop in an <if> testing the collection if an empty one should drop the fragment instead
```

MyBatis sẽ để chuỗi `... WHERE id IN` gửi thẳng đến database và gây lỗi cú pháp tại đó, với thông báo lỗi không chỉ ra được mapper hay tham số nào.

### `LarkBatisNoKeyException`

Statement khai báo `useGeneratedKeys` nhưng JDBC driver không trả về khoá nào. Ngoại lệ này giúp ngăn chặn giá trị id bằng `0` lan truyền trong ứng dụng và gây lỗi ở những vị trí không liên quan.

### `LarkBatisKeyCountMismatchException`

```text
Statement com.example.app.OrderMapper.insertAll expected 500 generated keys
but the driver returned 1
```

Một số JDBC driver hoạt động như vậy. Bỏ qua lỗi này sẽ khiến một phần của đợt batch không có id mà không ai hay biết. MyBatis cũng ghi nhận trường hợp lỗi tương tự.

### `LarkBatisUnboundedVariantsException`

```text
LarkBatis statement com.example.app.UserMapper.search has produced more than 64 distinct
SQL texts; statement caches will keep growing. Prefer SqlFragment.allowed(...) or @OrderBy
over unbounded fragments.
```

Chỉ phát sinh khi bật tuỳ chọn `fail-on-unbounded-fragment`. Nếu không bật, hệ thống chỉ ghi nhận một dòng log cảnh báo. Thông tin `statementId()` và `limit()` được đính kèm trong exception.

### `LarkBatisRollbackOnlyException`

Phương thức `commit()` được gọi trên một transaction đã bị scope con bên trong đánh dấu rollback vì kết thúc scope mà không commit. Ném lỗi rõ ràng luôn tốt hơn việc rollback trong im lặng khiến caller lầm tưởng thao tác đã thành công.

## Tích hợp với Spring

`SpringLarkBatisSession.translate` chuyển đổi ngoại lệ qua `SQLExceptionTranslator` của Spring, mặc định sử dụng `SQLExceptionSubclassTranslator`. Bộ dịch này phân tích cây phân cấp lớp chuẩn của `SQLException` thay vì tra cứu bảng mã lỗi riêng của từng nhà cung cấp database.

Nhờ đó, lỗi trùng khoá duy nhất sẽ chuyển thành `DuplicateKeyException`, lỗi deadlock thành `CannotAcquireLockException`, hoàn toàn tương thích với `JdbcTemplate`. Các cấu hình `@ExceptionHandler` và quy tắc `@Retryable` hiện có trong dự án tiếp tục hoạt động mà không cần sửa đổi.

Các ngoại lệ riêng của LarkBatis ở trên (`LarkBatisRejectedException`, `LarkBatisEmptyForeachException`,...) không phải là `SQLException` nên được chuyển tiếp nguyên vẹn.

## Ghi log

LarkBatis sử dụng `java.util.logging` và xuất rất ít thông tin log; cảnh báo theo dõi biến thể SQL gần như là nội dung duy nhất. Hệ thống không tích hợp tính năng ghi log SQL, vì điều đó đòi hỏi mọi thân phương thức sinh ra đều phải gánh thêm một nhánh rẽ kiểm tra log. Hãy sử dụng driver hoặc connection pool (`net.ttddyy:datasource-proxy`, p6spy) cho nhu cầu này.

Trong thực tế, bạn không cần log SQL khi chạy vì toàn bộ câu SQL *đã nằm sẵn trong mã nguồn*. Bạn chỉ cần mở tệp `UserMapper$$Impl.java` và đọc hằng số `static final String`.
