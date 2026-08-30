# Shape và value

Mọi quyết định thiết kế trong LarkBatis đều bắt nguồn từ một lát cắt. Một bên: mọi thứ
suy ra được từ **shape** của mapper, và shape thì ngừng thay đổi khi file được lưu. Bên
kia: những **giá trị** chảy qua một lời gọi lúc chạy.

Phía shape được resolve lúc build. Phía value là phần duy nhất còn lại.

## Danh sách đóng

Danh sách dưới đây là toàn bộ những gì được phép resolve lúc chạy, và nó đóng: một danh
sách mở sẽ âm thầm mọc lại thành một trình thông dịch.

| Resolve lúc chạy | Vì sao buộc phải thế |
|---|---|
| **Giá trị** tham số | Chúng là đầu vào |
| **Kết quả boolean** của một test `<if>` / `<when>` | Nó phụ thuộc vào giá trị tham số |
| **Kích thước** tập hợp trong `<foreach>` | Nó phụ thuộc vào giá trị tham số |
| Các **dòng** trong một `ResultSet` | Database sinh ra chúng |
| **Số cột thật**, khi bộ sinh code không phân tích được select list | `SELECT *` không có câu trả lời tĩnh |
| **Nội dung** của một `SqlFragment` | Cửa thoát hiểm, và nó được rà soát |

Mọi thứ khác đều xảy ra lúc build. Không phải "thường là", không phải "khi có thể": là
mọi thứ.

Bản thiết kế còn để dành một chỗ nữa — một `databaseId` chọn một lần lúc khởi động, để
mỗi statement có thể có biến thể riêng cho từng loại database. **Chỗ đó chưa bao giờ được
làm.** Hiện tại, thuộc tính `databaseId` trên một statement là lỗi biên dịch, và câu trả
lời cho hai loại database là hai interface mapper. Dòng này được nói rõ ra thay vì lặng lẽ
bỏ đi, vì một danh sách tự nhận là đóng thì phải trung thực về những gì nằm trong nó.

## Điều đó đổi lại được gì, từng mục một

| Quyết lúc build | MyBatis làm gì lúc chạy thay cho nó |
|---|---|
| `ps.setXxx` nào gắn mỗi tham số | Tra `TypeHandlerRegistry` theo kiểu Java và kiểu JDBC |
| Chỉ số cột nào nuôi mỗi setter | `MetaObject.setValue(propertyName, value)` bằng reflection cho mỗi cột trên mỗi dòng |
| Setter đó rốt cuộc là cái nào | `Reflector` dựng một map tên → `Invoker` cho mỗi lớp |
| `<where>` có phát từ khoá của nó không | Một lượt quét mảnh SQL đã ráp lúc chạy để tìm `AND`/`OR` đứng đầu |
| `<include refid>` bung ra thành cái gì | Tra từ một map trong `Configuration` |
| Biểu thức Java cho mỗi `test` | OGNL phân tích rồi đánh giá dựa trên một `ObjectWrapper` |
| Lớp nào hiện thực mapper | `Proxy.newProxyInstance` + điều phối qua `MapperMethod` |

## Những hệ quả thật sự cảm nhận được

**Lỗi kiểu dời về lúc biên dịch.** Một `#{customerName}` không tồn tại trên kiểu tham số
là lỗi build có nêu tên phương thức. Trong MyBatis nó là một `ReflectionException` lúc
chạy, trên đúng nhánh code xui xẻo.

**Không có metadata nào phải viết cho native image.** Không `Proxy`, không
`Class.forName`, không `setAccessible`, nên chẳng có gì để khai báo. Tính chất này là *hệ
quả* của lát cắt, không phải một tính năng được thêm vào.

**Không thể vô tình đưa reflection quay lại.** Chẳng có runtime nào để mà làm chuyện đó.
Một yêu cầu tính năng cần soi kiểu lúc chạy thì không có chỗ nào để đặt, và đó là lý do
[danh sách tính năng bị bỏ](../features/mybatis-differences.md) lại như hiện tại.

**Một số tính năng MyBatis trở thành bất khả thi chứ không phải chưa hiện thực.** Phân
biệt đó quan trọng khi đọc danh sách bị bỏ. `<discriminator>` chọn lớp kết quả từ một giá
trị cột, nghĩa là *shape* của kết quả phụ thuộc vào một giá trị lúc chạy, nên tự thân nó
đã nằm sai phía của lát cắt. Lazy loading cần một proxy cho mỗi đối tượng kết quả. Plugin
móc vào một pipeline runtime vốn không tồn tại. Không cái nào trong số đó là "chưa làm".

## Chỗ nào lát cắt gây khó chịu

Ba chỗ, và cần thành thật rằng đó là những đánh đổi chứ không phải phần thắng miễn phí.

**1 · Số phần tử của `<foreach>`.** Số placeholder đúng là một giá trị lúc chạy, nên câu
SQL của những statement đó được ráp lúc chạy. LarkBatis biên dịch vòng lặp thay vì thông
dịch một cái cây, nhưng câu SQL vẫn thay đổi, và đó là lý do những statement ấy có theo
dõi biến thể cũng như lý do `@PadPow2` tồn tại.

**2 · `SELECT *`.** Số cột không biết được lúc build. Riêng statement đó lùi về đọc theo
tên, với chỉ số lấy từ `ResultSetMetaData` ở dòng đầu tiên. Vẫn đúng, chậm hơn, và được báo
lúc build để nó là một quyết định.

**3 · `${}`.** Đôi khi một định danh thật sự đến từ cấu hình. Thay vì cấm nó, lát cắt
được cưỡng chế ở mức kiểu: chỉ `SqlFragment`, các kiểu giá trị đóng, hoặc
`@OrderBy(allowed = {...})` mới được nối vào, và văn bản tuỳ ý có đúng một điểm vào có
tên.

## Phép thử cho mọi tính năng mới

Trước khi thêm bất cứ thứ gì, câu hỏi là: *thứ này có cần một giá trị lúc chạy không nằm
trong danh sách không?*

- **Không** → nó thuộc về lúc build, và câu hỏi thiết kế duy nhất còn lại là code sinh ra
  nên trông thế nào.
- **Có** → hoặc danh sách phải dài thêm, và điều đó đòi một lý do rất tốt, hoặc tính năng
  bị bỏ kèm một lỗi biên dịch nêu tên thứ thay thế.

Hãy đọc [danh sách tính năng bị bỏ](../features/mybatis-differences.md) với câu hỏi đó
trong đầu và nó sẽ thôi trông có vẻ tuỳ tiện.
