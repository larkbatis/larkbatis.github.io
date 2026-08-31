# Build Plugins

You need a build plugin **only if some of your statements live in mapper XML**. A purely
annotation-based project works with the annotation processor alone.

## Why a plugin at all

`Filer.getResource` has no specified way to reach files under `src/main/resources`, and
the implementations that get there disagree on how. The processor therefore reads mapper
XML with plain `java.io`, taking a directory path as an option.

Supplying that path is half the job. The other half is registering the XML files as compile
inputs, without which an XML-only edit triggers no regeneration at all. Both plugins exist
to do those two things. Neither generates code itself, and neither adds anything to the
application's runtime classpath.

## Gradle

```kotlin title="build.gradle.kts"
plugins {
    java
    id("io.github.larkbatis") version "0.1.0-SNAPSHOT"
}

dependencies {
    implementation("io.github.larkbatis:larkbatis-runtime:0.1.0-SNAPSHOT")
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0-SNAPSHOT")
    // larkbatis-processor lands on annotationProcessor automatically
}
```

What it does, and all it does:

- passes `-Alarkbatis.mapperDir=<dirs>` to `compileJava` (default `src/main/resources`;
  only files whose root element is `<mapper>` are read, so other XML in the same tree is
  ignored),
- registers the mapper XML files as inputs of `compileJava`, so editing a mapper
  recompiles the mappers,
- adds `io.github.larkbatis:larkbatis-processor` to the `annotationProcessor`
  configuration.

```kotlin title="Configuration"
larkbatis {
    mapperDir = layout.projectDirectory.dir("src/main/mappers")
    mapperDirs.from("src/main/legacy-mappers")   // as many more as the module has
    addProcessorDependency = false               // manage the processor version yourself
    addParametersFlag = false                    // only with @Param on every parameter
}
```

It also registers `larkbatisScan`, the [migration report](../features/migration.md), over
this project:

```console
./gradlew larkbatisScan
./gradlew larkbatisScan --args="--summary src/main"
```

## Maven

```xml title="pom.xml"
<build>
  <plugins>
    <plugin>
      <groupId>io.github.larkbatis</groupId>
      <artifactId>larkbatis-maven-plugin</artifactId>
      <version>0.1.0-SNAPSHOT</version>
      <extensions>true</extensions>   <!-- required -->
    </plugin>
  </plugins>
</build>
```

```xml title="Configuration (all optional)"
<configuration>
  <mapperDir>src/main/mappers</mapperDir>     <!-- default: src/main/resources -->
  <mapperDirs>                                <!-- as many more as the module has -->
    <mapperDir>src/main/legacy-mappers</mapperDir>
  </mapperDirs>
  <addProcessorPath>false</addProcessorPath>  <!-- default: true -->
  <addParameters>false</addParameters>        <!-- default: true -->
</configuration>
```

### `<extensions>true</extensions>` is not optional

Maven finalizes every mojo's configuration **before the first mojo of a project runs**, so
a mojo bound to an early phase cannot add compiler arguments to the `compile` execution.
The plugin therefore works as a build extension (`AbstractMavenLifecycleParticipant`),
which runs before execution plans are calculated. For each project declaring it, the
extension:

- injects `-Alarkbatis.mapperDir=<dirs>` into `maven-compiler-plugin`'s `<compilerArgs>`
  (skipped where that option is already passed by hand),
- appends `larkbatis-processor` to `<annotationProcessorPaths>`, creating the element
  when absent,
- binds `larkbatis:refresh` at `generate-sources`,
- sets the `larkbatis.mapperDir` project property.

Both injections target **every `compile`-bound execution** of the compiler plugin, not
just its plugin-level `<configuration>`. Maven copies plugin-level configuration into those
executions while the project is being read, before any extension runs, and the plan uses
the execution's own configuration.

Without `<extensions>true</extensions>` none of this happens, **silently**. Run
`mvn larkbatis:check` to diagnose that case.

### The `refresh` goal

`maven-compiler-plugin` recompiles on stale `.java` files only, so an XML-only edit would
otherwise change nothing. `larkbatis:refresh` touches the mapper interface source whose
XML content changed since the last build. Change detection is by **content hash**, recorded
in `target/larkbatis/mapper-xml.properties`, so neither a future-dated file nor a coarse
filesystem clock can mislead it the way timestamps would. The goal is best-effort: IO
problems become warnings, never a failed build.

### Three things worth knowing

!!! warning "Other annotation processors"

    If `<annotationProcessorPaths>` did not exist before, creating it switches javac from
    classpath processor discovery to explicit paths only. Add your other processors
    (Lombok, MapStruct, …) to it, or set `<addProcessorPath>false</addProcessorPath>` and
    manage the paths yourself.

!!! warning "`addProcessorPath=false` on JDK 23+"

    javac no longer discovers processors from the compile classpath, and
    `-Alarkbatis.mapperDir` does not count as asking for annotation processing either.
    If you opt out and put `larkbatis-processor` on the classpath instead, add it to
    `<annotationProcessorPaths>` or set `<proc>full</proc>` yourself. The failure mode
    otherwise is no generated mappers and no error.

!!! danger "Do not set `<useIncrementalCompilation>false</useIncrementalCompilation>`"

    The processor is *aggregating*: it writes one `LarkBatisMappers` registry listing
    every mapper in the compilation. The compiler plugin's default behaviour recompiles
    all sources once any of them is stale, which is what makes that registry whole.
    Compiling only the stale sources would regenerate it from a partial view.

## Limits shared by both plugins

| | |
|---|---|
| Test-scoped mappers | Not supported. Only `compileJava` / the `compile` execution is wired. Mapper interfaces belong in `src/main/java`; test sources use them as ordinary classes |
| Multi-module builds | Everything is per-project. A mapper XML must live in the same module as the interface its `namespace` names; one pointing elsewhere is ignored with a build warning |
| `mapperDir` containing a comma | Not supported. The processor treats commas as separators between directories |
| A mapper directory in another module | Allowed but pointless: a namespace has to name an interface compiled in the same module, and a file matching none is reported and ignored |

Several directories at once — and the rules for combining them with the singular
setting — are in [Configuration](../features/configuration.md#mapper-xml-in-more-than-one-directory).

## Doing it without a plugin

Passing `-Alarkbatis.mapperDir` by hand works and generates correct code. What you lose
is the input registration: editing only an XML file may not regenerate anything, so you
have to `clean` first. [Configuration](../features/configuration.md) has the full option
list.
