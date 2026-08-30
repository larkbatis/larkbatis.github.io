# foreach và batch

`<foreach>` là ca khó nhất trong SQL động, bởi vì số lượng placeholder đúng là thứ duy
nhất về câu SQL mà thật sự không biết được trước lúc chạy. LarkBatis biên dịch nó
thành **hai vòng lặp duyệt cùng những phần tử đó theo cùng thứ tự đó**: một vòng nối
placeholder, một vòng gắn giá trị.

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
2.  Số phần tử của tập hợp làm đổi câu SQL, nên statement này được theo dõi y như một
    chỗ chèn `${}`.
3.  Vòng lặp thứ hai. Không có tầng đặt tên `__frch_id_0` nào để dẫn giá trị đi qua, vì
    chỉ số vòng lặp đã nối placeholder thứ *k* với giá trị thứ *k* rồi.

## Những gì lặp được

| Kiểu tập hợp | `item` | `index` |
|---|---|---|
| `List<T>`, mọi `Collection<T>` | phần tử | vị trí |
| `T[]` | phần tử | vị trí |
| `Map<K, V>` | **giá trị** | **khoá** |

Tất cả đều phải **có kiểu tĩnh**: `List<Long>`, không phải `List`. Chính kiểu phần tử là
thứ quyết định chọn `ps.setLong` thay vì `ps.setString` ngay lúc build.

Vòng lặp lồng được, và `item` của vòng ngoài có thể làm `collection` của vòng trong:

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

Các vòng lặp ngang hàng có thể dùng lại cùng một tên `index`; bộ sinh code tự đổi tên
tách chúng ra.

## Dùng `index`

`index` là vị trí (hoặc khoá của map), và nó bind được như mọi giá trị khác. Đây
chính là chiêu "giữ nguyên thứ tự đầu vào" quen thuộc:

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

## Gắn một property của phần tử

Thân vòng lặp không nhất thiết phải gắn chính phần tử đó:

```xml
<foreach collection="probes" item="p" open="(" separator="," close=")">#{p.email}</foreach>
```

## Tập hợp rỗng { #empty-collections }

!!! danger "`<foreach>` rỗng thì ném exception"

    ```text
    LarkBatisEmptyForeachException:
      <foreach collection="ids"> is empty in statement com.example.app.UserBatchMapper.findByIds;
      wrap the loop in an <if> testing the collection if an empty one should drop the fragment instead
    ```

MyBatis đóng góp *hoàn toàn không gì cả* cho một tập hợp rỗng, kể cả `open` và `close`.
Kết cục là `... WHERE id IN` đi thẳng xuống
database rồi chết ở đó, với một lỗi cú pháp không gọi tên cả mapper lẫn tham số. Chết
ngay tại đây thì gọi tên được cả hai, đúng ở chỗ gọi đang giữ cái danh sách rỗng ấy.

Nếu bạn thật sự muốn mảnh SQL đó biến mất, hãy nói ra, và bạn giữ được đúng hành vi của
MyBatis:

```xml
<if test="ids != null and !ids.isEmpty()">
  AND id IN
  <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
</if>
```

## `@PadPow2`: chặn số biến thể SQL { #padpow2-bounding-the-sql-variants }

Câu SQL của một statement có `<foreach>` thay đổi theo số phần tử, nên statement cache
của driver và của database sẽ phình lên theo **mọi số phần tử từng gặp**. `@PadPow2`
làm tròn số placeholder lên luỹ thừa của hai gần nhất bằng cách lặp lại phần tử cuối,
qua đó chặn con số kia ở log₂(n) biến thể thay vì n. Hibernate gọi đúng chiêu này là
`in_clause_parameter_padding`.

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

Đặt trên interface thì áp cho mọi statement; đặt trên một phương thức thì chỉ cho phương
thức đó.

!!! warning "Phải tự bật, và có kiểm soát"

    Lặp lại phần tử cuối chỉ vô hình ở chỗ mà giá trị trùng không làm đổi kết quả, tức
    là một danh sách `IN`. Bộ sinh code cưỡng chế điều đó: thân `<foreach>` phải là đúng
    một lần bind `#{}` và statement không được là `INSERT`. Ngược lại thì việc chèn thêm
    là **lỗi biên dịch**, chứ không phải âm thầm nhân đôi các dòng.

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

Batch không phải một chế độ executor mà bạn cấu hình, bởi làm gì có executor nào. Nó là một
**chữ ký phương thức**: một `@Insert` có tham số là `List<T>` sẽ biên dịch thành
`addBatch()` / `executeBatch()`.

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

1.  Một batch rỗng là lệnh rỗng trả về 0. Khác với `<foreach>` rỗng, ở đây không sinh ra
    câu SQL méo mó nào cần bảo vệ bạn khỏi.
2.  Có những driver trả về ít khoá hơn số dòng. Làm ngơ chuyện đó sẽ để lại một phần
    batch mang id null mà chẳng ai hay. Xem [Khoá tự sinh](generated-keys.md).

!!! note "Batch và SQL động không đi cùng nhau"

    Câu SQL của một statement batch phải giống hệt nhau cho mọi dòng, và chính điều đó
    làm nó thành một prepared statement duy nhất. Một phương thức batch mà statement có
    chứa thẻ động là lỗi biên dịch.
