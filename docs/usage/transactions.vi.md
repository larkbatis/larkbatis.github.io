# Quản lý Transaction

Khi chạy độc lập (standalone JDBC), LarkBatis cung cấp `LarkBatisTx` hỗ trợ **programmatic transaction scope** tương thích với `AutoCloseable`. Khi chạy trong Spring Boot, transaction được quản lý qua annotation `@Transactional` thông qua `DataSourceUtils`.

## `LarkBatisTx` trong Standalone JDBC

```java
try (LarkBatisTx tx = session.begin()) {
    mapper.insert(user);
    mapper.updateBalance(account);
    tx.commit();
}
```

Ba nguyên tắc cốt lõi:

1. **`commit()` mang ngữ nghĩa vote (bỏ phiếu)**: Lệnh commit thực sự xuống database chỉ được thực hiện khi scope ngoài cùng đóng lại thành công. Điều này cho phép lồng các transaction scope một cách an toàn.
2. **Tự động chuyển sang rollback-only khi rời scope chưa commit**: Nếu xảy ra exception hoặc thoát khối `try` mà chưa gọi `tx.commit()`, toàn bộ transaction sẽ tự động chuyển sang trạng thái rollback-only.
3. **Commit trên transaction hỏng sẽ ném ngoại lệ rõ ràng**: Nếu scope con bên trong bị rollback và scope ngoài cố tình gọi `commit()`, hệ thống sẽ ném `LarkBatisRollbackOnlyException` thay vì âm thầm rollback trong im lặng.

```java
try (LarkBatisTx outer = session.begin()) {
    try (LarkBatisTx inner = session.begin()) {  // Tham gia vào transaction ngoài (nested scope)
        mapper.insert(a);
        inner.commit();                          // Bỏ phiếu (vote)
    }
    mapper.insert(b);
    outer.commit();                              // Bỏ phiếu; đóng scope ngoài cùng mới commit vật lý
}
```

### Transaction chỉ đọc (Read-Only)

```java
try (LarkBatisTx tx = session.begin(true)) {
    return mapper.findAll();
}
```

## Sử dụng với Spring `@Transactional`

Trong ứng dụng Spring, bạn không cần dùng `LarkBatisTx` mà sử dụng trực tiếp `@Transactional`:

```java
@Service
public class AccountService {

    private final AccountMapper accounts;

    public AccountService(AccountMapper accounts) {
        this.accounts = accounts;
    }

    @Transactional
    public void transfer(long from, long to, long amount) {
        Account a = accounts.findById(from);
        Account b = accounts.findById(to);
        a.setBalance(a.getBalance() - amount);
        b.setBalance(b.getBalance() + amount);
        accounts.updateBalance(a);
        accounts.updateBalance(b);
    }
}
```

`SpringLarkBatisSession.conn()` lấy kết nối thông qua `DataSourceUtils.getConnection(dataSource)`. Nhờ đó:
- Sử dụng chung transaction với `JdbcTemplate` hoặc Hibernate/JPA trong cùng một transaction context.
- Tự động hoàn trả kết nối về connection pool sau khi kết thúc transaction hoặc câu lệnh đơn lẻ.

## Nguyên tắc quản lý Connection trong mã nguồn sinh ra { #why-generated-code-never-closes-the-connection }

Mã nguồn Java sinh ra luôn tuân thủ cấu trúc sau:

```java
Connection c = s.conn();
try (PreparedStatement ps = c.prepareStatement(SQL)) {   // Statement được quản lý bằng try-with-resources
    // Thực thi truy vấn
} finally {
    s.release(c);                                        // Giải phóng connection qua session
}
```

- **PreparedStatement** và **ResultSet** luôn nằm trong `try-with-resources`.
- **Connection** tuyệt đối không bọc trong `try-with-resources` mà giải phóng qua `s.release(c)`. Điều này đảm bảo connection đang nằm trong transaction không bị đóng đột ngột.

