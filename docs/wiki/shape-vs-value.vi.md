# Nguyên tắc Shape vs. Value

Mọi quyết định thiết kế trong LarkBatis đều dựa trên một nguyên tắc phân tách ranh giới duy nhất:
- **Shape (Cấu trúc tĩnh)**: Tất cả những gì có thể suy ra từ mapper interface, file XML, POJO result class và kiểu dữ liệu tham số. Shape cố định ngay khi lưu file mã nguồn và được giải quyết toàn bộ lúc build.
- **Value (Giá trị động)**: Dữ liệu thực tế truyền qua các tham số và dòng dữ liệu trả về từ database lúc runtime.

## Danh sách đóng các phần tử đánh giá lúc Runtime

Dưới đây là **danh sách đóng** toàn bộ những gì LarkBatis cho phép đánh giá lúc runtime. Bất kỳ thành phần nào ngoài danh sách này đều không được phép suy diễn động lúc chạy:

| Thành phần runtime | Lý do kỹ thuật bắt buộc |
|---|---|
| **Giá trị** của tham số phương thức | Dữ liệu đầu vào từ phía gọi |
| **Kết quả boolean** của biểu thức `<if test>` / `<when test>` | Phụ thuộc vào giá trị tham số cụ thể |
| **Kích thước collection** trong `<foreach>` | Số lượng phần tử do caller truyền vào |
| **Dữ liệu dòng** trong `ResultSet` | Trả về từ database |
| **Thứ tự cột thực tế** khi không thể phân tích tĩnh select list | `SELECT *` hoặc chèn chuỗi `${}` trong select list |
| **Nội dung chuỗi** của một `SqlFragment` | Phục vụ các câu SQL tùy biến có kiểm soát qua lối thoát thủ công |

Mọi thứ khác đều được quyết định tĩnh từ pha build (`javac`).

## So sánh xử lý giữa LarkBatis và MyBatis

| Quyết định kỹ thuật | LarkBatis (Compile-Time) | MyBatis (Runtime) |
|---|---|---|
| Phương thức `ps.setXxx` bind tham số | Biên dịch thẳng lệnh gọi JDBC theo kiểu tĩnh | Tra cứu `TypeHandlerRegistry` theo cặp `(javaType, jdbcType)` |
| Chỉ số cột đọc vào setter | Xác định index tĩnh (`rs.getString(1)`) | Reflection `MetaObject.setValue()` cho từng cột trên mỗi dòng |
| Nhận diện hàm setter | Phân tích getter/setter lúc build | `Reflector` dựng HashMap ánh xạ name → `Invoker` |
| Xóa tiền tố trong `<where>` | Gập hằng số thành biểu thức điều kiện boolean | Quét và cắt chuỗi SQL sau khi ghép |
| Inlined nội dung `<include>` | Thay thế trực tiếp trong pha compile | Tra cứu Map trong `Configuration` lúc khởi động |
| Đánh giá biểu thức `test` | Mã Java boolean thuần | Trình thông dịch OGNL evaluate động qua `ObjectWrapper` |
| Khởi tạo Mapper | Khởi tạo class `Mapper$$Impl` trực tiếp | JDK `Proxy.newProxyInstance` điều phối qua `MapperMethod` |

## Hệ quả kỹ thuật của nguyên tắc Shape vs. Value

1. **Phát hiện lỗi kiểu dữ liệu ngay lúc build**: Một lỗi gõ sai tên thuộc tính `#{customerName}` sẽ báo lỗi compile `javac` kèm tên method mapper, thay vì ném `ReflectionException` lúc runtime ở nhánh code hiếm khi chạy tới.
2. **Loại bỏ hoàn toàn Reflection Metadata cho Native Image**: Do không sử dụng `Proxy`, `Class.forName`, hay `setAccessible()`, ứng dụng không cần cấu hình file `reflect-config.json` cho GraalVM Native Image.
3. **Ngăn chặn triệt để suy diễn kiểu động lúc runtime**: Do không có runtime reflection engine, hệ thống không thể vô tình mang các cơ chế tra cứu động quay trở lại.
4. **Lý giải rõ ràng cho các tính năng bị loại bỏ**: 
   - Thẻ `<discriminator>` chọn class kết quả dựa trên giá trị cột (nghĩa là *Shape* của đối tượng phụ thuộc vào *Value* runtime), vi phạm trực tiếp nguyên tắc Shape vs. Value.
   - Lazy loading đòi hỏi bọc dynamic proxy trên từng entity kết quả.
   - Plugin/Interceptor can thiệp vào dynamic pipeline vốn không tồn tại trong LarkBatis.

## Các đánh đổi kỹ thuật (Trade-offs)

1. **Biến thể prepared statement của `<foreach>`**: Số lượng phần tử trong collection là giá trị runtime, do đó câu SQL buộc phải được dựng lúc chạy. LarkBatis hạn chế số biến thể statement bằng `@PadPow2` và theo dõi qua `LarkBatisSql.trackVariants()`.
2. **Đọc theo tên cột đối với `SELECT *`**: Khi không thể phân tích cú pháp tĩnh danh sách cột, LarkBatis fallback về đọc index cột từ `ResultSetMetaData` một lần duy nhất ở dòng đầu tiên.
3. **Kiểm soát an toàn cho `${}`**: Để hỗ trợ các nhu cầu sắp xếp động thực tế mà không mở cổng SQL Injection, LarkBatis yêu cầu kiểu dữ liệu của `${}` phải là `SqlFragment`, kiểu tập giá trị đóng, hoặc gắn `@OrderBy(allowed = {...})`.

