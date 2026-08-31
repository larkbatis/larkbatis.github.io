# Cài đặt

LarkBatis bao gồm ba artifact chính trong cấu hình build: hai thư viện runtime nhỏ và một annotation processor chỉ chạy lúc biên dịch (không xuất hiện trên runtime classpath của ứng dụng).

| Artifact | Scope | Vai trò |
|---|---|---|
| `io.github.larkbatis:larkbatis-annotations` | `implementation` | Chứa các annotation của mapper (retention `CLASS`, không chứa logic) |
| `io.github.larkbatis:larkbatis-runtime` | `implementation` | `LarkBatisSession`, `LarkBatisTx`, `JdbcCodec`, `SqlFragment` (không phụ thuộc gì ngoài JDBC) |
| `io.github.larkbatis:larkbatis-processor` | `annotationProcessor` | Annotation processor sinh code Java thuần lúc biên dịch |

Phiên bản hiện tại: **`0.1.0`**.

## Yêu cầu môi trường

| Thành phần | Yêu cầu |
|---|---|
| Java | Java 17 trở lên |
| Trình biên dịch | **Chỉ hỗ trợ javac.** Processor phụ thuộc vào cơ chế phân tích AST và multi-round type resolution của javac. Không hỗ trợ ECJ (Eclipse Compiler for Java) |
| Công cụ build | Gradle hoặc Maven. Cần cài đặt thêm build plugin nếu dự án sử dụng mapper XML |
| Database | Mọi cơ sở dữ liệu có JDBC driver chuẩn |

## Cấu hình Gradle

```kotlin title="build.gradle.kts"
plugins {
    java
}

java {
    toolchain { languageVersion = JavaLanguageVersion.of(17) }
}

dependencies {
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0")
    implementation("io.github.larkbatis:larkbatis-runtime:0.1.0")
    annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")
}

tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.add("-parameters") // (1)!
}
```

1.  Cờ `-parameters` yêu cầu `javac` lưu tên tham số thật vào bytecode class file. Nếu thiếu cờ này, các bản build incremental của Gradle có thể truyền class file chứa tên tham số nhân tạo (`arg0`, `arg1`) cho processor, khiến bộ biên dịch không tìm thấy tên tham số cho `#{id}`. Bạn cũng có thể dùng `@Param("...")` trực tiếp trên từng tham số. Xem thêm [Khắc phục sự cố](../usage/troubleshooting.md#what-the-flag-actually-does).

## Cấu hình Maven

```xml title="pom.xml"
<dependencies>
  <dependency>
    <groupId>io.github.larkbatis</groupId>
    <artifactId>larkbatis-annotations</artifactId>
    <version>0.1.0</version>
  </dependency>
  <dependency>
    <groupId>io.github.larkbatis</groupId>
    <artifactId>larkbatis-runtime</artifactId>
    <version>0.1.0</version>
  </dependency>
</dependencies>

<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-compiler-plugin</artifactId>
      <configuration>
        <parameters>true</parameters>
        <annotationProcessorPaths>
          <path>
            <groupId>io.github.larkbatis</groupId>
            <artifactId>larkbatis-processor</artifactId>
            <version>0.1.0</version>
          </path>
        </annotationProcessorPaths>
      </configuration>
    </plugin>
  </plugins>
</build>
```

## Cấu hình Spring Boot

Sử dụng starter tiện ích của Spring Boot, không cần `@MapperScan`:

```kotlin
dependencies {
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0")
    implementation("io.github.larkbatis:larkbatis-spring-boot-starter:0.1.0")
    annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")
}
```

Xem [Spring Boot](spring-boot.md) để biết cách thiết lập chi tiết và [Tích hợp Spring](../usage/spring.md) để hiểu cơ chế hoạt động bên dưới.

## Dự án sử dụng Mapper XML

Nếu bạn định nghĩa câu truy vấn trong file XML thay vì annotation, hãy thêm [build plugin](build-plugins.md) tương ứng. Do annotation processor đọc XML qua file I/O thông thường (ngoài phạm vi `Filer`), build plugin giúp thông báo cho Gradle/Maven biết các file XML là compile input cần theo dõi khi thay đổi:

=== "Gradle"

    ```kotlin
    plugins {
        java
        id("io.github.larkbatis") version "0.1.2"
    }
    ```

=== "Maven"

    ```xml
    <plugin>
      <groupId>io.github.larkbatis</groupId>
      <artifactId>larkbatis-maven-plugin</artifactId>
      <version>0.1.2</version>
      <extensions>true</extensions>
    </plugin>
    ```

## Thứ tự cấu hình khi dùng Lombok

Hãy khai báo `larkbatis-processor` **đứng sau** Lombok trong danh sách `annotationProcessor`. Lombok tạo getter/setter trên AST khi processor của nó chạy; nếu LarkBatis chạy trước, nó sẽ thấy class POJO không có getter/setter nào và báo lỗi:

```kotlin
annotationProcessor("org.projectlombok:lombok")
annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")  // bắt buộc đặt sau Lombok
```

## Bước tiếp theo

[Viết mapper đầu tiên :material-arrow-right:](quick-start.md){ .md-button .md-button--primary }

