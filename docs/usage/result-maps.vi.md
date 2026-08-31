# Result map và join

Thẻ `<resultMap>` định nghĩa ánh xạ tường minh giữa cột và property, đồng thời hỗ trợ nạp dữ liệu cho **một** cấp lồng nhau (`<association>` cho quan hệ 1-1, `<collection>` cho quan hệ 1-N) từ chính câu lệnh JOIN đó.

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

`<association>` hoạt động tương tự cho một đối tượng con đơn lẻ:

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

## Cơ chế biên dịch

Bộ sinh code phát sinh một vòng lặp gom nhóm: khởi tạo đối tượng cha mới mỗi khi giá trị cột `<id>` thay đổi, và bỏ qua đối tượng con nếu khoá của bảng con nhận giá trị `NULL` (trường hợp `LEFT JOIN` không khớp dữ liệu con):

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

1.  MyBatis xử lý việc này bằng cách tạo `CacheKey` cho từng dòng: dùng reflection duyệt các cột id, băm giá trị và tra cứu đối tượng cha trong `Map`. LarkBatis lưu khoá cha trong biến cục bộ có kiểu tĩnh và so sánh trực tiếp bằng `!=`, giúp loại bỏ hoàn toàn chi phí boxing và tra map.
2.  Phép kiểm tra khoá con khác null giúp tránh khởi tạo đối tượng con rỗng khi `LEFT JOIN` không khớp.

## Quy tắc sắp xếp { #the-ordering-rule }

!!! warning "ResultSet bắt buộc phải sắp xếp theo khoá của bảng cha"

    Đây là điều kiện kỹ thuật bắt buộc để vòng lặp gom nhóm hoạt động mà không cần lưu cache map. Nếu dữ liệu của cùng một cha bị ngắt quãng bởi dòng của một cha khác, vòng lặp sẽ tạo ra hai đối tượng cha riêng biệt thay vì gộp lại.

    ```sql
    ORDER BY t.id, m.jersey   -- khoá của cha luôn đứng trước
    ```

    Statement dùng result map lồng nhau mà **thiếu mệnh đề `ORDER BY`** sẽ nhận một cảnh báo lúc build.

## Không dùng auto-mapping trong `<resultMap>`

Một result map chỉ ánh xạ **đúng những gì được khai báo tường minh**. Không có `autoMapping` và không có việc khớp cột ngầm định bên trong một `<resultMap>`.

- Thẻ `<result>` có cột không xuất hiện trong danh sách SELECT là **cảnh báo build**, và property đó sẽ giữ giá trị mặc định.
- Thẻ `<id>` có cột không xuất hiện trong danh sách SELECT là **lỗi build**, vì đây là cột bắt buộc để điều khiển vòng lặp gom nhóm.

Nếu muốn tự động ánh xạ cột sang property theo quy ước `snake_case` → `camelCase`, hãy sử dụng `resultType`. `resultType` dành cho "tự động ánh xạ những gì khớp", còn `resultMap` dành cho "ánh xạ chính xác những gì khai báo".

## Vị trí cột

Khi danh sách SELECT phân tích cú pháp tĩnh được, vị trí cột là hằng số. Khi không phân tích được, statement đó sẽ dùng resolver sinh riêng để đọc `ResultSetMetaData` đúng một lần ở dòng đầu tiên. Xem [Đọc theo vị trí hay theo tên](mappers.md#positional-or-name-based-reads).

## Các tính năng result map không hỗ trợ { #narrowed-on-purpose }

Mỗi mục dưới đây là một **lỗi biên dịch nêu rõ giải pháp thay thế**:

| Không hỗ trợ | Giải pháp thay thế |
|---|---|
| Lồng quá một cấp, hoặc hai ánh xạ lồng trong cùng một map | Một câu lệnh join, một khoá gom nhóm |
| `select=` trên `<association>` / `<collection>` (nested select) | Viết câu lệnh join tường minh (nested select chính là nguyên nhân gây lỗi N+1) |
| `resultMap=` bên trong một ánh xạ lồng | Khai báo trực tiếp `<id>`/`<result>` của con để duy trì giới hạn một cấp rõ ràng |
| `columnPrefix` | Đặt alias cho các cột con ngay trong danh sách SELECT |
| `extends` | Khai báo tường minh tất cả các ánh xạ |
| `<constructor>` | Result class được khởi tạo bằng constructor không tham số và các setter |
| `<discriminator>` | Tách thành các statement riêng biệt với kiểu kết quả tương ứng |
| `autoMapping` | Khai báo ánh xạ tường minh, hoặc dùng `resultType` |
| `<id column="x"/>` mà không có `property` | Ánh xạ khoá vào một property rồi đánh dấu `<id>` cho nó |
| Type alias trong `type` / `ofType` / `javaType` | Dùng tên class đầy đủ (FQN) |

Đồ thị đối tượng sâu hơn hai cấp nên được ghép trong Java từ hai statement độc lập: số lượt round-trip xuống database không đổi mà logic ghép nối lại hoàn toàn minh bạch.

## `Stream` và result map lồng nhau

Khai báo kiểu trả về `Stream` trên một `<resultMap>` lồng nhau là **lỗi biên dịch**. Một đối tượng cha trải trên nhiều dòng nên chỉ hoàn chỉnh khi đối tượng cha tiếp theo bắt đầu. Việc trả về `Stream` từ con trỏ đọc từng dòng đòi hỏi phải đệm dữ liệu vào bộ nhớ, làm mất đi ý nghĩa tiết kiệm RAM của `Stream`. Xem [Stream kết quả](streaming.md).
