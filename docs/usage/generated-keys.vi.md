# Khoá tự sinh

`@Options(useGeneratedKeys = true, ...)` hỏi driver lấy khoá mà một `INSERT` sinh ra rồi
gán nó vào một property của đối tượng tham số.

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

1.  **Tên cột** khoá viết tường minh, bởi vì `RETURN_GENERATED_KEYS` mang ý nghĩa khác
    nhau trên các database khác nhau. Xem bên dưới.
2.  Cả setter lẫn accessor đều được chọn lúc build từ `keyProperty` và kiểu khai báo của
    property đó.

## Luôn gọi tên các cột khoá

!!! warning "`keyColumn` là tuỳ chọn trong annotation nhưng trên thực tế gần như bắt buộc"

    `prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)` không khả chuyển:

    - **Oracle** trả về `ROWID`, không phải giá trị sequence của bạn.
    - **PostgreSQL** trả về *mọi* cột của dòng vừa chèn.

    Truyền một `String[]` tên cột tường minh là dạng duy nhất mang cùng một nghĩa ở mọi
    nơi. Khi có `keyColumn`, bộ sinh code phát ra `prepareStatement(sql, String[])`. Khi
    thiếu nó, chẳng có tên nào để bỏ vào mảng, nên nó lùi về `RETURN_GENERATED_KEYS` và
    đưa ra một **cảnh báo build bắt buộc**:

    ```text
    warning: useGeneratedKeys without keyColumn falls back to RETURN_GENERATED_KEYS,
    which returns ROWID on Oracle and all columns on PostgreSQL. Name the key column(s)
    explicitly.
    ```

    Hãy coi cảnh báo đó là lỗi khi review. Nó là khác biệt giữa "chạy được trên H2" và
    "chạy được trên production".

Ngược lại, `keyProperty` là **bắt buộc**: `useGeneratedKeys` mà thiếu nó là lỗi biên
dịch, hỏi rằng khoá thì nên đi đâu.

Khoá tổ hợp thì viết cách nhau bằng dấu phẩy ở cả hai thuộc tính, và hai danh sách phải
dài bằng nhau, và lệch nhau là lỗi biên dịch nêu rõ cả hai con số:

```java
@Options(useGeneratedKeys = true, keyProperty = "tenantId,id", keyColumn = "tenant_id,id")
```

## `keyProperty` khi có nhiều tham số

Khi phương thức có nhiều hơn một tham số, `keyProperty` phải gọi tên cả tham số:

```java
@Insert("INSERT INTO users (name) VALUES (#{u.name})")
@Options(useGeneratedKeys = true, keyProperty = "u.id", keyColumn = "id")
int insert(@Param("u") User u, @Param("audit") String audit);
```

Sai tên là **lỗi lúc biên dịch**, không phải một `ReflectionException` lúc chạy.

## Insert theo batch

Một `@Insert` nhận `List<T>` biên dịch thành `addBatch()` / `executeBatch()`, và các khoá
quay về dưới dạng một `ResultSet` duy nhất phải khớp hàng với danh sách:

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

Phép kiểm số lượng này không phải lập trình phòng thủ cho có: có những driver trả về ít
khoá hơn số dòng, và MyBatis cũng ghi nhận đúng kiểu hỏng đó. Âm thầm chấp nhận sẽ để
lại một phần batch với id chưa được gán mà chẳng ai hay, nên
`LarkBatisKeyCountMismatchException` gọi tên statement, số lượng mong đợi và số lượng
thực tế.

## `<selectKey>` không được hỗ trợ { #selectkey-is-not-supported }

Những database không hỗ trợ khoá tự sinh (hoặc những quy trình đọc sequence *trước* khi
insert) vẫn dùng `<selectKey>` trong MyBatis. Nó không được hiện thực, bởi vì nó là một
statement thứ hai đội lốt một tuỳ chọn. Hãy viết statement thứ hai đó ra:

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

[Trình quét mã cũ](../features/migration.md) báo cáo mọi `<selectKey>` mà nó tìm thấy kèm
đúng cách sửa này.

## Khi không có khoá nào quay về

Nếu một statement khai báo `useGeneratedKeys` mà driver chẳng trả về gì,
`LarkBatisNoKeyException` được ném ra kèm tên statement, thay vì để một id `0` đi lang
thang trong code của bạn rồi chết ở một chỗ chẳng liên quan.
