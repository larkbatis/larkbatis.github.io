# Khác biệt với MyBatis

Mỗi mục trong danh sách này đều có lý do kỹ thuật rõ ràng, được chia thành ba nhóm. Khi đọc theo thứ tự này, bạn sẽ thấy thiết kế của LarkBatis mang tính nhất quán và chặt chẽ, không phải những quyết định tuỳ tiện.

## Nhóm 1: Loại bỏ hoàn toàn

Những tính năng này đòi hỏi một cơ chế không còn tồn tại trong LarkBatis: runtime type model, dynamic proxy, hoặc bộ thông dịch (interpreter) lúc chạy.

| Tính năng | Lý do không thể mang trở lại | Giải pháp thay thế |
|---|---|---|
| **OGNL đầy đủ trong thuộc tính `test`** | Bộ đánh giá biểu thức trên mô hình đối tượng runtime chính là bộ thông dịch cần loại bỏ | [Ngữ pháp biểu thức thu hẹp](../usage/dynamic-sql.md#the-test-grammar) |
| **`<bind>`** | Khởi tạo một biến OGNL mới lúc chạy | Tính toán giá trị trong Java rồi truyền vào qua tham số |
| **Họ annotation `@SelectProvider`** | Chuỗi SQL do phương thức Java dựng động lúc runtime hoàn toàn vô hình trước bộ sinh code lúc build | Đặt SQL trong mapper hoặc dùng [lối thoát thủ công](../usage/raw-sql.md#the-escape-hatch) |
| **Lazy loading** | Đòi hỏi bọc proxy trên từng đối tượng kết quả | Fetch dữ liệu sớm (eagerly) bằng phép join, hoặc tách thành hai statement |
| **Plugin / interceptor** | Không có đối tượng trung gian để bọc: 4 đối tượng MyBatis chặn bắt đã bị thay thế hoàn toàn bởi thân phương thức sinh sẵn | [Công thức thay thế bên dưới](#what-replaces-a-plugin) |
| **Tham số kiểu `Object` / `Map`** | Không có kiểu tĩnh để resolve `#{}` lúc compile | Dùng parameter object hoặc các tham số `@Param` |
| **`<discriminator>`** | Khiến *class* kết quả phụ thuộc vào giá trị cột lúc runtime | Tách thành các statement riêng biệt với kiểu kết quả riêng |
| **Lồng `select=` trong `<collection>`/`<association>`** | Phát sinh N+1 truy vấn thông qua runtime | Viết tường minh bằng câu lệnh join |
| **Cache cấp 2** | Không có cơ chế tương đương, và việc vô hiệu hoá cache ở tầng này luôn phức tạp | Đặt cache ở tầng service phía trên mapper, nơi việc invalidate cache rõ ràng và kiểm soát được |
| **Gọi `addMapper()` lúc runtime** | Danh sách mapper được chốt cố định lúc biên dịch | Không cần xử lý; tập mapper đóng giúp tối ưu hoá toàn bộ quá trình build |
| **`RowBounds`** | Phân trang trên bộ nhớ từ ResultSet đầy đủ | Phân trang trực tiếp trong SQL bằng `LIMIT` và `OFFSET` dưới dạng tham số |
| **`<selectKey>`** | Đội lốt một tuỳ chọn nhưng thực chất là một statement thứ hai chạy ngầm | Viết tường minh statement thứ hai. [Ví dụ](../usage/generated-keys.md#selectkey-is-not-supported) |
| **Constructor mapping (`<constructor>`)** | Class kết quả được khởi tạo bằng constructor không tham số và setter | Dùng setter |
| **`<parameterMap>`** | Đã bị deprecated ngay trong MyBatis | Dùng `#{}` với các tham số có kiểu rõ ràng |
| **`objectFactory` / `objectWrapperFactory`** | Hook can thiệp vào tầng reflection nay đã không còn | |
| **Type alias** | Alias là bảng tra cứu lúc runtime; LarkBatis hoạt động ở pha build | Dùng tên class đầy đủ (FQN) |
| **Cache cấp 1** | Không có session lưu trạng thái để giữ cache | |
| **`ExecutorType.BATCH` / `REUSE`** | Không có lớp executor trung gian | Batch được định nghĩa qua [chữ ký phương thức](../usage/foreach-and-batches.md#jdbc-batches) |

### Giải pháp thay thế plugin { #what-replaces-a-plugin }

Đây là rào cản phổ biến nhất khi chuyển đổi dự án thực tế. Hầu như mọi dự án MyBatis lâu năm đều có ít nhất một plugin phân trang hoặc ghi log.

Trong MyBatis, `Interceptor` áp dụng chính xác lên 4 đối tượng: `Executor`, `StatementHandler`, `ParameterHandler` và `ResultSetHandler`. Mỗi đối tượng được tạo qua factory method của `Configuration` kết thúc bằng `interceptorChain.pluginAll(...)`, và được `Plugin.wrap` bọc lại bằng `Proxy.newProxyInstance`.

Cả hai nửa của cơ chế đó đều không còn trong LarkBatis, và đây là quyết định thiết kế cốt lõi:

- **4 đối tượng đó không tồn tại.** Chúng được thay thế hoàn toàn bởi thân phương thức sinh sẵn. Thân phương thức này mượn một `Connection`, gọi `prepareStatement` với chuỗi SQL hằng số, gán tham số bằng các lệnh `ps.setXxx` định kiểu tĩnh từ lúc build, và đọc dòng qua `RowReader` sinh sẵn. Không hề có executor trung gian giữa lời gọi mapper và JDBC để chèn code vào.
- **Cơ chế bọc là `Proxy.newProxyInstance`**, lời gọi duy nhất mà runtime và code sinh ra tuyệt đối không sử dụng. Giữ lại plugin đồng nghĩa với việc phải giữ lại proxy, và mục tiêu tương thích native image chỉ khả thi khi loại bỏ hoàn toàn proxy.

Cách chuyển đổi cho từng loại plugin:

| Loại plugin | Giải pháp thay thế |
|---|---|
| Phân trang (PageHelper,...) | Dùng `LIMIT` / `OFFSET` làm tham số `#{}` thông thường, và viết một statement đếm số lượng riêng. Kích thước trang không còn lưu ngầm trong `ThreadLocal`, triệt tiêu lỗi rò rỉ trạng thái giữa các luồng mà plugin dạng này thường mắc phải |
| Audit dữ liệu — `created_at`, `updated_by` | Gán giá trị trực tiếp ở tầng service trước khi gọi mapper, dùng giá trị mặc định của cột trong database, hoặc đưa danh sách cột này vào đoạn [`<sql>` fragment](../usage/xml-mappers.md) để các câu insert tái sử dụng |
| Xoá mềm (Soft delete) | Thêm `AND deleted = false` vào câu lệnh hoặc đưa vào đoạn `<sql>` dùng chung. Minh bạch, dễ tìm kiếm (grep) trong mã nguồn, và không lo bị bỏ quên bởi những truy vấn vô tình bỏ qua interceptor |
| Mã hoá hoặc che giấu dữ liệu cột (masking) | Tạo một [`LarkBatisTypeHandler`](../usage/types.md#custom-type-handlers), đăng ký cho kiểu dữ liệu tương ứng qua [`-Alarkbatis.typeHandlers`](configuration.md#type-handlers-for-a-whole-build). Trường hợp này chuyển đổi gần như tương đương 1-1 |
| Ghi log SQL | Xử lý ở tầng driver hoặc connection pool: `net.ttddyy:datasource-proxy`, p6spy |
| Multi-tenancy, tên bảng hoặc schema động | Dùng [`SqlFragment`](../usage/raw-sql.md) qua `${}`. Đây là cổng kiểm soát duy nhất cho phép chèn chuỗi SQL thô |
| Đo thời gian thực thi, metrics, tracing | Dùng decorator bọc quanh mapper bean, hoặc áp dụng Spring AOP |

!!! tip "Mapper bean trong LarkBatis là một đối tượng Java thuần"

    Trong MyBatis, bản thân mapper *là* một JDK dynamic proxy, đó là lý do lập trình viên buộc phải dùng interceptor khi muốn can thiệp hành vi. Trong LarkBatis, mapper là một class thông thường được sinh ra (`UserMapper$$Impl`) và đăng ký dưới dạng bean chuẩn của Spring. Do đó, bạn có thể áp dụng Spring AOP dễ dàng, hoặc tự viết decorator implement cùng interface để tuỳ biến logic.

## Nhóm 2: Giữ lại nhưng thu hẹp phạm vi

Các tính năng này vẫn hoạt động bình thường. Việc thu hẹp phạm vi giúp chúng có thể biên dịch tĩnh hoàn toàn lúc build.

| Tính năng | Phạm vi thu hẹp | Lý do kỹ thuật |
|---|---|---|
| **`<where>` / `<set>` / `<trim>`** | Thuộc tính cố định dạng chuỗi, được gập hằng số lúc build | Các thuộc tính này trong thực tế không bao giờ thay đổi theo từng lần gọi |
| **`<foreach>`** | Collection, mảng và `Map` phải định kiểu tĩnh. Ném exception nếu collection rỗng. Tuỳ chọn `@PadPow2` | Kiểu phần tử quyết định việc gọi `setLong` hay `setString`. [Chi tiết](../usage/foreach-and-batches.md) |
| **`<sql>` / `<include>`** | `refid` phải là hằng số cố định, được inline lúc build | `refid` tính toán động lúc chạy đòi hỏi bảng tra cứu runtime |
| **Lồng `<resultMap>`** | Tối đa một cấp, qua phép join, ResultSet bắt buộc phải sắp xếp theo khoá của bảng cha | Thay thế `CacheKey` và map tra cứu theo từng dòng bằng phép so sánh định kiểu tĩnh `!=`. [Chi tiết](../usage/result-maps.md) |
| **TypeHandler tuỳ biến** | Khai báo `@Handler` hoặc `typeHandler=` tại vị trí sử dụng, hoặc `-Alarkbatis.typeHandlers` theo kiểu Java; khai báo tường minh, không quét tự động | Tự động phát hiện đòi hỏi quét registry và kiểm tra theo từng cột lúc đọc. Khai báo tường minh giúp xác định handler chính xác ngay lúc build |
| **`${}`** | Chỉ chấp nhận `SqlFragment`, kiểu dữ liệu tập giá trị đóng, hoặc `@OrderBy(allowed = {...})` | Đảm bảo mọi điểm chèn SQL thô đều được kiểm tra kiểu tĩnh và dễ kiểm toán mã nguồn. [Chi tiết](../usage/raw-sql.md) |
| **Nhiều `DataSource`** | Tạm hoãn; tự viết session riêng cho từng `DataSource` | Chỉ thiết kế khi có use-case thực tế từ hệ thống production |

## Nhóm 3: Chuyển dịch sang pha build

Bạn không cần cấu hình những mục này nữa vì không còn gì để cấu hình lúc runtime.

| Khái niệm trong MyBatis | Giải pháp thay thế trong LarkBatis |
|---|---|
| Tra cứu `TypeHandlerRegistry` cho từng tham số và từng cột | Lệnh gọi `ps.setXxx` / `rs.getXxx` được chọn sẵn từ lúc build |
| `Reflector` / `MetaObject` / `BeanWrapper` | Gọi trực tiếp setter trong class đọc dòng sinh sẵn |
| Registry `<typeHandlers>` | Đăng ký theo kiểu Java lúc build với `-Alarkbatis.typeHandlers`, hoặc khai báo tại chỗ với `@Handler` / `typeHandler`. Không quét package, không `@MappedTypes`, không cần `jdbcType`, không tra cứu runtime |
| Cấu hình `mapUnderscoreToCamelCase` | Áp dụng lúc build, và mặc định bật (*on*). Cờ `-Alarkbatis.mapUnderscoreToCamelCase=false` dùng để giữ nguyên hành vi cũ của MyBatis |
| Điều phối qua `MapperProxy` + `MapperMethod` | Gọi trực tiếp phương thức trong class thực thi cụ thể |
| Quét classpath tìm mapper bằng `ResolverUtil` | Trình biên dịch đã nắm toàn bộ danh sách mapper |
| Phân tích XPath + kiểm tra DTD cho từng mapper khi khởi động ứng dụng | Phân tích cú pháp một lần duy nhất lúc build |
| `SqlSourceBuilder` tạo danh sách `ParameterMapping` | Ký tự giữ chỗ `?` và gán tham số theo vị trí được sinh trực tiếp vào mã nguồn |
| `@MapperScan` + `MapperFactoryBean` | Sinh sẵn class `@Configuration` với các phương thức `@Bean` thuần tuý |

## Các điểm phân kỳ hành vi cần chú ý khi migration { #behavioural-divergences-to-check-when-migrating }

Có 4 vị trí LarkBatis *hoạt động bình thường* nhưng cho ra kết quả khác với MyBatis. Trình biên dịch sẽ không báo lỗi ở những điểm này, vì vậy bạn cần nắm rõ:

**1 · `<foreach>` rỗng sẽ ném exception.** MyBatis không đóng góp chuỗi nào vào câu SQL (kể cả `open` và `close`), khiến đoạn `... WHERE id IN` bị lỗi cú pháp tại cơ sở dữ liệu. LarkBatis chủ động ném `LarkBatisEmptyForeachException` nêu rõ tên mapper và tên tham số. Để giữ hành vi bỏ qua điều kiện của MyBatis, hãy bọc vòng lặp trong `<if test="ids != null and !ids.isEmpty()">`.

**2 · So sánh với null trả về false, không ép về 0.** OGNL ép kiểu null thành 0, nên biểu thức `test="age <= 18"` trong MyBatis trả về *true* khi `age` là null. Trong LarkBatis, nếu bất kỳ toán hạng nào là null thì phép so sánh luôn trả về **false**. Riêng phép kiểm tra `== null` / `!= null` hoạt động hoàn toàn giống nhau ở cả hai bên.

**3 · Gọi phương thức trên đối tượng null trả về false, không ném exception.** Biểu thức `user.isActive()` khi `user` nhận giá trị null sẽ đánh giá thành `false`. MyBatis sẽ ném `NullPointerException`.

**4 · Khoảng trắng trong câu SQL được ghép chuẩn hoá.** Các đoạn SQL được nối với nhau bằng đúng một dấu cách đơn và cắt bỏ khoảng trắng thừa. Khoảng trắng ngẫu nhiên của MyBatis khác nhau giữa các phiên bản khi xử lý thẻ `<trim>`. Về mặt ngữ nghĩa ngữ pháp SQL là tương đương; nhưng so sánh chuỗi từng ký tự một sẽ thấy khác nhau.

## Cơ chế kiểm thử và đảm bảo tính đúng đắn

Hệ thống test vi sai (differential test harness) chạy cùng một mapper qua cả hai luồng: luồng thông dịch của MyBatis và luồng sinh code của LarkBatis trên cùng một `DataSource` ghi nhận dữ liệu (recording `DataSource`), so sánh từng câu SQL và từng tham số được bind. Việc quét toàn bộ kho mapper XML trong mã nguồn gốc của MyBatis là cách đo đạc độ bao phủ thực tế của ngữ pháp biểu thức. Bộ quét migration `larkbatis-scan` cũng dùng chung frontend này, vì vậy [báo cáo quét](migration.md) luôn phản ánh chính xác những gì sẽ biên dịch được.
