# Chuyển đổi từ MyBatis

Lộ trình chuyển đổi mượt mà chính là mục tiêu cốt lõi của dự án, và là điểm khác biệt lớn nhất giữa LarkBatis với Micronaut Data hay jOOQ. Vì vậy, bộ công cụ hỗ trợ chuyển đổi được đầu tư kỹ lưỡng tương đương với bản thân bộ sinh code.

## Bắt đầu bằng việc quét mã nguồn

Công cụ `larkbatis-scan` quét trực tiếp codebase MyBatis hiện có và in ra chi phí chuyển đổi ước tính kèm số dòng và tên tệp cụ thể. Công cụ không biên dịch mã nguồn và không giải quyết dependency, vì vậy bạn có thể chạy ngay trên một service vừa checkout về mà chưa từng build, giúp trả lời nhanh câu hỏi "dự án này có phù hợp để chuyển đổi hay không".

Với dự án đã tích hợp Gradle plugin, task quét mã nguồn đã được đăng ký sẵn trên thư mục dự án:

```console
$ ./gradlew larkbatisScan
$ ./gradlew larkbatisScan --args="--summary --min=BLOCKER src/main"
```

Bộ scanner chạy trong một tiến trình riêng biệt với cấu hình tách rời, không ảnh hưởng đến cấu hình của ứng dụng. Để quét một dự án hoàn toàn mới chưa từng cài đặt LarkBatis, hãy build bản phân phối CLI:

```console
$ ./gradlew :larkbatis-scanner:installDist
$ ./build/install/larkbatis-scanner/bin/larkbatis-scan /path/to/legacy-service
```

```text
larkbatis-scan — what would it cost to move this codebase to LarkBatis

usage: larkbatis-scan [options] <path>...

  --summary            counts only, no per-line detail
  --min=LEVEL          detail level: BLOCKER, EDIT, REVIEW, INFO (default REVIEW)
  --limit=N            most findings listed per file (default 40)
  --out=FILE           also write the report to FILE
  --fail-on-blocker    exit 1 when anything is blocked on a dropped feature
```

Công cụ tuyệt đối không tự ý ghi đè mã nguồn của bạn. Bản báo cáo là kết quả bàn giao, và việc chỉnh sửa mã nguồn thuộc quyền quyết định của bạn.

### Sử dụng cùng frontend với trình biên dịch

Bộ scanner phụ thuộc vào `larkbatis-processor` và sử dụng **chính bộ kiểm tra ngữ pháp và bộ phân tích cú pháp XML** mà quá trình build thực tế sử dụng. Nhờ đó, báo cáo quét không bao giờ sai lệch so với những gì trình biên dịch chấp nhận. Vị trí dòng được xác định qua quét văn bản, vì không parser XML nào trả về toạ độ dòng chính xác cho một đoạn `${}` nằm giữa một khối text.

### 4 mức độ nghiêm trọng

Được sắp xếp theo mức độ cần con người đánh giá và đưa ra quyết định thiết kế:

| Mức độ | Ý nghĩa |
|---|---|
| **BLOCKER** | Không có tính năng tương đương trong LarkBatis (tính năng đã bị loại bỏ). Cần thay đổi thiết kế của mapper |
| **EDIT** | Cần viết lại theo cú pháp rõ ràng đã định hình. Công cụ có thể chỉ ra chính xác đoạn code cần sửa |
| **REVIEW** | Được hỗ trợ, nhưng cần lập trình viên xem xét và lựa chọn phương án xử lý |
| **INFO** | Biên dịch được ngay; thông tin hữu ích giúp nắm bắt trước khi triển khai |

### Đơn vị đánh giá là từng statement

Không phải theo tệp, và không phải theo từng phát hiện đơn lẻ. Việc một thẻ `<bind>` xuất hiện trong mapper có 90 statement không thể phủ nhận 89 statement còn lại, và con số "1.113 lỗi" là thứ không ai có thể xử lý ngay được. Một kết luận định lượng như *"N trên M statement biên dịch được ngay mà không cần sửa"* là cơ sở thuyết phục nhất để đưa ra đề xuất chuyển đổi.

Bản báo cáo cũng hiển thị **mức độ tập trung** của các vấn đề: số lượng tệp chứa lỗi và top 5 tệp chiếm nhiều lỗi nhất. Trong kho mapper mẫu của chính MyBatis, có tới 1.003 trên tổng số 1.006 lỗi ngữ pháp chỉ nằm trong đúng 3 tệp, và 1.000 lỗi trong số đó nằm ở một tệp fixture sinh tự động duy nhất. Nếu không có cột thống kê mức độ tập trung, bạn sẽ dễ lầm tưởng toàn bộ dự án gặp vấn đề nghiêm trọng.

## Các hạng mục scanner phát hiện

| Hạng mục phát hiện | Mức độ | Cách khắc phục |
|---|---|---|
| Chèn trực tiếp `${}` | EDIT | Khai báo tham số kiểu `SqlFragment`, kiểu tập giá trị đóng, hoặc `@OrderBy(allowed={...})`. Tại nơi gọi hàm, chuỗi `String` được bọc thành `SqlFragment.identifier(x)` |
| `${}` nằm trong danh sách SELECT | REVIEW | Statement này sẽ fallback về đọc theo tên cột. Cần xem xét có thể cố định danh sách cột hay không |
| Biểu thức `test=` ngoài ngữ pháp hỗ trợ | EDIT | Viết lại biểu thức hoặc đưa logic tính toán vào Java |
| Kiểm tra truthiness theo kiểu OGNL (`test="count"`) | EDIT | Đổi thành `count != 0`, `user != null`, `list.isEmpty()` |
| Tham số kiểu `Map` hoặc `Object` | BLOCKER | Dùng parameter object hoặc các tham số `@Param` cụ thể |
| Họ annotation `@SelectProvider` | BLOCKER | Đưa SQL vào mapper, hoặc dùng lối thoát thủ công |
| Plugin / interceptor | BLOCKER | Phân trang, audit và xoá mềm chuyển thành SQL tường minh, type handler hoặc decorator. [Công thức cho từng loại plugin](mybatis-differences.md#what-replaces-a-plugin) |
| Lazy loading | BLOCKER | Fetch sớm bằng phép join, hoặc tách thành hai statement |
| Lồng `select=` trong result map | BLOCKER | Viết lại bằng câu lệnh join |
| Result map lồng nhau sâu hơn một cấp | BLOCKER | Ghép dữ liệu trong Java từ hai statement riêng biệt |
| Thẻ result map có `extends` | BLOCKER | Khai báo tường minh tất cả ánh xạ cần thiết |
| Thẻ `<discriminator>` | BLOCKER | Tách thành các statement riêng với kiểu kết quả tương ứng |
| Ánh xạ constructor (`<constructor>`) | BLOCKER | Dùng constructor không tham số và các setter |
| Thẻ `<bind>` | BLOCKER | Tính toán trong Java và truyền vào qua tham số |
| Thẻ `<parameterMap>` | BLOCKER | Dùng `#{}` với tham số định kiểu rõ ràng |
| Cache cấp 2 | BLOCKER | Đặt cache ở tầng service phía trên mapper |
| `RowBounds` | BLOCKER | Dùng `LIMIT` / `OFFSET` dưới dạng tham số SQL thực sự |
| `statementType` khác `PREPARED` | BLOCKER | Gọi stored-procedure thông qua lối thoát thủ công |
| `objectFactory` / `objectWrapperFactory` | BLOCKER | Can thiệp vào tầng reflection nay đã bị loại bỏ |
| Thẻ `<include>` có `refid` động | BLOCKER | `refid` bắt buộc phải là hằng số cố định |
| Thẻ `<selectKey>` | REVIEW | Dùng `useGeneratedKeys` với `keyProperty`/`keyColumn` tường minh, hoặc tách thành statement riêng |
| TypeHandler tuỳ biến | REVIEW | Thuộc tính `typeHandler=` trong XML được đọc nguyên vẹn; viết lại class handler theo interface `LarkBatisTypeHandler` |
| Thẻ `<script>` trong annotation | REVIEW | Vẫn được đọc, nhưng áp dụng cùng quy tắc ngữ pháp; cần kiểm tra các biểu thức bên trong |
| Sử dụng trực tiếp `SqlSession` | REVIEW | Gọi qua mapper interface, hoặc dùng `session.query(SqlFragment, binder, GeneratedRow.READER)` |
| Cấu hình `mapUnderscoreToCamelCase` đang tắt | REVIEW | LarkBatis áp dụng lúc build và mặc định bật. Giữ nguyên hành vi cũ với `-Alarkbatis.mapUnderscoreToCamelCase=false`, hoặc gắn `@Column` / `<resultMap>` cho các cột bị ảnh hưởng |
| Nhiều môi trường / nhiều `DataSource` | REVIEW | Mỗi lần build hiện tại hỗ trợ một `DataSource` chính |
| Thẻ `<foreach>` | INFO | Được hỗ trợ; thống kê để theo dõi số lượng biến thể SQL có thể sinh ra |
| Statement động | INFO | Được biên dịch thành các biến điều kiện cục bộ (`condition locals`) và `StringBuilder` |

## Thứ tự thực hiện khuyến nghị

1. **Quét mã nguồn và đọc kỹ cột mức độ tập trung trước.** Nếu các lỗi nghiêm trọng (blocker) chỉ nằm trong một vài tệp, tính khả thi của việc chuyển đổi sẽ rất cao.
2. **Bắt đầu thử nghiệm với một mapper đơn lẻ, chưa vội chuyển đổi cả module.** Mapper là đơn vị biên dịch độc lập.
3. **Cấu hình thứ tự nạp annotation processor nếu dự án dùng Lombok:** khai báo `larkbatis-processor` chạy *sau* Lombok. Đây là lỗi phổ biến nhất trong ngày đầu tiên, thường xuất hiện dưới dạng "class kết quả không có getter/setter".
4. **Sửa các điểm gọi chứa `${}` tiếp theo.** Đây là các mục mức EDIT mang tính cơ học, và việc rà soát này cũng là dịp kiểm tra lại toàn bộ các điểm chèn SQL thô trong codebase.
5. **Chỉnh sửa các biểu thức `test=`.** Chủ yếu là lỗi truthiness: `count` → `count != 0`. Hãy đối chiếu cả [sự khác biệt khi so sánh null](mybatis-differences.md#behavioural-divergences-to-check-when-migrating).
6. **Thảo luận thiết kế cho các mục BLOCKER.** Mỗi mục đều có giải pháp thay thế, nhưng đòi hỏi quyết định kỹ thuật cụ thể chứ không đơn thuần là sửa cú pháp.
7. **Chạy toàn bộ test suite hiện có của dự án.** Đây là tiêu chuẩn nghiệm thu thực tế và quan trọng nhất.

## Ghi nhận thực tế

Một đợt chuyển đổi thử nghiệm trên bản sao của một service nội bộ thực tế đã hoàn thành và vượt qua 100% test suite. Quá trình này đã phát hiện hai lỗi mà unit test thông thường không bắt được: vấn đề **thứ tự nạp Lombok processor** và việc **đổi tên package auto-configuration trong Spring Boot 4** (khiến Spring context không khởi động được). Cả hai lỗi này hiện đã được khắc phục triệt để và bổ sung test tự động.

Hạng mục duy nhất còn lại là kiểm chứng service đã chuyển đổi vận hành liên tục trong môi trường thực tế trong một tuần.

## Những thay đổi trong quy trình làm việc

Có ba điểm thay đổi mà bạn và đội ngũ phát triển nên thống nhất trước khi bắt đầu:

- **Sửa SQL đồng nghĩa với việc phải build lại.** Đối với đội ngũ quen sửa mapper XML rồi restart ngay, đây là một thay đổi thực sự. Đổi lại, javac sẽ bắt toàn bộ lỗi sai kiểu dữ liệu vốn trước đây chỉ lộ ra lúc runtime.
- **Thời gian build tăng nhẹ.** Chi phí build tăng là có thật, được các kỹ sư trả một lần mỗi ngày lúc phát triển thay vì để hệ thống production phải trả giá trên từng truy vấn. Đây là việc chuyển dịch chi phí sang trái (shift-left), không phải triệt tiêu hoàn toàn.
- **Cần cập nhật các vị trí gọi `${}`.** Khối lượng sửa đổi tỷ lệ thuận với số lượng điểm gọi `${}`, không phải số lượng mapper. Bộ scanner sẽ hỗ trợ định hình chính xác đoạn code cần sửa.

Để xem đánh giá khách quan về những lợi ích nhận lại, hãy tham khảo [Hiệu năng](../wiki/performance.md), đặc biệt là phần phân tích truy vấn đơn dòng.
