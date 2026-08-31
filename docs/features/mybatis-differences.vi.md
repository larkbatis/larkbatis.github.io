# Khác biệt so với MyBatis

Tất cả các thay đổi trong LarkBatis đều bắt nguồn từ một mục tiêu thiết kế nhất quán: loại bỏ hoàn toàn bộ thông dịch runtime, reflection và dynamic proxy để chuyển toàn bộ việc phân tích sang pha biên dịch (`javac`).

## Nhóm 1: Các tính năng chủ động loại bỏ

Các tính năng này đòi hỏi reflection hoặc dynamic bytecode manipulation lúc runtime—những cơ chế không còn tồn tại trong kiến trúc của LarkBatis.

| Tính năng | Lý do loại bỏ | Giải pháp thay thế |
|---|---|---|
| **OGNL runtime trong `test`** | Đòi hỏi bộ thông dịch biểu thức lúc runtime | [Ngữ pháp biểu thức an toàn](../usage/dynamic-sql.md#the-test-grammar) |
| **`<bind>`** | Tạo biến OGNL động lúc chạy | Tính toán trước trong mã Java rồi truyền vào tham số mapper |
| **Provider annotations (`@SelectProvider`, v.v.)** | Chuỗi SQL dựng động trong Java không thể phân tích trước lúc build | Đặt SQL trong mapper hoặc dùng [lối thoát thủ công (`SqlFragment`)](../usage/raw-sql.md#the-escape-hatch) |
| **Lazy loading** | Đòi hỏi bọc bytecode proxy trên từng đối tượng kết quả | Dùng phép `JOIN` để lấy dữ liệu ngay, hoặc tách thành hai câu truy vấn riêng |
| **Plugin / Interceptor** | Không còn 4 đối tượng trung gian (`Executor`, `StatementHandler`, v.v.) để chặn | [Xem giải pháp thay thế Plugin bên dưới](#what-replaces-a-plugin) |
| **Tham số `Object` / `Map` không định kiểu** | Không xác định được kiểu dữ liệu tĩnh để sinh lệnh `ps.setXxx` | Dùng parameter class rõ ràng hoặc khai báo từng tham số với `@Param` |
| **`<discriminator>`** | Khiến class trả về phụ thuộc vào giá trị dữ liệu lúc runtime | Tách thành các phương thức truy vấn riêng biệt cho từng loại entity |
| **Lồng `select="..."` trong result map** | Nguy cơ gây ra lỗi N+1 truy vấn lúc runtime | Viết câu lệnh `JOIN` tường minh |
| **Level-2 Cache (`<cache>`)** | Quản lý cache ở tầng ORM rất dễ gây xung đột dữ liệu | Triển khai cache ở tầng Service (ví dụ Spring `@Cacheable`) |
| **`RowBounds`** | Đọc toàn bộ ResultSet vào RAM rồi mới cắt trang gây lãng phí bộ nhớ | Phân trang trực tiếp trong SQL bằng `LIMIT` và `OFFSET` |
| **`<selectKey>`** | Statement thứ hai chạy ngầm | Tách thành câu lệnh truy vấn thứ hai độc lập. Xem [Generated Keys](../usage/generated-keys.md#selectkey-is-not-supported) |
| **Constructor mapping (`<constructor>`)** | Yêu cầu khớp constructor phức tạp | Dùng constructor mặc định và setter |
| **Type alias** | Là bảng tra cứu động lúc runtime | Dùng tên class đầy đủ (FQN) |
| **Level-1 Cache (Session cache)** | `LarkBatisSession` là stateless để đảm bảo an toàn đa luồng | Quản lý transaction rõ ràng |
| **`ExecutorType.BATCH` / `REUSE`** | Không dùng executor trung gian | Batch insert được định nghĩa qua [chữ ký phương thức nhận `List<T>`](../usage/foreach-and-batches.md#jdbc-batches) |

### Giải pháp thay thế cho MyBatis Plugin { #what-replaces-a-plugin }

Trong MyBatis, `Interceptor` chặn bắt 4 đối tượng: `Executor`, `StatementHandler`, `ParameterHandler`, và `ResultSetHandler` bằng cách bọc chúng qua `Proxy.newProxyInstance()`.

Trong LarkBatis, 4 đối tượng này **không còn tồn tại**. Chúng được thay thế hoàn toàn bằng thân phương thức sinh sẵn gọi trực tiếp JDBC (`Connection.prepareStatement`, `ps.setLong`, `rs.getString`).

Bảng hướng dẫn thay thế các trường hợp sử dụng Plugin phổ biến:

| Mục đích của Plugin | Giải pháp trong LarkBatis |
|---|---|
| Phân trang (PageHelper, v.v.) | Truyền `limit` và `offset` làm tham số `#{}` thông thường, và viết phương thức `count()` riêng biệt. Điều này triệt tiêu hoàn toàn nguy cơ rò rỉ bộ nhớ `ThreadLocal` |
| Tự động điền `created_at`, `updated_by` | Gán giá trị trực tiếp ở tầng Service trước khi gọi mapper, dùng giá trị mặc định của cột trong database, hoặc đưa danh sách cột vào đoạn [`<sql>` fragment](../usage/xml-mappers.md) |
| Xoá mềm (Soft delete) | Thêm điều kiện `AND deleted = false` vào câu truy vấn hoặc trích xuất vào `<sql>` fragment dùng chung. Rõ ràng, dễ tìm kiếm (grep) và không bị bỏ sót |
| Mã hoá hoặc che giấu dữ liệu (masking) | Tạo [`LarkBatisTypeHandler`](../usage/types.md#custom-type-handlers) và cấu hình qua [`-Alarkbatis.typeHandlers`](configuration.md#type-handlers-for-a-whole-build) |
| Ghi log SQL | Cấu hình ở tầng DataSource hoặc Connection Pool (ví dụ `net.ttddyy:datasource-proxy`, `p6spy`) |
| Multi-tenancy (tên schema / bảng động) | Dùng [`SqlFragment`](../usage/raw-sql.md) qua cú pháp `${}` an toàn |
| Metrics, tracing, APM | Áp dụng Spring AOP hoặc viết Decorator bọc quanh mapper bean |

## Nhóm 2: Các tính năng giữ lại nhưng thu hẹp phạm vi

Các tính năng này vẫn được hỗ trợ nhưng tuân theo quy tắc kiểm tra kiểu tĩnh lúc biên dịch:

| Tính năng | Phạm vi thu hẹp | Lý do kỹ thuật |
|---|---|---|
| **`<where>`, `<set>`, `<trim>`** | Thuộc tính prefix/suffix cố định, gập hằng số lúc build | Tối ưu hóa chuỗi SQL và loại bỏ regex scanning lúc runtime |
| **`<foreach>`** | Collection, mảng phải có kiểu tĩnh. Ném exception nếu rỗng. Hỗ trợ `@PadPow2` | Xác định kiểu setter JDBC chính xác từ trước. Xem [foreach & Batching](../usage/foreach-and-batches.md) |
| **`<sql>`, `<include>`** | `refid` phải là hằng số cố định, được inline lúc build | Loại bỏ bảng tra cứu XML DOM lúc runtime |
| **`<resultMap>` lồng nhau** | Tối đa 1 cấp quan hệ 1-N qua phép join; yêu cầu `ORDER BY` theo khóa bảng cha | Ánh xạ dữ liệu dạng single-pass streaming hiệu năng cao. Xem [Result Maps](../usage/result-maps.md) |
| **Custom TypeHandler** | Khai báo tường minh tại vị trí dùng hoặc qua compiler option `-Alarkbatis.typeHandlers` | Loại bỏ cơ chế quét classpath runtime |
| **`${}` (Chèn chuỗi động)** | Chỉ chấp nhận `SqlFragment`, enum/primitive, hoặc `@OrderBy(allowed = {...})` | Ngăn ngừa triệt để lỗi bảo mật SQL Injection |

## Nhóm 3: Các tính năng chuyển dịch hoàn toàn sang pha build

Các cơ chế sau đã được giải quyết xong trong quá trình biên dịch (`javac`), không cần cấu hình runtime:

| Khái niệm cũ trong MyBatis | Cách xử lý trong LarkBatis |
|---|---|
| Tra cứu `TypeHandlerRegistry` cho từng tham số/cột | Lệnh gọi `ps.setXxx` và `rs.getXxx` được hardcode trực tiếp vào mã nguồn sinh ra |
| `Reflector`, `MetaObject`, `BeanWrapper` | Gọi trực tiếp setter của Java Bean |
| Cấu hình `mapUnderscoreToCamelCase` | Mặc định luôn bật (*enabled*) lúc build (có thể tắt qua `-Alarkbatis.mapUnderscoreToCamelCase=false`) |
| `MapperProxy` + `MapperMethod` dispatch | Gọi trực tiếp phương thức trong class `Mapper$$Impl` |
| Quét classpath tìm mapper XML khi khởi động | Bộ biên dịch và build plugin xử lý xong lúc build |
| `@MapperScan` + `MapperFactoryBean` | Tự động sinh class `@Configuration` chứa các `@Bean` phương thức thuần túy |

## Các điểm khác biệt về hành vi cần lưu ý khi Migration { #behavioural-divergences-to-check-when-migrating }

Khi chuyển đổi từ MyBatis sang LarkBatis, hãy lưu ý 4 điểm khác biệt sau:

1. **`<foreach>` rỗng sẽ ném exception**: Nếu collection truyền vào rỗng, LarkBatis sẽ ném `LarkBatisEmptyForeachException` thay vì sinh ra câu SQL lỗi `WHERE id IN ()`. Nếu muốn bỏ qua điều kiện khi danh sách rỗng, hãy bọc thẻ này trong `<if test="ids != null and !ids.isEmpty()">`.
2. **So sánh với null trả về false**: Trong MyBatis/OGNL, giá trị null khi so sánh số học được ép về 0 (ví dụ `age <= 18` trả về `true` nếu `age` là null). Trong LarkBatis, so sánh số học với null luôn trả về **`false`**.
3. **Gọi phương thức trên đối tượng null trả về false**: Biểu thức `user.isActive()` khi `user` là null sẽ an toàn trả về `false` thay vì ném `NullPointerException`.
4. **Khoảng trắng trong SQL được chuẩn hóa**: Các đoạn SQL động được nối với nhau bằng đúng 1 khoảng trắng và loại bỏ các khoảng trắng thừa.

## Đảm bảo tính đúng đắn qua Differential Testing

Hệ thống kiểm thử vi sai (differential test harness) của LarkBatis chạy cùng một mapper trên cả hai công cụ: MyBatis gốc và LarkBatis mã sinh ra, kết nối tới recording `DataSource` để kiểm tra từng ký tự SQL và tham số binding nhằm đảm bảo tính tương thích tuyệt đối.

