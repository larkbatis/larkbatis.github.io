# Mapper XML

Khi một mapper interface được đánh dấu bằng `@Mapper`, LarkBatis sẽ tìm kiếm các câu lệnh SQL trong file mapper XML có `namespace` trùng với FQN của interface.

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

Khai báo DTD được giữ lại để IDE hỗ trợ gợi ý cú pháp. File DTD không bị tải về qua mạng lúc build.

## Vai trò của annotation `@Mapper`

Mapper chỉ dùng annotation (`@Select`, v.v.) không cần gắn `@Mapper` vì processor tự nhận diện qua method annotations. Với các mapper sử dụng XML, annotation `@Mapper` trên interface là tín hiệu bắt buộc để processor phát hiện và quét file XML tương ứng.

## Kết hợp Annotation và XML trong cùng một Mapper

Mỗi phương thức trừu tượng chỉ được định nghĩa **hoặc** qua annotation **hoặc** qua XML:

```java
@Mapper
public interface UserMapper {

    @Select("SELECT id, name FROM users WHERE id = #{id}")
    User findById(long id);          // Định nghĩa qua Annotation

    List<User> search(UserSearch q); // Định nghĩa trong file UserMapper.xml (id="search")
}
```

Khai báo cả hai hoặc bỏ trống phương thức sẽ bị báo lỗi biên dịch `javac`.

## Thư mục quét Mapper XML

Processor quét các file XML trong các thư mục được cấu hình qua `-Alarkbatis.mapperDir`. Build plugin (Gradle/Maven) mặc định cấu hình thư mục này là `src/main/resources` và đăng ký các file XML làm compilation input để hỗ trợ incremental build.

Chỉ các file XML có root element là `<mapper>` mới được xử lý.

## Bảng hỗ trợ các thẻ XML

| Thẻ XML | Trạng thái hỗ trợ |
|---|---|
| `<select>`, `<insert>`, `<update>`, `<delete>` | Đầy đủ |
| `<sql>`, `<include>` | Đầy đủ (chỉ hỗ trợ `refid` hằng số tĩnh, được inlined trực tiếp lúc build) |
| `<if>`, `<choose>`, `<when>`, `<otherwise>` | Đầy đủ (với ngữ pháp kiểm tra kiểu tĩnh an toàn) |
| `<where>`, `<set>`, `<trim>` | Đầy đủ (xử lý tiền tố/hậu tố bằng logic biên dịch) |
| `<foreach>` | Đầy đủ (hỗ trợ `List`, mảng, `Map`). Xem [foreach & Batching](foreach-and-batches.md) |
| `<resultMap>` | Hỗ trợ join 1 cấp (`<association>`, `<collection>`). Xem [Result Maps](result-maps.md) |
| `<bind>`, `<discriminator>`, `<parameterMap>`, `<cache>`, `<selectKey>` | Không hỗ trợ. Xem [Khác biệt với MyBatis](../features/mybatis-differences.md) |

`resultType` và `resultMap` nhận **tên class đầy đủ (FQN)** (ví dụ `com.example.app.User`). Không hỗ trợ alias registry động.

## Inlining `<sql>` và `<include>`

Thuộc tính `refid` trong `<include>` được processor resolve và inlined trực tiếp lúc build:

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

Nhờ được inlined hoàn toàn lúc build, câu truy vấn vẫn được phân tích tĩnh danh sách cột để sinh lệnh đọc theo vị trí cột (`rs.getString(1)`).

## Các annotations bổ sung trên Mapper XML

Các annotation như `@Param`, `@Options`, `@PadPow2` vẫn hoạt động bình thường trên các phương thức ánh xạ qua XML:

```java
@Mapper
public interface UserBatchMapper {

    List<User> findByIds(List<Long> ids);

    @PadPow2
    List<User> findByIdsPadded(List<Long> ids);

    int deleteByIds(@Param("ids") List<Long> ids, @Param("keepName") String keepName);
}
```

