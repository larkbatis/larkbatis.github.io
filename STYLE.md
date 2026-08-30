# Style sheet

Rules for both languages on this site. They exist because a first pass over the corpus
found the same tic repeated hundreds of times: 262 em dashes in 25,000 words of English,
and a Vietnamese translation that had inherited the English sentence architecture wholesale.

Run the checks in [Enforcement](#enforcement) before publishing.

---

## English

### Punctuation

**Budget: fewer than 0.3 em dashes per 100 words** (the corpus started at 1.05, roughly one
every two sentences). The em dash is the right tool for a genuine interruption. It is the
wrong tool for a definition, a list, an appositive, or a second thought — all of which have
their own punctuation.

| Instead of a dash | Use |
|---|---|
| `X — the thing that does Y — is Z` | a relative clause, or two sentences |
| `A, B and C — none of that matters` | a colon, or start the sentence with the conclusion |
| `it is fast — 54 ns per row` | a colon |
| `this is deliberate — see [X]` | a full stop, then the sentence |

### Do not justify every decision the same way

The corpus reached for one shape whenever a design choice needed defending:
*"That is not a shortcut / an oversight / style. It is deliberate."* It appeared 24 times
(`deliberate`, `on purpose`, `by design`) plus 39 `rather than` and 5 `That is not`.

The reader stops registering an argument that always arrives in the same clothes. Vary the
move:

- state the constraint first and let the decision follow from it
- name the failure the alternative produces
- give the number
- show the two-line code difference
- say nothing, because the surrounding text already made it obvious

`deliberate` is worth keeping where the reader would otherwise file something as a bug.
Spend it there and nowhere else.

### One explanation, one home

Four explanations were being retold on six or seven pages each, in slightly different words
every time. That is what made the corpus feel padded. Each now has a canonical page; every
other mention is one sentence plus a link.

| Topic | Canonical page |
|---|---|
| `-parameters` and Gradle incremental builds | `usage/troubleshooting.md` |
| Why the `Connection` is not in try-with-resources | `usage/transactions.md#why-generated-code-never-closes-the-connection` |
| `DataSourceUtils` and the connection contract | `usage/spring.md` |
| `RETURN_GENERATED_KEYS` portability | `usage/generated-keys.md` |
| Why `Filer.getResource` forces a build plugin | `getting-started/build-plugins.md` |

Adding a sixth retelling of any of these is a review comment, not an edit.

### Sentence openings

26 sentences opened with `That is` / `This is` / `It is` / `There is`. They point backwards
at an abstraction the reader has to reconstruct. Name the thing instead.

### `See [X].`

25 sections ended with one. Keep it where the link is genuinely the next thing to read;
delete it where the link already appears in the paragraph above.

---

## Vietnamese

Vietnamese pages are `*.vi.md` siblings, built by `mkdocs-static-i18n`. They are
**rewritten from the English, not translated sentence by sentence.** The defect the first
pass produced was not vocabulary — it was English sentence architecture carried over intact.

### Register, by directory

Follows the `vietnamese-tech-writing` skill's document-register table.

| Directory | Register | Address |
|---|---|---|
| `docs/index.vi.md`, `getting-started/`, `usage/` | `eng-readme` | `bạn` |
| `wiki/` — architecture, design notes | `eng-impersonal` | **no `bạn` at all** |
| `features/` | `eng-readme` | `bạn`, sparingly |

Impersonal does not mean stiff. Vietnamese drops the subject comfortably where English
cannot:

| Not | But |
|---|---|
| `Bạn có thể tự kiểm bằng cách đọc code` | `Có thể tự kiểm bằng cách đọc code` |
| `Bạn sẽ thấy một lỗi biên dịch` | `Trình biên dịch sẽ báo lỗi` |
| `Bạn cần khai báo requires static java.compiler` | `Cần khai báo requires static java.compiler` |

### Sentence shape

Vietnamese carries a mid-sentence parenthetical badly. Where the English interrupts itself,
the Vietnamese splits into two sentences or uses a colon.

```
❌  release() là tấm gương phản chiếu của nó — lệnh rỗng khi ở trong transaction,
    một lần đóng thật khi ở ngoài.
✅  release() làm ngược lại: trong transaction thì không làm gì, ngoài transaction
    thì đóng thật.
```

### Do not calque an English metaphor

This is the failure mode a linter cannot catch, because each one is a novel phrase rather
than a dictionary entry. Every row below was found in the first pass.

| ❌ Calque | English behind it | ✅ Native |
|---|---|---|
| `thứ chịu lực` | load-bearing | `bắt buộc, không phải cho đẹp` |
| `tấm gương phản chiếu của nó` | its mirror | `làm ngược lại` |
| `nhánh nổ ra` | a branch fires | `nhánh được chọn` |
| `transaction nhiễm độc` | a poisoned transaction | `transaction đã bị đánh dấu hỏng` |
| `khoác áo một tuỳ chọn` | wearing the costume of an option | `đội lốt một tuỳ chọn` |
| `một cái nhún vai` | a shrug | delete it |
| `Đường thất bại` | the failure path | `nhánh xử lý lỗi` |

When an English sentence leans on a metaphor, say what the metaphor *means* in Vietnamese
rather than importing the image.

### Glossary — fixed for this site

Vietnamese engineering prose is natively bilingual. The terms below stay English inside
Vietnamese sentences; translating them is the loudest machine-translation tell.

**Keep English:** `mapper`, `statement`, `annotation`, `processor`, `build`, `runtime`,
`proxy`, `reflection`, `transaction`, `connection`, `cache`, `driver`, `pool`, `stream`,
`batch`, `commit`, `rollback`, `deploy`, `production`, `staging`, `pipeline`, `bean`,
`getter`, `setter`, `parser`, `token`, `native image`, `shape` (the project's own term —
gloss it once on first use per page).

**Translate, and hold the choice:**

| EN | ✅ | ❌ was |
|---|---|---|
| resolve (a name, a type) | `resolve`, or `xác định` | `phân giải` |
| SQL text | `câu SQL`, `chuỗi SQL` | `văn bản SQL` |
| splice | `chèn thẳng vào SQL` | `chỗ nối` |
| cardinality | `số phần tử` | `lực lượng` |
| guarded append | `chỉ nối khi điều kiện đúng` | `lệnh nối có canh gác` |
| code generator | `bộ sinh code` | — (keep) |
| compile error | `lỗi biên dịch` | — (keep) |
| allocation | `cấp phát` | — (keep) |
| wrapper type | `kiểu bọc` | `lớp bọc` |
| entry point | `điểm vào` | — (keep) |
| intermediate representation | `IR`, gloss once | `biểu diễn trung gian` |

### Tone marks and numbers

- **kiểu mới** throughout: `hoà`, `thuỷ`, `khoá`, `tuỳ`, `huỷ`. The corpus is already 100%
  consistent here — do not reintroduce `khóa` / `tùy`.
- Decimal comma, thousands period: `3,38 ms`, `10.000 dòng`, `1.500 dòng`.
- NFC Unicode. The validator's `--fix` rewrites violations in place.

---

## Enforcement

```bash
S=../.claude/skills/vietnamese-tech-writing

# README-register pages
python3 $S/scripts/validate_copy.py docs/index.vi.md docs/getting-started/*.vi.md \
        docs/usage/*.vi.md docs/features/*.vi.md --register eng-readme

# Impersonal pages
python3 $S/scripts/validate_copy.py docs/wiki/*.vi.md --register eng-impersonal

# Em-dash budget, both languages
python3 scripts/check_style.py
```

`LAW001` (regulated superlative) fires on `duy nhất` and `phổ biến nhất` in technical prose,
where they mean "the only" and "the most common" rather than an advertising claim. It is
suppressed in `scripts/check_style.py`; do not silence the rule globally, because it is
correct for anything user-facing.

`PRO002` on a `wiki/` page is a real finding — that directory takes no `bạn`.
