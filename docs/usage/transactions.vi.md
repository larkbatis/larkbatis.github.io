# Transaction

Trong ứng dụng độc lập, `LarkBatisTx` quản lý phạm vi transaction. Khi tích hợp với Spring, bạn sử dụng `@Transactional` chuẩn và LarkBatis sẽ tự động đồng bộ kết nối qua Spring Transaction Manager.

## `LarkBatisTx`

```java
try (LarkBatisTx tx = session.begin()) {
    mapper.insert(user);
    mapper.updateBalance(account);
    tx.commit();
}
```

Ba nguyên tắc cốt lõi giúp đảm bảo an toàn dữ liệu mặc định:

**1 · `commit()` là một lá phiếu (vote), không phải lệnh commit tức thì.** Việc commit thực sự chỉ diễn ra khi phạm vi ngoài cùng đóng lại. Cơ chế này cho phép lồng các scope transaction mà phạm vi bên trong không vô tình commit dở dang công việc của phạm vi bên ngoài.

**2 · Rời khỏi một scope mà không gọi `commit()` sẽ đánh dấu toàn bộ transaction là rollback-only.** Một lệnh `return` sớm, một exception không bắt, hoặc quên gọi `tx.commit()`: tất cả đều kích hoạt rollback an toàn. Bạn không bao giờ rơi vào tình huống lưu dữ liệu dở dang do thoát khối lệnh bất ngờ.

**3 · Gọi commit trên transaction đã bị đánh dấu hỏng sẽ ném ngoại lệ ngay lập tức.** Nếu một scope bên trong kết thúc mà không commit rồi scope ngoài gọi `commit()`, hệ thống sẽ ném `LarkBatisRollbackOnlyException` thay vì âm thầm rollback khiến lập trình viên tưởng nhầm là đã lưu thành công.

```java
try (LarkBatisTx outer = session.begin()) {
    try (LarkBatisTx inner = session.begin()) {  // tham gia vào transaction ngoài
        mapper.insert(a);
        inner.commit();                          // bỏ phiếu hợp lệ
    }
    mapper.insert(b);
    outer.commit();                              // bỏ phiếu; đóng scope ngoài cùng mới commit xuống DB
}
```

### Transaction chỉ đọc (Read-Only)

```java
try (LarkBatisTx tx = session.begin(true)) {
    return mapper.findAll();
}
```

### Kiểm tra trạng thái transaction

`session.hasActiveTransaction()` cho biết luồng hiện tại có đang nằm trong transaction hay không. Phương thức này phục vụ mục đích chẩn đoán hoặc cho các đoạn code cần phân biệt logic trong và ngoài transaction.

## Sử dụng trong Spring

Trong ứng dụng Spring, không dùng `LarkBatisTx` mà sử dụng `@Transactional`:

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

Cơ chế này hoạt động vì `SpringLarkBatisSession.conn()` lấy kết nối qua `DataSourceUtils`. Phương thức này trả về đúng `Connection` đang gắn với transaction Spring hiện tại và chỉ mở kết nối mới khi chưa có transaction nào. `release()` đóng vai trò ngược lại: là no-op khi ở trong transaction, và đóng kết nối thực sự khi ở ngoài transaction.

| Tình huống | Kết quả | Cơ chế hoạt động |
|---|---|---|
| `@Transactional` trên service | Hoạt động | `DataSourceUtils` trả về connection của transaction hiện tại |
| `REQUIRES_NEW`, `NESTED`, rollback rules | Hoạt động | Spring Transaction Manager xử lý; LarkBatis chỉ mượn Connection |
| `readOnly = true` | Hoạt động | Spring tự động đặt cờ readOnly trên Connection |
| Mapper gọi ngoài transaction | Hoạt động | Chế độ auto-commit; Connection được đóng và hoàn trả về pool ngay khi gọi `release` |
| Chia sẻ transaction với `JdbcTemplate` hoặc JPA | Hoạt động | Cùng dùng chung `DataSourceUtils` và `PlatformTransactionManager` |
| Phương thức trả về `Stream` | Hoạt động | Trong transaction thì `release` là no-op; luôn bọc `Stream` trong `try-with-resources` |

## Vì sao code sinh ra không bao giờ đóng Connection trực tiếp { #why-generated-code-never-closes-the-connection }

```java
Connection c = s.conn();
try (PreparedStatement ps = c.prepareStatement(SQL)) {   // (1)!
    // ...
} finally {
    s.release(c);                                        // (2)!
}
```

1.  **Statement** nằm trong try-with-resources. **Connection** thì không.
2.  Chỉ `s.release(c)` mới biết connection này có thực sự được phép đóng hay không.

Đặt `Connection` vào try-with-resources sẽ đóng mất một connection đang thuộc về một
transaction đang chạy, và điều đó sai dưới Spring cũng như sai dưới `LarkBatisTx`. Đây
là một [lằn ranh thiết kế](../wiki/design-rules.md): mọi thân phương thức sinh ra đều
mang đúng hình dạng này, và các bài test của bộ phát mã khẳng định điều đó.

## Dịch exception

`s.translate(e, sql)` biến một `SQLException` checked thành cây exception unchecked, mang
theo câu SQL (hoặc một id giả-statement như `tx:commit`) đang được thực thi.

- **Độc lập:** `LarkBatisException` và các lớp con của nó. `e.sql()` cho bạn văn bản
  của statement.
- **Spring:** `SQLExceptionTranslator` của Spring, mặc định là
  `SQLExceptionSubclassTranslator`. Bộ dịch này đọc cây lớp con `SQLException` chuẩn chứ
  không dùng bảng mã lỗi riêng theo từng hãng. Nhờ vậy một vi phạm ràng buộc duy nhất sẽ đến
  dưới dạng `DuplicateKeyException`, y hệt như khi đến từ `JdbcTemplate`, và những
  `@ExceptionHandler` sẵn có của bạn vẫn chạy nguyên.

Xem [Lỗi và chẩn đoán](../features/errors.md) để có danh sách exception đầy đủ.
