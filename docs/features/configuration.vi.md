# Cấu hình

LarkBatis có ba vị trí cấu hình, được phân chia rõ ràng dựa trên *thời điểm* chúng có hiệu lực: tuỳ chọn processor lúc biên dịch, thiết lập runtime khi khởi động, và cấu hình build plugin nằm ở giữa.

## Tuỳ chọn cho Processor

Được truyền cho javac dưới dạng tham số `-A<name>=<value>`.

| Tuỳ chọn | Ý nghĩa | Mặc định |
|---|---|---|
| `larkbatis.registryPackage` | Package cho class `LarkBatisMappers` sinh ra | Tiền tố package chung của tất cả các mapper |
| `larkbatis.mapperDir` | Các thư mục chứa mapper XML, phân tách bằng dấu phẩy hoặc dấu phân cách đường dẫn hệ thống. Chỉ một tham số duy nhất dù có bao nhiêu thư mục, vì javac chỉ giữ lại tham số `-A` cuối cùng nếu lặp lại cùng một tên. Chỉ những tệp có phần tử gốc là `<mapper>` mới được đọc | Build plugin tự động gán là `src/main/resources` |
| `larkbatis.mapUnderscoreToCamelCase` | Khi đặt `false`, dấu gạch dưới sẽ có ý nghĩa phân biệt khi khớp nhãn cột với thuộc tính (giống mặc định cũ của MyBatis). Giá trị khác `true` hoặc `false` sẽ báo lỗi build | `true` |
| `larkbatis.typeHandlers` | Khai báo type handler mặc định cho từng kiểu Java, dạng cặp `javaType:handlerClass` phân tách bằng dấu phẩy. Đây là giải pháp thay thế khối `<typeHandlers>` lúc build | Không có |
| `larkbatis.springConfig` | Khi đặt `false`, ngăn chặn việc tự động sinh class `@Configuration` cho Spring | Tự động sinh khi tìm thấy `spring-context` trên classpath biên dịch |
| `larkbatis.springConfigPackage` | Package cho class `LarkBatisMapperConfiguration` sinh ra | Giống `registryPackage` |

=== "Gradle"

    ```kotlin
    tasks.withType<JavaCompile>().configureEach {
        options.compilerArgs.add("-Alarkbatis.registryPackage=com.example.app")
    }
    ```

=== "Maven"

    ```xml
    <configuration>
      <compilerArgs>
        <arg>-Alarkbatis.registryPackage=com.example.app</arg>
      </compilerArgs>
    </configuration>
    ```

!!! warning "Tự cấu hình `mapperDir` thủ công sẽ mất khả năng theo dõi file đầu vào"

    Mặc dù code sinh ra vẫn chính xác, nhưng công cụ build không biết các tệp XML là input biên dịch. Do đó, nếu chỉ chỉnh sửa tệp XML thì code có thể không được sinh lại tự động. Khi đó bạn cần chạy `clean` trước, hoặc sử dụng [build plugin](../getting-started/build-plugins.vi.md).

### Quy ước đặt tên cột { #column-naming }

Mặc định, cột `created_at` sẽ tự động khớp với setter `setCreatedAt`, và quyết định ánh xạ này được ghi thẳng vào reader sinh sẵn thay vì đọc từ cấu hình lúc runtime. Bạn có thể tắt quy ước này để giữ nguyên hành vi cũ của MyBatis (vốn mặc định tắt):

```
-Alarkbatis.mapUnderscoreToCamelCase=false
```

| | Bật (Mặc định) | Tắt |
|---|---|---|
| `user_name` → `userName` | Khớp | **Không khớp**, thuộc tính giữ giá trị mặc định |
| `@Column("zip_code")` → nhãn `zip_code` | Khớp | Khớp |
| `@Column("zip_code")` → nhãn `zipCode` | Khớp | Không khớp |
| Resolver sinh sẵn | `getColumnLabel(i).replace("_", "").toLowerCase(…)` | `getColumnLabel(i).toLowerCase(…)` |

Việc bật mặc định tính năng này có thể thay đổi hành vi đối với các dự án chuyển đổi từ MyBatis chưa từng cấu hình: các cột trước đây MyBatis bỏ qua nay sẽ được đọc vào đối tượng. Khi tắt tính năng này, quá trình build sẽ **nêu rõ từng cột không thể khớp vào thuộc tính** và thuộc tính bị ảnh hưởng. MyBatis bỏ qua các trường hợp này trong im lặng, và việc nhận giá trị null trên production là điều không mong muốn:

```text
UserMapper.all: mapUnderscoreToCamelCase is off, so these columns reach no property and
their properties keep their defaults: user_name -> userName. Alias the column in the SQL,
or name it with @Column.
```

Khác với MyBatis, quy ước này áp dụng cho **cả hai phía**: khi bật, thuộc tính hoặc `@Column` có tên `usr_email` vẫn khớp với nhãn cột `usrEmail`. MyBatis chỉ loại bỏ dấu gạch dưới trên nhãn cột nên cặp tên này sẽ bị lệch trên MyBatis.

### Type handlers cho toàn bộ project { #type-handlers-for-a-whole-build }

Khối `<typeHandlers>` trong tệp `mybatis-config.xml` cho phép đăng ký handler một lần và áp dụng cho mọi thuộc tính thuộc kiểu đó. Trong LarkBatis, cấu hình tương đương được quyết định trong pha `javac`:

```
-Alarkbatis.typeHandlers=com.example.Money:com.example.MoneyHandler,\
                         com.example.Json:com.example.JsonHandler
```

Mỗi mục cấu hình sẽ áp dụng cho mọi thuộc tính và mọi tham số `#{}` thuộc kiểu dữ liệu đó mà không khai báo handler riêng. Annotation `@Handler` hoặc thuộc tính `typeHandler` trong XML vẫn có độ ưu tiên cao hơn, vì khai báo trực tiếp tại vị trí sử dụng luôn là chỉ định cụ thể nhất.

Mọi mục cấu hình đều được kiểm tra chặt chẽ khi build: cả kiểu dữ liệu Java và class handler đều phải tồn tại trên compilation classpath; class handler phải implement `LarkBatisTypeHandler<ThatType>`, phải là public, cụ thể và có constructor public không tham số. Cấu hình này sinh ra cấu trúc tương tự như khi dùng `@Handler`: một trường `static final` của class handler được gọi trực tiếp.

!!! tip "Cấu hình không sử dụng tới sẽ phát cảnh báo build"

    Nếu bạn đăng ký một kiểu dữ liệu nhưng không có thuộc tính hoặc tham số `#{}` nào trong toàn bộ lần biên dịch sử dụng tới, đây rất có thể là lỗi chính tả trong tên kiểu Java. Trình biên dịch sẽ phát cảnh báo nhắc nhở thay vì bỏ qua trong im lặng.

| Điểm khác biệt với MyBatis | Chi tiết |
|---|---|
| Quét tự động `<package name="…"/>`, `@MappedTypes` | Không quét tự động. Từng cặp kiểu - handler được khai báo tường minh, giúp danh sách rõ ràng và dễ đọc |
| Phần `jdbcType` trong registry `(javaType, jdbcType)` | Reader sinh sẵn đã biết chính xác cột cần đọc, không cần phân biệt dựa trên JDBC type |
| Registry tra cứu lúc runtime | Handler được biên dịch thẳng vào mã nguồn. Không còn bất kỳ bước tra cứu nào lúc chạy |

## Cờ trình biên dịch quan trọng

| Cờ | Lý do |
|---|---|
| `-parameters` | Tính năng build tăng dần của Gradle sẽ chạy lại aggregating processor trên các **tệp .class**, nơi tên tham số chỉ được lưu giữ nếu có cờ này. Không có cờ này, tham số `#{id}` không thể resolve được. Giải pháp thay thế là gắn `@Param` cho mọi tham số |

## Cấu hình Build Plugin

=== "Gradle"

    ```kotlin
    larkbatis {
        mapperDir = layout.projectDirectory.dir("src/main/mappers")
        addProcessorDependency = false   // Tu quan ly phien ban cua processor
        addParametersFlag = false        // Ban da tu truyen -parameters hoac dung @Param o moi noi
    }
    ```

=== "Maven"

    ```xml
    <configuration>
      <mapperDir>src/main/mappers</mapperDir>     <!-- Mac dinh: src/main/resources -->
      <addProcessorPath>false</addProcessorPath>  <!-- Mac dinh: true -->
      <addParameters>false</addParameters>        <!-- Mac dinh: true -->
    </configuration>
    ```

| Cấu hình | Mặc định | Ý nghĩa |
|---|---|---|
| `mapperDir` / `<mapperDir>` | `src/main/resources` | Một thư mục chứa mapper XML |
| `mapperDirs` / `<mapperDirs>` | Rỗng | Khai báo nhiều thư mục, xem bên dưới |
| `addProcessorDependency` / `<addProcessorPath>` | `true` | Tự động thêm `larkbatis-processor` vào annotation processor path |
| `addParametersFlag` / `<addParameters>` | `true` | Tự động bật cờ `-parameters`. Tắt tuỳ chọn này đòi hỏi phải có `@Param` trên từng tham số mapper. Maven tôn trọng thẻ `<parameters>false</parameters>` tường minh và sẽ phát cảnh báo thay vì ghi đè |

Với Maven, bạn bắt buộc phải khai báo `<extensions>true</extensions>` trên plugin. Nếu thiếu, plugin sẽ không hoạt động và không có thông báo lỗi. Xem [Build Plugin](../getting-started/build-plugins.md).

### Khai báo Mapper XML trong nhiều thư mục { #mapper-xml-in-more-than-one-directory }

Tương đương với khối `<mappers>` hoặc cấu hình `mybatis.mapper-locations` trong MyBatis. Dùng danh sách thư mục thay vì Ant pattern, vì quá trình quét diễn ra lúc build trên hệ thống tệp chứ không phải lúc khởi động trên classpath:

=== "Gradle"

    ```kotlin
    larkbatis {
        mapperDirs.from("src/main/mappers", "src/main/legacy-mappers")
    }
    ```

=== "Maven"

    ```xml
    <configuration>
      <mapperDirs>
        <mapperDir>src/main/mappers</mapperDir>
        <mapperDir>src/main/legacy-mappers</mapperDir>
      </mapperDirs>
    </configuration>
    ```

Từng thư mục được quét đệ quy, toàn bộ tệp XML được đăng ký làm input biên dịch và chuyển đến javac trong một tuỳ chọn `-Alarkbatis.mapperDir` duy nhất.

| Quy tắc | Chi tiết |
|---|---|
| Dùng cả hai cấu hình | `mapperDir` được quét trước, sau đó đến danh sách `mapperDirs` |
| Một thư mục được khai báo hai lần | Chỉ quét một lần để tránh báo lỗi trùng lặp namespace |
| Giá trị mặc định `src/main/resources` | Chỉ áp dụng khi không cấu hình cả hai tuỳ chọn trên. Nhờ đó việc liệt kê danh sách thư mục không vô tình đưa thêm thư mục resources vào |
| Một namespace xuất hiện ở hai thư mục | Báo lỗi biên dịch, không áp dụng cơ chế ghi đè (last-one-wins). Hai tệp xung đột về cùng một mapper và trình biên dịch không thể tự quyết định tệp nào đúng |
| Thư mục không tồn tại | Phát cảnh báo build. Lệnh `mvn larkbatis:check` liệt kê mọi thư mục đã resolve và đánh dấu thư mục bị thiếu |
| Thư mục nằm ngoài module | Được phép sử dụng nhưng hiếm khi cần thiết: mọi namespace tìm thấy vẫn phải trỏ tới một mapper interface được biên dịch *tại module này* |

!!! warning "Không hỗ trợ nạp Mapper XML từ dependency jar"

    Các mẫu tìm kiếm dạng `classpath*:` là cơ chế lúc khởi động runtime. Mapper interface nằm trong một thư mục jar phụ thuộc đã được sinh code cùng với XML của chính nó khi jar đó được đóng gói, do đó không còn gì cho dự án hiện tại quét lại.

## Thiết lập Runtime

Chỉ có hai thiết lập, cả hai đều nhằm kiểm soát chi phí vận hành của `${}`: bộ nhớ cache của statement được định danh bằng chuỗi câu SQL, do đó một fragment có tập giá trị không giới hạn sẽ khiến cache phình to không điểm dừng.

=== "Spring Boot"

    ```yaml title="application.yml"
    larkbatis:
      max-sql-variants: 64
      fail-on-unbounded-fragment: false
    ```

=== "System properties"

    ```console
    -Dlarkbatis.maxSqlVariants=64
    -Dlarkbatis.failOnUnboundedVariants=true
    ```

=== "Bằng code Java"

    ```java
    LarkBatisSql.maxSqlVariants(64);
    LarkBatisSql.failOnUnboundedVariants(true);
    ```

| Thiết lập | Mặc định | Tác vụ |
|---|---|---|
| `max-sql-variants` | `64` | Số lượng chuỗi SQL riêng biệt tối đa mà một statement được phép sinh ra trước khi LarkBatis cảnh báo |
| `fail-on-unbounded-fragment` | `false` | Khi đặt `true`, ném `LarkBatisUnboundedVariantsException` thay vì chỉ ghi log một dòng cảnh báo |

Cả hai thuộc tính đều được định nghĩa trong `META-INF/spring-configuration-metadata.json` của `larkbatis-spring-boot-autoconfigure`, giúp IDE tự động gợi ý và phát hiện lỗi gõ sai trong `application.yml`.

Ngưỡng giới hạn **chỉ kích hoạt đúng một lần cho mỗi statement**: khi đã vượt ngưỡng, bộ đếm dừng lưu giữ thêm chuỗi SQL mới để tránh làm tăng bộ nhớ cho trường hợp đã vượt tầm kiểm soát.

!!! tip "Cấu hình giá trị khác nhau theo từng môi trường"

    Môi trường production chỉ nên ghi log, không nên ném lỗi: hệ thống đang vận hành không nên bị dừng chỉ vì một xu hướng cần cảnh báo. Môi trường staging nên bật ném lỗi để lập trình viên phát hiện sớm các đoạn fragment không giới hạn. Việc đặt `fail-on-unbounded-fragment: true` trong cấu hình staging là cách tiếp cận chuẩn mực.

## Các tính năng không triển khai

| Tính năng | Lý do |
|---|---|
| `log-sql` | Đòi hỏi mọi phương thức sinh ra phải có nhánh rẽ kiểm tra log. Việc ghi log SQL thuộc tầng driver hoặc connection pool: `net.ttddyy:datasource-proxy`, p6spy |
| `ExecutorType`, cấu hình cache, `defaultStatementTimeout`, `lazyLoadingEnabled`,... | Không có executor, không có cache, không hỗ trợ lazy loading. Xem [Khác biệt với MyBatis](mybatis-differences.vi.md) |
| Chọn `DataSource` theo từng mapper | Tạm hoãn. Khai báo một `SpringLarkBatisSession` cho từng `DataSource` và tự viết phương thức `@Bean` khởi tạo mapper |

## Tích hợp Spring: Tuỳ biến class `@Configuration` sinh sẵn

| Tình huống | Cách xử lý |
|---|---|
| Mapper nằm ngoài các package được quét | Thêm cờ `-Alarkbatis.springConfigPackage=com.example.app`, hoặc dùng `@Import(LarkBatisMapperConfiguration.class)` |
| Muốn tự khai báo các mapper bean thủ công | Thêm cờ `-Alarkbatis.springConfig=false` |
| Ứng dụng có nhiều hơn một `DataSource` | Cơ chế auto-configuration có điều kiện `@ConditionalOnSingleCandidate` sẽ tự lùi lại thay vì đoán mò. Đánh dấu một datasource là `@Primary`, hoặc tắt class cấu hình sinh sẵn |
