# 9 Nguyên tắc thiết kế cốt lõi (Design Rules)

Chín nguyên tắc bất biến chi phối toàn bộ mã nguồn và kiến trúc của LarkBatis. Nếu vi phạm bất kỳ nguyên tắc nào, một bộ phận tương ứng của hệ thống sẽ bị phá vỡ.

---

### 1 · Phân tách tuyệt đối giữa Shape và Value

Chỉ các phần tử sau được phép resolve lúc runtime:
- Giá trị của tham số phương thức.
- Kết quả boolean của biểu thức `<if test>` / `<when test>`.
- Kích thước collection của `<foreach>`.
- Dữ liệu các dòng trong `ResultSet`.
- Số lượng cột thực tế khi select list không thể phân tích tĩnh (`SELECT *`).
- Nội dung chuỗi của `SqlFragment`.

**Hệ quả nếu vi phạm:** Runtime sẽ dần biến tướng trở lại thành một dynamic interpreter.

---

### 2 · Tuyệt đối không dùng Reflection lúc Runtime

Không dùng `Proxy`, không dùng `Class.forName` và không dùng `setAccessible`, kể cả trong thư viện runtime lẫn trong mã nguồn sinh ra.

**Hệ quả nếu vi phạm:** GraalVM Native Image sẽ đòi hỏi cấu hình reachability metadata thủ công, làm mất đi ưu thế hàng đầu của dự án.

---

### 3 · Module Build-time không bao giờ xuất hiện trên Runtime Classpath

`larkbatis-processor`, `larkbatis-gradle-plugin` và `larkbatis-maven-plugin` là các công cụ chỉ phục vụ pha biên dịch.

**Hệ quả nếu vi phạm:** Mã nguồn processor có thể bị gọi lúc runtime, dẫn đến việc vi phạm nguyên tắc 1 và 2 ngoài tầm kiểm soát.

---

### 4 · Kiểm soát an toàn cho `${}`

`${}` chỉ chấp nhận `SqlFragment`, kiểu tập giá trị đóng (`int`, `long`, `boolean`, enum), hoặc tham số có gắn `@OrderBy(allowed = {...})`. Tham số kiểu `String` thuần sẽ **báo lỗi biên dịch**. `SqlFragment.unsafeRawSql()` là điểm kiểm toán duy nhất cho SQL thô trong toàn bộ dự án.

**Hệ quả nếu vi phạm:** Việc kiểm toán lỗ hổng SQL Injection sẽ quay lại cảnh phải rà soát thủ công từng file mapper.

---

### 5 · Ngữ pháp biểu thức `test` tĩnh và tối giản

Thuộc tính `<if test>` chỉ chấp nhận kiểm tra null, so sánh giá trị trên thuộc tính có kiểu tĩnh, toán tử boolean `and`/`or`/`not`, và các hàm `size()`/`length()`/`isEmpty()`. Không hỗ trợ OGNL truthiness ngầm định: `test="count"` hoặc `test="user"` là lỗi biên dịch.

**Hệ quả nếu vi phạm:** Trình thông dịch OGNL runtime sẽ phải mang quay trở lại.

---

### 6 · Đọc ResultSet tối ưu theo vị trí cột

Đọc theo vị trí cột cố định (`rs.getLong(1)`) khi phân tích được danh sách SELECT lúc build. Khi không phân tích được (`SELECT *`), chỉ quét `ResultSetMetaData` đúng **một lần duy nhất** ở dòng đầu tiên để lấy mảng chỉ số cột.

**Hệ quả nếu vi phạm:** Hệ thống phải tra cứu tên cột trên từng dòng, gây suy giảm hiệu năng nghiêm trọng.

---

### 7 · Quản lý Connection qua Spring `DataSourceUtils`

`LarkBatisSession.conn()` luôn gọi qua `DataSourceUtils.getConnection(dataSource)`. Tuyệt đối không bọc `Connection` trong khối `try-with-resources`. Class `@Configuration` sinh ra phải đặt `proxyBeanMethods = false`.

**Hệ quả nếu vi phạm:** Annotation `@Transactional` sẽ mất tác dụng: mỗi phương thức mapper tự mở và đóng connection riêng lẻ, phá vỡ transaction context.

---

### 8 · Mã nguồn sinh ra phải trực quan và dễ debug

Mã nguồn Java sinh ra là một **tính năng**: cấu trúc rõ ràng, dễ đọc và cho phép đặt breakpoint debug trực tiếp trong IDE. Các điều kiện boolean được lưu vào biến cục bộ và tái sử dụng chung cho cả lệnh nối SQL lẫn lệnh bind tham số.

**Hệ quả nếu vi phạm:** Lập trình viên mất khả năng debug trực quan trong IDE.

---

### 9 · Khai báo tường minh `keyColumn` cho `useGeneratedKeys`

Luôn truyền mảng tên cột khóa chính vào `prepareStatement(sql, String[])` để đảm bảo tính di động trên Oracle và PostgreSQL. Bắt buộc kiểm tra số lượng khóa trả về trong batch insert.

**Hệ quả nếu vi phạm:** Chạy đúng trên H2/MySQL nhưng trả về sai khóa chính trên Oracle/PostgreSQL trên môi trường production.

---

## Cơ chế thực thi kiểm soát chất lượng

- **`CompileFailTest`**: Mỗi ràng buộc biên dịch đều có unit test tự động xác nhận `javac` báo lỗi đúng như kỳ vọng.
- **Golden Snapshot Testing**: Mã nguồn sinh ra được commit vào git và theo dõi diff liên tục.
- **Differential Testing**: Đối chiếu chuỗi SQL và tham số JDBC sinh ra trực tiếp với kết quả thông dịch của MyBatis.
- **Emitter Specification**: Cấu trúc code sinh ra được kiểm chuẩn so với các class Java mẫu viết tay.

