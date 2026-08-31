# Architecture & Design Wiki

The reference sections explain *how* to use LarkBatis. This wiki explains *why* LarkBatis is built the way it is, along with the technical trade-offs behind each design decision.

<div class="grid cards" markdown>

-   **[Architecture](architecture.md)**

    The two-phase compile/runtime model, module breakdown, and internal pipeline from AST to emitted Java source.

-   **[Shape vs Value](shape-vs-value.md)**

    The core architectural principle: separating compile-time structural decisions from runtime value evaluation.

-   **[Generated Code](generated-code.md)**

    Anatomy of generated Java files and why readable generated code is a primary design goal.

-   **[Call Lifecycle](call-flow.md)**

    Tracing a single database query through LarkBatis versus the standard MyBatis call stack.

-   **[Design Rules](design-rules.md)**

    Nine non-negotiable architectural constraints that govern all LarkBatis code changes.

-   **[Performance & Benchmarks](performance.md)**

    Microbenchmark results, realistic database latency comparisons, and scenarios where build-time compilation helps most.

</div>

## The Core Concept

In standard MyBatis, every query execution involves runtime overhead: dynamic JDK proxy dispatch, runtime OGNL expression evaluation for `<if>` tags, runtime `TypeHandler` registry lookups, and reflective bean setter calls for every single result row.

None of that structural work actually depends on runtime data. The query shape and data model are completely fixed once you save your code.

LarkBatis shifts that entire resolution phase into `javac`. It analyzes mapper interfaces and XML during compilation and emits plain, readable JDBC code. The runtime footprint is approximately 1,500 lines of code with zero reflection, zero bytecode manipulation, and native GraalVM compatibility out of the box.

## The Problem We Solve

Ahead-of-time compilation for database queries isn't new—frameworks like Micronaut Data and jOOQ have taken similar approaches.

However, existing tools require rewriting your entire query layer into their custom DSLs or query methods. They don't support existing MyBatis XML mappers, dynamic SQL tags (`<if>`, `<where>`, `<foreach>`), and `#{}` / `${}` parameter bindings that vast enterprise codebases rely on.

LarkBatis provides a direct upgrade path for MyBatis codebases: keep your existing mapper XML and SQL patterns, but replace runtime interpretation with compile-time generated code.
