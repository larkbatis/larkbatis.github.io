# Java Module (JPMS)

`larkbatis-annotations` và `larkbatis-runtime` phát hành dưới dạng **module có tên
thật**, không phải automatic module, và ba artifact Spring cũng vậy. Code mapper sinh ra
dùng được từ một consumer modular, và module path không hề có split package. Đây là một
yêu cầu thiết kế của dự án, không phải thứ có thì tốt.

| Artifact | Tên module |
|---|---|
| `larkbatis-annotations` | `io.github.larkbatis.annotations` |
| `larkbatis-runtime` | `io.github.larkbatis.runtime` |
| `larkbatis-spring` | `io.github.larkbatis.spring` |
| `larkbatis-spring-boot-autoconfigure` | `io.github.larkbatis.spring.boot` |
| `larkbatis-spring-boot-starter` | `io.github.larkbatis.spring.boot.starter` |

`larkbatis-processor` chỉ dùng lúc build và không bao giờ xuất hiện trên module path.

## Bản mô tả phía consumer

Ba chỉ thị, và cái thứ ba mới là cái làm người ta bất ngờ:

```java title="module-info.java"
module com.example.app {
    requires io.github.larkbatis.runtime;             // (1)!
    requires static io.github.larkbatis.annotations;  // (2)!
    requires static java.compiler;                     // (3)!
}
```

1.  Những gì phần thân sinh ra thực sự gọi tới: `LarkBatisSession`, `JdbcCodec`,
    `RowReader`, `LarkBatisSql`.
2.  Mọi annotation của mapper đều có retention `CLASS`, nên đây chỉ là một cạnh phụ
    thuộc lúc biên dịch.
3.  Mọi file nguồn phát ra đều mang `@javax.annotation.processing.Generated`, nằm trong
    `java.compiler`. Retention `SOURCE` khiến nó thành `static`.

!!! failure "`package javax.annotation.processing is not visible`"

    Đây là thứ bạn nhận được khi thiếu `requires static java.compiler`, và thông báo lỗi
    lại trỏ vào file **được sinh ra**, nên lần đầu gặp rất dễ rối. Cứ thêm chỉ thị đó vào.

## Những thứ bạn *không* cần

- **`requires java.sql`**: `io.github.larkbatis.runtime` đã requires nó *transitive*,
  vì API của chính nó đưa cho bạn `Connection`, `ResultSet` và `PreparedStatement`. Một
  module đọc được runtime thì đã gọi tên được các kiểu đó rồi.
- **`opens`, ở bất cứ đâu**: không module LarkBatis nào cần tới. Chẳng có reflection
  nào để mà mở cho ai cả.
- **một `exports` cho code sinh ra**: nó nằm trong chính package của bạn, ngay cạnh
  interface mapper mà nó hiện thực.

## JDBC driver của bạn có thể cần chỉ thị riêng

Đó là việc của driver, không phải của tầng mapper, nhưng nó vẫn sẽ đáp xuống
`module-info.java` của bạn. H2 là ví dụ hay gặp:

```java
module com.example.app {
    requires io.github.larkbatis.runtime;
    requires static io.github.larkbatis.annotations;
    requires static java.compiler;

    // automatic module, tên lấy từ manifest của jar — kiểm tra lại bằng
    // `jar --describe-module` sau mỗi lần nâng cấp
    requires com.h2database;

    // JdbcDataSource của H2 hiện thực javax.naming.Referenceable, mà một automatic
    // module thì không khai báo requires của riêng nó được, nên consumer phải đọc
    // java.naming thay cho nó.
    requires java.naming;
}
```

Một automatic module không khai báo được `requires` của riêng mình, nên mọi thứ nó cần
mà nền tảng không cho sẵn đều trở thành việc của consumer. Hãy chạy
`jar --describe-module` với jar của driver sau mỗi lần nâng cấp, vì tên của một automatic
module lấy từ manifest và có thể đổi.

## Native image

Tầng mapper chẳng có gì để khai báo. Không `Proxy.newProxyInstance`, không
`Class.forName`, không `setAccessible` ở bất cứ đâu trong runtime hay trong code sinh
ra, nên cũng không có metadata reachability nào phải viết. JDBC driver của bạn thì vẫn
có thể kèm theo hoặc cần metadata riêng, và đó là chuyện của driver.

!!! warning "Chưa được kiểm chứng bằng một bản build thật"

    Khẳng định đó mang tính cấu trúc, và có thể tự kiểm bằng cách đọc code. Nhưng bản
    build native image thì **vẫn chưa từng chạy**; đó là phần việc M5 còn treo. Hãy coi
    nó là một kỳ vọng có cơ sở chứ chưa phải một kết quả. Xem
    [Hiệu năng](../wiki/performance.md#native-image).

Module `larkbatis-sample` của repository lõi là một consumer modular chạy được, và cũng
là đối tượng dự kiến của bài kiểm tra đó.
