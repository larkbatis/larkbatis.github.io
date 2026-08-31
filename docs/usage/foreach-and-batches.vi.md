# foreach và batch

`<foreach>` là trường hợp phức tạp nhất trong SQL động vì số lượng placeholder chỉ được xác định lúc runtime. LarkBatis biên dịch nó thành **hai vòng lặp duyệt qua cùng tập phần tử theo đúng thứ tự**: một vòng dựng chuỗi placeholder (`?, ?, ?`), một vòng gán giá trị tham số vào `PreparedStatement`.

```xml
<select id="findByIds" resultType="com.example.app.User">
  SELECT id, name, email, created_at FROM users WHERE id IN
  <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
  ORDER BY id
</select>
```

```java
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
        // ... đọc các dòng
    }
}
```

1.  Xem [Tập hợp rỗng](#empty-collections) bên dưới.
2.  Số lượng phần tử thay đổi làm thay đổi chuỗi câu SQL, nên statement này được theo dõi biến thể tương tự như một điểm chèn `${}`.
3.  Vòng lặp thứ hai gán trực tiếp giá trị theo chỉ số vòng lặp, không cần biến trung gian `__frch_id_0`.

## Các kiểu dữ liệu hỗ trợ lặp

| Kiểu tập hợp | `item` | `index` |
|---|---|---|
| `List<T>`, mọi `Collection<T>` | phần tử | vị trí |
| `T[]` | phần tử | vị trí |
| `Map<K, V>` | **giá trị** | **khoá** |

Tất cả đều phải **định kiểu tĩnh rõ ràng**: `List<Long>`, không dùng raw type `List`. Kiểu phần tử là cơ sở để bộ sinh code chọn gọi `ps.setLong` thay vì `ps.setString` ngay lúc build.

Hỗ trợ vòng lặp lồng nhau, và `item` của vòng ngoài có thể làm `collection` của vòng trong:

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

Các vòng lặp ngang hàng có thể dùng lại cùng một tên `index`; bộ sinh code sẽ tự động phân tách phạm vi biến.

## Sử dụng `index`

`index` là vị trí (hoặc khoá của map), và có thể bind như mọi tham số khác. Đây là kỹ thuật quen thuộc để giữ nguyên thứ tự đầu vào:

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

Với `Map`, `index` là khoá còn `item` là giá trị:

```xml
<foreach collection="filters" item="value" index="column" separator=" OR ">
  (name = #{column} AND email = #{value})
</foreach>
```

## Gán thuộc tính của phần tử

Thân vòng lặp có thể gán property của phần tử thay vì chính phần tử đó:

```xml
<foreach collection="probes" item="p" open="(" separator="," close=")">#{p.email}</foreach>
```

## Tập hợp rỗng { #empty-collections }

!!! danger "`<foreach>` rỗng sẽ ném exception"

    ```text
    LarkBatisEmptyForeachException:
      <foreach collection="ids"> is empty in statement com.example.app.UserBatchMapper.findByIds;
      wrap the loop in an <if> testing the collection if an empty one should drop the fragment instead
    ```

    MyBatis không chèn bất kỳ chuỗi nào (kể cả `open` và `close`) khi tập hợp rỗng, dẫn đến câu SQL lỗi cú pháp `... WHERE id IN` gửi xuống database mà không chỉ rõ mapper hay tham số nào.

    LarkBatis chủ động ném `LarkBatisEmptyForeachException` ngay tại chỗ gọi kèm đầy đủ thông tin.

Nếu bạn muốn đoạn SQL đó biến mất khi danh sách rỗng, hãy bọc trong thẻ `<if>` để giữ đúng hành vi của MyBatis:

```xml
<if test="ids != null and !ids.isEmpty()">
  AND id IN
  <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
</if>
```

## `@PadPow2`: Giới hạn số biến thể SQL { #padpow2-bounding-the-sql-variants }

Câu SQL của một statement có `<foreach>` thay đổi theo số phần tử, khiến statement cache của JDBC driver và database bị phình to theo từng kích thước danh sách. `@PadPow2` làm tròn số placeholder lên luỹ thừa của 2 gần nhất bằng cách lặp lại phần tử cuối cùng, qua đó chặn số biến thể ở mức log₂(n) thay vì n. Trong Hibernate, kỹ thuật tương đương có tên là `in_clause_parameter_padding`.

```java
@PadPow2
List<User> findByIdsPadded(List<Long> ids);
```

```java
int p0 = LarkBatisSql.padPow2(n0);
// ... phát ra p0 placeholder
Long last0 = null;
for (Long id : ids) {
    JdbcCodec.setLong(ps, i++, id);
    last0 = id;
}
for (int k0 = n0; k0 < p0; k0++) {
    JdbcCodec.setLong(ps, i++, last0);      // lặp lại phần tử cuối
}
```

Đặt trên interface thì áp dụng cho mọi statement; đặt trên phương thức thì chỉ áp dụng cho phương thức đó.

!!! warning "Quy tắc an toàn bắt buộc"

    Việc lặp lại phần tử cuối cùng chỉ an toàn tuyệt đối trong mệnh đề `IN`. Bộ sinh code kiểm tra nghiêm ngặt: thân `<foreach>` phải chứa duy nhất một liên kết `#{}` và câu lệnh không phải là `INSERT`. Nằm ngoài các điều kiện này, việc pad sẽ **báo lỗi biên dịch**.

## `VALUES` nhiều dòng

Một `<foreach>` trong `INSERT` dựng nên một statement với nhiều bộ giá trị:

```xml
<insert id="insertAll">
  INSERT INTO users (name, email, created_at) VALUES
  <foreach collection="users" item="u" separator=",">
    (#{u.name}, #{u.email}, #{u.createdAt})
  </foreach>
</insert>
```

## Batch của JDBC { #jdbc-batches }

Batch trong LarkBatis không phải là một chế độ cấu hình Executor như trong MyBatis, mà được định nghĩa trực tiếp qua **chữ ký phương thức**: một phương thức `@Insert` nhận tham số `List<T>` sẽ tự động biên dịch thành luồng JDBC `addBatch()` / `executeBatch()`.

```java
@Insert("INSERT INTO orders (status, total, placed_at) VALUES (#{status}, #{total}, #{placedAt})")
@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
int insertAll(List<Order> orders);
```

```java
public int insertAll(List<Order> orders) {
    if (orders.isEmpty()) {
        return 0;                                   // (1)!
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
                throw new LarkBatisKeyCountMismatchException(STMT, orders.size(), i); // (2)!
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

1.  Batch rỗng sẽ trả về 0 ngay lập tức mà không gửi lệnh nào xuống database.
2.  Một số JDBC driver trả về ít khoá hơn số dòng. Kiểm tra này giúp phát hiện lỗi thiếu ID trong batch. Xem [Khoá tự sinh](generated-keys.md).

!!! note "Batch không đi cùng với SQL động"

    Câu SQL của statement batch phải giống hệt nhau cho mọi dòng dữ liệu để sử dụng chung một PreparedStatement duy nhất. Phương thức batch có chứa thẻ động là lỗi biên dịch.
