# Installation

LarkBatis needs just three artifacts in your build: two small runtime jars, and one annotation processor that never touches your runtime classpath.

| Artifact | Scope | What it is |
|---|---|---|
| `io.github.larkbatis:larkbatis-annotations` | `implementation` | Mapper annotations. No logic, `CLASS` retention |
| `io.github.larkbatis:larkbatis-runtime` | `implementation` | `LarkBatisSession`, `LarkBatisTx`, `JdbcCodec`, `SqlFragment`. Zero dependencies beyond JDBC |
| `io.github.larkbatis:larkbatis-processor` | `annotationProcessor` | The code generator. Build-only: never include on runtime classpath |

Current version: **`0.1.0`**.

## Requirements

| | |
|---|---|
| Java | 17 or newer (the project builds on Java 17 toolchains) |
| Compiler | **javac only.** The processor depends on javac behavior (declaration order of elements and multi-round resolution). ECJ / Eclipse batch compiler is not supported |
| Build tool | Gradle or Maven. You only need a build plugin if you use mapper XML |
| Database | Any database with a standard JDBC driver |

## Gradle

```kotlin title="build.gradle.kts"
plugins {
    java
}

java {
    toolchain { languageVersion = JavaLanguageVersion.of(17) }
}

dependencies {
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0")
    implementation("io.github.larkbatis:larkbatis-runtime:0.1.0")
    annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")
}

tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.add("-parameters") // (1)!
}
```

1.  This flag tells javac to preserve parameter names in class files. Without it, Gradle incremental builds can pass compiled classes to the processor with parameters named `arg0`, `arg1`, breaking `#{id}` parameter binding. Alternatively, you can annotate every parameter with `@Param("...")`. See [Troubleshooting](../usage/troubleshooting.md#what-the-flag-actually-does) for why clean builds mask this issue.

## Maven

```xml title="pom.xml"
<dependencies>
  <dependency>
    <groupId>io.github.larkbatis</groupId>
    <artifactId>larkbatis-annotations</artifactId>
    <version>0.1.0</version>
  </dependency>
  <dependency>
    <groupId>io.github.larkbatis</groupId>
    <artifactId>larkbatis-runtime</artifactId>
    <version>0.1.0</version>
  </dependency>
</dependencies>

<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-compiler-plugin</artifactId>
      <configuration>
        <parameters>true</parameters>
        <annotationProcessorPaths>
          <path>
            <groupId>io.github.larkbatis</groupId>
            <artifactId>larkbatis-processor</artifactId>
            <version>0.1.0</version>
          </path>
        </annotationProcessorPaths>
      </configuration>
    </plugin>
  </plugins>
</build>
```

## Spring Boot

A single starter replaces the runtime dependencies above, and you don't need `@MapperScan`:

```kotlin
dependencies {
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0")
    implementation("io.github.larkbatis:larkbatis-spring-boot-starter:0.1.0")
    annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")
}
```

See [Spring Boot](../spring/spring-boot.md) for full setup instructions, and [Spring Integration](../spring/spring.md) for how transactions and connections work under the hood.

## Mapper XML

If any of your SQL statements live in mapper XML files instead of annotations, add the [build plugin](build-plugins.md) for your build tool. It passes your XML directory to the processor and registers those XML files as compilation inputs, ensuring XML edits trigger code regeneration.

=== "Gradle"

    ```kotlin
    plugins {
        java
        id("io.github.larkbatis") version "0.1.2"
    }
    ```

=== "Maven"

    ```xml
    <plugin>
      <groupId>io.github.larkbatis</groupId>
      <artifactId>larkbatis-maven-plugin</artifactId>
      <version>0.1.2</version>
      <extensions>true</extensions>
    </plugin>
    ```

## Using Lombok

Always declare `larkbatis-processor` **after** `org.projectlombok:lombok`. Lombok generates getters and setters into the AST during its own processor pass, and javac runs discovered processors in classpath order. If LarkBatis runs first, it sees a result class with no accessors.

```kotlin
annotationProcessor("org.projectlombok:lombok")
annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")  // after lombok
```

The compiler error explicitly warns you if it spots Lombok annotations on a class missing accessors. Reordering the dependencies fixes it.

## Next

[Write your first mapper :material-arrow-right:](quick-start.md){ .md-button .md-button--primary }
