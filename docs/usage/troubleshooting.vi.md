# Xử lý sự cố

## Không có file nào được sinh ra

Hãy kiểm tra theo thứ tự các bước sau:

1. **Annotation processor đã đặt đúng configuration chưa?** Sử dụng `annotationProcessor` trong Gradle, hoặc `<annotationProcessorPaths>` trong Maven compiler plugin (không phải `implementation` hay `<dependencies>`).
2. **Bạn có đang biên dịch bằng javac không?** Eclipse Compiler for Java (ECJ) không được hỗ trợ. Processor dựa vào hành vi chuẩn của javac (thứ tự khai báo phần tử trong AST và khả năng resolve qua nhiều round xử lý).
3. **Interface mapper có annotation statement hoặc `@Mapper` không?** Đây là hai điều kiện kích hoạt duy nhất. Một interface thuần XML mà thiếu `@Mapper` sẽ bị processor bỏ qua.
4. **Sử dụng JDK 23+ với cấu hình `addProcessorPath=false`?** javac từ JDK 23 không còn tự động tìm processor từ compile classpath. Hãy thêm processor vào `annotationProcessorPaths` hoặc khai báo `<proc>full</proc>`.

## `#{id}` không resolve được và tham số nhận tên `arg0`, `arg1`

```text
error: no parameter or property named 'id' in findById(long)
```

Quá trình biên dịch **tăng dần (incremental build)** của Gradle chạy lại các aggregating processor trên những mapper không thay đổi từ **file .class** đã biên dịch trước đó. Mặc định javac không lưu tên tham số vào bytecode, do đó processor chỉ thấy các tên tổng hợp `arg0`, `arg1`.

### Cờ `-parameters` có tác dụng gì { #what-the-flag-actually-does }

Mặc định javac loại bỏ tên tham số khỏi bytecode để tiết kiệm dung lượng. `findById(long id)` biên dịch ra bytecode sẽ mất tên `id`. Cờ `-parameters` yêu cầu javac ghi thêm thuộc tính `MethodParameters` vào class file, giúp giữ lại tên thật của tham số trong bytecode.

Khi build sạch (clean build), processor đọc tên từ AST nên luôn chính xác. Nhưng khi build tăng dần, Gradle truyền lại các class file cũ, nên processor chỉ có thể lấy lại tên tham số nếu class file có attribute này.

Chi phí chỉ tốn vài byte trong mỗi file .class và hoàn toàn không ảnh hưởng tới hiệu năng runtime. Các framework lớn như Spring Boot, Jackson và Micronaut đều yêu cầu cờ này.

=== "Cách 1: Biên dịch kèm cờ `-parameters`"

    ```kotlin title="build.gradle.kts"
    tasks.withType<JavaCompile>().configureEach {   // (1)!
        options.compilerArgs.add("-parameters")     // (2)!
    }
    ```

    1.  `configureEach` áp dụng cờ cho toàn bộ các compile task trong project (kể cả test và custom source set).
    2.  Bên Maven tương đương cấu hình `<parameters>true</parameters>` trong `maven-compiler-plugin`.

=== "Cách 2: Khai báo `@Param` tường minh cho mọi tham số"

    ```java
    User findById(@Param("id") long id);
    ```

    `@Param` lưu tên tham số trực tiếp trong metadata của annotation nên luôn tồn tại trong bytecode bất kể cờ biên dịch nào.

## Lỗi liên quan đến Lombok / Class kết quả không có accessor nào

Lombok chèn getter và setter vào AST khi processor của chính nó chạy. Do đó, `larkbatis-processor` bắt buộc phải được cấu hình chạy **sau** Lombok trong chuỗi `annotationProcessor`:

```kotlin
annotationProcessor("org.projectlombok:lombok")
annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0-SNAPSHOT")  // đặt sau Lombok
```

## Sửa mapper XML nhưng code không sinh lại

Processor đọc mapper XML trực tiếp từ file hệ thống thay vì qua `Filer` của compiler, vì vậy build tool cần được cấu hình để nhận diện các file XML là đầu vào biên dịch:

- **Khi dùng [build plugin](../getting-started/build-plugins.md)?** Gradle plugin tự động đăng ký các file XML làm input của `compileJava`; Maven plugin qua goal `larkbatis:refresh` sẽ tự động chạm (touch) các file Java tương ứng khi hash của XML thay đổi.
- **Dùng Maven nhưng không thấy code cập nhật?** Kiểm tra xem đã bật `<extensions>true</extensions>` trong cấu hình plugin chưa. Nếu thiếu, extension lifecycle sẽ không chạy. Chạy `mvn larkbatis:check` để kiểm tra.
- **Truyền thủ công `-Alarkbatis.mapperDir`?** Khi không dùng plugin, hãy chạy `clean` trước khi biên dịch lại sau khi sửa XML.

Cũng kiểm tra xem phần tử gốc của file có phải `<mapper>` không, vì mọi thứ khác trong
thư mục đều bị bỏ qua, và xem `namespace` của nó có gọi tên một interface **trong cùng
module** không. Một namespace vắt qua module sẽ bị bỏ qua kèm cảnh báo build.

## `package javax.annotation.processing is not visible`

Một consumer modular cần `requires static java.compiler`, bởi vì mọi file nguồn phát ra
đều mang `@Generated`. Thông báo lỗi lại trỏ vào file *được sinh ra*, và chính điều đó
làm nó khó hiểu. Xem [Java Module](../getting-started/jpms.md).

## `useGeneratedKeys without keyColumn falls back to RETURN_GENERATED_KEYS`

Một cảnh báo build bắt buộc, và đáng để coi như lỗi: Oracle trả về `ROWID` còn PostgreSQL
trả về mọi cột dưới cờ đó. Hãy gọi tên cột khoá tường minh. Xem
[Khoá tự sinh](generated-keys.md).

## `LarkBatisEmptyForeachException` lúc chạy

Một tập hợp trong `<foreach>` bị rỗng. Nếu mảnh SQL đó cần biến mất khi tập hợp rỗng,
tức đúng hành vi MyBatis, thì hãy nói ra:

```xml
<if test="ids != null and !ids.isEmpty()">
  AND id IN <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
</if>
```

Xem [foreach và batch](foreach-and-batches.md#empty-collections).

## `test="count"` là lỗi biên dịch

Tính đúng-sai kiểu OGNL cố ý không được tái tạo. Hãy viết `count != 0`, `user != null`,
hoặc `!list.isEmpty()`. Xem [ngữ pháp test](dynamic-sql.md#the-test-grammar).

## Một tham số `String` gắn vào `${}` là lỗi biên dịch

Kỷ luật `${}` bắt buộc như vậy. Hãy dùng `@OrderBy(allowed = {...})`, một `SqlFragment`,
hoặc một kiểu
giá trị đóng. Xem [SQL thô](raw-sql.md).

## `LarkBatisRollbackOnlyException` khi commit

Một phạm vi transaction bên trong đã rời đi mà không bỏ phiếu, làm hỏng transaction,
rồi phạm vi ngoài mới gọi commit. Exception này vẫn tốt hơn một lần rollback âm thầm
trông y như thành công. Xem [Transaction](transactions.md).

## `LarkBatisUnboundedVariantsException`

Bạn đã đặt `fail-on-unbounded-fragment: true` (rất tốt, ở staging) và một statement sinh
ra nhiều hơn `max-sql-variants` câu SQL khác nhau. Hãy tìm cái `${}` hoặc cái
`<foreach>` không bị chặn rồi hoặc đóng tập giá trị lại bằng `SqlFragment.allowed(...)` /
`@OrderBy`, hoặc chặn số phần tử bằng `@PadPow2`. Xem
[Theo dõi biến thể SQL](raw-sql.md#tracking-sql-variants).

## Một statement lùi về đọc dòng theo tên

Việc này được báo lúc build. Nó nghĩa là select list không phân tích được: `SELECT *`,
một chỗ chèn `${}` trong select list, hoặc một biểu thức không đặt alias như `1 + 1`.
Statement đó vẫn đúng và chậm hơn ở mức đo được. Hãy đặt alias cho biểu thức, hoặc viết
rõ các cột ra, nếu bạn muốn lấy lại phép đọc theo vị trí.

## Code sinh ra không đóng Connection

Việc bỏ sót đó là đúng, và các bài test của bộ phát mã khẳng định như vậy. Chỉ
`s.release(c)` mới biết connection có thuộc về một transaction đang chạy hay không. Xem
[Transaction](transactions.md#why-generated-code-never-closes-the-connection).
