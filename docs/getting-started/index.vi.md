# Cài đặt

LarkBatis là ba artifact trên bản build của bạn: hai jar runtime nhỏ và một annotation
processor không bao giờ lọt ra classpath ứng dụng.

| Artifact | Scope | Là gì |
|---|---|---|
| `io.github.larkbatis:larkbatis-annotations` | `implementation` | Các annotation cho mapper. Không chứa logic, retention `CLASS` |
| `io.github.larkbatis:larkbatis-runtime` | `implementation` | `LarkBatisSession`, `LarkBatisTx`, `JdbcCodec`, `SqlFragment`. Không phụ thuộc gì ngoài JDBC |
| `io.github.larkbatis:larkbatis-processor` | `annotationProcessor` | Bộ sinh code. Chỉ dùng lúc build: tuyệt đối không được xuất hiện trên classpath lúc chạy |

Phiên bản hiện tại: **`0.1.0`**.

## Yêu cầu

| | |
|---|---|
| Java | 17 trở lên (bản thân dự án build trên toolchain Java 17) |
| Trình biên dịch | **Chỉ javac.** Processor phụ thuộc vào hành vi của javac: thứ tự khai báo của các phần tử, và việc resolve nhiều vòng cho kiểu được sinh ra. ECJ / Eclipse batch compilation không được hỗ trợ |
| Công cụ build | Gradle hoặc Maven. Chỉ cần plugin build nếu bạn dùng mapper XML |
| Database | Bất cứ thứ gì có JDBC driver |

## Gradle

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

1.  Cờ này bảo javac giữ lại tên tham số thật trong file class. Thiếu nó, một bản build
    incremental của Gradle có thể đưa cho processor một phương thức mapper mà tham số tên
    là `arg0`, `arg1`, khiến `#{id}` không còn gì để đối chiếu. Đặt tên cho từng tham số
    bằng `@Param("...")` cũng được.
    [Xử lý sự cố](../usage/troubleshooting.md#what-the-flag-actually-does) giải thích vì
    sao build sạch lại giấu mất vấn đề này.

## Maven

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

## Spring Boot

Một starter thay cho cả ba khai báo ở trên, và không cần `@MapperScan`:

```kotlin
dependencies {
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0")
    implementation("io.github.larkbatis:larkbatis-spring-boot-starter:0.1.0")
    annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")
}
```

Xem [Spring Boot](spring-boot.md) để có phần thiết lập đầy đủ và
[Tích hợp Spring](../usage/spring.md) để biết bên dưới nó chạy thế nào.

## Mapper XML

Nếu có statement nào của bạn nằm trong mapper XML thay vì trong annotation, hãy thêm
[plugin build](build-plugins.md) tương ứng với công cụ build của bạn. Processor đọc
mapper XML bằng `java.io` thuần, nằm ngoài `Filer` của trình biên dịch, bởi vì đặc tả của
`Filer.getResource` không đảm bảo với tới được `src/main/resources`. Vì vậy phải nói cho
công cụ build biết rằng những file đó là đầu vào biên dịch.

=== "Gradle"

    ```kotlin
    plugins {
        java
        id("io.github.larkbatis") version "0.1.0"
    }
    ```

=== "Maven"

    ```xml
    <plugin>
      <groupId>io.github.larkbatis</groupId>
      <artifactId>larkbatis-maven-plugin</artifactId>
      <version>0.1.0</version>
      <extensions>true</extensions>
    </plugin>
    ```

## Dùng chung với Lombok

Hãy khai báo `larkbatis-processor` **sau** `org.projectlombok:lombok`. Lombok ghi
getter và setter của nó vào AST khi processor của chính nó chạy, còn javac thì chạy các
processor tìm được theo đúng thứ tự trên classpath. Khai báo trước, LarkBatis sẽ nhìn
thấy một lớp kết quả không có lấy một accessor nào.

```kotlin
annotationProcessor("org.projectlombok:lombok")
annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")  // sau
```

Lỗi build có nêu đúng vấn đề khi nó phát hiện annotation của Lombok trên lớp đó, nhưng
cách sửa vẫn chỉ là một dòng thứ tự này.

## Tiếp theo

[Viết mapper đầu tiên :material-arrow-right:](quick-start.md){ .md-button .md-button--primary }
