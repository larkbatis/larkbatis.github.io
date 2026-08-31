# Generated Keys (Khóa tự tăng)

`@Options(useGeneratedKeys = true, ...)` yêu cầu JDBC driver trả về Generated Keys (khóa tự tăng / sequence) sau khi thực thi `INSERT` và tự động gán vào trường của đối tượng tham số.

```java
@Insert("INSERT INTO users (name, email, created_at) VALUES (#{name}, #{email}, #{createdAt})")
@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
int insert(User u);
```

Mã nguồn Java sinh ra:

```java
private static final String[] KEYS_insert = { "id" };

@Override
public int insert(User u) {
    Connection c = s.conn();
    try (PreparedStatement ps = c.prepareStatement(SQL_insert, KEYS_insert)) {  // (1)!
        ps.setString(1, u.getName());
        ps.setString(2, u.getEmail());
        JdbcCodec.setInstant(ps, 3, u.getCreatedAt());
        int n = ps.executeUpdate();
        try (ResultSet gk = ps.getGeneratedKeys()) {
            if (gk.next()) {
                u.setId(gk.getLong(1));                                          // (2)!
            }
        }
        return n;
    } catch (SQLException e) {
        throw s.translate(e, SQL_insert);
    } finally {
        s.release(c);
    }
}
```

1.  Truyền mảng tên cột `KEYS_insert` tường minh vào `prepareStatement` thay vì dùng cờ chung `RETURN_GENERATED_KEYS`.
2.  Lệnh gọi setter `u.setId()` được xác định tĩnh từ lúc build.

## Tầm quan trọng của `keyColumn`

!!! warning "Luôn khai báo `keyColumn` tường minh"

    Lệnh `prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)` có hành vi không đồng nhất giữa các database:
    - **Oracle**: Trả về `ROWID` thay vì giá trị sequence thực tế.
    - **PostgreSQL**: Trả về tất cả các cột của bản ghi vừa chèn.

    Chỉ khi truyền tên cột cụ thể qua `keyColumn` (ví dụ `keyColumn = "id"`), JDBC driver mới trả về đúng giá trị mong đợi trên mọi hệ quản trị database. Nếu bỏ trống `keyColumn`, compiler sẽ phát cảnh báo lúc build.

Với khóa chính tổ hợp (composite key), phân tách các tên bằng dấu phẩy:

```java
@Options(useGeneratedKeys = true, keyProperty = "tenantId,id", keyColumn = "tenant_id,id")
```

## Khi phương thức có nhiều tham số

Khi phương thức nhận nhiều tham số, `keyProperty` phải chỉ rõ tên biến tham số tiền tố:

```java
@Insert("INSERT INTO users (name) VALUES (#{u.name})")
@Options(useGeneratedKeys = true, keyProperty = "u.id", keyColumn = "id")
int insert(@Param("u") User u, @Param("audit") String audit);
```

## Generated Keys trong Batch Insert

Khi thực hiện batch insert nhận `List<T>`, Generated Keys được đọc tuần tự và gán vào từng phần tử trong danh sách:

```java
int n = LarkBatisSql.sum(ps.executeBatch());
try (ResultSet gk = ps.getGeneratedKeys()) {
    int i = 0;
    while (gk.next() && i < orders.size()) {
        orders.get(i).setId(gk.getLong(1));
        i++;
    }
    if (i != orders.size()) {
        throw new LarkBatisKeyCountMismatchException(STMT_insertAll, orders.size(), i);
    }
}
```

Nếu số lượng khóa trả về không khớp với số dòng gửi đi, hệ thống lập tức ném `LarkBatisKeyCountMismatchException`.

## Thẻ `<selectKey>` không được hỗ trợ

LarkBatis loại bỏ thẻ `<selectKey>` vì nó ẩn giấu một câu lệnh truy vấn thứ hai bên trong cấu hình. Thay vào đó, hãy tách thành 2 phương thức mapper tường minh:

```java
@Select("SELECT user_seq.NEXTVAL FROM dual")
long nextUserId();

@Insert("INSERT INTO users (id, name) VALUES (#{id}, #{name})")
int insert(User u);
```

```java
try (LarkBatisTx tx = session.begin()) {
    u.setId(mapper.nextUserId());
    mapper.insert(u);
    tx.commit();
}
```

