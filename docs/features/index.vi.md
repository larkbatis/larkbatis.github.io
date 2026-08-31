# Ma trận tính năng

Bảng tổng hợp chi tiết mức độ hỗ trợ các tính năng trong LarkBatis: :material-check: Đã hỗ trợ đầy đủ kèm test kiểm thử; :material-alert: Thu hẹp phạm vi theo quy tắc an toàn; :material-close: Chủ động loại bỏ (báo lỗi compile kèm giải pháp thay thế).

Phiên bản hiện tại: **`0.1.0`**.

## Khai báo Statement

| Tính năng | Trạng thái | Ghi chú kỹ thuật |
|---|---|---|
| `@Select`, `@Insert`, `@Update`, `@Delete` | :material-check: | Chấp nhận mảng `String[]`, tự động nối với nhau bằng dấu cách |
| `<select>`, `<insert>`, `<update>`, `<delete>` trong mapper XML | :material-check: | Namespace là FQN của interface, `id` khớp với tên phương thức. Xem [Mapper XML](../usage/xml-mappers.md) |
| Kết hợp cả annotation và XML trong cùng một mapper | :material-check: | Xử lý độc lập theo từng phương thức (báo lỗi compile nếu trùng lặp hoặc thiếu định nghĩa) |
| Tham số liên kết `#{}` | :material-check: | Xác định kiểu dữ liệu tĩnh từ tham số phương thức lúc biên dịch |
| Chèn chuỗi động `${}` | :material-alert: | Chỉ chấp nhận `SqlFragment`, enum/primitive, hoặc `@OrderBy`. Xem [Raw SQL & An toàn](../usage/raw-sql.md) |
| `@Param` | :material-check: | Đặt tên tham số tường minh cho câu lệnh SQL |
| `@Options(useGeneratedKeys, keyProperty, keyColumn)` | :material-check: | Tự động gán khóa chính tự tăng sau khi insert. Xem [Generated Keys](../usage/generated-keys.md) |
| `<selectKey>` | :material-close: | Thay thế bằng hai câu truy vấn độc lập để kiểm soát transaction rõ ràng |
| Provider annotations (`@SelectProvider`, v.v.) | :material-close: | Chuỗi SQL dựng động qua reflection lúc runtime không thể phân tích trước lúc build |
| Tham số kiểu `Map` hoặc `Object` không định kiểu | :material-close: | Cần định nghĩa parameter class rõ ràng hoặc gắn `@Param` cho từng tham số |
| `RowBounds` | :material-close: | Phân trang trên bộ nhớ (in-memory) gây lãng phí RAM. Nên dùng `LIMIT`/`OFFSET` trực tiếp trong SQL |

## SQL Động (Dynamic SQL)

| Tính năng | Trạng thái | Ghi chú kỹ thuật |
|---|---|---|
| `<if>` | :material-check: | Biên dịch thành biến `boolean` cục bộ, đánh giá điều kiện một lần duy nhất |
| `<choose>`, `<when>`, `<otherwise>` | :material-check: | Biên dịch thành khối lệnh `if-else` trong mã Java thuần |
| `<where>`, `<set>` | :material-check: | Constant-fold lúc biên dịch, không quét chuỗi regex lúc runtime |
| `<trim>` | :material-alert: | Chỉ hỗ trợ chuỗi tiền tố/hậu tố cố định |
| `<sql>`, `<include>` | :material-alert: | `refid` phải cố định, được inline trực tiếp lúc biên dịch |
| `<foreach>` | :material-alert: | Ném exception nếu collection rỗng. Xem [foreach & Batching](../usage/foreach-and-batches.md) |
| `@PadPow2` | :material-check: | Giới hạn số lượng biến thể prepared statement trong mệnh đề `IN` |
| `<bind>` | :material-close: | Nên tính toán biến trong mã Java trước khi truyền vào mapper |
| Biểu thức OGNL phức tạp trong `test` | :material-close: | Thay thế bằng [ngữ pháp biểu thức an toàn](../usage/dynamic-sql.md#the-test-grammar) |
| `databaseId` | :material-close: | Nên tách riêng từng interface mapper cho mỗi loại database vendor |

## Ánh xạ kết quả (Result Mapping)

| Tính năng | Trạng thái | Ghi chú kỹ thuật |
|---|---|---|
| Ánh xạ `resultType` theo quy ước | :material-check: | Tự động chuyển đổi `snake_case` sang `camelCase` lúc biên dịch |
| Đọc dòng theo chỉ số vị trí cột | :material-check: | Tối ưu khi câu `SELECT` liệt kê tên cột rõ ràng |
| Fallback đọc theo tên cột | :material-check: | Sử dụng khi câu truy vấn là `SELECT *` (phân giải index một lần qua `ResultSetMetaData`) |
| Kết quả kiểu vô hướng (Scalar) | :material-check: | Đọc trực tiếp kiểu nguyên thủy / wrapper từ cột đầu tiên |
| Trả về `List<T>` | :material-check: | Đọc danh sách bản ghi tuần tự |
| Trả về `Stream<T>` | :material-check: | Stream kết nối con trỏ database, caller chịu trách nhiệm đóng stream. Xem [Streaming](../usage/streaming.md) |
| `<resultMap>` | :material-alert: | Ánh xạ tường minh các cột được định nghĩa, không tự động auto-mapping |
| `<association>`, `<collection>` | :material-alert: | Hỗ trợ 1 cấp join, yêu cầu câu truy vấn `ORDER BY` theo khóa của bảng cha |
| Lồng `select="..."` trong result map | :material-close: | Tránh phát sinh lỗi N+1 truy vấn; nên viết câu `JOIN` tường minh |
| `<discriminator>` | :material-close: | Kiểu class kết quả phải cố định từ lúc biên dịch |
| `<constructor>` mapping | :material-close: | POJO kết quả yêu cầu constructor không tham số và setter |
| `extends`, `columnPrefix`, `autoMapping` | :material-close: | Khai báo tường minh tất cả ánh xạ cần thiết |
| Lazy loading | :material-close: | Tránh tạo bytecode proxy bọc quanh đối tượng kết quả |
| Type alias | :material-close: | Sử dụng tên class đầy đủ (FQN) |

## Kiểu dữ liệu & Type Handlers

| Tính năng | Trạng thái | Ghi chú kỹ thuật |
|---|---|---|
| Kiểu nguyên thủy và wrapper | :material-check: | Sử dụng `JdbcCodec` để xử lý `null` an toàn |
| `String`, `BigDecimal`, `BigInteger`, `byte[]` | :material-check: | Đọc/ghi trực tiếp qua JDBC |
| `java.sql.Date`, `Time`, `Timestamp` | :material-check: | Đọc/ghi trực tiếp qua JDBC |
| `Instant`, `LocalDate`, `LocalTime`, `LocalDateTime` | :material-check: | Hỗ trợ toàn diện API `java.time` chuẩn |
| Enum (theo `name()`) | :material-check: | Kiểu tập đóng an toàn, được phép dùng trong `${}` |
| `@Column` | :material-check: | Đặt tên cột thủ công trên field hoặc getter/setter. Xem [Annotations](annotations.md#column) |
| Custom TypeHandler với `@Handler` | :material-check: | Gắn trên field, param hoặc trong XML. Xem [Kiểu dữ liệu](../usage/types.md#custom-type-handlers) |
| `<typeHandlers>` cấp toàn cục | :material-check: | Cấu hình qua compiler option `-Alarkbatis.typeHandlers`. Xem [Cấu hình](configuration.md) |
| Quét tự động TypeHandler (`<package>`) | :material-close: | Không quét classpath lúc runtime; cần khai báo tường minh lúc biên dịch |

## Session & Quản lý Transaction

| Tính năng | Trạng thái | Ghi chú kỹ thuật |
|---|---|---|
| Scope `LarkBatisTx`, cơ chế vote-to-commit | :material-check: | Hỗ trợ lồng scope transaction độc lập. Xem [Transactions](../usage/transactions.md) |
| Spring `@Transactional` | :material-check: | Tích hợp trực tiếp qua `DataSourceUtils` |
| Dịch mã lỗi Spring | :material-check: | Tự động chuyển đổi sang cây exception `DataAccessException` |
| Spring Boot Starter | :material-check: | Tương thích cả Spring Boot 3 và Spring Boot 4 trong cùng một jar |
| Sinh `@Configuration` tự động | :material-check: | Thiết lập `proxyBeanMethods = false` để tránh CGLIB proxy |
| Batch insert | :material-check: | Hỗ trợ phương thức nhận `List<T>` gọi `addBatch()` tự động |
| Insert nhiều bản ghi qua `VALUES (...)` | :material-check: | Sử dụng `<foreach>` để sinh câu SQL gộp tối ưu |
| Escape hatch (`query`, `queryOne`, `update`) | :material-check: | Thực thi qua `SqlFragment`, không nhận chuỗi `String` tùy tiện |
| `ExecutorType.BATCH` / `REUSE` | :material-close: | Không dùng executor trung gian phức tạp |
| Plugins / Interceptors | :material-close: | Xem [Giải pháp thay thế Plugin](mybatis-differences.md#what-replaces-a-plugin) |
| Level-2 Cache (`<cache>`, `<cache-ref>`) | :material-close: | Nên cài đặt cache ở tầng Service thay vì tầng ORM |
| Level-1 Cache | :material-close: | `LarkBatisSession` là stateless, không lưu trữ entity cache |
| Đăng ký `addMapper()` động lúc runtime | :material-close: | Danh sách mapper được chốt cố định lúc biên dịch |
| Ghi log SQL (`log-sql`) | :material-close: | Sử dụng logging proxy ở tầng DataSource (như `datasource-proxy`, `p6spy`) |

## Build & Đóng gói

| Tính năng | Trạng thái | Ghi chú kỹ thuật |
|---|---|---|
| Annotation processor (javac) | :material-check: | Chỉ hỗ trợ `javac`, không hỗ trợ ECJ |
| Gradle plugin | :material-check: | Tự động cấu hình compile inputs và processor path |
| Maven plugin | :material-check: | Yêu cầu cấu hình `<extensions>true</extensions>` |
| JPMS (Java Module System) | :material-check: | Tất cả artifact đều có `module-info.java` chuẩn |
| Tương thích với Lombok | :material-check: | Khai báo `larkbatis-processor` chạy sau Lombok |
| Incremental compilation | :material-alert: | Aggregating processor; cần bật cờ `-parameters` |
| GraalVM Native Image | :material-alert: | Sẵn sàng về mặt cấu trúc (không dùng reflection); kiểm thử quy trình build đầy đủ ở mốc M5 |
| Quét mã nguồn cũ `larkbatis-scan` | :material-check: | Công cụ CLI phân tích mức độ tương thích. Xem [Migration](migration.md) |

## Tài liệu liên quan

- [Khác biệt với MyBatis](mybatis-differences.md): Chi tiết các thay đổi hành vi và hướng xử lý
- [Danh mục Annotations](annotations.md): Chi tiết toàn bộ annotation của LarkBatis
- [Runtime API](runtime-api.md): Bề mặt API public lúc runtime
- [Tùy chọn cấu hình](configuration.md): Danh mục đầy đủ các compiler option và application properties

