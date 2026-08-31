# Khoá tự sinh

`@Options(useGeneratedKeys = true, ...)` yêu cầu JDBC driver trả về khoá tự sinh sau câu lệnh `INSERT` và gán trực tiếp vào property của đối tượng tham số.

```java
@Insert("INSERT INTO users (name, email, created_at) VALUES (#{name}, #{email}, #{createdAt})")
@Options(useGeneratedKeys = true, keyProperty = "id", keyColumn = "id")
int insert(User u);
```

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

1.  **Tên cột** khoá được khai báo tường minh vì `RETURN_GENERATED_KEYS` có hành vi không đồng nhất giữa các hệ quản trị database. Xem chi tiết bên dưới.
2.  Cả setter lẫn accessor đều được xác định tĩnh lúc build từ `keyProperty` và kiểu dữ liệu của property đó.

## Luôn khai báo tên cột khoá tường minh

!!! warning "`keyColumn` là tuỳ chọn trong annotation nhưng gần như bắt buộc trên production"

    `prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)` không đảm bảo tính di động (portable):

    - **Oracle** trả về `ROWID` thay vì giá trị sequence thực tế.
    - **PostgreSQL** trả về *toàn bộ* các cột của dòng vừa chèn.

    Truyền một mảng `String[]` tên cột tường minh là cách duy nhất mang lại hành vi nhất quán trên mọi database. Khi có `keyColumn`, bộ sinh code phát ra `prepareStatement(sql, String[])`. Khi thiếu nó, hệ thống buộc phải fallback về `RETURN_GENERATED_KEYS` và phát ra một **cảnh báo build bắt buộc**:

    ```text
    warning: useGeneratedKeys without keyColumn falls back to RETURN_GENERATED_KEYS,
    which returns ROWID on Oracle and all columns on PostgreSQL. Name the key column(s)
    explicitly.
    ```

    Hãy xử lý cảnh báo này trong quá trình code review để đảm bảo ứng dụng vận hành chính xác trên môi trường production.

`keyProperty` là **thuộc tính bắt buộc**: bật `useGeneratedKeys` mà thiếu `keyProperty` là lỗi biên dịch.

Với khoá tổ hợp (composite keys), hãy phân tách các tên bằng dấu phẩy ở cả hai thuộc tính; hai danh sách phải có cùng số lượng phần tử:

```java
@Options(useGeneratedKeys = true, keyProperty = "tenantId,id", keyColumn = "tenant_id,id")
```

## `keyProperty` khi có nhiều tham số

Khi phương thức có nhiều hơn một tham số, `keyProperty` phải chỉ rõ tên tham số tiền tố:

```java
@Insert("INSERT INTO users (name) VALUES (#{u.name})")
@Options(useGeneratedKeys = true, keyProperty = "u.id", keyColumn = "id")
int insert(@Param("u") User u, @Param("audit") String audit);
```

Tên tham số không tồn tại sẽ bị bắt ngay **lúc biên dịch**, không phải lỗi `ReflectionException` lúc runtime.

## Insert theo batch

Một `@Insert` nhận `List<T>` biên dịch thành `addBatch()` / `executeBatch()`, và các khoá trả về dưới dạng một `ResultSet` duy nhất được ánh xạ tương ứng vào từng phần tử của danh sách:

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

Phép kiểm tra số lượng này đảm bảo an toàn: một số JDBC driver trả về ít khoá hơn số dòng chèn thực tế. Việc bỏ qua lỗi này sẽ khiến một phần dữ liệu trong batch có id không được gán mà không ai hay biết. `LarkBatisKeyCountMismatchException` sẽ chỉ rõ tên statement, số lượng khoá kỳ vọng và số lượng thực tế nhận được.

## `<selectKey>` không được hỗ trợ { #selectkey-is-not-supported }

Những database không hỗ trợ khoá tự sinh (hoặc quy trình đọc sequence *trước* khi insert) thường dùng `<selectKey>` trong MyBatis. Tính năng này không được hỗ trợ vì thực chất nó là một câu lệnh thứ hai chạy ngầm ẩn dưới dạng tuỳ chọn. Hãy viết tường minh câu lệnh thứ hai đó ra:

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

[Trình quét mã cũ](../features/migration.md) sẽ tự động phát hiện mọi thẻ `<selectKey>` và gợi ý đoạn code thay thế tương ứng.

## Khi không có khoá nào trả về

Nếu một statement khai báo `useGeneratedKeys` mà JDBC driver không trả về khoá nào, `LarkBatisNoKeyException` sẽ được ném ra kèm tên statement, ngăn ngừa việc giá trị mặc định `0` lan truyền trong ứng dụng và gây lỗi ở tầng nghiệp vụ khác.
