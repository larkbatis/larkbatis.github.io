# Transactions

Outside Spring, `LightBatisTx` is the transaction scope. Inside Spring, you use
`@Transactional` and LightBatis stays out of the way entirely.

## `LightBatisTx`

```java
try (LightBatisTx tx = session.begin()) {
    mapper.insert(user);
    mapper.updateBalance(account);
    tx.commit();
}
```

Three rules, and they are all about making the safe outcome the default one:

**1 · `commit()` is a vote, not the commit.** The actual commit happens when the
outermost scope closes. That is what lets scopes nest without an inner one committing
work the outer one has not finished.

**2 · Leaving a scope without voting marks the whole transaction rollback-only.** An
early `return`, a thrown exception, a forgotten `commit()` — all of them roll back. You
never get half the work persisted because a path out of the block was overlooked.

**3 · Committing a poisoned transaction throws.** If an inner scope left without voting
and the outer one then calls `commit()`, you get `LightBatisRollbackOnlyException` rather
than a silent rollback that looks like a successful commit to the caller.

```java
try (LightBatisTx outer = session.begin()) {
    try (LightBatisTx inner = session.begin()) {  // joins the outer transaction
        mapper.insert(a);
        inner.commit();                          // votes
    }
    mapper.insert(b);
    outer.commit();                              // votes; the outermost close commits
}
```

### Read-only

```java
try (LightBatisTx tx = session.begin(true)) {
    return mapper.findAll();
}
```

### Checking

`session.hasActiveTransaction()` reports whether the calling thread is inside a scope.
It is there for diagnostics and for code that must behave differently in and out of a
transaction — not as something generated code consults.

## Under Spring

Do not use `LightBatisTx` in a Spring application. Use `@Transactional`:

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

This works because `SpringLightBatisSession.conn()` asks `DataSourceUtils`, which hands
back the connection already bound to the running transaction and opens a fresh one only
when there is none. `release()` is its mirror: a no-op inside a transaction, a real close
outside one.

| Scenario | | Why |
|---|---|---|
| `@Transactional` on a service, mapper called inside | works | `DataSourceUtils` returns the transaction's connection |
| `REQUIRES_NEW`, `NESTED`, rollback rules | works | Spring handles all of it; LightBatis only asks for a connection |
| `readOnly = true` | works | Spring sets the flag on that connection |
| Mapper called outside any transaction | works | Auto-commit; the connection is closed immediately on release |
| Sharing a transaction with `JdbcTemplate` or JPA | works | Same `DataSourceUtils`, same `DataSourceTransactionManager` |
| A `Stream`-returning method | works | Inside a transaction `release` is a no-op and the transaction keeps the connection; `try (Stream<T> …)` either way |

## Why generated code never closes the Connection

```java
Connection c = s.conn();
try (PreparedStatement ps = c.prepareStatement(SQL)) {   // (1)!
    ...
} finally {
    s.release(c);                                        // (2)!
}
```

1.  The **statement** is in try-with-resources. The **connection** is not.
2.  Only `release` knows whether this connection may really be closed.

Putting the `Connection` in try-with-resources would close a connection that belongs to
a running transaction, which is wrong under Spring and wrong under `LightBatisTx`. This
is a [design red line](../wiki/design-rules.md): every generated body takes this shape,
and the emitter tests assert it.

## Exception translation

`s.translate(e, sql)` turns a checked `SQLException` into the unchecked tree, carrying
the SQL text (or a pseudo-statement id such as `tx:commit`) that was executing.

- **Standalone:** `LightBatisException` and its subclasses. `e.sql()` gives you the
  statement text.
- **Spring:** Spring's `SQLExceptionTranslator` — by default
  `SQLExceptionSubclassTranslator`, which reads the standard `SQLException` subclass tree
  rather than a per-vendor error-code table. So a unique-constraint violation arrives as
  `DuplicateKeyException`, exactly as it would from `JdbcTemplate`, and your existing
  `@ExceptionHandler`s keep working.

See [Errors and Diagnostics](../features/errors.md) for the full exception list.
