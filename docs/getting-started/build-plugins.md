# Build Plugins

You only need a build plugin **if some of your statements live in mapper XML**. If your project uses annotations only, the annotation processor alone is enough.

## Why a plugin?

`Filer.getResource` in Java annotation processing has no standard way to load files from `src/main/resources`, and compilers handle it inconsistently. That's why the processor reads mapper XML directly from the filesystem using plain `java.io`, taking directory paths as compiler options.

Passing those paths is only half the job. The other half is telling your build tool that XML files are compilation inputs. Without that, editing an XML file won't trigger a recompile. That's all these plugins do: they configure compiler options and track XML files as inputs. They don't generate code themselves, and they add nothing to your runtime classpath.

## Gradle

```kotlin title="build.gradle.kts"
plugins {
    java
    id("io.github.larkbatis") version "0.1.2"
}

dependencies {
    implementation("io.github.larkbatis:larkbatis-runtime:0.1.0")
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0")
    // larkbatis-processor is added to annotationProcessor automatically
}
```

What the plugin does:

- Passes `-Alarkbatis.mapperDir=<dirs>` to `compileJava` (defaults to `src/main/resources`; it only parses XML files whose root element is `<mapper>`, ignoring other XML files).
- Registers mapper XML files as task inputs for `compileJava`, so editing XML triggers recompilation.
- Adds `io.github.larkbatis:larkbatis-processor` to `annotationProcessor`.

```kotlin title="Configuration"
larkbatis {
    mapperDir = layout.projectDirectory.dir("src/main/mappers")
    mapperDirs.from("src/main/legacy-mappers")   // add as many extra directories as needed
    addProcessorDependency = false               // manage processor version manually
    addParametersFlag = false                    // disable automatic -parameters flag (requires @Param on all parameters)
}
```

It also registers the `larkbatisScan` task to generate a [migration report](../features/migration.md):

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
      <version>0.1.2</version>
      <extensions>true</extensions>   <!-- required -->
    </plugin>
  </plugins>
</build>
```

```xml title="Configuration (all optional)"
<configuration>
  <mapperDir>src/main/mappers</mapperDir>     <!-- default: src/main/resources -->
  <mapperDirs>                                <!-- extra directories -->
    <mapperDir>src/main/legacy-mappers</mapperDir>
  </mapperDirs>
  <addProcessorPath>false</addProcessorPath>  <!-- default: true -->
  <addParameters>false</addParameters>        <!-- default: true -->
</configuration>
```

### `<extensions>true</extensions>` is required

Maven freezes plugin configurations before any build tasks run. Because of that, a regular plugin running in an early phase cannot inject arguments into `maven-compiler-plugin`.

To solve this, the LarkBatis plugin runs as a Maven build extension (`AbstractMavenLifecycleParticipant`), executing before the build plan is constructed. For each module, it:

- Injects `-Alarkbatis.mapperDir=<dirs>` into `maven-compiler-plugin`'s `<compilerArgs>`.
- Appends `larkbatis-processor` to `<annotationProcessorPaths>` (creating the element if missing).
- Binds `larkbatis:refresh` to the `generate-sources` phase.
- Sets the `larkbatis.mapperDir` project property.

Without `<extensions>true</extensions>`, none of this runs, and Maven will fail **silently** without errors. Run `mvn larkbatis:check` to verify your configuration.

### The `refresh` goal

`maven-compiler-plugin` only recompiles when `.java` source files change. To ensure XML edits trigger recompilation, `larkbatis:refresh` touches the corresponding Java mapper interface whenever its XML content changes.

Change detection uses a **content hash** stored in `target/larkbatis/mapper-xml.properties`, making it immune to filesystem timestamp inaccuracies. If IO issues occur during hash checking, it outputs a warning rather than failing the build.

### Good to know

!!! warning "Other annotation processors"

    If `<annotationProcessorPaths>` didn't exist previously, creating it stops javac from automatically scanning the compilation classpath for processors. Make sure to add your other processors (Lombok, MapStruct, etc.) to `<annotationProcessorPaths>` as well, or set `<addProcessorPath>false</addProcessorPath>` and manage them yourself.

!!! warning "`addProcessorPath=false` on JDK 23+"

    Starting with JDK 23, javac no longer discovers processors from the compile classpath by default. If you disable `addProcessorPath`, you must either list `larkbatis-processor` in `<annotationProcessorPaths>` or pass `<proc>full</proc>`. Otherwise, no mappers will be generated.

!!! danger "Do not set `<useIncrementalCompilation>false</useIncrementalCompilation>`"

    LarkBatis is an aggregating processor: it generates a single `LarkBatisMappers` registry listing every mapper in the compilation. Incremental compilation ensures all sources recompile when any mapper changes, keeping the registry complete.

## Common limitations

| | |
|---|---|
| Test-scoped mappers | Not supported. Only main compilation source sets are wired. Put mapper interfaces in `src/main/java`; tests can call them as normal classes |
| Multi-module builds | Configuration is per-module. XML files must live in the same module as the mapper interface named in their `namespace` |
| Commas in `mapperDir` | Not supported (commas are treated as path separators) |

See [Configuration](../features/configuration.md#mapper-xml-in-more-than-one-directory) for details on multi-directory setups.

## Working without a plugin

You can pass `-Alarkbatis.mapperDir` manually without any plugin. The only downside is that XML edits won't be automatically tracked as build inputs, so you'll need to run `./gradlew clean` or `mvn clean` after modifying XML files. See [Configuration](../features/configuration.md) for all compiler options.
