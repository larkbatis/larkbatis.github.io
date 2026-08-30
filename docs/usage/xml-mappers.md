# Mapper XML

An interface annotated `@Mapper` takes each method's SQL from the mapper XML statement
with the same id. The namespace is the interface's fully-qualified name.

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

The DTD reference is kept so existing files parse unchanged and editors keep completing.
The build neither fetches it nor validates against it.

## Why `@Mapper` is needed here

Purely annotation-based mappers do not need the marker: the processor finds them because
their methods carry `@Select` and friends. An XML-only interface has no annotation
anywhere, so without `@Mapper` it would never reach a processing round at all. That is
the marker's whole job.

## Statement resolution is per method

Each abstract method takes its SQL from **either** its annotation **or** the XML.
Having both, or having neither, is a compile error naming the method. So a mapper can mix
freely:

```java
@Mapper
public interface UserMapper {

    @Select("SELECT id, name FROM users WHERE id = #{id}")
    User findById(long id);          // from the annotation

    List<User> search(UserSearch q); // from UserMapper.xml
}
```

## Where the XML is found

The processor scans the directories given by `-Alarkbatis.mapperDir`. The
[build plugins](../getting-started/build-plugins.md) pass it for you, defaulting to
`src/main/resources`, and register the files as compile inputs so an XML edit
regenerates.

Only files whose **root element is `<mapper>`** are read, so Spring configuration,
logback settings and anything else in the same tree is ignored. A mapper XML whose
`namespace` names an interface in another module is skipped with a build warning.

## Supported elements

| Element | Support |
|---|---|
| `<select>` `<insert>` `<update>` `<delete>` | Full |
| `<sql>` / `<include>` | Static `refid` only, inlined at build time |
| `<if>` `<choose>`/`<when>`/`<otherwise>` | Full, with the [narrow test grammar](dynamic-sql.md#the-test-grammar) |
| `<where>` `<set>` `<trim>` | Literal attributes only, constant-folded at build time |
| `<foreach>` | Statically-typed collections, arrays and maps. [See here](foreach-and-batches.md) |
| `<resultMap>` | One level of `<association>` / `<collection>`. [See here](result-maps.md) |
| `<bind>` `<discriminator>` `<parameterMap>` `<cache>` `<selectKey>` | Not supported; see [MyBatis Differences](../features/mybatis-differences.md) |

`resultType` and `resultMap` take **fully-qualified class names**. There is no type-alias
registry: an alias is a runtime lookup table, and this is a build.

## `<sql>` and `<include>`

`refid` is resolved and inlined at build time, so it must be a literal. A computed
`refid` is a compile error.

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

After inlining, the statement is indistinguishable from one written out in full,
including for select-list parsing, so `<include>` does not cost you positional row
reads.

## Whitespace

Fragments are joined with exactly one space and the result is trimmed. The policy is
documented and fixed, and it does not reproduce MyBatis's incidental whitespace, which
differs between MyBatis versions in `<trim>` handling. If you are comparing generated SQL
against MyBatis output character by character, expect whitespace to differ and semantics not
to.

## Annotations that still apply

XML statements are still bound to a Java method, so method-level and interface-level
annotations still work: `@PadPow2` on a `<foreach>` statement, `@Param` on the
parameters, `@Options` on an `<insert>`:

```java
@Mapper
public interface UserBatchMapper {

    List<User> findByIds(List<Long> ids);

    @PadPow2
    List<User> findByIdsPadded(List<Long> ids);

    int deleteByIds(@Param("ids") List<Long> ids, @Param("keepName") String keepName);
}
```
