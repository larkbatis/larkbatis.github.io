# Configuration

There are three places to configure LightBatis, and they are cleanly separated by *when*
they take effect: processor options at compile time, runtime settings at startup, build
plugin settings in between.

## Processor options

Passed to javac as `-A<name>=<value>`.

| Option | Meaning | Default |
|---|---|---|
| `lightbatis.registryPackage` | Package for the generated `LightBatisMappers` | The common package prefix of all mappers |
| `lightbatis.mapperDir` | Directories of mapper XML, comma- or path-separator-separated. Only files whose root element is `<mapper>` are read | Set by the build plugin to `src/main/resources` |
| `lightbatis.springConfig` | `false` suppresses the generated Spring `@Configuration` | Emitted when spring-context is on the build classpath |
| `lightbatis.springConfigPackage` | Package for the generated `LightBatisMapperConfiguration` | Same as `registryPackage` |

=== "Gradle"

    ```kotlin
    tasks.withType<JavaCompile>().configureEach {
        options.compilerArgs.add("-Alightbatis.registryPackage=com.example.app")
    }
    ```

=== "Maven"

    ```xml
    <configuration>
      <compilerArgs>
        <arg>-Alightbatis.registryPackage=com.example.app</arg>
      </compilerArgs>
    </configuration>
    ```

!!! warning "Setting `mapperDir` by hand loses input registration"

    It generates correct code, but nothing tells the build tool the XML files are compile
    inputs — so an XML-only edit may not regenerate. Run `clean` first, or use a
    [build plugin](../getting-started/build-plugins.md).

## Compiler flags that matter

| Flag | Why |
|---|---|
| `-parameters` | Gradle incremental builds re-run aggregating processors over **class files**, where parameter names survive only with this flag. Without it, `#{id}` cannot resolve. The alternative is `@Param` on every parameter |

## Build plugin settings

=== "Gradle"

    ```kotlin
    lightbatis {
        mapperDir = layout.projectDirectory.dir("src/main/mappers")
        addProcessorDependency = false   // manage the processor version yourself
    }
    ```

=== "Maven"

    ```xml
    <configuration>
      <mapperDir>src/main/mappers</mapperDir>     <!-- default: src/main/resources -->
      <addProcessorPath>false</addProcessorPath>  <!-- default: true -->
    </configuration>
    ```

Maven additionally requires `<extensions>true</extensions>` on the plugin declaration, or
nothing happens — silently. See [Build Plugins](../getting-started/build-plugins.md).

## Runtime settings

Only two, and both are about the operational cost of `${}`: statement caches are keyed by
SQL text, so a fragment whose value set is not bounded grows them without limit.

=== "Spring Boot"

    ```yaml title="application.yml"
    lightbatis:
      max-sql-variants: 64
      fail-on-unbounded-fragment: false
    ```

=== "System properties"

    ```console
    -Dlightbatis.maxSqlVariants=64
    -Dlightbatis.failOnUnboundedVariants=true
    ```

=== "Programmatic"

    ```java
    LightBatisSql.maxSqlVariants(64);
    LightBatisSql.failOnUnboundedVariants(true);
    ```

| Setting | Default | Effect |
|---|---|---|
| `max-sql-variants` | `64` | Distinct SQL texts one statement may produce before LightBatis complains |
| `fail-on-unbounded-fragment` | `false` | `true` throws `LightBatisUnboundedVariantsException` instead of logging one warning |

The threshold fires **exactly once per statement**: past it, the counter stops retaining
texts, so the throwing mode does not keep growing a set it has already given up on.

!!! tip "Different values per environment"

    Production should log, not throw — a running system should not start failing because
    of a log-worthy trend. Staging should throw, because that is where you want to find
    the unbounded fragment. Setting `fail-on-unbounded-fragment: true` in a staging
    profile is the intended use.

## Not implemented

| | |
|---|---|
| `log-sql` | Appears in the design document's property list and is deliberately absent. Every generated body would have to carry a logging branch. SQL logging belongs to the driver or the pool — `net.ttddyy:datasource-proxy`, p6spy |
| `mapUnderscoreToCamelCase` | Applied at build time, always. There is no runtime to switch it in |
| `ExecutorType`, cache settings, `defaultStatementTimeout`, `lazyLoadingEnabled`, … | No executor, no cache, no lazy loading. See [MyBatis Differences](mybatis-differences.md) |
| Per-mapper `DataSource` selection | Deferred. Declare one `SpringLightBatisSession` per `DataSource` and write the mapper `@Bean` methods yourself |

## Spring: when the generated `@Configuration` does not fit

| Situation | What to do |
|---|---|
| Mappers outside the scanned packages | `-Alightbatis.springConfigPackage=com.example.app`, or `@Import(LightBatisMapperConfiguration.class)` |
| Declaring the mapper beans yourself | `-Alightbatis.springConfig=false` |
| More than one `DataSource` | The auto-configuration is `@ConditionalOnSingleCandidate` and backs off rather than guessing. Mark one `@Primary`, or suppress the generated class |
