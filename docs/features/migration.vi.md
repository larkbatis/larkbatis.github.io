# Chuyển đổi từ MyBatis (Migration)

Lộ trình chuyển đổi dễ dàng từ MyBatis là mục tiêu thiết kế hàng đầu của LarkBatis. Công cụ `larkbatis-scan` hỗ trợ quét phân tích toàn bộ codebase MyBatis hiện tại, xác định chi phí chuyển đổi và chỉ ra chính xác các dòng code cần chỉnh sửa.

## Quét phân tích codebase cũ với `larkbatis-scan`

Công cụ `larkbatis-scan` phân tích trực tiếp các file Java mapper và XML mà không cần giải quyết dependency hay biên dịch dự án. Bạn có thể chạy ngay trên một repository vừa `git clone`:

Nếu dự án đã cài đặt Gradle plugin:

```console
$ ./gradlew larkbatisScan
$ ./gradlew larkbatisScan --args="--summary --min=BLOCKER src/main"
```

Đối với dự án chưa cài đặt LarkBatis, bạn có thể build và chạy công cụ CLI độc lập:

```console
$ ./gradlew :larkbatis-scanner:installDist
$ ./build/install/larkbatis-scanner/bin/larkbatis-scan /path/to/legacy-service
```

```text
larkbatis-scan — what would it cost to move this codebase to LarkBatis

usage: larkbatis-scan [options] <path>...

  --summary            counts only, no per-line detail
  --min=LEVEL          detail level: BLOCKER, EDIT, REVIEW, INFO (default REVIEW)
  --limit=N            most findings listed per file (default 40)
  --out=FILE           also write the report to FILE
  --fail-on-blocker    exit 1 when anything is blocked on a dropped feature
```

Công cụ chỉ đọc và xuất báo cáo, **tuyệt đối không tự ý chỉnh sửa file mã nguồn**.

### Đồng bộ hoàn toàn với bộ biên dịch

`larkbatis-scan` sử dụng chung parser XML và bộ phân tích ngữ pháp biểu thức từ `larkbatis-processor`. Do đó, kết quả báo cáo của scanner phản ánh chính xác 100% những gì `javac` sẽ chấp nhận hoặc từ chối lúc biên dịch.

### 4 mức độ cảnh báo

| Mức độ | Ý nghĩa |
|---|---|
| **BLOCKER** | Sử dụng tính năng đã bị loại bỏ trong LarkBatis. Cần thay đổi thiết kế của mapper |
| **EDIT** | Cần sửa lại cú pháp (scanner sẽ chỉ rõ dòng code và đoạn cần sửa) |
| **REVIEW** | Tính năng được hỗ trợ nhưng cần lập trình viên kiểm tra lại hành vi (ví dụ câu truy vấn fallback về đọc theo tên cột) |
| **INFO** | Biên dịch thành công; thông tin bổ sung để theo dõi số lượng biến thể prepared statement |

## Danh mục các hạng mục được scanner phân tích

| Hạng mục phát hiện | Mức độ | Hướng xử lý |
|---|---|---|
| Sử dụng chuỗi `${}` tùy tiện | EDIT | Đổi kiểu tham số sang `SqlFragment`, kiểu tập đóng (enum/primitive), hoặc `@OrderBy(allowed={...})` |
| `${}` nằm trong mệnh đề SELECT | REVIEW | Câu truy vấn sẽ fallback về đọc theo tên cột qua `ResultSetMetaData` |
| Biểu thức `test` ngoài ngữ pháp hỗ trợ | EDIT | Viết lại biểu thức hoặc tính toán logic trong Java trước khi gọi mapper |
| Kiểm tra truthiness kiểu OGNL (`test="count"`) | EDIT | Viết rõ điều kiện: `count != 0`, `user != null`, `!list.isEmpty()` |
| Tham số kiểu `Map` hoặc `Object` | BLOCKER | Tạo parameter class cụ thể hoặc khai báo `@Param` cho từng tham số |
| Provider annotations (`@SelectProvider`, v.v.) | BLOCKER | Chuyển SQL vào mapper hoặc sử dụng lối thoát thủ công `session.query(...)` |
| Plugins / Interceptors | BLOCKER | Chuyển sang SQL tường minh, TypeHandler hoặc Spring AOP. Xem [Thay thế Plugin](mybatis-differences.md#what-replaces-a-plugin) |
| Lazy loading | BLOCKER | Dùng phép `JOIN` để lấy dữ liệu ngay, hoặc tách thành hai câu truy vấn độc lập |
| Lồng `select="..."` trong result map | BLOCKER | Viết lại câu truy vấn bằng mệnh đề `JOIN` tường minh |
| Result map lồng sâu hơn 1 cấp | BLOCKER | Thực hiện join 1 cấp hoặc ghép dữ liệu trong tầng Service |
| `<resultMap extends="...">` | BLOCKER | Khai báo tường minh tất cả ánh xạ cột cần thiết |
| Thẻ `<discriminator>` | BLOCKER | Tách thành các phương thức truy vấn riêng biệt theo từng entity con |
| Constructor mapping (`<constructor>`) | BLOCKER | Sử dụng constructor mặc định và các hàm setter |
| Thẻ `<bind>` | BLOCKER | Tính toán biến trước trong mã Java |
| Thẻ `<parameterMap>` | BLOCKER | Dùng `#{}` với tham số có kiểu rõ ràng |
| Level-2 Cache (`<cache>`) | BLOCKER | Cài đặt cache ở tầng Service (ví dụ Spring `@Cacheable`) |
| `RowBounds` | BLOCKER | Phân trang bằng `LIMIT` và `OFFSET` trực tiếp trong câu SQL |
| `statementType` dạng `CALLABLE` | BLOCKER | Gọi stored procedure qua lối thoát thủ công `session.update(...)` |
| Thẻ `<include>` có `refid` động | BLOCKER | Đổi `refid` thành hằng số cố định |
| Thẻ `<selectKey>` | REVIEW | Dùng `@Options(useGeneratedKeys = true, keyProperty = "...", keyColumn = "...")` |
| Custom TypeHandler | REVIEW | Triển khai lại class theo interface `LarkBatisTypeHandler` |
| Cấu hình `mapUnderscoreToCamelCase` đang tắt | REVIEW | LarkBatis mặc định luôn bật. Có thể tắt bằng `-Alarkbatis.mapUnderscoreToCamelCase=false` |
| Thẻ `<foreach>` | INFO | Hỗ trợ đầy đủ; xem xét thêm `@PadPow2` nếu danh sách phần tử biến động nhiều |

## Quy trình Migration khuyến nghị

1. **Quét mã nguồn với `larkbatis-scan`**: Phân tích tổng thể và xem các lỗi BLOCKER tập trung ở những mapper nào.
2. **Chuyển đổi từng mapper độc lập**: LarkBatis mapper có thể hoạt động song song với các mapper MyBatis cũ trong cùng dự án.
3. **Cấu hình thứ tự Lombok**: Nếu dự án dùng Lombok, bắt buộc khai báo `larkbatis-processor` chạy **sau** Lombok trong `annotationProcessor`.
4. **Sửa các vị trí dùng `${}` và biểu thức `test`**: Đổi sang `SqlFragment` và viết rõ điều kiện so sánh null/số học.
5. **Xử lý các mục BLOCKER**: Đổi plugin sang Spring AOP/DataSource proxy, đổi lazy loading sang JOIN.
6. **Chạy toàn bộ unit/integration test suite của dự án**: Đảm bảo tất cả test cases cũ đều pass 100%.

## Thay đổi trong quy trình làm việc

- **Sửa SQL cần biên dịch lại**: Thay vì sửa XML rồi khởi động lại ứng dụng, bạn cần build project để `javac` sinh lại mã nguồn Java.
- **Thời gian build tăng nhẹ**: Chi phí phân tích và sinh code diễn ra một lần lúc build trên máy developer hoặc CI, giúp giải phóng hoàn toàn gánh nặng cho production.
- **Kỷ luật an toàn cho `${}`**: Mọi điểm chèn chuỗi động đều phải được kiểm soát qua kiểu dữ liệu tĩnh để loại bỏ nguy cơ SQL Injection.

