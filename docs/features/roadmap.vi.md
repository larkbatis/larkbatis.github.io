# Lộ trình phát triển (Roadmap)

Các cột mốc phát triển được sắp xếp theo nguyên tắc: **ưu tiên giải quyết rủi ro ngữ nghĩa cao nhất trước và chứng minh hiệu năng thực tế sớm nhất.**

## Tiến độ các cột mốc

| Cột mốc | Nội dung công việc | Trạng thái |
|---|---|---|
| **M0** | Benchmark POC: Kiểm chứng hiệu năng trực tiếp trên MyBatis bằng `ObjectWrapperFactory` trước khi viết code | :material-check: |
| **M1** | Runtime core; processor cho annotation; sinh code `Mapper$$Impl` và `RowReader`; `useGeneratedKeys`; `SqlFragment` | :material-check: |
| **M2** | Gradle plugin; mapper XML; dynamic tags (`<if>`, `<where>`, v.v.); bộ phân tích ngữ pháp biểu thức; differential test harness với MyBatis | :material-check: |
| **M3** | Thẻ `<foreach>`, tối ưu `@PadPow2`, JDBC batch insert | :material-check: |
| **M4** | Thẻ `<resultMap>` lồng 1 cấp qua join, trả về `Stream<T>`, transaction management, Spring Boot Starter | :material-check: |
| **M5** | Bộ benchmark JMH mở rộng, CLI tool `larkbatis-scan`, tài liệu kiến trúc | :material-check: (ngoại trừ kiểm thử native-image) |

Các tính năng bổ sung đã hoàn thành: Maven plugin, named JPMS modules cho 5 artifact, và tương thích đồng thời Spring Boot 3 và Spring Boot 4.

## M0: Kiểm chứng giả thuyết sớm

Cột mốc M0 chứng minh tính khả thi của giải pháp trước khi bắt tay vào phát triển toàn diện. Bằng cách cài đặt một `ObjectWrapperFactory` sinh code cho result class và gắn vào MyBatis `Configuration`, chúng tôi đo lường được mức cải thiện hiệu năng khi loại bỏ reflection ở khâu đọc dòng (`ResultSet`).

Kết quả đo lường ban đầu cho thấy mức giảm hơn 70% latency và 80% bộ nhớ cấp phát, khẳng định tính đúng đắn của kiến trúc sinh mã nguồn trước lúc build.

## M5: Các hạng mục đang hoàn thiện

| Hạng mục | Trạng thái |
|---|---|
| Bộ benchmark JMH `larkbatis-benchmarks` | Đã hoàn thành. Xem [Hiệu năng & Benchmark](../wiki/performance.md) |
| Công cụ quét mã nguồn `larkbatis-scan` | Đã hoàn thành. Xem [Migration](migration.md) |
| Kiểm thử GraalVM Native Image | **Đang lên kế hoạch.** Cấu trúc code đã sẵn sàng (không reflection), đang chờ thiết lập môi trường CI với GraalVM |
| Vận hành thử nghiệm trên môi trường production | Đã vượt qua 100% test suite trên service thực tế |

!!! warning "Lưu ý về GraalVM Native Image"

    LarkBatis không dùng reflection, không tạo JDK dynamic proxy, và không gọi `setAccessible()`. Về mặt lý thuyết, bạn không cần cấu hình reflection metadata. Tuy nhiên, bài test build native image thực tế vẫn đang trong quá trình thực hiện.

## Các tính năng chủ động trì hoãn

| Tính năng | Lý do |
|---|---|
| Hỗ trợ nhiều DataSource trên cùng mapper | Tạm hoãn để tránh làm phức tạp kiến trúc khi chưa có yêu cầu thực tế từ production |
| Mapper trong test scope | Hiện tại build plugin chỉ hỗ trợ source set `compileJava` chính |
| Cấu hình `log-sql` nội tại | Nên sử dụng logging proxy ở tầng Connection Pool hoặc DataSource (`datasource-proxy`, `p6spy`) |

## Các tính năng không nằm trong kế hoạch

Các tính năng sau sẽ không được thêm vào vì vi phạm nguyên tắc [Shape vs. Value](../wiki/shape-vs-value.md) và đòi hỏi phải mang lại runtime interpreter / reflection:

OGNL đầy đủ · `<bind>` · `@SelectProvider` · Lazy loading · Plugins/Interceptors · Tham số `Object`/`Map` không định kiểu · `<discriminator>` · N+1 `select` lồng nhau · Level-2 Cache trong ORM · `RowBounds` in-memory.

