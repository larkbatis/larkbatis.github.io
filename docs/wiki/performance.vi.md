# Hiệu năng

Các số liệu được phân chia thành ba nhóm rõ ràng: số liệu đọc trực tiếp từ mã nguồn (chắc chắn đúng), số liệu đo lường thực nghiệm từ benchmark, và các nhận định mang tính luận điểm chưa có số liệu đo thực tế.

## Số liệu chắc chắn từ mã nguồn

| Chỉ số | MyBatis | LarkBatis | Cơ sở xác định |
|---|---|---|---|
| Số dòng code trên classpath runtime | 40.017 dòng | ~1.500 dòng | Đếm trực tiếp trong `src/main/java/org/apache/ibatis` (393 tệp). Con số của LarkBatis là mục tiêu thiết kế |
| Thư viện phụ thuộc lúc runtime | ognl 3.4.11, javassist 3.32 | Không có gì ngoài JDBC | Cả hai đều khai báo `compile` + `optional` trong POM của MyBatis: tuy là tuỳ chọn nhưng bắt buộc phải có khi dùng SQL động hoặc lazy loading |
| Điểm gọi reflection trên đường dẫn truy vấn nóng | 4 nhóm | 0 | `createCacheKey`, `getBoundSql` (OGNL), `setParameters`, `handleResultSets` |
| Thao tác reflection trên mỗi dòng dữ liệu | 1 × số lượng cột | 0 | `applyAutomaticMappings` gọi `metaObject.setValue(property, value)` cho từng cột, qua chuỗi `BeanWrapper` → `MethodInvoker.invoke` |
| Tệp `META-INF/native-image` phải viết tay | Nhiều tệp | 0 | mybatis-3 không cung cấp reachability metadata; issue hỗ trợ GraalVM của MyBatis đã mở từ năm 2019 |
| Bắt lỗi sai kiểu tham số | Lúc runtime | Lúc compile | Mapper là interface thông thường với implementation cụ thể, javac kiểm tra kiểu tĩnh |
| Kiểm toán các điểm chèn SQL thô | Đọc từng mapper | Một lệnh `grep` | Mọi chuỗi SQL tuỳ ý (cả `${}` lẫn lối thoát thủ công) đều bắt buộc đi qua `SqlFragment.unsafeRawSql`. MyBatis không có điểm quy tụ tương đương |

## Đo lường trên bản POC sinh code

Số liệu thu được từ bản thử nghiệm sinh code lúc build (proof of concept) cho MyBatis. Lấy kết quả tốt nhất trong ba lần chạy, thực hiện phương thức `findAll` trên 10.000 dòng dữ liệu.

| Chỉ số | MyBatis gốc | AOT hoàn toàn | Mức chênh lệch (Δ) |
|---|---|---|---|
| Bộ nhớ cấp phát trên mỗi dòng | ≈ 1,0 KB | 129 B | **−87%** |
| Độ trễ trên mỗi dòng | 0,30 µs | 0,08 µs | **−73%** |
| Truy vấn 10.000 dòng · Thời gian | ≈ 3,0 ms | 0,8 ms | **−72%** |
| Truy vấn 10.000 dòng · Cấp phát bộ nhớ | ≈ 10 MB | 1,23 MB | **−88%** |
| Tìm kiếm động · Thời gian | 15–20 µs | 9,5 µs | **−45%** |
| Tìm kiếm động · Cấp phát bộ nhớ | 28 KB | 12 KB | **−57%** |

Mức 129 B trên mỗi dòng còn lại gần như toàn bộ là dữ liệu thực (payload): bản thân đối tượng bean cùng các chuỗi `String` do driver trả về. Đây là mức tiêu thụ sàn tối thiểu, không phải con số trung gian.

### Ba kết luận kỹ thuật quan trọng

**1 · Luồng đọc dòng dữ liệu cải thiện vượt trội hơn luồng dựng SQL động** (−73%/−87% so với −45%/−57%). Nhiều suy đoán ban đầu cho rằng JIT compiler có thể inline `MethodInvoker` đủ tốt để reflection trở nên rẻ và phần tiết kiệm lớn nhất phải đến từ việc ghép chuỗi SQL. Thực tế đo lường cho thấy JIT không làm được điều đó, và tối ưu đọc dòng mới là nơi mang lại bước nhảy vọt.

**2 · Phân tích thoát (Escape analysis) không dọn dẹp được rác sinh ra theo từng cột.** Nếu làm được, MyBatis gốc đã không cấp phát tới ~1,0 KB rác trên mỗi dòng. Chuỗi gọi `setValue` → `BeanWrapper` → `Invoker` quá sâu khiến JIT không thể thay thế vô hướng (scalar replacement) cho `PropertyTokenizer` và mảng `Object[]`.

**3 · Lợi ích tỷ lệ thuận với số lượng dòng trả về.** Mức cải thiện 3,0 ms → 0,8 ms trên 10.000 dòng là rất rõ rệt. Tuy nhiên, trên câu lệnh `findById` chỉ trả về một dòng đơn lẻ, mức tiết kiệm khoảng 0,2 µs so với độ trễ mạng khoảng 1 ms là không đáng kể.

!!! quote "Nhận định khách quan"

    **LarkBatis là khoản đầu tư hiệu quả cho các truy vấn báo cáo, xuất dữ liệu, xử lý hàng loạt (batch) và danh sách nhiều dòng.
    Hệ thống hầu như không tạo ra sự khác biệt về độ trễ đối với các truy vấn tìm kiếm một bản ghi đơn lẻ.**

    Một đề xuất chuyển đổi bỏ qua thực tế này sẽ mất đi tính thuyết phục ngay khi người khác tự chạy benchmark kiểm chứng.

### Bốn yếu tố bắt buộc phải công bố kèm số liệu benchmark

- **Số lượng kiểu bean khác nhau** được thực thi. Nếu chỉ chạy 1 kiểu bean, các điểm gọi là monomorphic và JIT đang ở trạng thái thuận lợi nhất cho MyBatis gốc; khoảng cách thực tế trên production sẽ còn rộng hơn.
- **Số lượng cột trên mỗi dòng**, vì cả lượng cấp phát bộ nhớ lẫn độ trễ đều tăng theo số cột.
- **Dùng JMH hay vòng lặp tự viết**, và cách thức đo bộ nhớ (JFR, `ThreadMXBean`, `-prof gc`).
- **Phiên bản JDK.** Kể từ JDK 18, `Method.invoke` nhanh hơn đáng kể nhờ JEP 416, do đó cùng một bộ test trên JDK 17 và JDK 21 sẽ cho hai kết quả khác nhau.

## Đo lường trên chính LarkBatis { #measured-on-larkbatis-itself }

Bộ test `larkbatis-benchmarks` chạy lại toàn bộ phép so sánh trên bản hiện thực chính thức thay vì bản POC. Tất cả số liệu dưới đây được đo bằng JMH 1.37, 2 fork × 5 lần warmup × 5 lần đo (mỗi lần 1 giây), lượng cấp phát đo qua `-prof gc` (`gc.alloc.rate.norm`), so sánh giữa MyBatis 3.5.19 và H2 2.3.232 trên máy Apple M5 Pro.

!!! info "Tất cả số liệu đo trên Temurin 21"

    Luồng reflection của MyBatis nhanh hơn rõ rệt sau JEP 416. Trích dẫn số liệu JDK 17 mà không nêu rõ sẽ phóng đại lợi thế của LarkBatis thêm khoảng 20%. Xem chi tiết tại [Mục so sánh phiên bản JDK](#jdk-version-matters).

### Đọc dòng dữ liệu

Thực thi `findAll()` trên toàn bộ bảng. `NarrowRow` gồm 4 cột, `WideRow` gồm 12 cột.

| Số dòng | Số cột | MyBatis | LarkBatis | Thời gian | Cấp phát bộ nhớ |
|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 1,48 µs | 0,36 µs | **−75%** | 6,6 KB → 1,8 KB (−73%) |
| 1 | 12 | 3,29 µs | 0,43 µs | **−87%** | 10,7 KB → 1,9 KB (−83%) |
| 100 | 4 | 17,1 µs | 3,23 µs | **−81%** | 67,6 KB → 10,2 KB (−85%) |
| 100 | 12 | 39,4 µs | 5,78 µs | **−85%** | 107 KB → 19,1 KB (−82%) |
| 10.000 | 4 | 1,53 ms | 0,29 ms | **−81%** | 6,77 MB → 1,05 MB (−84%) |
| 10.000 | 12 | 3,38 ms | 0,54 ms | **−84%** | 10,2 MB → 1,88 MB (−82%) |

Tính trên mỗi dòng ở quy mô 10.000 dòng và 12 cột: **338 ns → 54 ns**, và **1.018 B → 188 B**.

Các số liệu từ bản POC hoàn toàn chính xác và có phần thận trọng: POC đo được −72%/−88%, còn ở đây đạt −84%/−82% khi chạy cùng một JDBC driver thực sự ở cả hai bên trên phiên bản JDK có lợi cho MyBatis.

Mức tiết kiệm tăng theo **số lượng cột**, không chỉ theo số dòng. Khi tăng từ 4 lên 12 cột, chi phí trên mỗi dòng của MyBatis tăng gần gấp đôi trong khi LarkBatis hầu như không biến động. MyBatis phải chi trả cho `PropertyTokenizer`, mảng `Object[]`, tra cứu map và gọi reflection cho từng cột; trong khi reader sinh sẵn chỉ thực hiện các lệnh `getX` và `putfield` trực tiếp.

### Truy vấn một dòng qua kết nối mạng thực tế

Thực thi `findById(7)`: 1 dòng, 4 cột.

| Phương thức truyền | MyBatis | LarkBatis | Thời gian | Cấp phát bộ nhớ |
|---|---:|---:|---:|---:|
| Cùng tiến trình (In-process) | 1,45 µs | 0,36 µs | −75% | 6,6 KB → 1,6 KB (−75%) |
| H2 qua loopback TCP | 94,2 µs ± 1,7 | 89,2 µs ± 1,0 | **−5%** | 8,9 KB → 4,0 KB (−55%) |

Khi có kết nối socket và giao thức mạng thực tế tham gia vào, mức chênh lệch thời gian ở tầng mapper chỉ còn khoảng 5%. Kết nối loopback TCP là hình thức truyền dữ liệu qua mạng rẻ nhất, vì vậy nếu database đặt ở máy chủ khác, mức chênh lệch về thời gian sẽ còn nhỏ hơn nữa. Tuy nhiên, mức tiết kiệm bộ nhớ (−55%) vẫn được giữ nguyên và giúp giảm đáng kể áp lực lên Garbage Collector (GC) khi tải cao.

### SQL động

Ba nhánh `<if>` nằm trong thẻ `<where>`. **Mọi trường hợp đều trả về đúng 1 dòng**, do câu lệnh ghim điều kiện `id = #{pinnedId}` và các điều kiện tuỳ chọn đều không làm giảm số dòng; nhờ đó chi phí đọc dòng là hằng số và chỉ có thời gian ghép chuỗi SQL thay đổi.

| Số nhánh được chọn | MyBatis | LarkBatis | Thời gian | Cấp phát bộ nhớ |
|---|---:|---:|---:|---:|
| Không có nhánh nào | 2,15 µs | 0,41 µs | **−81%** | 10,4 KB → 2,1 KB (−79%) |
| 1 nhánh | 3,60 µs | 1,48 µs | **−59%** | 15,9 KB → 6,9 KB (−56%) |
| Cả 3 nhánh | 4,86 µs | 2,14 µs | **−56%** | 18,4 KB → 7,8 KB (−57%) |

Khi không có nhánh nào được chọn, LarkBatis không cần ghép chuỗi vì câu lệnh là một chuỗi hằng số `String`, đem lại mức cải thiện 81%. Khi các nhánh bắt đầu hoạt động, LarkBatis phải thực hiện thao tác với `StringBuilder`, và mức chênh lệch ổn định ở khoảng 56%: đây là chi phí vận hành thực tế của SQL động khi cả hai bên đều phải dựng chuỗi.

Điều này củng cố kết luận từ bản POC: đo lường thực tế đạt **−56% cho SQL động so với −84% cho luồng đọc dòng**. Việc ghép chuỗi là thao tác xử lý chuỗi mà cả hai bên đều phải làm; chi phí thông dịch của MyBatis ở phần này nhỏ hơn nhiều so với chi phí reflection trên từng cột trong luồng đọc dòng mà LarkBatis đã loại bỏ.

### Thời gian khởi động ứng dụng (Cold Startup)

Đo trên Cold JVM, 1 shot cho mỗi fork, chạy 10 fork. Cả hai bên cùng khởi tạo ứng dụng tương đương: 4 mapper interface (trong đó một interface chứa 50 statement), 1 mapper XML, và thực hiện 1 truy vấn thực tế ở cuối. Đo trên JDK 17 để có sai số nhỏ nhất.

| Chỉ số | MyBatis | LarkBatis |
|---|---:|---:|
| Khởi động nguội đến dòng đầu tiên | 61,8 ms ± 3,7 | **6,3 ms ± 0.8** |
| Cấp phát bộ nhớ | 27,0 MB | 15,8 MB |

**Cải thiện −90%.** Khoảng thời gian 55 ms của MyBatis dành cho việc phân tích XML, khởi tạo `Reflector`, đăng ký type handler, nạp class OGNL/XPath và dựng đối tượng `MappedStatement` cho 51 câu lệnh. LarkBatis không phải làm bất kỳ việc nào trong số đó lúc chạy vì mọi thứ đã hoàn thành trong quá trình `javac`.

Trong ứng dụng Spring Boot thực tế, con số này nằm dưới thời gian khởi tạo context và làm ấm connection pool. Tuy nhiên, mức giảm 55 ms mang ý nghĩa lớn trong môi trường serverless hoặc native image.

### Hành vi Megamorphic: Lợi thế gần như không đổi

Thực hiện 50 lần đọc 1 dòng từ bảng 6 cột. Trường hợp `mono` đọc 1 result class 50 lần; trường hợp `mega` đọc 50 result class khác nhau (mỗi class 1 lần).

| Kịch bản | MyBatis | LarkBatis | Lợi thế của LarkBatis |
|---|---|---:|---:|
| Monomorphic (1 kiểu bean) | 103,5 µs | 22,8 µs | 4,54× |
| Megamorphic (50 kiểu bean) | 123,4 µs | 26,2 µs | 4,71× |
| Mức suy giảm khi megamorphic | **+19,3%** | **+15,0%** | |

MyBatis chậm hơn 19% khi xử lý 50 kiểu bean so với 1 kiểu, nhưng LarkBatis cũng tăng 15% cho cùng thay đổi, khiến khoảng cách lợi thế chỉ nới rộng nhẹ từ 4,54× lên 4,71×.

Lượng cấp phát bộ nhớ thể hiện rõ bản chất: 394 KB so với 398 KB ở MyBatis, 100,4 KB so với 100,8 KB ở LarkBatis. Chi phí megamorphic nằm ở việc JIT không thể inline tối đa, không phát sinh thêm công việc; và lượng cấp phát bộ nhớ theo từng cột của MyBatis vẫn giữ nguyên trong cả hai trường hợp.

!!! warning "Không nên lập luận rằng 'càng nhiều class thì khoảng cách càng lớn'"

    Một codebase có hàng trăm result class không làm nới rộng thêm khoảng cách hiệu năng giữa hai bên. Số liệu chứng minh lợi thế của LarkBatis đã rất lớn ngay từ một kiểu bean đơn lẻ và duy trì ổn định ở mọi quy mô.

### Ảnh hưởng của phiên bản JDK { #jdk-version-matters }

Bộ test được chạy trên hai phiên bản JDK trước và sau JEP 416 (JEP 416 chuyển cơ chế core reflection sang sử dụng method handle). LarkBatis yêu cầu tối thiểu Java 17, và JEP 416 xuất hiện từ Java 18.

| Kịch bản kiểm thử | JDK 17 | JDK 21 | Mức thay đổi |
|---|---:|---:|---:|
| MyBatis, 10.000 dòng × 4 cột | 2,13 ms | 1,53 ms | **−28%** |
| MyBatis, 10.000 dòng × 12 cột | 3,95 ms | 3,38 ms | **−14%** |
| MyBatis, 100 dòng × 4 cột | 22,8 µs | 17,1 µs | **−25%** |
| LarkBatis, 10.000 dòng × 4 cột | 0,30 ms | 0,29 ms | −4% |
| LarkBatis, 10.000 dòng × 12 cột | 0,58 ms | 0,54 ms | −7% |
| LarkBatis, 100 dòng × 4 cột | 3,56 µs | 3,23 µs | −9% |

**MyBatis nhanh hơn rõ rệt trên JDK mới; trong khi LarkBatis hầu như không thay đổi.** Điều này hoàn toàn khớp với lý thuyết: luồng đọc từng cột của MyBatis kết thúc bằng lệnh `Method.invoke` (được Java 21 tối ưu), trong khi code sinh sẵn của LarkBatis không hề dùng reflection nên không phụ thuộc vào cải tiến này.

Do đó, khoảng cách hiệu năng thu hẹp lại trên JDK mới hơn: **7,1× trên JDK 17, và 5,3× trên JDK 21** cho cùng khối lượng công việc 10.000 dòng × 4 cột. Luôn cần nêu rõ phiên bản JDK khi trích dẫn số liệu benchmark.

### Phương pháp đo và lý do lựa chọn

- **Dùng pinned session ở cả hai bên.** `SqlSession` của MyBatis giữ một connection trong suốt vòng đời; `JdbcLarkBatisSession` mặc định lấy và đóng connection cho mỗi statement. Nếu so sánh trực tiếp thì chỉ một bên phải gánh chi phí kết nối H2. Trường hợp benchmark khởi động là ngoại lệ duy nhất đo cả chi phí kết nối.
- **Hạ cache cấp 1 của MyBatis xuống phạm vi `STATEMENT`.** Mặc định là `SESSION`, và mỗi benchmark giữ một session mở, vì vậy lần gọi `findById(1)` thứ hai sẽ trả về đối tượng trong cache mà không chạm vào JDBC. Thay đổi cấu hình này là yếu tố phân biệt giữa việc đo lường truy vấn thực tế với việc tra cứu một `HashMap`. Cache cấp 2 được tắt hoàn toàn vì LarkBatis không hỗ trợ.
- **Sử dụng JDBC driver thực sự ở cả hai bên.** Không dùng `ResultSet` giả lập để cô lập tầng mapper; chi phí của H2 nằm trong cả hai số liệu, giúp khoảng cách chênh lệch đo được là *cận dưới* thực tế.
- **Chạy H2 qua TCP server riêng** cho kịch bản đo độ trễ mạng: kiểm thử qua socket và giao thức mạng thực tế trên loopback.
- **Thử nghiệm megamorphic sinh tự động 50 result class và 200 điểm gọi từ build script.** Nếu dùng reflection để gọi sẽ vô tình đưa chính chi phí cần đo vào cả hai bên.
- **Tuyệt đối không chạy tác vụ build nào khác khi JMH đang chạy.**

## Các luận điểm chưa có số liệu đo lường thực tế

| Luận điểm | Lý do tin tưởng | Điểm cần thận trọng |
|---|---|---|
| Native image hoạt động ngay mà không cần cấu hình | Không có `Proxy`, không có `Class.forName`, không có `setAccessible` trong runtime hay code sinh ra | Chưa chạy bản build native image thực tế nào |
| Hoạt động ổn định khi xử lý đồng thời (concurrency) | Code sinh ra không chứa trạng thái có thể biến đổi (mutable state) dùng chung; session là điểm tiếp giáp duy nhất | Mọi benchmark ở đây đều là đơn luồng. Cạnh tranh tài nguyên, hành vi pool và áp lực GC khi chạy song song chưa được đo lường |
| Thời gian build duy trì ở mức chấp nhận được | Quá trình sinh code diễn ra theo từng mapper và có tính tăng dần | Chưa đo đạc trên codebase quy mô hàng nghìn mapper |

## Tương thích GraalVM Native Image { #native-image }

!!! warning "Đã sẵn sàng về cấu trúc, chưa kiểm chứng thực tế"

    LarkBatis không chứa bất kỳ lệnh gọi `Proxy.newProxyInstance`, `Class.forName` hay `setAccessible` nào trong runtime lẫn trong code sinh ra. Do đó không cần viết reachability metadata cho tầng mapper. Đây là đặc tính có thể kiểm chứng trực tiếp bằng cách đọc mã nguồn.

    Tuy nhiên, **chưa có bản build native image thực tế nào được thực hiện**. Dự án không công bố đây là kết quả hoàn chỉnh cho đến khi có thử nghiệm thực tế.

JDBC driver của ứng dụng có thể vẫn cần metadata riêng của chính nó. Đó là yêu cầu của driver, không thuộc tầng mapper.

## Lợi ích ít được nhắc tới nhưng giá trị nhất

**Khả năng đọc trực tiếp câu SQL sẽ chạy ngay trong IDE.** Có thể mở tệp `UserMapper$$Impl.java`, đặt breakpoint bên trong nhánh `<if>`, và theo dõi stack trace trỏ chính xác đến dòng code Java cụ thể thay vì chuỗi gọi trừu tượng `MapperProxy.invoke → MapperMethod.execute → …`.

Đối với một dự án có 300 phương thức mapper, khả năng debug minh bạch này mang lại giá trị thực tế hàng ngày lớn hơn nhiều so với việc tiết kiệm vài micro giây cho mỗi truy vấn.
