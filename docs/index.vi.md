---
hide:
  - navigation
---

# LarkBatis

**Một MyBatis biên dịch sẵn.** Câu SQL, vị trí tham số, lựa chọn type handler, ánh xạ cột sang setter, cây SQL động: mọi thứ suy ra được từ *shape* của mapper đều được bộ sinh code giải quyết xong ngay lúc build. Khi thực thi lúc runtime, ứng dụng chỉ chạy các class mapper Java thuần sinh sẵn cùng một tầng JDBC mỏng khoảng 1.500 dòng, không phụ thuộc thư viện ngoài, không reflection, không dynamic proxy, không OGNL.

Bạn giữ nguyên mô hình lập trình quen thuộc của MyBatis: interface mapper, tham số `#{}` / `${}`, mapper XML, các thẻ `<if>`/`<where>`/`<foreach>`, `<resultMap>`. Thứ bị loại bỏ là tầng thông dịch nặng nề lúc runtime.

```java
public interface UserMapper {

    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);
}
```

Quá trình build sinh ra `UserMapper$$Impl`: mã nguồn hoàn toàn minh bạch, có thể đọc và đặt breakpoint debug trực tiếp trong IDE:

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

    Interface mapper, mapper XML, SQL động, `<foreach>`, result map, Generated Keys, stream, transaction.

-   :material-sitemap: **[Wiki](wiki/index.md)**

    Kiến trúc hai pha hoạt động ra sao, code sinh ra trông thế nào, và lý do cho từng lằn ranh thiết kế.

-   :material-checkbox-multiple-marked: **[Tính năng](features/index.md)**

    Bảng hỗ trợ chi tiết: LarkBatis làm được gì, thu hẹp phạm vi những gì, và chủ động loại bỏ những gì.

</div>

## Lý do thiết kế

MyBatis resolve lời gọi mapper lúc runtime. Mỗi truy vấn phải đi qua một JDK dynamic proxy, một lần OGNL đánh giá từng `<if test>`, và một lần tra cứu `TypeHandler` cho mỗi tham số. Phần tốn kém nhất nằm ở khâu đọc dữ liệu: mỗi cột trên mỗi dòng đều gọi `setValue` qua reflection, kéo theo việc cấp phát `PropertyTokenizer` cùng mảng `Object[]` chỉ để thực hiện một thao tác gán trường (`putfield`).

Không phần nào trong quy trình trên phụ thuộc vào giá trị dữ liệu lúc chạy. Chúng phụ thuộc vào *shape* của mapper — thứ vốn đã cố định ngay từ lúc lưu mã nguồn. LarkBatis resolve shape một lần duy nhất lúc build và phát ra trực tiếp các lời gọi JDBC.

| Chỉ số | MyBatis | LarkBatis |
|---|---|---|
| Số dòng mã nguồn trên classpath lúc chạy | ~40.000 dòng | ~1.500 dòng |
| Phụ thuộc thư viện lúc chạy | ognl, javassist | Không có gì ngoài JDBC thuần |
| Reflection trên đường dẫn truy vấn nóng | 4 nhóm điểm gọi | Hoàn toàn không |
| Thao tác reflection trên mỗi dòng dữ liệu | 1 lần cho mỗi cột | Hoàn toàn không |
| Metadata `native-image` viết tay | Bắt buộc | Không cần[^1] |
| Bắt lỗi sai kiểu tham số | Lúc runtime | Lúc biên dịch |
| Rà soát điểm chèn SQL thô | Đọc từng mapper | Chỉ cần một lệnh `grep` tìm `unsafeRawSql` |

[^1]: Đây là hệ quả cấu trúc: runtime không dùng reflection nên không cần metadata. Tuy nhiên bản build native image thực tế vẫn chưa được thực hiện; xem [Hiệu năng](wiki/performance.md#native-image).

Lợi ích hiệu năng là có thật và cần nêu rõ phạm vi áp dụng thực tế. Đo lường với MyBatis 3.5.19 trên JDK 21, truy vấn 10.000 dòng × 12 cột giảm từ **3,38 ms và 10,2 MB cấp phát xuống còn 0,54 ms và 1,88 MB**. Tính trên mỗi dòng: 338 ns và 1.018 B giảm còn 54 ns và 188 B. Thời gian khởi động nguội (cold startup) tới dòng đầu tiên giảm từ 61,8 ms xuống 6,3 ms.

Nửa còn lại được đo lường qua kết nối mạng thực tế. Một truy vấn `findById` trả về 1 dòng mất **94,2 µs trên MyBatis và 89,2 µs trên LarkBatis**: mức chênh lệch khoảng 5% đo trên TCP loopback. Đối với database đặt ở máy chủ từ xa, khoảng cách thời gian này sẽ còn nhỏ hơn nữa. **LarkBatis mang lại giá trị vượt trội cho các truy vấn báo cáo, xuất dữ liệu (export), xử lý batch và danh sách nhiều dòng. Đối với thao tác tra cứu một bản ghi đơn lẻ, hệ thống hầu như không tạo ra sự khác biệt về độ trễ.** [Hiệu năng](wiki/performance.md) cung cấp đầy đủ số liệu và phương pháp đo kiểm chứng.

## Ba điểm đánh đổi kỹ thuật

1. **Sửa SQL đồng nghĩa với việc phải build lại.** Nếu quy trình làm việc cũ là sửa mapper XML rồi restart ngay, đây là một thay đổi thực tế. Đổi lại, javac sẽ bắt toàn bộ lỗi sai kiểu dữ liệu vốn trước đây chỉ lộ ra lúc runtime.
2. **Thời gian xử lý chuyển dịch sang pha build (shift-left).** Quá trình sinh code đòi hỏi chi phí biên dịch: lập trình viên trả chi phí này một lần lúc build thay vì để hệ thống production gánh chịu trên từng truy vấn.
3. **Cần cập nhật các vị trí gọi `${}`.** Tham số kiểu `String` gắn trực tiếp vào `${}` là lỗi biên dịch. Giá trị này bắt buộc phải dùng [`SqlFragment`](usage/raw-sql.md), kiểu dữ liệu tập giá trị đóng, hoặc `@OrderBy(allowed = {...})`.

## Trạng thái dự án

Hiện tại là **`0.1.0-SNAPSHOT`**, chưa phát hành lên Maven Central. Các milestone M1 đến M4 đã hoàn thành: lõi runtime, annotation processor, mapper XML kèm thẻ động, `<foreach>` và batch insert, result map join một cấp, kiểu trả về `Stream`, transaction, cả hai build plugin, mô tả JPMS và tích hợp Spring. M5 đã hoàn thành [bộ benchmark](wiki/performance.md) và [công cụ quét mapper cũ](features/migration.md). Xem [Lộ trình phát triển](features/roadmap.md).
