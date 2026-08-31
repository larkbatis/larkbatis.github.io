---
hide:
  - navigation
---

# LarkBatis

**MyBatis được biên dịch sẵn tại thời điểm build.** Câu lệnh SQL, thứ tự tham số, lựa chọn type handler, ánh xạ cột sang setter, cây SQL động: mọi thứ suy ra được từ cấu trúc (shape) của mapper đều được xử lý xong ngay lúc biên dịch (`javac`). Khi chạy ở runtime, ứng dụng chỉ thực thi các class Java thuần được sinh sẵn cùng tầng JDBC mỏng khoảng 1.500 dòng code—không phụ thuộc thư viện ngoài, không reflection, không dynamic proxy và không OGNL.

Bạn giữ nguyên mô hình làm việc quen thuộc của MyBatis: mapper interface, tham số `#{}` / `${}`, mapper XML, các thẻ `<if>`/`<where>`/`<foreach>`, và `<resultMap>`. Thứ duy nhất được loại bỏ là tầng thông dịch nặng nề lúc runtime.

```java
public interface UserMapper {

    @Select("SELECT id, name, email, created_at FROM users WHERE id = #{id}")
    User findById(long id);
}
```

Quá trình build sinh ra `UserMapper$$Impl`: mã nguồn rõ ràng, có thể đọc và đặt breakpoint debug trực tiếp trong IDE:

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

    Cài đặt annotations, runtime và annotation processor, rồi viết mapper đầu tiên.

-   :material-book-open-variant: **[Hướng dẫn sử dụng](usage/index.md)**

    Mapper interface, mapper XML, dynamic SQL, `<foreach>`, result map, Generated Keys, stream và transaction.

-   :material-sitemap: **[Kiến trúc & Thiết kế](wiki/index.md)**

    Cách thức hoạt động của mô hình hai pha, giải thích mã nguồn sinh ra và các nguyên tắc thiết kế cốt lõi.

-   :material-checkbox-multiple-marked: **[Tính năng](features/index.md)**

    Ma trận hỗ trợ chi tiết: những gì LarkBatis hỗ trợ, giới hạn hoặc chủ động loại bỏ.

</div>

## Lý do thiết kế

MyBatis thông dịch mapper lúc runtime. Mỗi truy vấn phải đi qua một JDK dynamic proxy, bộ phân tích OGNL đánh giá từng thẻ `<if test>`, và tra cứu `TypeHandler` cho mỗi tham số. Phần tốn tài nguyên nhất nằm ở khâu đọc dữ liệu: mỗi cột trên mỗi dòng đều gọi `setValue` qua reflection, kéo theo việc cấp phát `PropertyTokenizer` cùng mảng `Object[]` chỉ để thực hiện một lệnh gán trường dữ liệu (`putfield`).

Các thông tin trên đều đã cố định ngay khi bạn lưu file mã nguồn. LarkBatis xử lý cấu trúc này một lần duy nhất lúc build và phát ra trực tiếp các lệnh gọi JDBC tối ưu.

| Tiêu chí | MyBatis | LarkBatis |
|---|---|---|
| Số dòng code trên runtime classpath | ~40.000 dòng | ~1.500 dòng |
| Phụ thuộc thư viện runtime | ognl, javassist | Không có gì ngoài JDBC thuần |
| Điểm gọi reflection trên luồng truy vấn | 4 nhóm điểm gọi | Không có |
| Thao tác reflection trên mỗi dòng dữ liệu | 1 lần cho mỗi cột | Không có |
| Cấu hình `native-image` thủ công | Bắt buộc | Không cần[^1] |
| Bắt lỗi sai kiểu tham số | Lúc runtime | Ngay lúc biên dịch |
| Rà soát điểm chèn SQL động | Đọc từng mapper XML | Một lệnh `grep` tìm `unsafeRawSql` |

[^1]: Đây là hệ quả cấu trúc: runtime không dùng reflection nên không cần cấu hình metadata. Tuy nhiên bản build native image thực tế vẫn đang trong quá trình kiểm thử; xem [Hiệu năng](wiki/performance.md#native-image).

Các đo lường thực tế với MyBatis 3.5.19 trên JDK 21: truy vấn 10.000 dòng × 12 cột giảm từ **3,38 ms và 10,2 MB bộ nhớ xuống còn 0,54 ms và 1,88 MB** (trên mỗi dòng: 338 ns / 1.018 B giảm còn 54 ns / 188 B). Thời gian khởi động nguội (cold startup) tới dòng kết quả đầu tiên giảm từ 61,8 ms xuống 6,3 ms.

Khi chạy qua kết nối mạng, truy vấn `findById` trả về 1 dòng mất **94,2 µs trên MyBatis và 89,2 µs trên LarkBatis** (chênh lệch ~5% đo trên TCP loopback). **LarkBatis mang lại lợi thế vượt trội cho các truy vấn báo cáo, xuất dữ liệu (export), xử lý batch và danh sách nhiều dòng. Đối với tra cứu một bản ghi đơn lẻ qua mạng, sự khác biệt về độ trễ là không đáng kể.** Xem chi tiết tại trang [Hiệu năng & Benchmark](wiki/performance.md).

## Ba điểm đánh đổi kỹ thuật

1. **Sửa SQL yêu cầu phải biên dịch lại.** Thay vì sửa XML rồi restart ứng dụng, bạn cần build lại project. Đổi lại, `javac` sẽ bắt toàn bộ lỗi cú pháp và sai kiểu dữ liệu ngay lập tức.
2. **Chuyển dịch thời gian xử lý sang pha build (shift-left).** Chi phí phân tích và sinh code được thực hiện một lần khi build máy developer hoặc CI, giải phóng hoàn toàn gánh nặng cho production.
3. **Tuân thủ kỷ luật an toàn cho `${}`.** Gán trực tiếp biến `String` vào `${}` sẽ báo lỗi biên dịch. Bạn cần dùng [`SqlFragment`](usage/raw-sql.md), kiểu dữ liệu tập đóng (enum/số), hoặc `@OrderBy(allowed = {...})` để ngăn ngừa SQL injection.


