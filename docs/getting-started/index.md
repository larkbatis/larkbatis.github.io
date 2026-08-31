# Installation

LarkBatis is three artifacts on your build: two small runtime jars, and one annotation
processor that never reaches the application classpath.

| Artifact | Scope | What it is |
|---|---|---|
| `io.github.larkbatis:larkbatis-annotations` | `implementation` | The mapper annotations. No logic, `CLASS` retention |
| `io.github.larkbatis:larkbatis-runtime` | `implementation` | `LarkBatisSession`, `LarkBatisTx`, `JdbcCodec`, `SqlFragment`. Zero dependencies beyond JDBC |
| `io.github.larkbatis:larkbatis-processor` | `annotationProcessor` | The generator. Build-only: it must never appear on a runtime classpath |

Current version: **`0.1.0`**.

## Requirements

| | |
|---|---|
| Java | 17 or newer (the project itself builds on a Java 17 toolchain) |
| Compiler | **javac only.** The processor depends on javac behaviour: declaration order of elements, and multi-round resolution of generated types. ECJ / Eclipse batch compilation is not supported |
| Build tool | Gradle or Maven. A build-tool plugin is required only if you use mapper XML |
| Database | Anything with a JDBC driver |

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

1.  The flag makes javac keep real parameter names in the class file. Without it, an
    incremental Gradle build can hand the processor a mapper method whose parameters are
    called `arg0`, `arg1`, leaving `#{id}` nothing to resolve against. Annotating every
    parameter with `@Param("...")` works too.
    [Troubleshooting](../usage/troubleshooting.md#what-the-flag-actually-does) explains
    why clean builds hide the problem.

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

One starter replaces the three declarations above, and there is no `@MapperScan`:

```kotlin
dependencies {
    implementation("io.github.larkbatis:larkbatis-annotations:0.1.0")
    implementation("io.github.larkbatis:larkbatis-spring-boot-starter:0.1.0")
    annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")
}
```

[Spring Boot](spring-boot.md) has the full setup, and
[Spring Integration](../usage/spring.md) covers what happens under it.

## Mapper XML

If any of your statements live in mapper XML rather than in annotations, add the
[build plugin](build-plugins.md) for your build tool. It passes the mapper directory to the
processor and registers those XML files as compile inputs, without which an XML-only edit
regenerates nothing.

=== "Gradle"

    ```kotlin
    plugins {
        java
        id("io.github.larkbatis") version "0.1.0"
    }
    ```

=== "Maven"

    ```xml
    <plugin>
      <groupId>io.github.larkbatis</groupId>
      <artifactId>larkbatis-maven-plugin</artifactId>
      <version>0.1.0</version>
      <extensions>true</extensions>
    </plugin>
    ```

## Using Lombok as well

Declare `larkbatis-processor` **after** `org.projectlombok:lombok`. Lombok writes its
getters and setters into the AST when its own processor runs, and javac runs discovered
processors in classpath order. Declared first, LarkBatis sees a result class with no
accessors at all.

```kotlin
annotationProcessor("org.projectlombok:lombok")
annotationProcessor("io.github.larkbatis:larkbatis-processor:0.1.0")  // after
```

The build error names the problem when it spots a Lombok annotation on the class. The fix
is that one line of ordering.

## Next

[Write your first mapper :material-arrow-right:](quick-start.md){ .md-button .md-button--primary }
