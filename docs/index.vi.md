---
hide:
  - navigation
---

# LarkBatis

**Một MyBatis biên dịch sẵn.** Câu SQL, vị trí tham số, lựa chọn type handler, ánh xạ cột
sang setter, cây SQL động: mọi thứ suy ra được từ *shape* của một mapper đều được bộ sinh
code xử lý xong ngay lúc build. Chạy thật lúc runtime chỉ còn các lớp mapper Java thuần đã
sinh sẵn cộng một lớp JDBC mỏng, khoảng 1.500 dòng, không phụ thuộc gì ngoài JDBC, không
reflection, không proxy, không OGNL.

Bạn giữ nguyên mô hình lập trình MyBatis đang có: interface mapper, tham số `#{}`, mapper
XML, `<if>`/`<where>`/`<foreach>`, `<resultMap>`. Thứ mất đi là trình thông dịch nằm bên
dưới.

```java
public interface UserMapper {

    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);
}
```

Bản build sinh ra `UserMapper$$Impl`, và đó là code bạn đọc được và đặt breakpoint được:

```java
@Override
public User findById(long id) {
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(SQL_findById)) {
        ps.setLong(1, id);
        try (ResultSet rs = ps.executeQuery()) {
            return rs.next() ? UserRow.read(rs) : null;
        }
    } catch (SQLException e) {
        throw s.translate(e, SQL_findById);
    } finally {
        s.release(c);
    }
}
```

<div class="grid cards" markdown>

-   :material-rocket-launch: **[Bắt đầu](getting-started/index.md)**

    Cài annotations, runtime và annotation processor, rồi viết mapper đầu tiên.

-   :material-book-open-variant: **[Sử dụng](usage/index.md)**

    Interface mapper, mapper XML, SQL động, `<foreach>`, result map, khoá tự sinh,
    stream, transaction.

-   :material-sitemap: **[Wiki](wiki/index.md)**

    Kiến trúc hai pha hoạt động ra sao, code sinh ra trông thế nào, và vì sao mỗi lằn
    ranh thiết kế lại được vạch ở đúng chỗ đó.

-   :material-checkbox-multiple-marked: **[Tính năng](features/index.md)**

    Bảng hỗ trợ: LarkBatis làm được gì, thu hẹp cái gì, và cố ý bỏ cái gì.

</div>

## Vì sao

MyBatis resolve một lời gọi mapper lúc chạy. Mỗi truy vấn phải đi qua một JDK proxy, một
lần OGNL đánh giá từng `<if test>`, và một lần tra `TypeHandler` cho mỗi tham số. Rồi tới
phần đắt nhất: mỗi cột trên mỗi dòng là một lần `setValue` bằng reflection, và mỗi lần như
vậy lại cấp phát một `PropertyTokenizer` cùng một `Object[]` trước khi tới được thứ thực
chất chỉ là một lệnh `putfield`.

Không phần nào trong đó phụ thuộc vào giá trị. Chúng phụ thuộc vào *shape* của mapper, mà
shape thì cố định ngay từ lúc bạn lưu file. LarkBatis resolve shape một lần, lúc build,
rồi phát ra thẳng các lời gọi JDBC.

| | MyBatis | LarkBatis |
|---|---|---|
| Số dòng nằm trên classpath lúc chạy | ~40.000 | ~1.500 |
| Phụ thuộc lúc chạy | ognl, javassist | không gì ngoài JDBC |
| Reflection trên đường truy vấn nóng | 4 nhóm call site | không |
| Thao tác reflection mỗi dòng | 1 mỗi cột | không |
| Metadata `native-image` viết tay | bắt buộc | không cần[^1] |
| Sai kiểu tham số bị bắt lúc | chạy | biên dịch |
| Rà soát chỗ chèn SQL thô | đọc từng mapper | một lệnh `grep` cho `unsafeRawSql` |

[^1]: Đây là hệ quả cấu trúc: không có reflection nào để mà khai báo. Nhưng bản build
    native image thì vẫn chưa chạy lần nào; xem
    [Hiệu năng](wiki/performance.md#native-image).

Lợi ích hiệu năng là có thật nhưng hẹp, và cần nói thẳng nó áp dụng ở đâu. Đo với MyBatis
3.5.19 trên JDK 21, đọc 10.000 dòng 12 cột giảm từ **3,38 ms và 10,2 MB cấp phát xuống
0,54 ms và 1,88 MB**. Tính trên mỗi dòng, 338 ns và 1.018 B thành 54 ns và 188 B. Thời
gian khởi động nguội tới dòng đầu tiên giảm từ 61,8 ms xuống 6,3 ms.

Nửa còn lại được đo qua socket thật chứ không phỏng đoán. Một `findById` trả về một dòng
mất **94,2 µs trên MyBatis và 89,2 µs trên LarkBatis**: chênh năm phần trăm, đo trên TCP
loopback, tức là round trip rẻ nhất có thể có. Một database thật chỉ làm khoảng cách đó
hẹp thêm. **LarkBatis đáng tiền cho truy vấn báo cáo, export, batch và màn hình danh
sách. Nó gần như không thay đổi gì cho việc tra cứu một bản ghi.**
[Hiệu năng](wiki/performance.md) có đầy đủ số liệu, phương pháp đo, và hai kết quả đi
ngược lại phỏng đoán thông thường.

## Cái giá phải trả

Ba đánh đổi sòng phẳng, xếp theo đúng thứ tự các đội thực sự gặp phải:

1. **Sửa SQL là phải build lại.** Nếu quy trình của bạn đang là "sửa mapper XML, khởi động
   lại", thì đây là thay đổi thật sự trong cách làm việc. Đổi lại, javac bắt giúp bạn
   những lỗi kiểu mà trước đây chỉ lộ ra dưới dạng exception lúc chạy.
2. **Thời gian dồn về phía build.** Sinh code không miễn phí. Chi phí đó do lập trình viên
   trả ở mỗi lần build, thay vì do production trả ở mỗi truy vấn.
3. **Các chỗ gọi `${}` phải sửa.** Một tham số `String` gắn vào `${}` là lỗi biên dịch. Nó
   phải trở thành [`SqlFragment`](usage/raw-sql.md), một kiểu giá trị đóng, hoặc một
   `switch` `@OrderBy(allowed = {...})`. Đợt chuyển đổi đó là lần đầu tiên có người thực
   sự soi lại toàn bộ chỗ chèn SQL thô trong codebase.

## Trạng thái

`0.1.0-SNAPSHOT`, và chưa publish lên Maven Central. Các mốc M1 đến M4 đã hiện thực xong:
lõi runtime, annotation processor, mapper XML kèm thẻ động, `<foreach>` và batch, result
map join một cấp, kiểu trả về `Stream`, transaction, cả hai plugin build, mô tả JPMS và
phần tích hợp Spring. M5 đã có [bộ benchmark](wiki/performance.md) và
[trình quét mã cũ](features/migration.md). Bài kiểm tra native image vẫn chưa chạy được vì
máy chưa cài GraalVM. Xem [Lộ trình](features/roadmap.md).
