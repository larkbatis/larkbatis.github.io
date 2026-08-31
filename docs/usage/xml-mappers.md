# Mapper XML

An interface annotated with `@Mapper` pairs each method with the mapper XML statement having the matching `id`. The XML `namespace` must match the fully-qualified name of the interface.

```java title="UserSearchMapper.java"
package com.example.app;

import io.github.larkbatis.annotations.Mapper;
import java.util.List;

@Mapper
public interface UserSearchMapper {

    List<User> search(UserSearch q);

    int rename(UserSearch q);
}
```

```xml title="src/main/resources/mappers/UserSearchMapper.xml"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
    "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.app.UserSearchMapper">

  <select id="search" resultType="com.example.app.User">
    SELECT id, name, email, created_at FROM users
    <where>
      <if test="name != null">AND name LIKE #{name}</if>
      <if test="email != null">AND email = #{email}</if>
    </where>
    ORDER BY id
  </select>

  <update id="rename">
    UPDATE users
    <set>
      <if test="name != null">name = #{name},</if>
      <if test="email != null">email = #{email},</if>
    </set>
    WHERE id = #{id}
  </update>

</mapper>
```

The DTD declaration is preserved so existing XML files parse without edits and IDE autocomplete keeps working. The build does not make network calls to fetch or validate the DTD.

## Why `@Mapper` is required here

Purely annotation-based mappers don't need `@Mapper`: javac discovers them because their methods carry `@Select`, `@Insert`, etc. However, an XML-only interface has no annotations at all, so without `@Mapper`, javac wouldn't pass it to the annotation processor. That is the annotation's only purpose.

## Statement resolution per method

Each method must have its SQL defined in **either** an annotation **or** XML. Having both or neither is a compile error. You can freely mix annotations and XML within the same interface:

```java
@Mapper
public interface UserMapper {

    @Select("SELECT id, name FROM users WHERE id = #{id}")
    User findById(long id);          // from annotation

    List<User> search(UserSearch q); // from UserMapper.xml
}
```

## Locating XML files

The processor scans directories configured via `-Alarkbatis.mapperDir`. The [build plugins](../getting-started/build-plugins.md) configure this for you (defaulting to `src/main/resources`) and track XML files as compilation inputs.

The processor only parses XML files whose **root tag is `<mapper>`**, automatically skipping Spring configs, logback files, or other resources. If an XML file has a `namespace` matching an interface in a different module, it is skipped with a build warning.

## Supported XML elements

| Element | Support |
|---|---|
| `<select>` `<insert>` `<update>` `<delete>` | Full support |
| `<sql>` / `<include>` | Static `refid` only (inlined at compile time) |
| `<if>` `<choose>`/`<when>`/`<otherwise>` | Full support using the [type-checked test grammar](dynamic-sql.md#the-test-grammar) |
| `<where>` `<set>` `<trim>` | Literal attributes only (constant-folded at build time) |
| `<foreach>` | Statically-typed collections, arrays, and maps. [Details](foreach-and-batches.md) |
| `<resultMap>` | 1-level `<association>` / `<collection>` joins. [Details](result-maps.md) |
| `<bind>` `<discriminator>` `<parameterMap>` `<cache>` `<selectKey>` | Not supported. [See differences](../features/mybatis-differences.md) |

`resultType` and `resultMap` require **fully-qualified class names**. Type aliases are not supported because they depend on runtime registries.

## Reusable SQL with `<sql>` and `<include>`

`<include refid="...">` tags are inlined directly at compile time. The `refid` must be a literal string:

```xml
<sql id="teamMemberJoin">
  SELECT t.id AS t_id, t.name AS t_name,
         m.id AS m_id, m.name AS m_name, m.jersey AS m_jersey
  FROM team t
  LEFT JOIN member m ON m.team_id = t.id
</sql>

<select id="findWithMembers" resultMap="teamWithMembers">
  <include refid="teamMemberJoin"/>
  WHERE t.id = #{id}
  ORDER BY t.id, m.jersey
</select>
```

Because `<include>` is inlined during AST construction, the resulting query is parsed just like a full query string, preserving fast positional column reads.

## Whitespace handling

SQL fragments are joined with a single space and trimmed. This behavior is consistent across builds. If you compare LarkBatis SQL output character-by-character with MyBatis, whitespace may differ slightly, but SQL semantics are identical.

## Method annotations with XML statements

Because XML statements are bound directly to Java methods, method-level annotations work as expected: `@PadPow2` for `<foreach>` padding, `@Param` for parameter naming, and `@Options` for generated keys:

```java
@Mapper
public interface UserBatchMapper {

    List<User> findByIds(List<Long> ids);

    @PadPow2
    List<User> findByIdsPadded(List<Long> ids);

    int deleteByIds(@Param("ids") List<Long> ids, @Param("keepName") String keepName);
}
```
