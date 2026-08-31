# Thẻ foreach & Batching

Trong SQL động, thẻ `<foreach>` có số lượng tham số giữ chỗ (`?`) thay đổi tùy theo kích thước collection runtime. LarkBatis biên dịch thẻ này thành **hai vòng lặp duyệt tuần tự**: vòng lặp thứ nhất dựng chuỗi placeholder `(?, ?, ...)`, vòng lặp thứ hai bind giá trị vào `PreparedStatement`.

```xml title="UserBatchMapper.xml"
<select id="findByIds" resultType="com.example.app.User">
  SELECT id, name, email, created_at FROM users WHERE id IN
  <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
  ORDER BY id
</select>
```

Mã nguồn Java sinh ra:

```java title="UserBatchMapper$$Impl.java"
@Override
public List<User> findByIds(List<Long> ids) {
    StringBuilder sb = new StringBuilder(144);
    sb.append("SELECT id, name, email, created_at FROM users WHERE id IN");
    int n0 = ids.size();
    if (n0 == 0) {
        throw new LarkBatisEmptyForeachException(STMT_findByIds, "ids");   // (1)!
    }
    sb.append(" (");
    for (int k0 = 0; k0 < n0; k0++) sb.append(k0 == 0 ? " ?" : " , ?");
    sb.append(" )");
    sb.append(" ORDER BY id");
    String sql = sb.toString();
    LarkBatisSql.trackVariants(STMT_findByIds, sql);                       // (2)!
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(sql)) {
        int i = 1;
        for (Long id : ids) {                                               // (3)!
            JdbcCodec.setLong(ps, i++, id);
        }
        // ... đọc ResultSet
    }
}
```

1.  Ném exception rõ ràng nếu danh sách rỗng thay vì sinh câu SQL lỗi cú pháp gửi xuống database.
2.  Theo dõi số lượng biến thể prepared statement để tránh tràn cache.
3.  Bind trực tiếp theo thứ tự duyệt, không cần biến trung gian tạm thời.

## Các kiểu Collection hỗ trợ

| Kiểu dữ liệu | Thuộc tính `item` | Thuộc tính `index` |
|---|---|---|
| `List<T>`, `Collection<T>` | Giá trị phần tử | Chỉ số index (0, 1, 2...) |
| `T[]` (Mảng) | Giá trị phần tử | Chỉ số index (0, 1, 2...) |
| `Map<K, V>` | **Value (Giá trị)** | **Key (Khóa)** |

Tất cả collection phải **được định kiểu generic rõ ràng** (ví dụ `List<Long>`, không dùng raw type `List`).

Hỗ trợ vòng lặp lồng nhau:

```xml
<select id="findByIdGroups" resultType="com.example.app.User">
  SELECT id, name, email, created_at FROM users WHERE
  <foreach collection="groups" item="group" separator=" OR ">
    id IN
    <foreach collection="group" item="id" open="(" separator="," close=")">#{id}</foreach>
  </foreach>
  ORDER BY id
</select>
```

```java
List<User> findByIdGroups(List<List<Long>> groups);
```

## Sử dụng `index` trong Vòng lặp

Biến `index` đại diện cho thứ tự vòng lặp (hoặc Map key) và có thể bind như một tham số thông thường:

```xml
<select id="findByIdsOrdered" resultType="com.example.app.User">
  SELECT id, name, email, created_at FROM users WHERE id IN
  <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
  ORDER BY CASE id
  <foreach collection="ids" item="orderedId" index="position">
    WHEN #{orderedId} THEN #{position}
  </foreach>
  END
</select>
```

Với `Map`, `index` là key và `item` là value:

```xml
<foreach collection="filters" item="value" index="column" separator=" OR ">
  (name = #{column} AND email = #{value})
</foreach>
```

## Xử lý Collection rỗng { #empty-collections }

!!! danger "Không cho phép collection rỗng mặc định"

    Khi collection truyền vào `<foreach>` rỗng, LarkBatis ném ngoại lệ `LarkBatisEmptyForeachException` kèm tên mapper và tên tham số.

    Nếu bạn muốn bỏ qua đoạn SQL này khi collection rỗng, hãy bọc thẻ `<foreach>` bên trong thẻ `<if>`:

```xml
<if test="ids != null and !ids.isEmpty()">
  AND id IN
  <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
</if>
```

## `@PadPow2`: Giới hạn biến thể Prepared Statement { #padpow2-bounding-the-sql-variants }

Kích thước collection thay đổi sẽ tạo ra nhiều biến thể câu lệnh SQL khác nhau trong statement cache. Annotation `@PadPow2` tự động đệm số lượng placeholder lên lũy thừa của 2 gần nhất bằng cách lặp lại phần tử cuối cùng, giúp giới hạn số biến thể câu lệnh ở mức log₂(n) thay vì n.

```java
@PadPow2
List<User> findByIdsPadded(List<Long> ids);
```

Code Java sinh ra tương ứng:

```java
int p0 = LarkBatisSql.padPow2(n0);
Long last0 = null;
for (Long id : ids) {
    JdbcCodec.setLong(ps, i++, id);
    last0 = id;
}
for (int k0 = n0; k0 < p0; k0++) {
    JdbcCodec.setLong(ps, i++, last0);      // Lặp lại phần tử cuối để đệm
}
```

!!! warning "Chỉ dùng cho mệnh đề `WHERE IN`"

    Việc lặp lại phần tử chỉ an toàn trong mệnh đề `WHERE ... IN (...)`. Bộ sinh code cấm dùng `@PadPow2` trong câu lệnh `INSERT` và sẽ báo lỗi compile nếu phát hiện.

## Batch Insert nhiều dòng với JDBC Batch { #jdbc-batches }

Trong LarkBatis, phương thức `@Insert` nhận tham số `List<T>` sẽ tự động được biên dịch thành JDBC batch (`addBatch()` / `executeBatch()`):

```java
@Insert("INSERT INTO orders (status, total, placed_at) VALUES (#{status}, #{total}, #{placedAt})")
@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
int insertAll(List<Order> orders);
```

Mã nguồn Java sinh ra:

```java
public int insertAll(List<Order> orders) {
    if (orders.isEmpty()) {
        return 0;                                   // Danh sách rỗng: trả về 0 ngay lập tức
    }
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(SQL_insertAll, KEYS_insertAll)) {
        for (Order order : orders) {
            JdbcCodec.setEnum(ps, 1, order.getStatus());
            ps.setBigDecimal(2, order.getTotal());
            JdbcCodec.setInstant(ps, 3, order.getPlacedAt());
            ps.addBatch();
        }
        int n = LarkBatisSql.sum(ps.executeBatch());
        try (ResultSet gk = ps.getGeneratedKeys()) {
            int i = 0;
            while (gk.next() && i < orders.size()) {
                orders.get(i).setId(gk.getLong(1));
                i++;
            }
            if (i != orders.size()) {
                throw new LarkBatisKeyCountMismatchException(STMT, orders.size(), i);
            }
        }
        return n;
    } catch (SQLException e) {
        throw s.translate(e, SQL_insertAll);
    } finally {
        s.release(c);
    }
}
```

!!! note "Batch insert không kết hợp với dynamic SQL"

    Câu lệnh SQL trong JDBC batch phải có cấu trúc cố định cho mọi phần tử. Do đó, phương thức batch không được phép chứa các thẻ động (`<if>`, `<choose>`, v.v.).

