# Configuration

There are three places to configure LarkBatis, and they are cleanly separated by *when*
they take effect: processor options at compile time, runtime settings at startup, build
plugin settings in between.

## Processor options

Passed to javac as `-A<name>=<value>`.

| Option | Meaning | Default |
|---|---|---|
| `larkbatis.registryPackage` | Package for the generated `LarkBatisMappers` | The common package prefix of all mappers |
| `larkbatis.mapperDir` | Directories of mapper XML, comma- or path-separator-separated — one option however many directories, since a repeated `-A` of the same name is the last one javac reads, not the union. Only files whose root element is `<mapper>` are read | Set by the build plugin to `src/main/resources` |
| `larkbatis.mapUnderscoreToCamelCase` | `false` makes underscores significant when a column label is matched to a property — MyBatis's own default. Anything that is not `true` or `false` is a build error | `true` |
| `larkbatis.typeHandlers` | A default handler per Java type, `javaType:handlerClass` pairs separated by commas — the build-time answer to a `<typeHandlers>` block | none |
| `larkbatis.springConfig` | `false` suppresses the generated Spring `@Configuration` | Emitted when spring-context is on the build classpath |
| `larkbatis.springConfigPackage` | Package for the generated `LarkBatisMapperConfiguration` | Same as `registryPackage` |

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

!!! warning "Setting `mapperDir` by hand loses input registration"

    It generates correct code, but nothing tells the build tool the XML files are compile
    inputs, so an XML-only edit may not regenerate. Run `clean` first, or use a
    [build plugin](../getting-started/build-plugins.md).

### Column naming

`created_at` reaches `setCreatedAt` by default, and the decision is baked into the
generated reader rather than read from a setting at runtime. Turning it off is how a
build keeps the semantics it had under MyBatis, whose own default is *off*:

```
-Alarkbatis.mapUnderscoreToCamelCase=false
```

| | On (default) | Off |
|---|---|---|
| `user_name` → `userName` | mapped | **not mapped**, the property keeps its default |
| `@Column("zip_code")` → label `zip_code` | mapped | mapped |
| `@Column("zip_code")` → label `zipCode` | mapped | not mapped |
| Generated resolver | `getColumnLabel(i).replace("_", "").toLowerCase(…)` | `getColumnLabel(i).toLowerCase(…)` |

Leaving it on is a behaviour change for a codebase migrating from a MyBatis config that
never set it: columns MyBatis left unmapped start being read. Switching it off makes the
build **name every column that stops reaching a property**, and the property it stops
reaching — MyBatis leaves that silent, and a null in production is a bad place to find
out:

```text
UserMapper.all: mapUnderscoreToCamelCase is off, so these columns reach no property and
their properties keep their defaults — user_name → userName. Alias the column in the SQL,
or name it with @Column.
```

Unlike MyBatis, the convention applies to **both** sides: with it on, a property or
`@Column` spelled `usr_email` still matches a label spelled `usrEmail`. MyBatis strips
underscores only from the label, so that one pairing misses there.

### Type handlers for a whole build

A `mybatis-config.xml` `<typeHandlers>` block registers a handler once and every property
of that type picks it up. The same thing, decided during `javac`:

```
-Alarkbatis.typeHandlers=com.example.Money:com.example.MoneyHandler,\
                         com.example.Json:com.example.JsonHandler
```

Each entry applies to every property and every `#{}` of that type that does not name a
handler of its own. `@Handler` and a `typeHandler` attribute both still win, because
naming it at the site is the more specific answer.

Every entry is checked while the build runs — the java type and the handler class must
both be on the compilation classpath, and the handler must implement
`LarkBatisTypeHandler<ThatType>`, be public and concrete, and have a public no-argument
constructor. What it produces is the same generated shape `@Handler` produces: one
`static final` field of the handler's own class, called directly.

!!! tip "An entry that moves nothing is a build warning"

    A registered type that no property or `#{}` in the compilation has is exactly what a
    typo in the java-type half looks like — no property changes, no error, no handler.
    That entry is named in a warning rather than left silent.

| Not carried across | |
|---|---|
| `<package name="…"/>` scanning, `@MappedTypes` | Nothing is scanned. Each pair is written out, which is also what makes the list readable |
| The `jdbcType` half of MyBatis's `(javaType, jdbcType)` registry | The generated reader knows the one column it is reading, so there is nothing to disambiguate |
| A runtime registry | The handler that wins is compiled in. There is no lookup left to do |

## Compiler flags that matter

| Flag | Why |
|---|---|
| `-parameters` | Gradle incremental builds re-run aggregating processors over **class files**, where parameter names survive only with this flag. Without it, `#{id}` cannot resolve. The alternative is `@Param` on every parameter |

## Build plugin settings

=== "Gradle"

    ```kotlin
    larkbatis {
        mapperDir = layout.projectDirectory.dir("src/main/mappers")
        addProcessorDependency = false   // manage the processor version yourself
        addParametersFlag = false        // you already pass -parameters, or use @Param everywhere
    }
    ```

=== "Maven"

    ```xml
    <configuration>
      <mapperDir>src/main/mappers</mapperDir>     <!-- default: src/main/resources -->
      <addProcessorPath>false</addProcessorPath>  <!-- default: true -->
      <addParameters>false</addParameters>        <!-- default: true -->
    </configuration>
    ```

| Setting | Default | |
|---|---|---|
| `mapperDir` / `<mapperDir>` | `src/main/resources` | One directory of mapper XML |
| `mapperDirs` / `<mapperDirs>` | empty | More of them, see below |
| `addProcessorDependency` / `<addProcessorPath>` | `true` | Whether `larkbatis-processor` is put on the annotation processor path |
| `addParametersFlag` / `<addParameters>` | `true` | Whether `-parameters` is turned on. Switching it off needs `@Param` on every mapper parameter — see the next section for why. Maven honours an explicit `<parameters>false</parameters>` and warns instead of overriding it |

Maven additionally requires `<extensions>true</extensions>` on the plugin declaration.
Without it nothing happens, and nothing says so. See [Build
Plugins](../getting-started/build-plugins.md).

### Mapper XML in more than one directory

The closest thing here to MyBatis's `<mappers>` block or
`mybatis.mapper-locations`. Directories rather than Ant patterns, because the
scan happens at build time against the filesystem, not at startup against the
classpath:

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

Each directory is scanned recursively, its XML is registered as a compile input, and
all of them reach javac in one `-Alarkbatis.mapperDir` option.

| Rule | |
|---|---|
| Both settings together | `mapperDir` is scanned first, then the list |
| A directory named twice | Scanned once — a second walk reports every namespace in it as declared by two files |
| The `src/main/resources` default | Applies only when the build names neither, so listing mapper trees does not quietly add a resources directory nobody mentioned |
| One namespace in two directories | A compile error, not a last-one-wins merge. The two files disagree about one mapper and nothing in the build can say which was meant |
| A directory that does not exist | A build warning naming it. `mvn larkbatis:check` lists every resolved directory and marks the missing ones |
| A directory outside the module | Allowed, and rarely useful: every namespace found still has to name a mapper interface compiled *here*, and a file matching none is reported and ignored |

!!! warning "Mapper XML inside a dependency jar has no equivalent"

    `classpath*:` patterns are a startup-time idea. A mapper interface shipped in a jar
    was already generated against its own XML when that jar was built, so there is
    nothing left for a consuming build to scan.

## Runtime settings

Only two, and both are about the operational cost of `${}`: statement caches are keyed by
SQL text, so a fragment whose value set is not bounded grows them without limit.

=== "Spring Boot"

    ```yaml title="application.yml"
    larkbatis:
      max-sql-variants: 64
      fail-on-unbounded-fragment: false
    ```

=== "System properties"

    ```console
    -Dlarkbatis.maxSqlVariants=64
    -Dlarkbatis.failOnUnboundedVariants=true
    ```

=== "Programmatic"

    ```java
    LarkBatisSql.maxSqlVariants(64);
    LarkBatisSql.failOnUnboundedVariants(true);
    ```

| Setting | Default | Effect |
|---|---|---|
| `max-sql-variants` | `64` | Distinct SQL texts one statement may produce before LarkBatis complains |
| `fail-on-unbounded-fragment` | `false` | `true` throws `LarkBatisUnboundedVariantsException` instead of logging one warning |

Both are described in `META-INF/spring-configuration-metadata.json`, shipped in
`larkbatis-spring-boot-autoconfigure`, so an IDE completes them in `application.yml`
with their defaults and marks a misspelt key.

The threshold fires **exactly once per statement**: past it, the counter stops retaining
texts, so the throwing mode does not keep growing a set it has already given up on.

!!! tip "Different values per environment"

    Production should log, not throw: a running system should not start failing because
    of a log-worthy trend. Staging should throw, because that is where you want to find
    the unbounded fragment. Setting `fail-on-unbounded-fragment: true` in a staging
    profile is the intended use.

## Not implemented

| | |
|---|---|
| `log-sql` | Every generated body would have to carry a logging branch. SQL logging belongs to the driver or the pool: `net.ttddyy:datasource-proxy`, p6spy |
| `ExecutorType`, cache settings, `defaultStatementTimeout`, `lazyLoadingEnabled`, … | No executor, no cache, no lazy loading. See [MyBatis Differences](mybatis-differences.md) |
| Per-mapper `DataSource` selection | Deferred. Declare one `SpringLarkBatisSession` per `DataSource` and write the mapper `@Bean` methods yourself |

## Spring: when the generated `@Configuration` does not fit

| Situation | What to do |
|---|---|
| Mappers outside the scanned packages | `-Alarkbatis.springConfigPackage=com.example.app`, or `@Import(LarkBatisMapperConfiguration.class)` |
| Declaring the mapper beans yourself | `-Alarkbatis.springConfig=false` |
| More than one `DataSource` | The auto-configuration is `@ConditionalOnSingleCandidate` and backs off rather than guessing. Mark one `@Primary`, or suppress the generated class |
