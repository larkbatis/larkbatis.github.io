# Hiệu năng & Benchmark

Số liệu so sánh được phân tách thành 3 nhóm rõ ràng: số liệu phân tích từ mã nguồn, số liệu đo lường thực nghiệm từ benchmark JMH, và các luận điểm thiết kế chưa có số liệu đo thực tế.

## So sánh cấu trúc mã nguồn

| Chỉ số kỹ thuật | MyBatis 3.5.19 | LarkBatis | Cơ sở so sánh |
|---|---|---|---|
| Số dòng code trên runtime classpath | 40.017 dòng | ~1.500 dòng | Đếm trong `src/main/java/org/apache/ibatis` (393 files) |
| Runtime dependencies | OGNL 3.4.11, Javassist 3.32 | 0 (chỉ JDBC) | Khai báo compile-time trong POM của MyBatis |
| Reflection call trên hot path | 4 giai đoạn | 0 | `createCacheKey`, `getBoundSql`, `setParameters`, `handleResultSets` |
| Thao tác reflection trên mỗi dòng kết quả | 1 × số lượng cột | 0 | `applyAutomaticMappings` gọi `metaObject.setValue()` cho từng cột |
| File `META-INF/native-image` phải viết tay | Bắt buộc nhiều file | 0 | MyBatis không có metadata sẵn cho GraalVM Native Image |
| Phát hiện lỗi sai kiểu tham số | Lúc runtime | Lúc compile (`javac`) | Mapper interface có implementation cụ thể với kiểu tĩnh |
| Điểm kiểm toán SQL thô | Rải rác từng file mapper | 1 lệnh `grep` duy nhất | Toàn bộ chuỗi SQL động tập trung qua `SqlFragment.unsafeRawSql()` |

## Số liệu đo lường thực tế (JMH Benchmark) { #measured-on-larkbatis-itself }

Toàn bộ số liệu dưới đây được đo bằng JMH 1.37:
- Cấu hình: 2 forks × 5 warmup iterations × 5 measurement iterations (1 giây/iteration).
- Đo cấp phát bộ nhớ bằng `-prof gc` (`gc.alloc.rate.norm`).
- Môi trường: OpenJDK 21 (Temurin), Apple M5 Pro, H2 Database 2.3.232.

### Đọc dữ liệu (Row Reading)

Thực thi `findAll()` trên toàn bộ bảng. `NarrowRow` gồm 4 cột, `WideRow` gồm 12 cột.

| Số dòng | Số cột | MyBatis | LarkBatis | Thời gian (Latency) | Cấp phát bộ nhớ (Heap Allocation) |
|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 1,48 µs | 0,36 µs | **−75%** | 6,6 KB → 1,8 KB (−73%) |
| 1 | 12 | 3,29 µs | 0,43 µs | **−87%** | 10,7 KB → 1,9 KB (−83%) |
| 100 | 4 | 17,1 µs | 3,23 µs | **−81%** | 67,6 KB → 10,2 KB (−85%) |
| 100 | 12 | 39,4 µs | 5,78 µs | **−85%** | 107 KB → 19,1 KB (−82%) |
| 10.000 | 4 | 1,53 ms | 0,29 ms | **−81%** | 6,77 MB → 1,05 MB (−84%) |
| 10.000 | 12 | 3,38 ms | 0,54 ms | **−84%** | 10,2 MB → 1,88 MB (−82%) |

Quy mô 10.000 dòng × 12 cột: **338 ns → 54 ns/dòng** và **1.018 B → 188 B/dòng**.

### Truy vấn đơn dòng qua kết nối mạng (TCP Loopback)

Thực thi `findById(7)`: 1 dòng, 4 cột.

| Hình thức kết nối | MyBatis | LarkBatis | Thời gian | Cấp phát bộ nhớ |
|---|---:|---:|---:|---:|
| In-process (Embedded) | 1,45 µs | 0,36 µs | −75% | 6,6 KB → 1,6 KB (−75%) |
| TCP Socket (Loopback) | 94,2 µs ± 1,7 | 89,2 µs ± 1,0 | **−5%** | 8,9 KB → 4,0 KB (−55%) |

Khi có độ trễ mạng và socket I/O tham gia, mức chênh lệch thời gian ở tầng mapper giảm xuống còn khoảng 5%. Tuy nhiên, mức giảm cấp phát bộ nhớ (−55%) vẫn giữ nguyên, giúp giảm tải đáng kể cho Garbage Collector (GC).

### Ghép chuỗi Dynamic SQL

Đo 3 nhánh `<if>` trong thẻ `<where>` (cố định trả về đúng 1 dòng để cô lập chi phí đọc dữ liệu):

| Số nhánh `<if>` kích hoạt | MyBatis | LarkBatis | Thời gian | Cấp phát bộ nhớ |
|---|---:|---:|---:|---:|
| 0 nhánh | 2,15 µs | 0,41 µs | **−81%** | 10,4 KB → 2,1 KB (−79%) |
| 1 nhánh | 3,60 µs | 1,48 µs | **−59%** | 15,9 KB → 6,9 KB (−56%) |
| 3 nhánh | 4,86 µs | 2,14 µs | **−56%** | 18,4 KB → 7,8 KB (−57%) |

Khi không có nhánh nào hoạt động, LarkBatis sử dụng chuỗi SQL hằng số sinh sẵn (cải thiện 81%). Khi có nhiều nhánh điều kiện, cả hai bên đều phải nối chuỗi qua `StringBuilder`, mức cải thiện đạt khoảng 56%.

### Thời gian khởi động (Cold Startup)

Đo trên Cold JVM (1 shot/fork, 10 forks) với 4 mapper interface (51 statements) và 1 truy vấn đầu tiên:

| Chỉ số | MyBatis | LarkBatis |
|---|---:|---:|
| Thời gian khởi động đến dòng đầu tiên | 61,8 ms ± 3,7 | **6,3 ms ± 0,8** (**−90%**) |
| Bộ nhớ cấp phát | 27,0 MB | 15,8 MB |

LarkBatis loại bỏ hoàn toàn chi phí khởi động 55 ms của MyBatis dành cho việc parse XML, khởi tạo `Reflector`, đăng ký type handlers và xây dựng `MappedStatement`.

### Ảnh hưởng của phiên bản JDK

JEP 416 (từ Java 18) tối ưu hóa core reflection bằng method handle, giúp MyBatis chạy nhanh hơn trên JDK mới:

| Kịch bản benchmark | JDK 17 | JDK 21 | Mức thay đổi |
|---|---:|---:|---:|
| MyBatis, 10.000 dòng × 4 cột | 2,13 ms | 1,53 ms | **−28%** |
| MyBatis, 10.000 dòng × 12 cột | 3,95 ms | 3,38 ms | **−14%** |
| LarkBatis, 10.000 dòng × 4 cột | 0,30 ms | 0,29 ms | −4% |
| LarkBatis, 10.000 dòng × 12 cột | 0,58 ms | 0,54 ms | −7% |

Do LarkBatis sinh lệnh gọi trực tiếp không dùng reflection, hiệu năng của LarkBatis độc lập với cải tiến JEP 416. Khoảng cách hiệu năng giữa hai bên là **7,1× trên JDK 17** và **5,3× trên JDK 21**.

## Ba kết luận kỹ thuật cốt lõi

1. **Đọc dữ liệu mang lại cải thiện lớn hơn ghép chuỗi SQL**: Tối ưu đọc `ResultSet` giúp giảm 84% thời gian xử lý CPU, trong khi tối ưu ghép chuỗi dynamic SQL giảm 56%.
2. **Escape Analysis không thể loại bỏ heap allocation của MyBatis**: Chuỗi gọi sâu `setValue → BeanWrapper → Invoker` ngăn JIT Compiler thực hiện scalar replacement cho `PropertyTokenizer` và `Object[]`.
3. **Hiệu quả tỷ lệ thuận với số lượng dòng kết quả**: LarkBatis mang lại lợi thế tối đa cho các tác vụ báo cáo, export dữ liệu lớn, xử lý batch và danh sách nhiều dòng. Với các truy vấn tìm kiếm 1 bản ghi đơn lẻ qua mạng, độ trễ phụ thuộc chủ yếu vào network I/O.

