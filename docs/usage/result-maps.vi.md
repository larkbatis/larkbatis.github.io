# Result Maps & Join

Thẻ `<resultMap>` định nghĩa ánh xạ tường minh giữa cột database và thuộc tính Java Bean, đồng thời hỗ trợ nạp dữ liệu cho quan hệ lồng nhau **1 cấp** (`<association>` cho 1-1, `<collection>` cho 1-N) từ câu lệnh `JOIN`.

```xml title="TeamMapper.xml"
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

Tương tự cho `<association>` (quan hệ 1-1):

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

## Thuật toán gom nhóm Single-pass

Mã nguồn Java sinh ra sử dụng vòng lặp gom nhóm single-pass: tạo đối tượng cha mới khi giá trị khóa `<id>` của bảng cha thay đổi, và bỏ qua đối tượng con nếu khóa con là `NULL` (trường hợp `LEFT JOIN` không có dữ liệu con):

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

1.  LarkBatis theo dõi khóa cha qua biến nguyên thủy cục bộ (`long lastKey`) và so sánh bằng toán tử `!=`, loại bỏ hoàn toàn việc tạo đối tượng `CacheKey`, reflection và `HashMap` lookup của MyBatis.
2.  Kiểm tra null trên khóa con để tránh khởi tạo đối tượng rỗng khi `LEFT JOIN` không tìm thấy bản ghi liên kết.

## Quy tắc bắt buộc về thứ tự sắp xếp { #the-ordering-rule }

!!! warning "Câu SQL bắt buộc phải có `ORDER BY` theo khóa cha"

    Để thuật toán gom nhóm single-pass hoạt động chính xác mà không cần lưu toàn bộ dữ liệu vào bộ nhớ tạm, ResultSet bắt buộc phải được sắp xếp theo khóa của bảng cha (`ORDER BY parent.id, child.id`).

    Nếu câu SQL thiếu mệnh đề `ORDER BY`, compiler sẽ phát cảnh báo lúc build.

## Nguyên tắc ánh xạ trong `<resultMap>`

Trong `<resultMap>`, LarkBatis **chỉ ánh xạ các cột được khai báo tường minh**. Không có cơ chế autoMapping ngầm định.

- Cột trong `<result>` không tồn tại trong `SELECT`: Phát cảnh báo build; thuộc tính Java giữ giá trị mặc định.
- Cột trong `<id>` không tồn tại trong `SELECT`: Báo lỗi compile (vì cột id bắt buộc phải có để thuật toán gom nhóm hoạt động).

Nếu bạn muốn tự động ánh xạ toàn bộ cột theo quy ước `snake_case` → `camelCase`, hãy sử dụng `resultType` thay vì `<resultMap>`.

## Các tính năng không hỗ trợ { #narrowed-on-purpose }

| Tính năng bị loại bỏ | Lý do & Giải pháp thay thế |
|---|---|
| Lồng sâu hơn 1 cấp, hoặc 2 collection trong 1 map | Tránh bùng nổ tích Descartes (Cartesian product). Hãy join 1 cấp hoặc ghép dữ liệu trong tầng Service |
| `select="..."` trong association/collection | Loại bỏ hoàn toàn vấn đề N+1 query. Hãy viết câu lệnh `JOIN` tường minh |
| `resultMap="..."` lồng nhau | Khai báo trực tiếp `<id>` / `<result>` của entity con |
| `columnPrefix` | Đặt alias cho cột con trực tiếp trong câu `SELECT` |
| `<resultMap extends="...">` | Khai báo tường minh tất cả ánh xạ cột |
| `<discriminator>` | Tách thành các phương thức truy vấn riêng theo từng entity con |
| `<constructor>` mapping | POJO sử dụng constructor không tham số và setter |

## `Stream<T>` và Result Map lồng nhau

Khai báo kiểu trả về `Stream<T>` trên một `<resultMap>` có association/collection lồng nhau sẽ **bị báo lỗi biên dịch**. Do một đối tượng cha trải dài trên nhiều dòng trong ResultSet, việc gom nhóm đòi hỏi phải nạp dữ liệu trước, làm mất đi tính năng streaming tiết kiệm RAM. Xem [Streaming](streaming.md).

