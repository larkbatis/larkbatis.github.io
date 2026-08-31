# Transactions

In standalone Java applications, `LarkBatisTx` manages transaction scopes. In Spring applications, you use standard `@Transactional` annotations and LarkBatis handles connection binding automatically.

## `LarkBatisTx` (Standalone Java)

```java
try (LarkBatisTx tx = session.begin()) {
    mapper.insert(user);
    mapper.updateBalance(account);
    tx.commit();
}
```

Key rules:

**1. `commit()` votes to commit.** The actual database commit executes only when the outermost transaction scope closes. This allows nested scopes without premature commits.

**2. Exiting without voting marks the transaction rollback-only.** Any unhandled exception, early `return`, or missing `commit()` call triggers an automatic rollback when the try-with-resources block exits.

**3. Committing a poisoned transaction throws an exception.** If an inner scope exits without voting and the outer scope calls `commit()`, LarkBatis throws `LarkBatisRollbackOnlyException` rather than silently rolling back.

```java
try (LarkBatisTx outer = session.begin()) {
    try (LarkBatisTx inner = session.begin()) {  // joins outer transaction
        mapper.insert(a);
        inner.commit();                          // records vote
    }
    mapper.insert(b);
    outer.commit();                              // records vote; outermost close executes commit
}
```

### Read-only scopes

```java
try (LarkBatisTx tx = session.begin(true)) {
    return mapper.findAll();
}
```

### Active transaction checks

`session.hasActiveTransaction()` checks whether the calling thread is inside an active transaction.

## Spring Integration

In Spring applications, do not use `LarkBatisTx`. Use standard `@Transactional` annotations:

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

This works because `SpringLarkBatisSession.conn()` delegates to Spring's `DataSourceUtils`, obtaining the connection bound to the active transaction. `release()` is a no-op during active transactions and closes the connection only outside transactions.

| Scenario | Behavior |
|---|---|
| `@Transactional` on services | `DataSourceUtils` returns the transaction's connection |
| Propagation rules (`REQUIRES_NEW`, `NESTED`) | Managed entirely by Spring Transaction Manager |
| `readOnly = true` | Handled by Spring on the connection |
| Outside transactions | Standard auto-commit per statement |
| Interop with `JdbcTemplate` / JPA | Shares identical transaction context via `DataSourceTransactionManager` |
| `Stream<T>` query methods | Transaction manages connection lifecycle; caller closes the stream |

## Why generated code never closes Connections directly

```java
Connection c = s.conn();
try (PreparedStatement ps = c.prepareStatement(SQL)) {   // (1)!
    ...
} finally {
    s.release(c);                                        // (2)!
}
```

1.  **Statements** are managed with try-with-resources.
2.  **Connections** are released via `s.release(c)`.

Closing a `Connection` directly inside try-with-resources would break active Spring or `LarkBatisTx` transactions. This is a core architectural rule: all generated methods use `s.release(c)`.

## Exception translation

`s.translate(e, sql)` converts checked `SQLException`s into runtime exception trees:

- **Standalone**: `LarkBatisException` and its subclasses. `e.sql()` provides the failed SQL query.
- **Spring**: Spring's `SQLExceptionTranslator` translates errors into Spring's `DataAccessException` hierarchy (e.g. `DuplicateKeyException`), matching `JdbcTemplate` behavior.

See [Errors and Diagnostics](../features/errors.md) for the complete list.
