# Build Plugins

You need a build plugin **only if some of your statements live in mapper XML**. A purely
annotation-based project works with the annotation processor alone.

## Why a plugin at all

The processor reads mapper XML with plain `java.io`, not through the compiler's `Filer`.
That is not a shortcut: `Filer.getResource` is not specified to reach files under
`src/main/resources`, and the implementations that do reach them do not agree on how. So
the processor takes a real directory path instead — and something has to hand it that
path *and* tell the build tool that those XML files are compile inputs, or an XML-only
edit will not trigger regeneration.

That is the entire job of both plugins. Neither generates code itself, and neither adds
anything to the application's runtime classpath.

## Gradle

```kotlin title="build.gradle.kts"
plugins {
    java
    id("io.github.lightbatis") version "0.1.0-SNAPSHOT"
}

dependencies {
    implementation("io.github.lightbatis:lightbatis-runtime:0.1.0-SNAPSHOT")
    implementation("io.github.lightbatis:lightbatis-annotations:0.1.0-SNAPSHOT")
    // lightbatis-processor lands on annotationProcessor automatically
}
```

What it does, and all it does:

- passes `-Alightbatis.mapperDir=<dir>` to `compileJava` (default `src/main/resources`;
  only files whose root element is `<mapper>` are read, so other XML in the same tree is
  ignored),
- registers the mapper XML files as inputs of `compileJava`, so editing a mapper
  recompiles the mappers,
- adds `io.github.lightbatis:lightbatis-processor` to the `annotationProcessor`
  configuration.

```kotlin title="Configuration"
lightbatis {
    mapperDir = layout.projectDirectory.dir("src/main/mappers")
    addProcessorDependency = false   // manage the processor version yourself
}
```

## Maven

```xml title="pom.xml"
<build>
  <plugins>
    <plugin>
      <groupId>io.github.lightbatis</groupId>
      <artifactId>lightbatis-maven-plugin</artifactId>
      <version>0.1.0-SNAPSHOT</version>
      <extensions>true</extensions>   <!-- required -->
    </plugin>
  </plugins>
</build>
```

```xml title="Configuration (all optional)"
<configuration>
  <mapperDir>src/main/mappers</mapperDir>     <!-- default: src/main/resources -->
  <addProcessorPath>false</addProcessorPath>  <!-- default: true -->
</configuration>
```

### `<extensions>true</extensions>` is not optional

Maven finalizes every mojo's configuration **before the first mojo of a project runs**,
so a mojo bound to an early phase cannot add compiler arguments to the `compile`
execution. The plugin therefore works as a build extension
(`AbstractMavenLifecycleParticipant`), which runs before execution plans are calculated.
For each project declaring it, the extension:

- injects `-Alightbatis.mapperDir=<dir>` into `maven-compiler-plugin`'s `<compilerArgs>`
  (skipped where that option is already passed by hand),
- appends `lightbatis-processor` to `<annotationProcessorPaths>`, creating the element
  when absent,
- binds `lightbatis:refresh` at `generate-sources`,
- sets the `lightbatis.mapperDir` project property.

Both injections target **every `compile`-bound execution** of the compiler plugin, not
just its plugin-level `<configuration>` — Maven copies plugin-level configuration into
those executions while the project is being read, before any extension runs, and the
execution's own configuration is what the plan uses.

Without `<extensions>true</extensions>` none of this happens, **silently**. Run
`mvn lightbatis:check` to diagnose that case.

### The `refresh` goal

`maven-compiler-plugin` recompiles on stale `.java` files only, so an XML-only edit would
otherwise change nothing. `lightbatis:refresh` touches the mapper interface source whose
XML content changed since the last build. Change detection is by **content hash**
(recorded in `target/lightbatis/mapper-xml.properties`), not timestamps, so neither a
future-dated file nor a coarse filesystem clock can mislead it. The goal is best-effort:
IO problems become warnings, never a failed build.

### Three things worth knowing

!!! warning "Other annotation processors"

    If `<annotationProcessorPaths>` did not exist before, creating it switches javac from
    classpath processor discovery to explicit paths only. Add your other processors
    (Lombok, MapStruct, …) to it — or set `<addProcessorPath>false</addProcessorPath>` and
    manage the paths yourself.

!!! warning "`addProcessorPath=false` on JDK 23+"

    javac no longer discovers processors from the compile classpath, and
    `-Alightbatis.mapperDir` does not count as asking for annotation processing either.
    If you opt out and put `lightbatis-processor` on the classpath instead, add it to
    `<annotationProcessorPaths>` or set `<proc>full</proc>` yourself — otherwise you get
    no generated mappers and no error.

!!! danger "Do not set `<useIncrementalCompilation>false</useIncrementalCompilation>`"

    The processor is *aggregating*: it writes one `LightBatisMappers` registry listing
    every mapper in the compilation. The compiler plugin's default behaviour recompiles
    all sources once any of them is stale, which is what makes that registry whole.
    Compiling only the stale sources would regenerate it from a partial view.

## Limits shared by both plugins

| | |
|---|---|
| Test-scoped mappers | Not supported. Only `compileJava` / the `compile` execution is wired. Mapper interfaces belong in `src/main/java`; test sources use them as ordinary classes |
| Multi-module builds | Everything is per-project. A mapper XML must live in the same module as the interface its `namespace` names; one pointing elsewhere is ignored with a build warning |
| `mapperDir` containing a comma | Not supported — the processor treats commas as separators between directories |

## Doing it without a plugin

Passing `-Alightbatis.mapperDir` by hand works and generates correct code. What you lose
is the input registration: editing only an XML file may not regenerate anything, so you
have to `clean` first. See [Configuration](../features/configuration.md) for the full
option list.
