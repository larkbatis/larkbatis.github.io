# Transaction

Ngoài Spring, `LarkBatisTx` là phạm vi transaction. Trong Spring, bạn dùng
`@Transactional` còn LarkBatis đứng hẳn sang một bên.

## `LarkBatisTx`

```java
try (LarkBatisTx tx = session.begin()) {
    mapper.insert(user);
    mapper.updateBalance(account);
    tx.commit();
}
```

Ba quy tắc, và cả ba đều nhằm biến kết cục an toàn thành kết cục mặc định:

**1 · `commit()` là một lá phiếu, không phải lệnh commit.** Việc commit thật sự xảy ra
khi phạm vi ngoài cùng đóng lại. Chính điều đó cho phép các phạm vi lồng nhau mà phạm vi
bên trong không commit mất phần việc mà phạm vi ngoài chưa làm xong.

**2 · Rời một phạm vi mà không bỏ phiếu sẽ đánh dấu cả transaction là chỉ-rollback.** Một
lệnh `return` sớm, một exception được ném ra, một `commit()` bị quên: tất cả đều
rollback. Bạn không bao giờ rơi vào cảnh một nửa công việc đã lưu chỉ vì bỏ sót một lối
ra khỏi khối lệnh.

**3 · Commit một transaction đã bị đánh dấu hỏng thì ném exception.** Nếu một phạm vi bên
trong rời đi mà không bỏ phiếu rồi phạm vi ngoài gọi `commit()`, bạn nhận
`LarkBatisRollbackOnlyException` chứ không phải một lần rollback âm thầm trông y như
một lần commit thành công dưới mắt người gọi.

```java
try (LarkBatisTx outer = session.begin()) {
    try (LarkBatisTx inner = session.begin()) {  // nhập vào transaction ngoài
        mapper.insert(a);
        inner.commit();                          // bỏ phiếu
    }
    mapper.insert(b);
    outer.commit();                              // bỏ phiếu; lần đóng ngoài cùng mới commit
}
```

### Chỉ đọc

```java
try (LarkBatisTx tx = session.begin(true)) {
    return mapper.findAll();
}
```

### Kiểm tra

`session.hasActiveTransaction()` cho biết luồng đang gọi có nằm trong một phạm vi hay
không. Phương thức này có mặt để chẩn đoán và cho những đoạn code phải hành xử khác nhau
trong và ngoài transaction, chứ không phải để code sinh ra tra cứu.

## Dưới Spring

Đừng dùng `LarkBatisTx` trong một ứng dụng Spring. Hãy dùng `@Transactional`:

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

Nó chạy được vì `SpringLarkBatisSession.conn()` đi hỏi `DataSourceUtils`. Hàm đó trả về
đúng connection đã gắn vào transaction đang chạy, và chỉ mở một connection mới khi chưa
có cái nào. `release()` làm ngược lại: lệnh rỗng khi ở trong
transaction, một lần đóng thật khi ở ngoài.

| Tình huống | | Vì sao |
|---|---|---|
| `@Transactional` trên service, mapper được gọi bên trong | chạy | `DataSourceUtils` trả về connection của transaction |
| `REQUIRES_NEW`, `NESTED`, các quy tắc rollback | chạy | Spring lo hết; LarkBatis chỉ đi xin một connection |
| `readOnly = true` | chạy | Spring đặt cờ đó lên connection |
| Mapper được gọi ngoài mọi transaction | chạy | Auto-commit; connection được đóng ngay khi release |
| Chia sẻ transaction với `JdbcTemplate` hoặc JPA | chạy | Cùng `DataSourceUtils`, cùng `DataSourceTransactionManager` |
| Phương thức trả về `Stream` | chạy | Trong transaction thì `release` là lệnh rỗng và transaction giữ connection; dùng `try (Stream<T> …)` trong mọi trường hợp |

## Vì sao code sinh ra không bao giờ đóng Connection { #why-generated-code-never-closes-the-connection }

```java
Connection c = s.conn();
try (PreparedStatement ps = c.prepareStatement(SQL)) {   // (1)!
    ...
} finally {
    s.release(c);                                        // (2)!
}
```

1.  **Statement** nằm trong try-with-resources. **Connection** thì không.
2.  Chỉ `release` mới biết connection này có thực sự được phép đóng hay không.

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
