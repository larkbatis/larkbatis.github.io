# Lộ trình phát triển

Các milestone được sắp xếp theo một tiêu chí duy nhất: **rủi ro ngữ nghĩa thấp nhất làm trước, mang lại lợi ích chứng minh được sớm nhất.**

## Trạng thái hiện tại

| Milestone | Phạm vi công việc | Trạng thái |
|---|---|---|
| **M0** | Nền tảng benchmark: thử nghiệm `ObjectWrapperFactory` trực tiếp trên mybatis-3 để kiểm chứng giả thuyết cốt lõi trước khi viết bất kỳ dòng code LarkBatis nào | :material-check: |
| **M1** | Nhân runtime; processor cho annotation với SQL tĩnh và `#{}`; class `$$Impl` + row reader; `useGeneratedKeys`; `SqlFragment` | :material-check: |
| **Milestone 2** | Gradle plugin; mapper XML; các thẻ động; ngữ pháp biểu thức. *Hạng mục có rủi ro ngữ nghĩa cao nhất*, được bảo chứng qua harness kiểm thử vi sai với MyBatis | :material-check: |
| **M3** | Thẻ `<foreach>`, kỹ thuật pad luỹ thừa 2 (`@PadPow2`), batch insert | :material-check: |
| **M4** | Thẻ `<resultMap>` lồng nhau một cấp qua join, phương thức trả về `Stream`, transaction, tích hợp Spring | :material-check: |
| **M5** | Bộ benchmark mở rộng, công cụ quét mapper cũ, tinh chỉnh tài liệu thiết kế | :material-check: (ngoại trừ smoke test trên native image) |

Các tính năng đi kèm đã hoàn thành: Maven plugin, mô tả JPMS cho toàn bộ 5 artifact phát hành, và tương thích đồng thời cả Spring Boot 3 lẫn Boot 4 trong cùng một jar.

## M0: Thử nghiệm kiểm chứng giả thuyết sớm nhất

Cột mốc này thể hiện rõ phương pháp luận của dự án. MyBatis có sẵn SPI `ObjectWrapperFactory`, cho phép sinh một `ObjectWrapper` cho từng result class rồi gắn vào `Configuration` **mà không cần sửa đổi mã nguồn MyBatis**. Nếu việc loại bỏ `Reflector` và `MetaObject` trên luồng đọc dòng giúp cải thiện hiệu năng rõ rệt, giả thuyết cốt lõi của LarkBatis coi như được chứng minh trên codebase thực tế chỉ với vài trăm dòng code thử nghiệm. Nếu không hiệu quả, dự án sẽ tiết kiệm được nhiều tháng làm việc vô ích.

Kết quả thử nghiệm cho thấy hiệu năng tăng vượt bậc. Xem [Hiệu năng](../wiki/performance.md).

## M5: Những hạng mục còn lại

| Hạng mục | Trạng thái |
|---|---|
| `larkbatis-benchmarks` (JMH; pinned session; cache phạm vi STATEMENT; H2 qua TCP; so sánh JDK 17 vs 21; thử nghiệm megamorphic với 50 bean) | Đã hoàn thành. [Kết quả](../wiki/performance.md#measured-on-larkbatis-itself) |
| `larkbatis-scanner` (`larkbatis-scan`) | Đã hoàn thành. [Chi tiết](migration.md) |
| **Smoke test trên GraalVM Native Image** | **Chưa chạy.** Máy phát triển hiện tại chưa cài đặt GraalVM |
| Chạy thử nghiệm một service đã chuyển đổi trong môi trường thực tế 1 tuần | Chưa thực hiện. Đợt chuyển đổi thử nghiệm đã vượt qua 100% test suite trên bản sao |
| Cập nhật tài liệu thiết kế dựa trên kết quả benchmark và bài học chuyển đổi thực tế | Đã hoàn thành |

!!! warning "Tuyên bố về Native Image chưa được kiểm chứng qua build thực tế"

    Không sử dụng reflection là tuyên bố định tính mạnh mẽ nhất của dự án, và mang tính cấu trúc: không có `Proxy`, không có `Class.forName`, không có `setAccessible`, điều này bạn có thể tự kiểm chứng bằng cách đọc mã nguồn. Tuy nhiên, **chưa có bản build native image thực tế nào được thực hiện**. Dự án không công bố đây là kết quả hoàn chỉnh cho đến khi có kiểm thử thực tế.

## Chủ động tạm hoãn

| Tính năng | Lý do |
|---|---|
| **Nhiều `DataSource`** (`@LarkBatisDataSource`) | Chưa thiết kế khi chưa có use-case thực tế từ dự án production. Hiện tại: tự khởi tạo một `SpringLarkBatisSession` cho từng `DataSource` và viết phương thức `@Bean` mapper thủ công |
| **Mapper chỉ dùng cho test** | Cả hai build plugin hiện tại chỉ gắn vào source set `compile` chính |
| **`log-sql`** | Đòi hỏi mọi method sinh ra phải có nhánh kiểm tra log. Thay vào đó hãy dùng log ở tầng driver hoặc pool |
| **Functional test cho Maven plugin** | Đang chờ các artifact có thể publish vào Maven local repository, tương tự trạng thái TestKit của Gradle plugin |

## Những tính năng sẽ không bao giờ thêm vào

Những mục dưới đây không nằm trong backlog. Mỗi mục đều vi phạm [ranh giới phân tách giữa shape và value](../wiki/shape-vs-value.md), và việc hỗ trợ chúng đồng nghĩa với việc phải mang trở lại một runtime có khả năng kiểm tra kiểu động.

OGNL đầy đủ · `<bind>` · Họ annotation `@SelectProvider` · Lazy loading · Plugin và interceptor · Tham số kiểu `Object`/`Map` · `<discriminator>` · Lồng select trong `<collection>` · Cache cấp 2 · Gọi `addMapper()` lúc runtime · `RowBounds` · Tự động quét TypeHandler qua classpath · `ExecutorType`.

Mỗi tính năng này đều đã có lỗi biên dịch rõ ràng kèm giải pháp thay thế tương ứng. Xem [Khác biệt với MyBatis](mybatis-differences.md).

## Chính sách phiên bản

Tài liệu được đánh phiên bản song song với các bản phát hành. Trình chọn phiên bản trên thanh điều hướng cho phép chuyển đổi giữa các bản tài liệu, và `latest` luôn trỏ tới bản phát hành mới nhất.
