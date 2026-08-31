# Configuration

LarkBatis configuration is organized by lifecycle stage: processor options at compile time, plugin settings in your build file, and runtime properties at startup.

## Annotation Processor Options

Passed to javac as `-A<name>=<value>`.

| Option | Description | Default |
|---|---|---|
| `larkbatis.registryPackage` | Package for the generated `LarkBatisMappers` registry | Common package prefix of all mappers |
| `larkbatis.mapperDir` | Directory containing mapper XML files (comma-separated for multiples). Only XML files with root tag `<mapper>` are parsed | `src/main/resources` (configured by build plugin) |
| `larkbatis.mapUnderscoreToCamelCase` | Set `false` if underscores in column names are significant (matching legacy MyBatis behavior) | `true` |
| `larkbatis.typeHandlers` | Comma-separated `javaType:handlerClass` pairs for project-wide type handlers | None |
| `larkbatis.springConfig` | Set `false` to disable generating Spring `@Configuration` classes | Generated automatically when Spring is on the classpath |
| `larkbatis.springConfigPackage` | Package for the generated Spring configuration class | Same as `registryPackage` |

=== "Gradle"

    ```kotlin
    tasks.withType<JavaCompile>().configureEach {
        options.compilerArgs.add("-Alarkbatis.registryPackage=com.example.app")
    }
    ```

=== "Maven"

    ```xml
    <configuration>
      <compilerArgs>
        <arg>-Alarkbatis.registryPackage=com.example.app</arg>
      </compilerArgs>
    </configuration>
    ```

### Column naming options { #column-naming }

By default, column `created_at` maps automatically to setter `setCreatedAt`. This transformation is baked into generated reader classes. To preserve legacy MyBatis behavior (where underscore mapping was disabled by default), set:

```
-Alarkbatis.mapUnderscoreToCamelCase=false
```

| Mapping Scenario | `true` (default) | `false` |
|---|---|---|
| `user_name` → `userName` | Mapped | **Not mapped** (property stays default/null) |
| `@Column("zip_code")` → column `zip_code` | Mapped | Mapped |
| `@Column("zip_code")` → column `zipCode` | Mapped | Not mapped |

When disabled, javac will report build warnings naming any columns that no longer map to properties.

### Project-wide custom type handlers { #type-handlers-for-a-whole-build }

In MyBatis, you declared `<typeHandlers>` in `mybatis-config.xml`. In LarkBatis, configure them at compile time:

```
-Alarkbatis.typeHandlers=com.example.Money:com.example.MoneyHandler,\
                         com.example.Json:com.example.JsonHandler
```

Each configured pair applies globally to all parameters and properties of that type. Local `@Handler` annotations or XML `typeHandler=` attributes override global defaults.

## Build Plugin Settings

=== "Gradle"

    ```kotlin
    larkbatis {
        mapperDir = layout.projectDirectory.dir("src/main/mappers")
        addProcessorDependency = false   // manage processor version manually
        addParametersFlag = false        // disable automatic -parameters flag
        mapUnderscoreToCamelCase = false  // disable camelCase mapping
        typeHandlers = "com.example.Money:com.example.MoneyHandler"
        registryPackage = "com.example.app"
        springConfig = false             // disable generating Spring @Configuration
        springConfigPackage = "com.example.config"
    }
    ```

=== "Maven"

    ```xml
    <configuration>
      <mapperDir>src/main/mappers</mapperDir>
      <addProcessorPath>false</addProcessorPath>
      <addParameters>false</addParameters>
      <mapUnderscoreToCamelCase>false</mapUnderscoreToCamelCase>
      <typeHandlers>com.example.Money:com.example.MoneyHandler</typeHandlers>
      <registryPackage>com.example.app</registryPackage>
      <springConfig>false</springConfig>
      <springConfigPackage>com.example.config</springConfigPackage>
    </configuration>
    ```

| Setting | Default | Description |
|---|---|---|
| `mapperDir` | `src/main/resources` | Primary mapper XML directory |
| `mapperDirs` | Empty | Additional mapper XML directories |
| `addProcessorDependency` / `<addProcessorPath>` | `true` | Adds `larkbatis-processor` to compilation automatically |
| `addParametersFlag` / `<addParameters>` | `true` | Adds `-parameters` javac flag for parameter name retention |
| `mapUnderscoreToCamelCase` | `true` | Toggles automatic `snake_case` → `camelCase` column mapping |
| `typeHandlers` | None | Comma-separated `Type:Handler` mappings |
| `registryPackage` | Common package prefix | Target package for `LarkBatisMappers` |
| `springConfig` | Auto | Toggles generation of Spring `@Configuration` |
| `springConfigPackage` | `registryPackage` | Target package for Spring configuration class |

### Configuring multiple XML directories { #mapper-xml-in-more-than-one-directory }


If your mapper XML files are split across multiple directories:

=== "Gradle"

    ```kotlin
    larkbatis {
        mapperDirs.from("src/main/mappers", "src/main/legacy-mappers")
    }
    ```

=== "Maven"

    ```xml
    <configuration>
      <mapperDirs>
        <mapperDir>src/main/mappers</mapperDir>
        <mapperDir>src/main/legacy-mappers</mapperDir>
      </mapperDirs>
    </configuration>
    ```

Each directory is scanned recursively and registered as a compilation input.

## Runtime Configuration Properties

These properties govern SQL variant monitoring to prevent dynamic `${}` splices from exhausting JDBC statement caches.

=== "Spring Boot (`application.yml`)"

    ```yaml
    larkbatis:
      max-sql-variants: 64
      fail-on-unbounded-fragment: false
    ```

=== "JVM System Properties"

    ```console
    -Dlarkbatis.maxSqlVariants=64
    -Dlarkbatis.failOnUnboundedVariants=true
    ```

=== "Java API"

    ```java
    LarkBatisSql.maxSqlVariants(64);
    LarkBatisSql.failOnUnboundedVariants(true);
    ```

| Property | Default | Description |
|---|---|---|
| `max-sql-variants` | `64` | Maximum distinct SQL strings a statement can generate before logging a warning |
| `fail-on-unbounded-fragment` | `false` | Throws `LarkBatisUnboundedVariantsException` instead of logging a warning when threshold is exceeded |

!!! tip "Recommendation for testing environments"

    Enable `fail-on-unbounded-fragment: true` in staging and integration test profiles to catch unconstrained dynamic query generation early.

## Unsupported Settings

| Setting | Reason |
|---|---|
| `log-sql` | SQL logging belongs at the connection pool or JDBC driver level (`datasource-proxy`, p6spy) |
| `ExecutorType`, `defaultStatementTimeout`, `lazyLoadingEnabled` | No runtime executor or proxy engine. See [MyBatis Differences](mybatis-differences.md) |
| Automatic per-mapper `DataSource` routing | Configure a `SpringLarkBatisSession` per `DataSource` and declare mapper `@Bean` methods explicitly |
