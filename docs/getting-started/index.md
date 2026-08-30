# Installation

LightBatis is three artifacts on your build: two small runtime jars and one annotation
processor that never reaches the application classpath.

| Artifact | Scope | What it is |
|---|---|---|
| `io.github.lightbatis:lightbatis-annotations` | `implementation` | The mapper annotations. No logic, `CLASS` retention |
| `io.github.lightbatis:lightbatis-runtime` | `implementation` | `LightBatisSession`, `LightBatisTx`, `JdbcCodec`, `SqlFragment`. Zero dependencies beyond JDBC |
| `io.github.lightbatis:lightbatis-processor` | `annotationProcessor` | The generator. Build-only — it must never appear on a runtime classpath |

Current version: **`0.1.0-SNAPSHOT`**. The artifacts are not yet on Maven Central, so
today you build the repositories locally and publish to your Maven local repository.

## Requirements

| | |
|---|---|
| Java | 17 or newer (the project itself builds on a Java 17 toolchain) |
| Compiler | **javac only.** The processor depends on javac behaviour — declaration order of elements, multi-round resolution of generated types. ECJ / Eclipse batch compilation is not supported |
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
    implementation("io.github.lightbatis:lightbatis-annotations:0.1.0-SNAPSHOT")
    implementation("io.github.lightbatis:lightbatis-runtime:0.1.0-SNAPSHOT")
    annotationProcessor("io.github.lightbatis:lightbatis-processor:0.1.0-SNAPSHOT")
}

tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.add("-parameters") // (1)!
}
```

1.  Clean builds read parameter names from the AST, but Gradle *incremental* builds
    re-run aggregating processors over unchanged mappers from their **class files**,
    where parameter names only survive with `-parameters`. This is a documented Gradle
    limitation. The alternative is naming every parameter with `@Param`.

!!! warning "Compile with `-parameters`"

    Without it, an incremental Gradle build can hand the processor a mapper method whose
    parameters are called `arg0`, `arg1` — and `#{id}` then has nothing to resolve
    against. Add the flag, or annotate every parameter with `@Param("...")`.

## Maven

```xml title="pom.xml"
<dependencies>
  <dependency>
    <groupId>io.github.lightbatis</groupId>
    <artifactId>lightbatis-annotations</artifactId>
    <version>0.1.0-SNAPSHOT</version>
  </dependency>
  <dependency>
    <groupId>io.github.lightbatis</groupId>
    <artifactId>lightbatis-runtime</artifactId>
    <version>0.1.0-SNAPSHOT</version>
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
            <groupId>io.github.lightbatis</groupId>
            <artifactId>lightbatis-processor</artifactId>
            <version>0.1.0-SNAPSHOT</version>
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
    implementation("io.github.lightbatis:lightbatis-annotations:0.1.0-SNAPSHOT")
    implementation("io.github.lightbatis:lightbatis-spring-boot-starter:0.1.0-SNAPSHOT")
    annotationProcessor("io.github.lightbatis:lightbatis-processor:0.1.0-SNAPSHOT")
}
```

See [Spring Boot](spring-boot.md) for the full setup and
[Spring Integration](../usage/spring.md) for what happens under it.

## Mapper XML

If any of your statements live in mapper XML rather than in annotations, add the
[build plugin](build-plugins.md) for your build tool. The processor reads mapper XML with
plain `java.io` — outside the compiler's `Filer` — because `Filer.getResource` is not
specified to reach `src/main/resources`, so the build tool has to be told those files
are compile inputs.

=== "Gradle"

    ```kotlin
    plugins {
        java
        id("io.github.lightbatis") version "0.1.0-SNAPSHOT"
    }
    ```

=== "Maven"

    ```xml
    <plugin>
      <groupId>io.github.lightbatis</groupId>
      <artifactId>lightbatis-maven-plugin</artifactId>
      <version>0.1.0-SNAPSHOT</version>
      <extensions>true</extensions>
    </plugin>
    ```

## Using Lombok as well

Declare `lightbatis-processor` **after** `org.projectlombok:lombok`. Lombok writes its
getters and setters into the AST when its own processor runs, and javac runs discovered
processors in classpath order — declared first, LightBatis sees a result class with no
accessors at all.

```kotlin
annotationProcessor("org.projectlombok:lombok")
annotationProcessor("io.github.lightbatis:lightbatis-processor:0.1.0-SNAPSHOT")  // after
```

The build error names the problem when it spots a Lombok annotation on the class, but the
fix is that one line of ordering.

## Next

[Write your first mapper :material-arrow-right:](quick-start.md){ .md-button .md-button--primary }
