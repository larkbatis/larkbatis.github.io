# Result map và join

Một `<resultMap>` khai báo mỗi property lấy từ cột nào, và có thể lấp đầy **một** cấp
lồng `<association>` (một đối tượng con duy nhất) hoặc `<collection>` (một `List`) từ
chính cái join đó.

```xml
<resultMap id="teamWithMembers" type="com.example.app.Team">
  <id     property="id"   column="t_id"/>
  <result property="name" column="t_name"/>
  <collection property="members" ofType="com.example.app.Member">
    <id     property="id"     column="m_id"/>
    <result property="name"   column="m_name"/>
    <result property="jersey" column="m_jersey"/>
  </collection>
</resultMap>

<select id="findAllWithMembers" resultMap="teamWithMembers">
  SELECT t.id AS t_id, t.name AS t_name,
         m.id AS m_id, m.name AS m_name, m.jersey AS m_jersey
  FROM team t LEFT JOIN member m ON m.team_id = t.id
  ORDER BY t.id, m.jersey
</select>
```

`<association>` hoạt động y hệt cho một đối tượng con đơn lẻ:

```xml
<resultMap id="teamWithCoach" type="com.example.app.Team">
  <id     property="id"   column="t_id"/>
  <result property="name" column="t_name"/>
  <association property="coach" javaType="com.example.app.Coach">
    <id     property="id"   column="c_id"/>
    <result property="name" column="c_name"/>
  </association>
</resultMap>
```

## Nó biên dịch thành cái gì

Một vòng lặp mở đối tượng cha mới mỗi khi cột `<id>` đổi giá trị, và bỏ qua đối tượng
con khi cột `<id>` của nó là `NULL`, tức là một cú `LEFT JOIN` trượt:

```java
List<Team> out = new ArrayList<>();
Team parent = null;
long lastKey = 0;
boolean has = false;
while (rs.next()) {
    long key = rs.getLong(1);
    if (!has || key != lastKey) {          // (1)!
        parent = new Team();
        parent.setId(key);
        parent.setName(rs.getString(2));
        parent.setMembers(new ArrayList<>());
        out.add(parent);
        lastKey = key;
        has = true;
    }
    if (rs.getObject(3) != null) {         // (2)!
        Member m = new Member();
        m.setId(rs.getLong(3));
        m.setName(rs.getString(4));
        m.setJersey(rs.getInt(5));
        parent.getMembers().add(m);
    }
}
```

1.  MyBatis làm việc này bằng cách dựng một `CacheKey` cho mỗi dòng: dùng reflection duyệt
    các cột id, đọc từng cột qua một `TypeHandler`, băm, rồi tra đối tượng cha trong một
    map. Ở đây khoá là một biến cục bộ có kiểu, so sánh bằng `!=`, nên một khoá `long`
    không tốn lần boxing nào cho mỗi dòng.
2.  Phép kiểm tra `LEFT JOIN` trượt. Không có nó, một đối tượng cha không khớp sẽ có thêm
    một đứa con toàn null.

## Quy tắc sắp xếp { #the-ordering-rule }

!!! warning "ResultSet phải được sắp theo khoá của cha"

    Đó là cái giá của việc không giữ một map. Những dòng quay lại một khoá **sau khi đã
    đi qua các dòng của một cha khác** sẽ tạo ra một đối tượng cha thứ hai thay vì gộp
    vào cái đầu tiên.

    ```sql
    ORDER BY t.id, m.jersey   -- khoá của cha đứng trước
    ```

    Một statement dùng result map lồng nhau mà **không có `ORDER BY` nào cả** sẽ nhận một
    ghi chú lúc build. Còn một `ORDER BY` sai thì không phát hiện được lúc build, nên cái
    đó thuộc về bạn.

## Không có auto-mapping

Một result map ánh xạ **đúng những gì nó khai báo**. Không có `autoMapping` và không có
việc khớp cột ngầm định bên trong một `<resultMap>`.

- Một `<result>` có cột không xuất hiện trong select list là một **cảnh báo build**, và
  property đó bị bỏ trống.
- Một `<id>` có cột không xuất hiện là một **lỗi build**, bởi chính cột đó là thứ vòng
  lặp đọc vào.

Nếu bạn muốn cột được khớp với tên property theo quy ước, hãy dùng `resultType` thay
thế. Đường đó *có* áp dụng `snake_case` → `camelCase`, ngay lúc build. Hai thứ này là
hai công cụ khác nhau: `resultType` cho "ánh xạ cái nào khớp", `resultMap` cho "ánh xạ
đúng cái tôi nói".

## Vị trí cột

Khi select list phân tích được, vị trí là hằng số. Khi không, riêng statement đó nhận một
bộ resolver sinh riêng, đọc `ResultSetMetaData` một lần ở dòng đầu tiên rồi khớp theo tên
cột mà result map đã khai báo. Cách nào cũng đúng, và bản build cho bạn biết đã rơi vào
trường hợp nào. Xem
[Đọc theo vị trí hay theo tên](mappers.md#positional-or-name-based-reads).

## Result map không làm được gì { #narrowed-on-purpose }

Mỗi mục dưới đây là một **lỗi biên dịch có nêu tên thứ thay thế**:

| Không hỗ trợ | Thay bằng |
|---|---|
| Lồng quá một cấp, hoặc hai ánh xạ lồng trong cùng một map | Một cú join, một khoá gom nhóm |
| `select=` trên `<association>` / `<collection>` (nested select) | Hãy viết cú join; nested select *chính là* cái N+1 mà nó tưởng đang tránh |
| `resultMap=` bên trong một ánh xạ lồng | Viết thẳng `<id>`/`<result>` của con ra, để giới hạn một cấp luôn nhìn thấy được |
| `columnPrefix` | Đặt alias cho các cột con ngay trong select list |
| `extends` | Viết thẳng các ánh xạ ra |
| `<constructor>` | Lớp kết quả được dựng bằng constructor không tham số và các setter |
| `<discriminator>` | Tách thành các statement riêng với kiểu kết quả riêng |
| `autoMapping` | Khai báo các ánh xạ, hoặc dùng `resultType` |
| `<id column="x"/>` mà không có `property` | Ánh xạ khoá vào một property rồi đánh dấu `<id>` cho nó |
| Type alias trong `type` / `ofType` / `javaType` | Tên lớp đầy đủ |

Đồ thị đối tượng sâu hơn thì được ráp bằng Java từ hai statement: vẫn đúng bấy nhiêu lượt
đi về, mà phần ráp nối thì hiện ra trong đoạn code bạn đọc được.

## `Stream` và result map lồng nhau

Kiểu trả về `Stream` trên một `<resultMap>` lồng nhau là **lỗi biên dịch**. Một đối tượng
cha trải trên nhiều dòng, nên nó chỉ hoàn chỉnh khi đối tượng cha tiếp theo bắt đầu; trả
lời điều đó từ một con trỏ đọc-từng-dòng đồng nghĩa với việc đệm toàn bộ kết quả, mà đó
đúng là thứ kiểu trả về `Stream` được chọn để tránh. Xem
[Stream kết quả](streaming.md).
