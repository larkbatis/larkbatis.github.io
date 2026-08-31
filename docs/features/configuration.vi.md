# Tùy chọn cấu hình

Cấu hình trong LarkBatis được phân chia rõ ràng theo từng giai đoạn: tùy chọn compiler processor lúc biên dịch, cấu hình build plugin, và thiết lập runtime khi ứng dụng khởi chạy.

## Tùy chọn Annotation Processor (Compile-time)

Truyền cho `javac` dưới dạng tham số `-A<key>=<value>`:

| Tùy chọn | Ý nghĩa | Giá trị mặc định |
|---|---|---|
| `larkbatis.registryPackage` | Tên package cho class factory `LarkBatisMappers` sinh ra | Tiền tố package chung của các mapper |
| `larkbatis.mapperDir` | Danh sách thư mục chứa mapper XML (phân tách bằng dấu phẩy) | Build plugin tự động gán `src/main/resources` |
| `larkbatis.mapUnderscoreToCamelCase` | Tự động ánh xạ `snake_case` sang `camelCase` lúc build | `true` |
| `larkbatis.typeHandlers` | Đăng ký TypeHandler toàn cục dạng `javaType:handlerClass,...` | Không có |
| `larkbatis.springConfig` | Bật/tắt tự động sinh class `@Configuration` cho Spring | `true` (khi có `spring-context` trên classpath) |
| `larkbatis.springConfigPackage` | Package cho class `LarkBatisMapperConfiguration` | Giống `registryPackage` |

=== "Gradle"

    ```kotlin title="build.gradle.kts"
    tasks.withType<JavaCompile>().configureEach {
        options.compilerArgs.add("-Alarkbatis.registryPackage=com.example.app")
    }
    ```

=== "Maven"

    ```xml title="pom.xml"
    <configuration>
      <compilerArgs>
        <arg>-Alarkbatis.registryPackage=com.example.app</arg>
      </compilerArgs>
    </configuration>
    ```

### Ánh xạ tên cột (Column Naming) { #column-naming }

Mặc định, cột `created_at` sẽ tự động được ánh xạ sang setter `setCreatedAt`. Để tắt quy tắc này (giữ nguyên cách xử lý cũ của MyBatis), cấu hình:

```
-Alarkbatis.mapUnderscoreToCamelCase=false
```

### Đăng ký TypeHandler toàn dự án { #type-handlers-for-a-whole-build }

Thay vì cấu hình thẻ `<typeHandlers>` trong XML runtime, bạn khai báo trực tiếp cho `javac`:

```
-Alarkbatis.typeHandlers=com.example.Money:com.example.MoneyHandler,\
                         com.example.JsonNode:com.example.JsonNodeHandler
```

Compiler sẽ xác thực cả kiểu dữ liệu Java lẫn class handler trong quá trình build, đảm bảo handler tồn tại và implement `LarkBatisTypeHandler` hợp lệ.

## Cờ trình biên dịch bắt buộc

| Cờ compiler | Lý do |
|---|---|
| `-parameters` | Yêu cầu `javac` lưu tên tham số phương thức vào bytecode. Điều này rất quan trọng để Gradle incremental build không bị mất tên biến `#{id}` thành `arg0`. Nếu không bật cờ này, bạn bắt buộc phải gắn `@Param` cho từng tham số |

## Cấu hình Build Plugin

=== "Gradle"

    ```kotlin title="build.gradle.kts"
    larkbatis {
        mapperDir = layout.projectDirectory.dir("src/main/mappers")
        mapperDirs.from("src/main/legacy-mappers")
        addProcessorDependency = false   // Tự quản lý dependency processor thủ công
        addParametersFlag = false        // Tắt tự động thêm cờ -parameters (nếu đã gắn @Param)
    }
    ```

=== "Maven"

    ```xml title="pom.xml"
    <configuration>
      <mapperDir>src/main/mappers</mapperDir>
      <mapperDirs>
        <mapperDir>src/main/legacy-mappers</mapperDir>
      </mapperDirs>
      <addProcessorPath>false</addProcessorPath>
      <addParameters>false</addParameters>
    </configuration>
    ```

### Cấu hình nhiều thư mục XML { #mapper-xml-in-more-than-one-directory }


## Cấu hình Runtime

Kiểm soát chi phí bộ nhớ của statement cache khi sử dụng `${}`:

=== "Spring Boot (`application.yml`)"

    ```yaml title="application.yml"
    larkbatis:
      max-sql-variants: 64                # Giới hạn số lượng biến thể prepared statement trước khi cảnh báo
      fail-on-unbounded-fragment: false   # Ném exception nếu vượt ngưỡng (khuyến khích bật trên staging)
    ```

=== "System Properties"

    ```console
    -Dlarkbatis.maxSqlVariants=64
    -Dlarkbatis.failOnUnboundedVariants=true
    ```

=== "Java API trực tiếp"

    ```java
    LarkBatisSql.maxSqlVariants(64);
    LarkBatisSql.failOnUnboundedVariants(true);
    ```

| Thuộc tính | Mặc định | Ý nghĩa |
|---|---|---|
| `max-sql-variants` | `64` | Số lượng câu SQL động riêng biệt tối đa cho một statement trước khi phát cảnh báo |
| `fail-on-unbounded-fragment` | `false` | Khi bật `true`, ném `LarkBatisUnboundedVariantsException` thay vì chỉ ghi log cảnh báo |

## Tùy biến Spring `@Configuration` sinh sẵn

| Nhu cầu | Giải pháp |
|---|---|
| Mapper nằm ngoài package quét mặc định | Thêm `-Alarkbatis.springConfigPackage=com.example.app` hoặc khai báo `@Import(LarkBatisMapperConfiguration.class)` |
| Tự cấu hình mapper bean thủ công | Thêm `-Alarkbatis.springConfig=false` để tắt sinh `@Configuration` tự động |
| Dự án có nhiều DataSource | Đánh dấu một `DataSource` là `@Primary`, hoặc tắt auto configuration để tự inject `SpringLarkBatisSession` riêng |

