# Wiki

Các trang tham khảo nói LarkBatis *làm gì*. Những trang này nói *vì sao* nó được dựng
như vậy, và cái giá của lựa chọn đó.

<div class="grid cards" markdown>

-   **[Kiến trúc](architecture.md)**

    Hai pha, cách chia module, và pipeline từ mã nguồn mapper tới Java sinh ra.

-   **[Shape và value](shape-vs-value.md)**

    Lát cắt duy nhất mà cả thiết kế đi theo: danh sách đóng những thứ được phép resolve
    lúc chạy.

-   **[Code sinh ra](generated-code.md)**

    Mỗi file phát ra trông như thế nào, và vì sao dễ đọc lại là một tính năng chứ không
    phải một thứ trang trí.

-   **[Vòng đời một lời gọi](call-flow.md)**

    Một lời gọi mapper, từng bước một, đặt cạnh đường đi của MyBatis mà nó thay thế.

-   **[Lằn ranh thiết kế](design-rules.md)**

    Chín quy tắc đúng trong mọi thay đổi, và cái gì vỡ nếu nới lỏng một quy tắc.

-   **[Hiệu năng](performance.md)**

    Những con số đã đo, những khẳng định chưa đo, và chỗ mà lợi ích thật sự không áp
    dụng.

</div>

## Tiền đề gói trong một đoạn

Một lời gọi mapper của MyBatis được resolve lúc chạy: điều phối qua proxy, OGNL đánh giá
từng `<if test>`, tra `TypeHandler` cho mỗi tham số, `setValue` bằng reflection cho mỗi
cột trên mỗi dòng. Không phần nào trong đó phụ thuộc vào *giá trị* chảy qua lời gọi.
Chúng phụ thuộc vào *shape* của mapper, mà shape thì ngừng thay đổi ngay khi file được
lưu. Vậy thì resolve shape một lần, lúc build, rồi phát ra thẳng các lời gọi JDBC. Còn
lại lúc chạy là chừng 1.500 dòng không phụ thuộc gì ngoài JDBC, và cũng không có metadata
reachability nào của GraalVM phải viết, vì chẳng có reflection ở đâu cả.

## Cái gì ở đây không mới

LarkBatis không phải một ý tưởng mới, và tài liệu thiết kế nói thẳng điều đó. Micronaut
Data biên dịch truy vấn thành code lúc build mà không dùng reflection; jOOQ sinh code từ
schema; Spring Data có một nhánh AOT. **Điều không cái nào trong số đó làm là giữ lại
mô hình mapper của MyBatis**: mapper XML, `#{}`, `<if>`, `<foreach>`, `<resultMap>`. Hàng
nghìn codebase ở Hàn Quốc và Nhật Bản đang chạy trên đúng mô hình đó hôm nay.

Giá trị nằm ở con đường chuyển đổi, không nằm ở ý tưởng. Cách đóng khung ấy quyết định
khá nhiều thứ trong thiết kế: đó là lý do frontend XML tồn tại, lý do bộ khung kiểm thử
vi sai đem SQL sinh ra so với đầu ra thông dịch của MyBatis, và lý do mọi tính năng bị bỏ
đều đi kèm một lỗi biên dịch nêu tên thứ thay thế thay vì im lặng.
