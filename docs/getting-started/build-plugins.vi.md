# Plugin build

Bạn **chỉ cần plugin build khi có statement nằm trong mapper XML**. Một project thuần
annotation chạy được chỉ với annotation processor.

## Vì sao lại phải có plugin

Processor đọc mapper XML bằng `java.io` thuần, không qua `Filer` của trình biên dịch.
Đó không phải một lối tắt: đặc tả của `Filer.getResource` không đảm bảo với tới được các
file dưới `src/main/resources`, còn những bản hiện thực có với tới được thì lại không
thống nhất cách làm. Vậy nên processor nhận vào một đường dẫn thư mục thật, và phải có ai
đó đưa cho nó đường dẫn ấy *đồng thời* báo cho công cụ build biết những file XML đó là
đầu vào biên dịch, nếu không thì sửa mỗi XML sẽ không kích hoạt sinh lại code.

Đó là toàn bộ nhiệm vụ của cả hai plugin. Không plugin nào tự sinh code, và không plugin
nào thêm bất cứ thứ gì vào classpath lúc chạy của ứng dụng.

## Gradle

```kotlin title="build.gradle.kts"
plugins {
    java
    id("io.github.larkbatis") version "0.1.2"
}

dependencies {
    implementation("io.github.larkbatis:larkbatis-runtime:0.1.0")
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0")
    // larkbatis-processor tự động được đưa vào annotationProcessor
}
```

Nó làm gì, và chỉ làm đúng những việc này:

- truyền `-Alarkbatis.mapperDir=<dirs>` cho `compileJava` (mặc định
  `src/main/resources`; chỉ những file có phần tử gốc là `<mapper>` mới được đọc, nên
  XML khác trong cùng cây thư mục bị bỏ qua),
- đăng ký các file mapper XML làm đầu vào của `compileJava`, để sửa một mapper thì các
  mapper được biên dịch lại,
- thêm `io.github.larkbatis:larkbatis-processor` vào configuration
  `annotationProcessor`.

```kotlin title="Cấu hình"
larkbatis {
    mapperDir = layout.projectDirectory.dir("src/main/mappers")
    mapperDirs.from("src/main/legacy-mappers")   // thêm bao nhiêu thư mục cũng được
    addProcessorDependency = false               // tự quản phiên bản processor
    addParametersFlag = false                    // chỉ khi mọi tham số đều có @Param
}
```

Plugin cũng đăng ký `larkbatisScan`, tức [báo cáo migration](../features/migration.md),
chạy trên chính project này:

```console
./gradlew larkbatisScan
./gradlew larkbatisScan --args="--summary src/main"
```

## Maven

```xml title="pom.xml"
<build>
  <plugins>
    <plugin>
      <groupId>io.github.larkbatis</groupId>
      <artifactId>larkbatis-maven-plugin</artifactId>
      <version>0.1.2</version>
      <extensions>true</extensions>   <!-- bắt buộc -->
    </plugin>
  </plugins>
</build>
```

```xml title="Cấu hình (đều là tuỳ chọn)"
<configuration>
  <mapperDir>src/main/mappers</mapperDir>     <!-- mặc định: src/main/resources -->
  <mapperDirs>                                <!-- thêm bao nhiêu thư mục cũng được -->
    <mapperDir>src/main/legacy-mappers</mapperDir>
  </mapperDirs>
  <addProcessorPath>false</addProcessorPath>  <!-- mặc định: true -->
  <addParameters>false</addParameters>        <!-- mặc định: true -->
</configuration>
```

### `<extensions>true</extensions>` không phải tuỳ chọn

Maven chốt cấu hình của mọi mojo **trước khi mojo đầu tiên của một project chạy**, nên
một mojo gắn vào pha sớm cũng không thể thêm tham số biên dịch vào execution `compile`.
Vì thế plugin hoạt động như một build extension
(`AbstractMavenLifecycleParticipant`), chạy trước khi kế hoạch thực thi được tính.
Với mỗi project khai báo nó, extension sẽ:

- chèn `-Alarkbatis.mapperDir=<dirs>` vào `<compilerArgs>` của
  `maven-compiler-plugin` (bỏ qua nếu tuỳ chọn đó đã được truyền tay),
- nối `larkbatis-processor` vào `<annotationProcessorPaths>`, tự tạo phần tử này nếu
  chưa có,
- gắn `larkbatis:refresh` vào `generate-sources`,
- đặt property `larkbatis.mapperDir` cho project.

Cả hai lần chèn đều nhắm vào **mọi execution gắn với `compile`** của compiler plugin,
chứ không chỉ khối `<configuration>` ở cấp plugin. Maven sao chép cấu hình cấp plugin vào
các execution đó ngay khi đọc project, trước khi bất kỳ extension nào chạy, và cái mà kế
hoạch dùng chính là cấu hình riêng của execution.

Thiếu `<extensions>true</extensions>` thì không việc nào ở trên xảy ra, và **xảy ra
trong im lặng**. Chạy `mvn larkbatis:check` để chẩn đoán trường hợp đó.

### Goal `refresh`

`maven-compiler-plugin` chỉ biên dịch lại dựa trên file `.java` đã cũ, nên sửa mỗi XML
thì mặc định chẳng thay đổi gì. `larkbatis:refresh` chạm vào file nguồn của interface
mapper có nội dung XML thay đổi kể từ lần build trước. Việc phát hiện thay đổi dựa trên
**băm nội dung** (ghi trong `target/larkbatis/mapper-xml.properties`), không dựa trên
mốc thời gian, nên cả file đề ngày tương lai lẫn đồng hồ hệ thống file thô đều không
đánh lừa được nó. Goal này chạy theo kiểu cố gắng hết sức: lỗi IO chỉ thành cảnh báo,
không bao giờ làm hỏng bản build.

### Ba điều đáng biết

!!! warning "Các annotation processor khác"

    Nếu trước đó `<annotationProcessorPaths>` chưa tồn tại, việc tạo nó ra sẽ chuyển
    javac từ chế độ tự tìm processor trên classpath sang chỉ dùng đường dẫn khai báo
    tường minh. Hãy thêm các processor khác của bạn (Lombok, MapStruct, …) vào đó, hoặc
    đặt `<addProcessorPath>false</addProcessorPath>` và tự quản các đường dẫn.

!!! warning "`addProcessorPath=false` trên JDK 23+"

    javac không còn tự tìm processor từ classpath biên dịch nữa, và
    `-Alarkbatis.mapperDir` cũng không được tính là lời yêu cầu xử lý annotation. Nếu
    bạn chọn không dùng và đặt `larkbatis-processor` lên classpath thay thế, hãy thêm nó
    vào `<annotationProcessorPaths>` hoặc tự đặt `<proc>full</proc>`. Nếu không, bạn sẽ
    chẳng có mapper nào được sinh ra mà cũng chẳng có lỗi nào báo.

!!! danger "Đừng đặt `<useIncrementalCompilation>false</useIncrementalCompilation>`"

    Processor này thuộc loại *aggregating*: nó ghi ra một registry `LarkBatisMappers`
    duy nhất liệt kê mọi mapper trong lần biên dịch. Hành vi mặc định của compiler plugin
    là biên dịch lại toàn bộ mã nguồn ngay khi có một file cũ đi, và chính điều đó làm
    cho registry kia đầy đủ. Chỉ biên dịch những file đã cũ sẽ sinh lại nó từ một góc
    nhìn thiếu.

## Giới hạn chung của cả hai plugin

| | |
|---|---|
| Mapper trong scope test | Không hỗ trợ. Chỉ `compileJava` / execution `compile` được nối dây. Interface mapper thuộc về `src/main/java`; mã test dùng chúng như lớp bình thường |
| Build nhiều module | Mọi thứ đều theo từng project. Một mapper XML phải nằm cùng module với interface mà `namespace` của nó gọi tên; cái nào trỏ đi nơi khác sẽ bị bỏ qua kèm cảnh báo build |
| `mapperDir` có chứa dấu phẩy | Không hỗ trợ; processor coi dấu phẩy là ký tự phân tách giữa các thư mục |
| Thư mục mapper nằm ở module khác | Được phép, nhưng vô ích: một `namespace` phải gọi tên interface được biên dịch trong cùng module, file nào không khớp sẽ bị báo và bỏ qua |

Cách khai báo nhiều thư mục cùng lúc, và quy tắc khi dùng chung với tuỳ chọn số ít, nằm ở
[Cấu hình](../features/configuration.md#mapper-xml-in-more-than-one-directory).

## Làm mà không cần plugin

Truyền tay `-Alarkbatis.mapperDir` vẫn chạy và vẫn sinh ra code đúng. Thứ bạn mất là
việc đăng ký đầu vào: sửa mỗi một file XML có thể sẽ chẳng sinh lại gì cả, nên bạn phải
`clean` trước. Xem [Cấu hình](../features/configuration.md) để có danh sách tuỳ chọn đầy đủ.
