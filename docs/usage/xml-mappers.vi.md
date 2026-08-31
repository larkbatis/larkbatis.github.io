# Mapper XML

Một interface chú thích `@Mapper` lấy SQL cho từng phương thức từ statement trong mapper XML có cùng id. Namespace chính là tên đầy đủ (FQN) của interface.

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

Phần khai báo DTD được giữ lại để các file sẵn có vẫn parse được nguyên trạng và editor vẫn hỗ trợ gợi ý cú pháp. Khai báo này không bị tải về hay kiểm tra lúc build.

## Vì sao cần annotation `@Mapper`

Mapper thuần annotation không cần đánh dấu: processor tự động nhận diện vì các phương thức mang `@Select` và các annotation statement tương ứng. Một interface chỉ dùng XML thì không có annotation statement nào trên phương thức, do đó cần `@Mapper` để processor nhận biết và đưa vào vòng xử lý.

## Gán statement cho từng phương thức

Mỗi phương thức trừu tượng lấy SQL **hoặc** từ annotation của nó **hoặc** từ XML. Khai báo cả hai, hoặc không khai báo ở đâu, đều là lỗi biên dịch nêu rõ tên phương thức. Nhờ vậy một mapper có thể kết hợp linh hoạt cả hai cách:

```java
@Mapper
public interface UserMapper {

    @Select("SELECT id, name FROM users WHERE id = #{id}")
    User findById(long id);          // lấy từ annotation

    List<User> search(UserSearch q); // lấy từ UserMapper.xml
}
```

## Vị trí quét file XML

Processor quét các thư mục được cấu hình qua `-Alarkbatis.mapperDir`. Các [build plugin](../getting-started/build-plugins.md) truyền sẵn tham số này (mặc định là `src/main/resources`), đồng thời đăng ký các file XML làm đầu vào biên dịch để tự động kích hoạt sinh lại code khi XML thay đổi.

Chỉ những file có **thẻ gốc là `<mapper>`** mới được xử lý, các file cấu hình Spring hay logback trong cùng thư mục đều được bỏ qua an toàn. Mapper XML có `namespace` trỏ tới interface ở module khác sẽ bị bỏ qua kèm một cảnh báo build.

## Các thẻ XML được hỗ trợ

| Thẻ | Mức độ hỗ trợ |
|---|---|
| `<select>`, `<insert>`, `<update>`, `<delete>` | Đầy đủ |
| `<sql>`, `<include>` | Chỉ hỗ trợ `refid` tĩnh, được chèn thẳng lúc build |
| `<if>`, `<choose>`/`<when>`/`<otherwise>` | Đầy đủ, với [ngữ pháp test thu hẹp](dynamic-sql.md#the-test-grammar) |
| `<where>`, `<set>`, `<trim>` | Chỉ hỗ trợ thuộc tính hằng, gập hằng số lúc build |
| `<foreach>` | Tập hợp, mảng và Map có kiểu tĩnh rõ ràng. [Xem chi tiết](foreach-and-batches.md) |
| `<resultMap>` | Hỗ trợ 1 cấp `<association>` / `<collection>`. [Xem chi tiết](result-maps.md) |
| `<bind>`, `<discriminator>`, `<parameterMap>`, `<cache>`, `<selectKey>` | Không hỗ trợ; xem [Khác biệt với MyBatis](../features/mybatis-differences.md) |

`resultType` và `resultMap` nhận **tên class đầy đủ (FQN)**. Không hỗ trợ type-alias registry lúc runtime vì mọi kiểu dữ liệu đều được resolve lúc build.

## `<sql>` và `<include>`

`refid` được tra và chèn thẳng vào lúc build, nên nó phải là hằng. Một `refid` tính toán
ra là lỗi biên dịch.

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

Sau khi chèn, statement không khác gì một statement viết đầy đủ ngay từ đầu, kể cả với
việc phân tích select list, nên `<include>` không làm bạn mất khả năng đọc dòng theo vị
trí.

## Khoảng trắng

Các mảnh được nối bằng đúng một dấu cách và kết quả được cắt hai đầu. Chính sách này cố
định và có ghi lại, và nó không sao chép khoảng trắng tình cờ của MyBatis, vốn khác nhau
giữa các phiên bản MyBatis ở cách xử lý `<trim>`. Nếu bạn đem so từng ký
tự SQL sinh ra với đầu ra của MyBatis, hãy chờ đợi khoảng trắng khác nhau còn ngữ nghĩa
thì không.

## Những annotation vẫn có tác dụng

Statement trong XML vẫn gắn với một phương thức Java, nên annotation ở mức phương thức
và mức interface vẫn hoạt động: `@PadPow2` trên một statement có `<foreach>`, `@Param`
trên các tham số, `@Options` trên một `<insert>`:

```java
@Mapper
public interface UserBatchMapper {

    List<User> findByIds(List<Long> ids);

    @PadPow2
    List<User> findByIdsPadded(List<Long> ids);

    int deleteByIds(@Param("ids") List<Long> ids, @Param("keepName") String keepName);
}
```
