# Wiki

The reference pages tell you *what* LightBatis does. These tell you *why* it is built the
way it is, and what that costs.

<div class="grid cards" markdown>

-   **[Architecture](architecture.md)**

    Two phases, the module split, and the pipeline from mapper source to generated Java.

-   **[Shape vs Value](shape-vs-value.md)**

    The single cut that the whole design follows: the closed list of things allowed to be
    resolved at runtime.

-   **[Generated Code](generated-code.md)**

    What each emitted file looks like, and why readability is a feature rather than a
    nicety.

-   **[Life of a Call](call-flow.md)**

    One mapper call, step by step, against the MyBatis path that it replaces.

-   **[Design Red Lines](design-rules.md)**

    Nine rules that hold in every change, and what breaks if one is relaxed.

-   **[Performance](performance.md)**

    The measured numbers, the unmeasured claims, and where the benefit genuinely does not
    apply.

</div>

## The premise in one paragraph

A MyBatis mapper call is resolved at runtime — the proxy dispatch, the OGNL evaluation of
every `<if test>`, the `TypeHandler` lookup per parameter, the reflective `setValue` per
column per row. None of that depends on the *values* flowing through the call. It depends
on the *shape* of the mapper, which stopped changing the moment you saved the file. So
resolve the shape once, at build time, and emit the JDBC calls directly. What remains at
runtime is roughly 1,500 lines with no dependencies beyond JDBC — and, because there is no
reflection anywhere, no GraalVM reachability metadata to write.

## What is deliberately not novel

LightBatis is not a new idea, and the design says so plainly. Micronaut Data compiles
queries into code at build time with no reflection; jOOQ generates from a schema; Spring
Data has an AOT branch. **What none of them do is keep the MyBatis mapper model** —
mapper XML, `#{}`, `<if>`, `<foreach>`, `<resultMap>` — which thousands of codebases in
Korea and Japan run on today.

The value is in the migration path, not in the idea. That framing decides a lot of the
design: it is why the XML frontend exists at all, why the differential test harness
compares generated SQL against MyBatis's interpreted output, and why every dropped feature
comes with a compile error naming the replacement rather than silence.
