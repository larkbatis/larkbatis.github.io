# Tài liệu Kiến trúc & Thiết kế (Wiki)

Mục tài liệu này trình bày các nguyên tắc thiết kế, kiến trúc nội bộ, cơ chế biên dịch và các đánh đổi kỹ thuật của LarkBatis.

<div class="grid cards" markdown>

-   **[Kiến trúc tổng thể](architecture.md)**

    Mô hình 2 pha, cấu trúc phân chia module và pipeline biên dịch từ Java/XML sang mã nguồn JDBC.

-   **[Shape vs. Value](shape-vs-value.md)**

    Nguyên tắc phân tách ranh giới cốt lõi: danh sách đóng các phần tử được đánh giá lúc runtime.

-   **[Mã nguồn sinh ra](generated-code.md)**

    Cấu trúc chi tiết của các class `Mapper$$Impl` và `RowReader` sinh ra.

-   **[Vòng đời một lời gọi mapper](call-flow.md)**

    So sánh chi tiết từng bước thực thi giữa luồng runtime của LarkBatis và MyBatis truyền thống.

-   **[Nguyên tắc thiết kế](design-rules.md)**

    9 quy tắc bất biến chi phối toàn bộ kiến trúc và các ràng buộc kỹ thuật.

-   **[Hiệu năng & Benchmark](performance.md)**

    Dữ liệu đo lường JMH thực tế, phân tích mức giảm latency/RAM và các giới hạn kỹ thuật.

</div>

## Tiền đề thiết kế

Trong MyBatis truyền thống, mỗi lời gọi mapper phải trải qua: điều phối qua Dynamic Proxy, OGNL evaluate từng biểu thức `<if test>`, tra cứu `TypeHandler` theo cặp type cho mỗi tham số, và gọi setter qua Java Reflection cho từng cột trên mỗi dòng `ResultSet`.

Toàn bộ các thông tin này phụ thuộc vào **Shape** (cấu trúc tĩnh của câu truy vấn và Java Bean), vốn không thay đổi sau khi lưu file mã nguồn. LarkBatis phân tích toàn bộ Shape trong pha build và sinh ra các lệnh gọi JDBC trực tiếp.

Runtime chỉ còn khoảng 1.500 dòng code JDBC thuần, loại bỏ hoàn toàn dynamic proxy, reflection và metadata config cho GraalVM Native Image.

## Định vị kỹ thuật

LarkBatis không phát minh ra khái niệm compile-time SQL generation (Micronaut Data hay jOOQ đã áp dụng các hướng tiếp cận tương tự). Điểm khác biệt mấu chốt của LarkBatis là **giữ nguyên mô hình mapper quen thuộc của MyBatis**: file XML, cú pháp `#{}` / `${}`, các thẻ `<if>`, `<foreach>`, `<resultMap>`.

Mục tiêu của LarkBatis là cung cấp lộ trình chuyển đổi trực tiếp cho các hệ thống MyBatis hiện có, mang lại hiệu năng cao và an toàn kiểu tĩnh mà không đòi hỏi viết lại toàn bộ mã nguồn truy vấn.

