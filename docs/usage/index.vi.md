# Sử dụng

Mọi thứ bạn viết trong LarkBatis chỉ là một trong hai thứ: một **interface mapper** có
các phương thức mang annotation statement, hoặc một interface mapper đánh dấu `@Mapper`
mà statement nằm trong **mapper XML**. Cả hai đều biên dịch ra cùng một lớp hiện thực;
chúng là hai frontend cho cùng một IR, không phải hai đường code khác nhau.

## Hình hài một project

```text
src/main/java/com/example/app/
    User.java                 # lớp kết quả: constructor không tham số, các setter
    UserMapper.java           # statement bằng annotation
    UserSearchMapper.java     # @Mapper — statement nằm trong XML
src/main/resources/mappers/
    UserSearchMapper.xml      # namespace = com.example.app.UserSearchMapper
```

Lúc build, processor phát ra, vào đúng package đó:

```text
UserMapper$$Impl.java              mỗi mapper một file
UserSearchMapper$$Impl.java
UserRow.java                       mỗi lớp kết quả một file
LarkBatisMappers.java             mỗi lần biên dịch một file
LarkBatisMapperConfiguration.java một file, nếu Spring có trên classpath lúc build
```

## Các trang trong mục này

<div class="grid cards" markdown>

-   **[Interface mapper](mappers.md)**

    Annotation statement, tham số `#{}`, `@Param`, lớp kết quả và cách các cột tìm ra
    setter của chúng.

-   **[Mapper XML](xml-mappers.md)**

    `@Mapper`, namespace, id của statement, `<sql>`/`<include>`, và cách một statement
    được gán cho mỗi phương thức.

-   **[SQL động](dynamic-sql.md)**

    `<if>`, `<choose>`, `<where>`, `<set>`, `<trim>`, cùng cái ngữ pháp `test` hẹp thay
    cho OGNL.

-   **[foreach và batch](foreach-and-batches.md)**

    Danh sách `IN`, `VALUES` nhiều dòng, vòng lặp lồng nhau, insert bằng `addBatch()` và
    `@PadPow2`.

-   **[Result map và join](result-maps.md)**

    `<resultMap>`, một cấp `<association>` / `<collection>`, và quy tắc sắp xếp khiến nó
    hoạt động.

-   **[Khoá tự sinh](generated-keys.md)**

    `useGeneratedKeys`, vì sao `keyColumn` lại quan trọng, và việc đếm khoá ở chế độ
    batch.

-   **[Stream kết quả](streaming.md)**

    Kiểu trả về `Stream<T>` trên một con trỏ đang mở, và ai là người sở hữu tài nguyên.

-   **[Transaction](transactions.md)**

    Ngữ nghĩa bỏ-phiếu-để-commit của `LarkBatisTx`, việc lồng nhau, và `@Transactional`.

-   **[SQL thô và SqlFragment](raw-sql.md)**

    Kỷ luật `${}`, `@OrderBy`, cửa thoát hiểm, và việc theo dõi biến thể SQL.

-   **[Kiểu dữ liệu và handler](types.md)**

    `#{}` tự gắn được những gì, `JdbcCodec`, `@Column`, `@Handler`, enum và `java.time`.

-   **[Tích hợp Spring](spring.md)**

    Những gì `mybatis-spring` làm mà LarkBatis không cần, và những gì nó vẫn còn làm.

-   **[Xử lý sự cố](troubleshooting.md)**

    Không sinh ra gì, tên tham số thành `arg0`, thứ tự Lombok, XML không được nhận.

</div>

## Hai quy tắc giải thích gần hết những điều bất ngờ

**1 · Quyết định được lúc build thì quyết định luôn.** Chỉ số cột, lựa chọn type
handler, tiền tố của `<trim>`, thân của `<include>`, việc một phép so sánh là trên `long`
hay `String`: không thứ nào trong đó bị đem ra soi lúc chạy. Nghĩa là sai ở bất kỳ chỗ
nào trong số đó đều là lỗi biên dịch chứ không phải một stack trace, và thông báo lỗi
gọi đúng tên phương thức mapper.

**2 · Không quyết định được thì phải nói ra tường minh.** Danh sách những thứ được resolve
lúc chạy là ngắn và đóng: giá trị tham số, kết quả boolean của các test
`<if>`/`<when>`, kích thước tập hợp trong `<foreach>`, các dòng trong `ResultSet`, số
cột thật khi không phân tích được select list, và nội dung của một `SqlFragment`. Bất cứ
thứ gì bạn muốn mà không nằm trong danh sách đó đều phải được viết rõ trong chữ ký của
phương thức mapper. Đó là lý do một `String` bind vào `${}` là lỗi biên dịch, chứ không
phải chuyện cho qua.

Phát biểu đầy đủ về ranh giới này nằm trong wiki:
[Shape và value](../wiki/shape-vs-value.md).
