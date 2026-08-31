# Lằn ranh thiết kế

Chín nguyên tắc bắt buộc phải tuân thủ trong mọi thay đổi của dự án. Các nguyên tắc này được đặt ra vì mang tính bắt buộc, không phải cho đẹp: nếu nới lỏng bất kỳ điều nào, một bộ phận cụ thể của hệ thống sẽ bị phá vỡ.

---

### 1 · Phân tách giữa Shape và Value

Chỉ những yếu tố sau được phép xác định lúc runtime: giá trị của tham số; kết quả boolean của `<if>`/`<when>`; số lượng phần tử trong collection của `<foreach>`; các dòng dữ liệu trong ResultSet; số lượng cột thực tế khi danh sách SELECT không thể phân tích cú pháp tĩnh; nội dung của `SqlFragment`.

Quy tắc này về mặt lý thuyết cũng cho phép chọn một `databaseId` một lần duy nhất lúc khởi động ứng dụng. Tuy nhiên hiện tại chưa có phần nào triển khai: thuộc tính `databaseId` sẽ báo lỗi biên dịch, do đó đây chỉ là một vị trí dự phòng trong thiết kế, không phải là một tính năng.

**Hệ quả nếu nới lỏng:** danh sách ngoại lệ sẽ phình to dần cho đến khi hệ thống buộc phải mang bộ thông dịch (interpreter) trở lại. Xem [Shape và Value](shape-vs-value.md).

---

### 2 · Tuyệt đối không dùng reflection lúc runtime

Không dùng `Proxy`, không dùng `Class.forName` và không dùng `setAccessible`, cả trong module runtime lẫn trong code sinh ra. `larkbatis-runtime` không có bất kỳ dependency nào ngoài JDBC thuần.

**Hệ quả nếu nới lỏng:** GraalVM native image sẽ đòi hỏi phải viết thủ công reachability metadata, làm mất đi lý do quan trọng nhất để dự án này tồn tại.

---

### 3 · Module chỉ dùng lúc build không bao giờ xuất hiện trên classpath runtime

`larkbatis-processor` và cả hai plugin Gradle/Maven đều là công cụ chỉ dùng trong pha biên dịch.

**Hệ quả nếu nới lỏng:** bộ sinh code có thể bị gọi lúc runtime, dẫn đến việc vi phạm nguyên tắc 1 và 2 mà không thể kiểm soát được.

---

### 4 · Kỷ luật kiểm soát `${}`

`${}` chỉ được liên kết với `SqlFragment`, các kiểu dữ liệu có tập giá trị đóng (`int`, `long`, `boolean`, enum), hoặc tham số được gắn annotation `@OrderBy(allowed = {...})`. Chữ ký phương thức nhận `String` thô sẽ **báo lỗi biên dịch**. `SqlFragment.unsafeRawSql` là điểm kiểm toán duy nhất cho các đoạn text SQL tuỳ ý, và lối thoát thủ công cũng chỉ nhận `SqlFragment`, không bao giờ nhận `String`. Các statement chứa `${}` sẽ được chèn thêm lệnh gọi `LarkBatisSql.trackVariants` sinh sẵn.

**Hệ quả nếu nới lỏng:** việc rà soát lỗ hổng SQL injection sẽ quay lại cảnh phải đọc thủ công từng mapper, và khả năng kiểm toán toàn bộ dự án bằng một lệnh `grep` duy nhất sẽ biến mất.

---

### 5 · Ngữ pháp biểu thức thu hẹp

Thuộc tính `<if test>` chỉ chấp nhận kiểm tra null, so sánh trên đường dẫn thuộc tính có kiểu tĩnh, các toán tử `and`/`or`/`not`, các phương thức `size()`/`length()`/`isEmpty()`, các phương thức trả về boolean, và biến boolean thuần. Ngữ pháp này chủ động không tái lập cơ chế truthiness của OGNL trong MyBatis: `test="count"` và `test="user"` là lỗi biên dịch, bắt buộc phải viết rõ `count != 0` hoặc `user != null`.

**Hệ quả nếu nới lỏng:** OGNL sẽ quay trở lại, kéo theo bộ đánh giá runtime, mô hình kiểu dữ liệu runtime và sự mơ hồ mà ngữ pháp này được tạo ra để loại bỏ.

---

### 6 · Trình đọc dòng (Row Reader)

Đọc theo vị trí cột (`rs.getLong(1)`) khi bộ sinh code phân tích được danh sách SELECT; ngược lại đọc theo tên cột với index được resolve **đúng một lần** từ `ResultSetMetaData` ở dòng đầu tiên. Một đoạn `${}` nằm trong danh sách SELECT sẽ hạ cấp statement đó xuống chế độ đọc theo tên, và trình biên dịch sẽ phát cảnh báo rõ ràng.

**Hệ quả nếu nới lỏng:** hệ thống phải tra cứu tên cột cho từng dòng dữ liệu, vốn là nguyên nhân chính gây suy giảm hiệu năng đã được loại bỏ.

---

### 7 · Spring: Hợp đồng quản lý Connection

`LarkBatisSession.conn()` luôn đi qua `DataSourceUtils`, không bao giờ gọi trực tiếp `dataSource.getConnection()`. Thân phương thức sinh ra **không được** đặt `Connection` trong khối try-with-resources; việc giải phóng kết nối phải gọi qua `s.release(c)` trong khối `finally`. Class `@Configuration` sinh ra phải đặt `proxyBeanMethods = false`. Auto-configuration của Spring Boot đăng ký qua `META-INF/spring/…AutoConfiguration.imports`, không dùng `spring.factories`.

**Hệ quả nếu nới lỏng:** `@Transactional` sẽ âm thầm mất tác dụng: mỗi lời gọi mapper sẽ tự mở một connection riêng và commit độc lập, gây lỗi toàn vẹn dữ liệu trong âm thầm.

---

### 8 · Code sinh ra là một tính năng

Mã nguồn sinh ra phải dễ đọc và có thể đặt breakpoint debug trực tiếp. Mỗi mapper tương ứng với một class `$$Impl`, mỗi result class tương ứng với một row reader. Các điều kiện `<if>` được đánh giá một lần duy nhất vào các biến cục bộ (`boolean c0 = …`), được tái sử dụng cho cả việc ghép chuỗi SQL lẫn việc gán tham số.

**Hệ quả nếu nới lỏng:** khả năng debug trực quan sẽ biến mất, trong khi đây lại là giá trị được các kỹ sư đánh giá cao nhất trong quá trình làm việc hàng ngày, vượt trên cả sự chênh lệch về micro giây.

---

### 9 · Xử lý `useGeneratedKeys`

Luôn truyền tường minh danh sách tên cột khoá vào `prepareStatement(sql, String[])`, vì Oracle trả về `ROWID` còn PostgreSQL trả về tất cả các cột nếu dùng `RETURN_GENERATED_KEYS`. Trình biên dịch sẽ phát cảnh báo lúc build khi thiếu `keyColumn`. Đồng thời bắt buộc phải kiểm tra số lượng khoá trả về trong chế độ batch.

**Hệ quả nếu nới lỏng:** code chạy đúng trên H2 nhưng trả về sai khoá trên môi trường production, và thao tác batch insert có thể bỏ sót id của một số dòng mà không phát hiện được.

---

## Cơ chế thực thi các nguyên tắc

Không dựa vào quy ước suông:

- **`CompileFailTest`**: mọi khẳng định "trường hợp này sẽ báo lỗi biên dịch" đều có unit test tự động tương ứng.
- **Golden snapshot**: kết quả sinh code được commit vào git và so sánh diff liên tục, đảm bảo các quy tắc định hình code (7, 8) không bị biến đổi âm thầm.
- **Quy chuẩn bộ sinh code (Emitter spec)**: cấu trúc mục tiêu của code sinh ra tồn tại dưới dạng các class Java mẫu đã biên dịch và kiểm thử thành công để đo đạc chất lượng bộ sinh code.
- **Kiểm thử vi sai (Differential test)**: câu SQL sinh ra được đối chiếu trực tiếp với kết quả thông dịch của MyBatis trên cùng một mapper, đảm bảo tính đúng đắn về mặt ngữ nghĩa cho nguyên tắc 5 và 6.
- **Code review chuyên trách** cho mọi thay đổi liên quan đến emitter và bề mặt công khai của runtime.

## Phản hồi các quan điểm phản biện

Bốn ý kiến phản biện phổ biến cần được giải đáp thẳng thắn:

| Luận điểm | Phản hồi |
|---|---|
| *"Micronaut Data, Quarkus Panache và jOOQ đã tồn tại sẵn."* | Đúng, và đó là bằng chứng cho thấy tính khả thi của giải pháp. Tuy nhiên, không có công cụ nào trong số đó giữ lại mô hình mapper MyBatis mà hàng nghìn hệ thống đang vận hành. Giá trị của LarkBatis nằm ở lộ trình chuyển đổi mượt mà, không nằm ở việc phát minh lại ý tưởng |
| *"Thời gian build sẽ tăng lên."* | Đúng, và đây là chi phí thực tế mà lập trình viên trả một lần mỗi ngày thay vì để hệ thống production phải trả giá liên tục. Chi phí này được giảm thiểu nhờ cơ chế xử lý tăng dần (incremental processing). Bản chất là chuyển dịch chi phí sang trái, không phải triệt tiêu |
| *"Sửa SQL đồng nghĩa với việc phải build lại."* | Đây là phản biện xác đáng nhất và không thể né tránh. Đối với đội ngũ quen sửa XML rồi restart, quy trình làm việc sẽ thay đổi. Tuy nhiên, câu SQL có lỗi kiểu dữ liệu đằng nào cũng sẽ sập lúc runtime; việc build lại giúp javac phát hiện lỗi ngay từ đầu |
| *"Bắt buộc dùng `SqlFragment` khiến phải sửa mọi vị trí gọi `${}`."* | Đúng, và khối lượng sửa đổi tỷ lệ với số lượng điểm gọi thay vì số lượng mapper. Bộ scanner hỗ trợ tự động định hình các trường hợp cơ học. Đổi lại, việc rà soát này giúp đội ngũ kiểm tra lại toàn bộ các điểm chèn SQL thô trong toàn bộ codebase |

Một ý kiến khác lo ngại code sinh ra làm phình to kích thước file jar và làm chậm IDE: trên thực tế, một class impl và một reader cho mỗi mapper chỉ tốn vài nghìn dòng code cho 300 phương thức mapper, nhỏ hơn rất nhiều so với 40.000 dòng mã nguồn framework mà nó thay thế.
