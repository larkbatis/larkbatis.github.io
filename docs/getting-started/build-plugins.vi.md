# Build Plugins

Bạn **chỉ cần cấu hình build plugin khi dự án sử dụng mapper XML**. Các dự án chỉ dùng annotation (`@Select`, `@Insert`...) hoàn toàn có thể chạy với `annotationProcessor` mà không cần plugin bổ sung.

## Vai trò của Build Plugin

Annotation processor đọc các file mapper XML bằng `java.io` thông thường (ngoài phạm vi `Filer`). Do `Filer.getResource` không đảm bảo truy cập được thư mục `src/main/resources`, processor cần nhận đường dẫn thư mục thực tế từ tham số dòng lệnh.

Plugin giúp:
1. Đăng ký các file XML làm compilation input để công cụ build (Gradle/Maven) nhận biết khi nào cần biên dịch lại.
2. Tự động truyền tham số `-Alarkbatis.mapperDir` cho `javac`.
3. Tự động thêm `larkbatis-processor` vào cấu hình biên dịch.

Các plugin chỉ hoạt động trong pha build và **không** thêm bất kỳ thư viện nào vào classpath lúc runtime.

## Cấu hình Gradle

```kotlin title="build.gradle.kts"
plugins {
    java
    id("io.github.larkbatis") version "0.1.2"
}

dependencies {
    implementation("io.github.larkbatis:larkbatis-runtime:0.1.0")
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0")
    // larkbatis-processor được plugin tự động thêm vào annotationProcessor
}
```

Tùy biến cấu hình:

```kotlin title="build.gradle.kts"
larkbatis {
    mapperDir = layout.projectDirectory.dir("src/main/mappers")
    mapperDirs.from("src/main/legacy-mappers")   // Khai báo nhiều thư mục mapper
    addProcessorDependency = false               // Tự quản lý phiên bản processor thủ công
    addParametersFlag = false                    // Tắt tự động thêm cờ -parameters (khi đã dùng @Param)
}
```

Plugin Gradle cũng hỗ trợ task `larkbatisScan` để quét mã nguồn MyBatis cũ (xem [Hướng dẫn Migration](../features/migration.md)):

```console
./gradlew larkbatisScan
./gradlew larkbatisScan --args="--summary src/main"
```

## Cấu hình Maven

```xml title="pom.xml"
<build>
  <plugins>
    <plugin>
      <groupId>io.github.larkbatis</groupId>
      <artifactId>larkbatis-maven-plugin</artifactId>
      <version>0.1.2</version>
      <extensions>true</extensions>   <!-- BẮT BUỘC -->
    </plugin>
  </plugins>
</build>
```

Tùy biến cấu hình:

```xml title="pom.xml"
<configuration>
  <mapperDir>src/main/mappers</mapperDir>     <!-- Mặc định: src/main/resources -->
  <mapperDirs>
    <mapperDir>src/main/legacy-mappers</mapperDir>
  </mapperDirs>
  <addProcessorPath>false</addProcessorPath>  <!-- Mặc định: true -->
  <addParameters>false</addParameters>        <!-- Mặc định: true -->
</configuration>
```

### Yêu cầu `<extensions>true</extensions>` trong Maven

Maven cấu hình các plugin trước khi thực thi. `larkbatis-maven-plugin` hoạt động như một Maven Build Extension (`AbstractMavenLifecycleParticipant`) chạy trước khi kế hoạch build được lập.

Extension này:
- Chèn `-Alarkbatis.mapperDir=<dirs>` vào `<compilerArgs>` của `maven-compiler-plugin`.
- Thêm `larkbatis-processor` vào `<annotationProcessorPaths>`.
- Gắn goal `larkbatis:refresh` vào lifecycle `generate-sources`.

Nếu thiếu `<extensions>true</extensions>`, Maven sẽ bỏ qua extension một cách **âm thầm**. Bạn có thể chạy `mvn larkbatis:check` để kiểm tra cấu hình.

### Goal `larkbatis:refresh`

Mặc định `maven-compiler-plugin` chỉ biên dịch lại khi file `.java` bị sửa đổi. Goal `larkbatis:refresh` tính toán hash nội dung của các file XML (lưu tại `target/larkbatis/mapper-xml.properties`) và tự động cập nhật timestamp của file Java interface tương ứng khi XML thay đổi, buộc Maven phải biên dịch lại mapper đó.

### Lưu ý quan trọng khi dùng Maven

!!! warning "Cấu hình cùng các processor khác (Lombok, MapStruct)"

    Khi `<annotationProcessorPaths>` được bật, `javac` sẽ tắt cơ chế tự động quét classpath. Hãy đảm bảo khai báo đầy đủ các processor khác (Lombok, MapStruct...) bên trong khối này.

!!! warning "Lưu ý trên JDK 23+"

    Từ JDK 23, `javac` không còn tự động tìm annotation processor trên compilation classpath. Luôn sử dụng `<annotationProcessorPaths>` hoặc đặt cờ `<proc>full</proc>`.

!!! danger "Không đặt `<useIncrementalCompilation>false</useIncrementalCompilation>`"

    LarkBatis processor là dạng *aggregating*: nó tổng hợp tất cả mapper trong lần biên dịch để tạo ra class `LarkBatisMappers`. Nếu tắt chế độ biên dịch đầy đủ, registry có thể bị thiếu các mapper không thay đổi.

## Giới hạn kỹ thuật

| Giới hạn | Chi tiết |
|---|---|
| Mapper trong test scope | Không hỗ trợ: mappers thuộc về `src/main/java`. Code kiểm thử gọi mapper như các class Java thông thường |
| Dự án multi-module | Xử lý theo từng module độc lập: file XML và interface mapper phải thuộc cùng một module compilation |
| Ký tự phân cách | Không đặt dấu phẩy trong tên thư mục `mapperDir` vì dấu phẩy được dùng để phân tách danh sách thư mục |

## Trường hợp không dùng Plugin

Nếu bạn muốn cấu hình thủ công mà không dùng plugin, bạn có thể tự truyền cờ `-Alarkbatis.mapperDir=src/main/resources` trong `compilerArgs`. Tuy nhiên, bạn sẽ cần chạy `mvn clean` hoặc `./gradlew clean` khi chỉnh sửa XML để đảm bảo code được sinh lại đầy đủ.

