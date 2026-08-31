# Các tính năng được hỗ trợ

Bảng tổng hợp tính năng đầy đủ. Ký hiệu :material-check: là đã hiện thực và có test kiểm thử; :material-alert: là được thu hẹp phạm vi theo quy tắc rõ ràng; :material-close: là chủ động loại bỏ từ khâu thiết kế (trình biên dịch sẽ báo lỗi kèm theo giải pháp thay thế).

Phiên bản hiện tại: **`0.1.0-SNAPSHOT`**. Các milestone từ M1 đến M4 đã hoàn thành, M5 đang được tiến hành.

## Statement

| | | Ghi chú |
|---|---|---|
| `@Select` `@Insert` `@Update` `@Delete` | :material-check: | Giá trị `String[]`, được nối với nhau bằng một dấu cách đơn |
| `<select>` `<insert>` `<update>` `<delete>` trong mapper XML | :material-check: | Namespace là FQN của interface, `id` là tên phương thức. [Chi tiết](../usage/xml-mappers.md) |
| Kết hợp cả annotation và XML trong cùng một mapper | :material-check: | Được xác định theo từng phương thức; nếu một phương thức khai báo cả hai hoặc không khai báo cái nào thì trình biên dịch sẽ báo lỗi |
| Tham số liên kết `#{}` | :material-check: | Được resolve dựa trên kiểu tham số của phương thức ngay lúc build |
| Chèn trực tiếp `${}` | :material-alert: | Chỉ chấp nhận `SqlFragment`, kiểu dữ liệu tập giá trị đóng, hoặc `@OrderBy`. [Chi tiết](../usage/raw-sql.md) |
| `@Param` | :material-check: | Đặt tên rõ ràng cho tham số |
| `@Options(useGeneratedKeys, keyProperty, keyColumn)` | :material-check: | [Chi tiết](../usage/generated-keys.md) |
| `<selectKey>` | :material-close: | Tách thành một statement thứ hai riêng biệt |
| Họ annotation `@SelectProvider` / `@InsertProvider` | :material-close: | SQL do phương thức Java dựng động lúc runtime là thứ bộ sinh code không thể nhìn thấy lúc build |
| Tham số kiểu `Map` hoặc `Object` | :material-close: | Không có kiểu cụ thể để resolve `#{}`. Cần dùng parameter object hoặc đặt `@Param` cho từng tham số |
| `RowBounds` | :material-close: | Phân trang trên bộ nhớ từ ResultSet đầy đủ gây lãng phí. Nên phân trang bằng SQL với `LIMIT`/`OFFSET` |

## SQL động

| | | Ghi chú |
|---|---|---|
| `<if>` | :material-check: | Biên dịch thành biến cục bộ `boolean`, chỉ đánh giá một lần |
| `<choose>` / `<when>` / `<otherwise>` | :material-check: | Logic loại trừ tương hỗ được biên dịch thẳng vào code |
| `<where>` / `<set>` | :material-check: | Constant-folded lúc build, không quét chuỗi lúc runtime |
| `<trim>` | :material-alert: | Chỉ hỗ trợ thuộc tính dạng chuỗi cố định, xử lý gập hằng số lúc build |
| `<sql>` / `<include>` | :material-alert: | `refid` phải cố định, được inline trực tiếp lúc build |
| `<foreach>` | :material-alert: | Collection, mảng, map phải định kiểu tĩnh. Ném exception nếu collection rỗng. [Chi tiết](../usage/foreach-and-batches.md) |
| `@PadPow2` | :material-check: | Giới hạn số biến thể SQL trong mệnh đề `IN`. Ép theo đúng shape danh sách `IN` |
| `<bind>` | :material-close: | Tạo biến OGNL lúc chạy. Nên tính toán giá trị trong Java rồi truyền vào qua tham số |
| OGNL trong thuộc tính `test` | :material-close: | Thay thế bằng [ngữ pháp biểu thức thu hẹp](../usage/dynamic-sql.md#the-test-grammar); kiểm tra truthiness theo kiểu OGNL sẽ báo lỗi biên dịch |
| `databaseId` | :material-close: | Thuộc tính `databaseId` sẽ báo lỗi biên dịch. Nên tách riêng từng interface mapper cho mỗi loại database |

## Ánh xạ kết quả

| | | Ghi chú |
|---|---|---|
| `resultType` theo quy ước đặt tên | :material-check: | Luôn chuyển đổi `snake_case` → `camelCase` lúc build |
| Đọc dòng theo vị trí cột | :material-check: | Áp dụng khi parser phân tích được danh sách cột trong câu SELECT |
| Fallback đọc theo tên cột | :material-check: | Dùng cho `SELECT *`,...; index cột chỉ được resolve một lần từ `ResultSetMetaData` |
| Kết quả kiểu vô hướng (scalar) | :material-check: | Đọc trực tiếp `long`, `String`,... từ cột 1 |
| Phương thức trả về `List<T>` | :material-check: | Đọc danh sách dòng vào List |
| Phương thức trả về `Stream<T>` | :material-check: | Caller có trách nhiệm đóng stream. [Chi tiết](../usage/streaming.md) |
| `<resultMap>` | :material-alert: | Chỉ ánh xạ tường minh các cột được khai báo, không auto-mapping |
| `<association>` / `<collection>` | :material-alert: | Hỗ trợ tối đa **một** cấp lồng nhau qua phép join, ResultSet bắt buộc phải sắp xếp theo khoá của bảng cha |
| Lồng `select=` trong result map | :material-close: | Đây chính là lỗi N+1 truy vấn. Cần viết tường minh bằng câu lệnh join |
| `<discriminator>` | :material-close: | Khiến kiểu class kết quả phụ thuộc vào giá trị cột lúc runtime |
| Constructor mapping (`<constructor>`) | :material-close: | Class kết quả được khởi tạo bằng constructor không tham số và các setter |
| Các thuộc tính `extends`, `columnPrefix`, `autoMapping` của `resultMap` | :material-close: | Khai báo tường minh tất cả các ánh xạ cần thiết |
| Lazy loading | :material-close: | Đòi hỏi phải bọc proxy cho từng đối tượng kết quả |
| Type alias | :material-close: | Dùng tên class đầy đủ (FQN) |

## Kiểu dữ liệu

| | | Ghi chú |
|---|---|---|
| Primitive và wrapper | :material-check: | Wrapper đi qua `JdbcCodec` để xử lý null an toàn |
| `String`, `BigDecimal`, `BigInteger`, `byte[]` | :material-check: | Đọc/ghi trực tiếp qua JDBC |
| `java.sql.Date` / `Time` / `Timestamp` | :material-check: | Hỗ trợ kiểu thời gian JDBC chuẩn |
| `Instant`, `LocalDate`, `LocalTime`, `LocalDateTime` | :material-check: | Hỗ trợ API `java.time` chuẩn Java 8+ |
| Enum (theo `name()`) | :material-check: | Thuộc kiểu giá trị đóng, hợp lệ khi dùng với `${}` |
| `@Column` | :material-check: | Đặt tên cột tương ứng trên field, setter hoặc getter. [Chi tiết](annotations.md#column) |
| TypeHandler tuỳ biến với `@Handler` | :material-check: | Khai báo trên thuộc tính, tham số hoặc trong mapper XML. [Chi tiết](../usage/types.md#custom-type-handlers) |
| `<typeHandlers>`, một handler cho mỗi kiểu Java | :material-check: | Khai báo qua cặp `-Alarkbatis.typeHandlers` và được resolve trong quá trình `javac`. [Chi tiết](configuration.md#type-handlers-for-a-whole-build) |
| Tự động quét TypeHandler (`<package>`, `@MappedTypes`) | :material-close: | Không quét classpath lúc chạy. Danh sách handler được khai báo tường minh lúc build |

## Session, transaction và thực thi

| | | Ghi chú |
|---|---|---|
| Scope `LarkBatisTx`, lồng nhau, cơ chế vote-to-commit | :material-check: | [Chi tiết](../usage/transactions.md) |
| `@Transactional` của Spring | :material-check: | Tích hợp qua `DataSourceUtils` |
| Dịch mã lỗi ngoại lệ Spring | :material-check: | Mặc định sử dụng `SQLExceptionSubclassTranslator` |
| Spring Boot auto-configuration | :material-check: | Tương thích cả Spring Boot 3 lẫn Spring Boot 4 trong cùng một jar |
| Sinh class `@Configuration` cho Spring | :material-check: | Đặt thuộc tính `proxyBeanMethods = false` |
| Batch insert | :material-check: | Định nghĩa qua chữ ký phương thức (tham số `List<T>`), không cần chuyển chế độ executor |
| Chèn nhiều dòng qua `VALUES` với `<foreach>` | :material-check: | Sinh câu SQL đa dòng tối ưu |
| Lối thoát thủ công (`query`, `queryOne`, `queryStream`, `update`) | :material-check: | Nhận `SqlFragment`, không bao giờ nhận chuỗi `String` tuỳ tiện |
| Chế độ `ExecutorType.BATCH` / `REUSE` | :material-close: | Không có lớp executor trung gian lúc runtime |
| Plugin / interceptor | :material-close: | 4 đối tượng mà MyBatis chặn bắt đã được thay thế hoàn toàn bằng thân phương thức sinh sẵn, không dùng JDK proxy. [Giải pháp thay thế plugin](mybatis-differences.md#what-replaces-a-plugin) |
| Cache cấp 2 (`<cache>`, `<cache-ref>`) | :material-close: | Nên đặt cache ở tầng service phía trên mapper, nơi dễ kiểm soát việc vô hiệu hoá cache |
| Cache cấp 1 | :material-close: | Không có đối tượng session lưu trạng thái để giữ cache |
| Gọi `addMapper()` lúc runtime | :material-close: | Danh sách mapper được chốt cố định ngay khi biên dịch |
| Nhiều `DataSource` trên cùng một mapper | :material-alert: | Tạm hoãn. Khai báo một session riêng cho từng `DataSource` và tự viết các phương thức `@Bean` |
| Ghi log SQL (`log-sql`) | :material-close: | Việc ghi log SQL thuộc trách nhiệm của driver hoặc connection pool: datasource-proxy, p6spy |

## Build và đóng gói

| | | Ghi chú |
|---|---|---|
| Annotation processor (javac) | :material-check: | Chỉ hỗ trợ `javac`; không hỗ trợ ECJ |
| Gradle plugin | :material-check: | [Chi tiết](../getting-started/build-plugins.md) |
| Maven plugin | :material-check: | Cần cấu hình `<extensions>true</extensions>` |
| JPMS module đặt tên | :material-check: | Cả 5 artifact phát hành đều có `module-info.java` chuẩn |
| Tương thích với Lombok | :material-check: | Khai báo processor của LarkBatis chạy *sau* Lombok |
| Build tăng dần (incremental build) | :material-alert: | Aggregating processor; cần biên dịch với cờ `-parameters` trên Gradle |
| Mapper chỉ dùng cho test | :material-close: | Chỉ hỗ trợ source set `compile` chính |
| GraalVM native image | :material-alert: | Đã sẵn sàng về mặt cấu trúc (không dùng reflection), nhưng **chưa qua kiểm thử thực tế trên build native** |
| Bộ quét mapper cũ | :material-check: | Công cụ CLI `larkbatis-scan`. [Chi tiết](migration.md) |

## Đọc tiếp

- [Khác biệt với MyBatis](mybatis-differences.md): danh sách chi tiết các tính năng bị loại bỏ hoặc thu hẹp kèm lý do kỹ thuật
- [Annotation](annotations.md): danh mục đầy đủ các annotation và thuộc tính
- [API runtime](runtime-api.md): các interface và class runtime công khai
- [Cấu hình](configuration.md): tuỳ chọn processor, thuộc tính và system property
