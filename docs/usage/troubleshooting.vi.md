# Xử lý sự cố

## Không có gì được sinh ra

Kiểm tra theo đúng thứ tự này:

1. **Processor có nằm đúng configuration không?** `annotationProcessor` trong Gradle,
   `annotationProcessorPaths` trong Maven, chứ không phải `implementation` /
   `<dependencies>`.
2. **Bạn có đang biên dịch bằng javac không?** ECJ / trình biên dịch batch của Eclipse
   không được hỗ trợ. Processor dựa vào hành vi của javac: thứ tự khai báo của các phần
   tử, và việc resolve nhiều vòng cho các kiểu được sinh ra.
3. **Interface đó có annotation statement hoặc `@Mapper` không?** Đó là hai kiểu kích
   hoạt duy nhất. Một interface chỉ dùng XML mà thiếu `@Mapper` sẽ không bao giờ lọt vào
   một vòng xử lý nào.
4. **Dùng JDK 23+ với `addProcessorPath=false`?** javac không còn tự tìm processor từ
   classpath biên dịch nữa, và `-Alarkbatis.mapperDir` cũng không được tính là lời yêu
   cầu xử lý annotation. Hãy thêm processor vào `annotationProcessorPaths` hoặc đặt
   `<proc>full</proc>`.

## `#{id}` không resolve được, và tham số mang tên `arg0`, `arg1`

```text
error: no parameter or property named 'id' in findById(long)
```

Một bản build **incremental** của Gradle chạy lại các aggregating processor trên những
mapper không đổi từ **file class** của chúng, nơi tên tham số chỉ sống sót nếu lớp đó
được biên dịch với `-parameters`. Build sạch thì đọc AST và chạy tốt; bản incremental
ngay sau đó thì không. Gradle đã ghi nhận hạn chế này, và nó không phải lỗi của
LarkBatis.

### Cờ đó thật ra làm gì { #what-the-flag-actually-does }

Mặc định javac vứt bỏ tên tham số. `findById(long id)` biên dịch ra một phương thức có
tham số không tên, và thứ gì đọc lại từ file class sẽ chỉ thấy cái tên tổng hợp `arg0`.
Cờ `-parameters` bảo javac ghi kèm mỗi phương thức một attribute `MethodParameters`, nhờ
đó tên thật còn lại trong bytecode.

Điều đó quan trọng ở đây vì processor xử lý `#{id}` bằng cách tìm một tham số tên `id`.
Với build sạch, nó đọc tên từ AST, mà AST thì lúc nào cũng có, nên không có gì sai. Với
build incremental, Gradle đưa cho nó những mapper mà nó không biên dịch lại, và cái tên
duy nhất còn dùng được là cái mà file class giữ lại.

Cái giá là vài byte mỗi phương thức trong jar, và không tốn gì lúc chạy. Spring Boot,
Jackson và Micronaut đều đòi đúng cờ này, nên đa số project đã có sẵn.

=== "Cách 1: biên dịch kèm `-parameters`"

    ```kotlin title="build.gradle.kts"
    tasks.withType<JavaCompile>().configureEach {   // (1)!
        options.compilerArgs.add("-parameters")     // (2)!
    }
    ```

    1.  `withType(...).configureEach` với tới mọi task biên dịch trong project, kể cả
        `compileTestJava` và các source set thêm vào sau này. Chỉ cấu hình riêng
        `compileJava` thì những task còn lại không có cờ.
    2.  Bên Maven tương đương với `<parameters>true</parameters>` trong
        `maven-compiler-plugin`, và [trang cài đặt](../getting-started/index.md#maven)
        đã đặt sẵn giúp bạn.

=== "Cách 2: đặt tên cho mọi tham số"

    ```java
    User findById(@Param("id") long id);
    ```

    `@Param` đặt cái tên vào trong annotation, mà annotation thì được lưu trong file class
    bất kể cờ biên dịch là gì. Cách này gõ nhiều hơn, đổi lại nó sống sót qua cả những bản
    build do người khác cấu hình.

## `Lombok has not run yet` / lớp kết quả không có accessor nào

Lombok ghi getter và setter của nó vào AST khi processor của **chính nó** chạy, còn javac
thì chạy các processor tìm được theo đúng thứ tự trên classpath. Khai báo trước,
LarkBatis sẽ nhìn thấy một lớp kết quả không có lấy một accessor nào.

```kotlin
annotationProcessor("org.projectlombok:lombok")
annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0-SNAPSHOT")  // sau
```

Thông báo lỗi có nói rõ điều đó khi nó phát hiện annotation của Lombok trên lớp, nhưng
cách sửa vẫn chỉ là một dòng thứ tự.

## Sửa mapper XML mà chẳng thay đổi gì

Processor đọc mapper XML bằng `java.io` thuần, nằm ngoài `Filer` của trình biên dịch, nên
phải nói cho công cụ build biết rằng những file đó là đầu vào biên dịch.

- **Đang dùng [plugin build](../getting-started/build-plugins.md)?** Gradle đăng ký các
  file làm đầu vào của `compileJava`; goal `larkbatis:refresh` của Maven chạm vào file
  nguồn của interface mapper có băm nội dung XML thay đổi. Cả hai đều phải chạy được ngay.
- **Dùng Maven mà chẳng thấy gì xảy ra?** Gần như chắc chắn bạn đã bỏ quên
  `<extensions>true</extensions>`, và thiếu nó thì mọi thứ hỏng trong **im lặng**. Hãy chạy
  `mvn larkbatis:check`.
- **Đang tự truyền tay `-Alarkbatis.mapperDir`?** Vậy thì chẳng có gì đăng ký đầu vào
  cả. Hãy chạy `clean` sau khi chỉ sửa XML.

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
