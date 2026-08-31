# Khắc phục sự cố (Troubleshooting)

## Processor không sinh ra bất kỳ file nào

Hãy kiểm tra theo thứ tự:

1. **Đã cấu hình đúng `annotationProcessor` chưa?** Trong Gradle dùng `annotationProcessor`, trong Maven dùng `<annotationProcessorPaths>` (không khai báo trong scope `implementation` hay `<dependencies>`).
2. **Có đang dùng `javac` chuẩn không?** Eclipse Compiler for Java (ECJ) không được hỗ trợ. Processor phụ thuộc vào AST chuẩn của OpenJDK/javac.
3. **Interface đã có annotation chưa?** Phải có ít nhất một method mang annotation `@Select`/`@Insert`... hoặc interface gắn `@Mapper` (nếu dùng XML).
4. **Chạy trên JDK 23+?** JDK 23 tắt mặc định tìm kiếm processor trên compile classpath. Cần khai báo rõ ràng trong `annotationProcessorPaths` hoặc thêm flag `-proc:full`.

## Lỗi `#{id}` không tìm thấy tham số (`arg0`, `arg1`)

```text
error: no parameter or property named 'id' in findById(long)
```

**Nguyên nhân**: Gradle incremental build chạy processor trên các **file `.class`** đã biên dịch trước đó. Mặc định `javac` không lưu tên tham số vào bytecode nên processor chỉ thấy `arg0`, `arg1`.

**Giải pháp**:
1. Bật cờ `-parameters` trong cấu hình biên dịch:
   ```kotlin title="build.gradle.kts"
   tasks.withType<JavaCompile>().configureEach {
       options.compilerArgs.add("-parameters")
   }
   ```
2. Hoặc gắn annotation `@Param("id")` tường minh trên tham số.

## Lỗi không tìm thấy Getter/Setter khi dùng Lombok

**Nguyên nhân**: Lombok chưa sinh xong accessor khi LarkBatis processor bắt đầu phân tích POJO.

**Giải pháp**: Khai báo `larkbatis-processor` chạy **sau** Lombok trong dependencies:

```kotlin title="build.gradle.kts"
dependencies {
    annotationProcessor("org.projectlombok:lombok:1.18.30")
    annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0") // Bắt buộc đặt sau Lombok
}
```

## Sửa file Mapper XML nhưng mã nguồn không sinh lại

- **Gradle**: Build plugin tự động đăng ký file XML làm input của `compileJava`.
- **Maven**: Đảm bảo đã bật `<extensions>true</extensions>` trong `larkbatis-maven-plugin`. Chạy `mvn larkbatis:check` để xác thực cấu hình.
- **Nếu cấu hình `-Alarkbatis.mapperDir` thủ công**: Chạy `./gradlew clean compileJava` hoặc `mvn clean compile` để buộc javac sinh lại toàn bộ code.

## Lỗi `package javax.annotation.processing is not visible`

Trong dự án sử dụng Java Module System (JPMS), file mã nguồn sinh ra có gắn `@Generated`. Thêm khai báo sau vào `module-info.java`:

```java
requires static java.compiler;
```

## Cảnh báo `useGeneratedKeys without keyColumn falls back to RETURN_GENERATED_KEYS`

Cần khai báo tường minh `keyColumn = "id"` trong `@Options` để đảm bảo JDBC driver trả về đúng khóa chính trên các database như Oracle và PostgreSQL.

## Ngoại lệ `LarkBatisEmptyForeachException` lúc runtime

Collection truyền vào `<foreach>` rỗng. Nếu muốn bỏ qua đoạn SQL này khi collection rỗng, bọc thẻ `<foreach>` bên trong thẻ `<if>`:

```xml
<if test="ids != null and !ids.isEmpty()">
  AND id IN <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
</if>
```

## Lỗi biên dịch khi dùng `test="count"`

LarkBatis không hỗ trợ OGNL truthiness ngầm định. Bạn phải so sánh tường minh: `count != 0`, `user != null`, hoặc `!list.isEmpty()`.

## Lỗi biên dịch khi gắn `String` vào `${}`

Chuỗi `${}` không nhận tham số kiểu `String` tự do để tránh SQL Injection. Hãy đổi kiểu sang `SqlFragment`, kiểu tập giá trị đóng (enum/primitive), hoặc gắn `@OrderBy(allowed = {...})`.

## Ngoại lệ `LarkBatisRollbackOnlyException` khi commit

Một transaction scope con bên trong đã kết thúc mà không gọi `commit()`, khiến transaction bị đánh dấu rollback-only. Kiểm tra lại luồng logic trong code để đảm bảo tất cả các scope lồng nhau đều gọi `commit()`.

