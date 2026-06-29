# WORKLOG — C2-App-069

> File này ghi lại các quyết định kỹ thuật quan trọng, ai làm gì, và những vướng mắc lớn trong quá trình phát triển.
> Mục tiêu: người mới đọc vào hiểu được "dự án đang làm gì, vì sao làm vậy" mà không cần đọc code trước.

---

## 2026-06-23 — PDF Agent: tính năng đọc & kiểm tra bài báo PDF có sẵn

### Vấn đề cần giải quyết
Trước đó, hệ thống (Research Agent) chỉ có thể tự viết một bài tổng quan tài liệu mới từ đầu. Nhưng người dùng nhiều khi đã có sẵn 1 bài báo (của mình hoặc người khác) và muốn kiểm tra: văn phong có ổn không, các nguồn trích dẫn có thật không hay bị "bịa". Vì vậy nhóm xây thêm một tính năng riêng cho việc này — gọi là PDF Agent.

Quyết định quan trọng nhất: PDF Agent KHÔNG tự kiểm tra lại bài mà chính hệ thống mình vừa viết ra. Lý do: nếu cùng một hệ thống vừa viết nội dung, vừa tự "nghi ngờ" nội dung của mình thì không có giá trị kiểm chứng độc lập. Các sản phẩm thị trường (Elicit, Scite, Paperpal) cũng tách riêng việc "viết" và việc "kiểm tra" thành 2 sản phẩm khác nhau.

### Những gì đã làm
- Xây tính năng này thành một phần hoàn toàn riêng biệt, không gắn vào quy trình viết bài hiện có — chỉ dùng lại các phần tra cứu bài báo đã có sẵn, không sửa gì ảnh hưởng tới phần đang chạy ổn.
- Người dùng tải lên file PDF, file LaTeX, hoặc file zip (gồm cả ảnh/hình minh họa) → hệ thống tự nhận diện loại file và chuyển thành file LaTeX có thể chỉnh sửa được, không mất ảnh.
- Hệ thống soát qua toàn bài để: (1) chỉ ra đoạn văn nào viết chưa rõ ràng, lặp ý, dùng thuật ngữ không thống nhất, kèm gợi ý sửa lại; (2) kiểm tra từng nguồn trích dẫn xem có tồn tại thật không; (3) kiểm tra các đường link trong bài có còn truy cập được không.
- Hai loại góp ý hiển thị khác nhau ngay trong văn bản, giống tính năng "Đề xuất chỉnh sửa" của Google Docs:
  - **Gợi ý sửa văn phong**: có sẵn bản đề xuất, người dùng có thể Đồng ý (áp dụng) hoặc Từ chối.
  - **Cảnh báo trích dẫn/link đáng ngờ**: không có bản sửa sẵn (vì không ai biết "đáp án đúng" cho một nguồn bị bịa) — người dùng chỉ có thể Bỏ qua, không có nút Đồng ý, để tránh ngầm gợi ý rằng cảnh báo đó có cách sửa sẵn.
- Người dùng cũng có thể bôi đen một đoạn bất kỳ để hỏi "Giải thích đoạn này nói gì" hoặc "Viết lại đoạn này" — phần viết lại luôn cần người dùng xác nhận trước khi áp dụng vào bài, không tự động ghi đè.
- Vị trí của mỗi góp ý được "neo" theo nội dung xung quanh (đoạn trước/sau) thay vì theo số thứ tự ký tự — nhờ vậy nếu người dùng sửa đoạn khác trong bài, các góp ý không bị lệch vị trí.
- Việc đọc file PDF (qua công cụ chuyển đổi/OCR riêng) được tách ra chạy trong một dịch vụ độc lập, vì công cụ này khá nặng — tránh làm chậm cả hệ thống chính.
- Kết quả được lưu vào đúng nơi lưu các bài tổng quan đã viết trước đó ("My Review"), chỉ thêm một trường đánh dấu đây là tài liệu người dùng tự tải lên.

### Đánh đổi đã chấp nhận
- Chưa có phương án dự phòng trả phí khi công cụ đọc PDF xử lý kém — tạm thời chỉ báo lỗi rõ cho người dùng.
- Lưu trữ tiến trình của tính năng này tách riêng khỏi tiến trình của tính năng viết bài chính, để tránh lẫn dữ liệu giữa hai tính năng.
- Hiện tại giả định chỉ có một người chỉnh sửa một tài liệu tại một thời điểm — chưa hỗ trợ nhiều người cùng sửa.

### Lỗi quan trọng đã phát hiện và sửa
- File zip người dùng tải lên có thể chứa đường dẫn độc hại để ghi đè file ngoài ý muốn trên server (lỗi an ninh dạng "đường dẫn thoát thư mục") — đã thêm bước kiểm tra chặn trước khi giải nén.
- Ban đầu hệ thống vô tình cho phép "Đồng ý" với cả cảnh báo trích dẫn giả — đã sửa để chặn hành động này.
- Việc áp dụng đoạn viết lại ban đầu không kiểm tra đoạn văn gốc có còn đúng như lúc người dùng bôi đen hay không — nếu người dùng vừa tự sửa tay đúng lúc hệ thống đang trả lời, bản viết lại có thể ghi đè sai chỗ. Đã thêm bước kiểm tra khớp chính xác trước khi cho ghi.

---

## 2026-06-(20-21) — Viết lại "bộ não" Research Agent + thêm Sơ đồ tri thức (Knowledge Graph)

### Vấn đề cần giải quyết
Sau khi rà lại cách hệ thống đang tìm và viết bài tổng quan, nhóm nhận ra 3 điểm yếu:
1. Hệ thống không hiểu được người dùng đang muốn gì trước khi tìm — kể cả khi người dùng chỉ gõ "hello" thì vẫn bị đẩy thẳng vào quy trình tìm bài báo.
2. Mỗi lần tìm chỉ dùng một câu hỏi tìm kiếm trên một nguồn dữ liệu — dễ bỏ sót những bài quan trọng nhìn từ góc khác hoặc nằm ở nguồn khác (một nghiên cứu đối chiếu cho thấy chỉ khoảng 20% bài AI chọn trùng với bài chuyên gia chọn nếu tìm kiểu này).
3. Các bước viết bài và kiểm tra trích dẫn lẽ ra có thể làm cùng lúc nhưng đang chạy lần lượt, khiến người dùng phải chờ 5-10 phút không cần thiết.

Đồng thời, nhóm muốn thêm một cách trực quan để xem lại bài tổng quan đã viết — không chỉ đọc văn xuôi tuyến tính mà còn xem được "ai đồng ý với ai, ai phản bác ai" qua một sơ đồ — gọi là Sơ đồ tri thức (Knowledge Graph).

### Những gì đã làm
- Chuyển toàn bộ quy trình tìm kiếm/viết bài/kiểm tra (trước đây là 4 chức năng tách rời, không liên kết với nhau) thành một quy trình duy nhất, có khả năng "dừng lại chờ người dùng xác nhận" ở vài điểm quan trọng rồi tiếp tục — giống một bản nhạc có những đoạn nghỉ định trước để người chỉ huy ra dấu trước khi chơi tiếp.
- Thêm bước mới: trước khi tìm kiếm thật, hệ thống hiển thị "kế hoạch nghiên cứu" (các câu hỏi sẽ tìm, nguồn sẽ tìm) cho người dùng xem và sửa trước — tránh tốn công tìm theo hướng sai.
- Cho phép tìm kiếm trên nhiều nguồn dữ liệu khác nhau cùng lúc (không chỉ Semantic Scholar mà còn thêm arXiv, OpenAlex, PubMed tuỳ chủ đề) để bao quát hơn.
- Xây dựng tính năng Sơ đồ tri thức: ráp lại dữ liệu mà hệ thống đã có sẵn sau khi viết bài (chủ đề → nhóm ý chính → bài báo → luận điểm) thành một sơ đồ trực quan, không cần gọi thêm AI tốn chi phí. Sơ đồ chỉ hiển thị những bài báo thực sự được trích dẫn trong bài viết, không phải toàn bộ hàng trăm bài đã quét qua — để sơ đồ gọn, đúng trọng tâm "xem lại bài đã viết" thay vì "xem toàn bộ kho tìm kiếm".
- Phát hiện một thiếu sót quan trọng: bước "lan rộng tìm kiếm theo trích dẫn" trước đây có lấy được thông tin "bài nào trích dẫn bài nào" nhưng lại không lưu lại — phải sửa để giữ lại thông tin này, vì không có nó thì sơ đồ sẽ thiếu hẳn các đường nối trích dẫn giữa bài báo.
- Sơ đồ hiển thị trong một khung riêng có thể mở ra, không phải một tab cố định cạnh bài viết — vì sơ đồ cần không gian rộng để hiển thị đẹp. Hiệu ứng chuyển động trong sơ đồ (xoay quanh tâm) mặc định tắt và tự tắt nếu máy người dùng có cài đặt "giảm chuyển động" — ưu tiên người dễ bị chóng mặt khi nhìn hình xoay liên tục hơn là hiệu ứng đẹp mắt.

### Đánh đổi đã chấp nhận
- Cơ sở dữ liệu tạm lưu tiến trình vẫn đang chạy ở dạng đơn giản (local), chưa chuyển sang hệ thống database chính thức — đủ dùng cho giai đoạn phát triển, biết sẽ phải đổi khi đưa lên server thật.
- Lớp "khái niệm" trong sơ đồ tri thức (tự động gắn nhãn các khái niệm khoa học bằng AI) chưa làm — để dành cho giai đoạn sau.
- Tìm kiếm đa nguồn đã viết xong và nối vào hệ thống nhưng chưa đo thử xem có thực sự tìm được nhiều bài hay hơn cách cũ không.

### Lỗi quan trọng đã phát hiện và sửa
- Sơ đồ bị lỗi hiển thị ở phía người dùng vì có những đường nối trích dẫn chỉ đến bài báo "ngoài phạm vi" (không nằm trong bài viết) — đã sửa để chỉ vẽ đường nối khi cả hai đầu đều có mặt trong sơ đồ.
- Tên trường dữ liệu giữa phần xử lý dữ liệu và phần hiển thị không khớp nhau — phải viết thêm một bước chuyển đổi ở giữa.
- Một số luận điểm tham chiếu tới bài báo không còn nằm trong phạm vi bài viết, gây ra các điểm "mồ côi" trong sơ đồ — đã thêm bước lọc bỏ.
- Khi nhiều bước chạy đồng thời, hệ thống theo dõi tiến trình (để hiển thị "đang làm gì" cho người dùng) bị thiếu một số sự kiện — phải nâng cấp cách lắng nghe sự kiện.

---

## 2026-06-(15-18) — Cải thiện chất lượng tìm kiếm/viết bài, làm trang Quản trị, gộp code từ nhiều người

### Vấn đề cần giải quyết
Sau khi luồng tìm-viết-kiểm tra cơ bản chạy được, nhóm rà soát lại và phát hiện 6 vấn đề ảnh hưởng tới chất lượng bài tổng quan được viết ra. Đồng thời cần làm trang Quản trị (Admin) để xem người dùng/hoạt động hệ thống, và phải liên tục gộp các nhánh code mà từng thành viên trong nhóm làm riêng (đăng nhập, lưu bài đã viết, phát hiện khoảng trống nghiên cứu, cập nhật cơ sở dữ liệu) vào nhánh code chung.

### Những gì đã làm (6 cải tiến chính cho chất lượng bài viết)
1. **Chọn bài báo "hạt giống" để lan rộng tìm kiếm công bằng hơn**: trước đây chỉ chọn theo số lượt trích dẫn/năm — cách này thiên vị bài mới, bỏ sót các bài nền tảng cũ nhưng vẫn rất quan trọng. Sửa lại: chọn cả nhóm bài có nhiều trích dẫn tổng cộng (bài nền tảng) VÀ nhóm bài có tốc độ trích dẫn nhanh gần đây (bài đang nổi), rồi gộp lại.
2. **Không loại bỏ bài mới đột phá chỉ vì chưa có nhiều trích dẫn**: trước đây có một ngưỡng số lượt trích dẫn tối thiểu cố định để giữ lại một bài — ngưỡng cố định này loại mất các bài vừa công bố (chưa kịp được trích dẫn nhiều) dù có thể rất quan trọng. Sửa thành ngưỡng linh hoạt theo thời gian, và cho bài được đánh dấu "có ảnh hưởng" được giữ lại dù trích dẫn còn thấp.
3. **Chọn dàn ý bài viết từ nguồn bài rộng hơn, có người dùng duyệt lại**: trước đây dàn ý chỉ được chọn từ 100 bài tìm được ban đầu — bỏ sót các bài hay được tìm thấy sau ở bước lan rộng. Sửa thành chọn từ tập bài lớn hơn (300-400 bài) và đa dạng hơn, đồng thời cho người dùng xem/sửa dàn ý trước khi hệ thống viết nội dung — sửa ở giai đoạn này rẻ hơn nhiều so với phát hiện sai sau khi đã viết xong.
4. **Sửa cách "hiểu" câu hỏi tìm kiếm cho đúng mục đích hơn**: mô hình AI dùng để so khớp câu hỏi người dùng với bài báo trước đây được huấn luyện cho việc khác (so sánh hai bài báo với nhau) — không tối ưu cho việc "so khớp một câu hỏi ngắn với nội dung bài báo". Đổi sang phiên bản mô hình được tinh chỉnh đúng cho việc tìm kiếm.
5. **Kiểm tra trích dẫn đáng tin hơn**: trước đây chỉ kiểm tra được khoảng 30% trích dẫn (do nguồn dữ liệu kiểm tra hạn chế). Thêm hai lớp kiểm tra dự phòng: nếu không kiểm tra được bằng cách thông thường thì thử đọc toàn văn bài báo trên arXiv (miễn phí, đạt khoảng 80%); nếu vẫn không được thì chỉ dùng phần tóm tắt để kiểm tra ở mức "không khẳng định đúng, chỉ phát hiện rõ sai" — tránh trường hợp khẳng định nhầm một trích dẫn là đúng trong khi thực ra chưa chắc, vì việc đó còn nguy hiểm hơn không kiểm tra.
6. **Không bỏ qua kiểm tra trích dẫn chỉ vì "có vẻ ủng hộ luận điểm"**: trước đây nếu một trích dẫn được dùng để "ủng hộ" một luận điểm thì được bỏ qua bước kiểm tra kỹ — nhưng đây chính là nhóm dễ bị sai lệch nhất (AI có xu hướng đơn giản hóa quá mức bài báo nó dùng để ủng hộ một luận điểm). Sửa để mọi trích dẫn đều được kiểm tra đầy đủ, ưu tiên độ chính xác hơn tốc độ.

### Công việc khác trong giai đoạn này
- Làm trang Quản trị (Admin): xem số liệu thống kê, danh sách người dùng, lịch sử hoạt động.
- Hợp nhất các nhánh code của từng thành viên (đăng nhập, lưu bài tổng quan đã viết, phát hiện khoảng trống nghiên cứu, cập nhật cấu trúc cơ sở dữ liệu, trang quản trị) vào nhánh phát triển chung — kiểm tra kỹ, xử lý xung đột code trước khi gộp.

### Đánh đổi đã chấp nhận
- Phân tích "bài nào cùng được trích dẫn với bài nào khác" (gợi ý mức độ liên quan gián tiếp) chưa làm — để dành cho giai đoạn sau.
- Lan rộng tìm kiếm theo trích dẫn hiện chỉ làm một lớp (bài trực tiếp trích dẫn/được trích dẫn), chưa làm tiếp lớp thứ hai — cần thêm dữ liệu thực tế để quyết định có cần không.

### Lỗi quan trọng đã phát hiện và sửa
- Thư viện kết nối cơ sở dữ liệu không tương thích với định dạng khóa truy cập mới của Supabase — sửa bằng cách gọi trực tiếp tới dịch vụ cơ sở dữ liệu thay vì qua thư viện trung gian.
- Hệ thống đăng nhập từ chối sai một số người dùng vì chỉ chấp nhận một trong hai kiểu mã hoá token, trong khi dự án đang dùng kiểu thứ ba — đã thêm hỗ trợ.
- Việc ghi log đăng nhập/đăng xuất bị âm thầm thất bại do quyền truy cập cơ sở dữ liệu chặn lại (lỗi không hiện ra ngoài) — phải đổi cách ghi log để dùng đúng quyền truy cập.
- Bước lan rộng tìm kiếm theo trích dẫn gọi nhiều yêu cầu cùng lúc tới Semantic Scholar và bị nhà cung cấp tạm khoá vì vượt giới hạn tốc độ gọi — sửa bằng cách gọi lần lượt, có chờ một khoảng ngắn giữa mỗi lượt.

---

## 2026-06-(11-14) — Bỏ khung sườn ban đầu, tự xây luồng riêng + đổi giao diện sang Vite + React

### Vấn đề cần giải quyết
Codebase ban đầu nhóm dùng làm điểm xuất phát là một khung sườn có sẵn ("Open Deep Research") được thiết kế cho việc tìm kiếm thông tin trên web nói chung — không phù hợp với nhu cầu cụ thể của dự án (tìm bài báo khoa học, kiểm tra trích dẫn). Việc giữ khung sườn này gây ra: phần code không liên quan tới mục tiêu dự án nằm rải rác trong hệ thống, và giao diện ban đầu (Streamlit) chỉ phù hợp cho demo đơn giản, không đủ linh hoạt cho nhiều bước tương tác (tìm → lan rộng → viết → kiểm tra → duyệt).

### Những gì đã làm
- Xoá bỏ toàn bộ phần khung sườn không dùng tới, vì không có chỗ nào trong kế hoạch dự án gọi tới phần này.
- Tổ chức lại phần gọi AI thành từng bước rõ ràng, tương ứng với từng giai đoạn trong quy trình (lên dàn ý, viết nội dung, trích luận điểm, kiểm tra luận điểm, chat thông thường) — tách phần "gọi AI" ra khỏi phần "xử lý nghiệp vụ" để dễ kiểm tra và sửa từng phần độc lập.
- Đổi giao diện từ Streamlit (vốn chỉ phù hợp cho một trang đơn giản) sang Vite + React — phù hợp hơn cho việc hiển thị nhiều bước, nhiều trạng thái, và sau này dễ thêm sơ đồ trực quan.
- Thêm hệ thống đăng nhập (qua Supabase Auth) để có thể lưu lại lịch sử nghiên cứu theo từng người dùng, không chỉ lưu tạm trong bộ nhớ.

### Đánh đổi đã chấp nhận
- Mất khả năng "dừng và tiếp tục sau" mà khung sườn cũ hỗ trợ sẵn — nhưng không cần thiết cho luồng tuần tự đơn giản ở giai đoạn này (sau này khi cần lại, nhóm tự xây tính năng tương đương, xem mục 2026-06-20/21 phía trên).
- Phần gọi AI được tự viết tay thay vì dùng thư viện trung gian có sẵn — ít tính năng có sẵn hơn nhưng dễ hiểu/dễ sửa hơn vì không có lớp ẩn nào ở giữa.
- Một số gói thư viện của khung sườn cũ vẫn còn khai báo trong cấu hình dự án — sẽ dọn ở một lần cập nhật riêng sau khi chắc chắn không còn chỗ nào dùng tới.

### Lỗi quan trọng đã phát hiện và sửa
- Lỗi khởi động chương trình do cách khai báo kiểu dữ liệu không tương thích phiên bản Python.
- Lệnh khởi động server trỏ sai tên thư mục project sau khi đổi tên (sót lại từ tên cũ).
- Thiếu một gói thư viện cần cho việc đăng nhập trong môi trường máy ảo Python đang dùng.

---

## 2026-06-07 — Khởi tạo repo & setup môi trường (máy Windows)

### Việc đã làm
- Clone mẫu khởi đầu của khoá học.
- Cài đặt sẵn cơ chế tự động ghi log mỗi khi dùng AI hỗ trợ code (yêu cầu của khoá học) — chạy tự động mỗi khi đẩy code lên, không cần làm thủ công.
- Tạo file cấu hình môi trường từ file mẫu.
- Xác nhận cơ chế ghi log hoạt động đúng.

### Công cụ AI đang dùng
Antigravity IDE — tự động ghi log, không cần thêm bước thủ công.

### Vấn đề gặp phải (đặc thù Windows)
- Cơ chế ghi log ban đầu được viết cho môi trường Linux/macOS, không chạy được thẳng trên Windows (thiếu một lớp giả lập Linux) — phải sửa lại script cho tương thích Windows.
- Một số lệnh sao chép file dùng cú pháp Linux không có sẵn trên Windows — đổi sang lệnh tương đương của Windows.

---

## 2026-06-07 — Khởi tạo repo & setup môi trường (máy macOS/Linux)

### Việc đã làm
- Clone mẫu khởi đầu của khoá học (đã có sẵn cơ chế ghi log AI cho nhiều công cụ AI khác nhau, không cần tự xây lại).
- Xác nhận môi trường chạy được trên máy, file cấu hình đã có đủ thông tin cần thiết.

### Quyết định
- Giữ nguyên mẫu khởi đầu của khoá học thay vì tự dựng project mới từ đầu — vì mẫu đã có sẵn các cơ chế cần thiết (ghi log, script khởi động đa nền tảng), tự làm lại sẽ tốn công vô ích cho cả nhóm. Đổi lại, nhóm phải tuân theo cách tổ chức file/script của mẫu này khi thêm công nghệ mới về sau.
- Mọi script hỗ trợ trong dự án nên gọi qua một lớp "khởi chạy chung" có sẵn trong mẫu — để không phụ thuộc việc máy mỗi người gọi lệnh Python khác nhau.

### Vấn đề gặp phải
- Một file script quan trọng bị thiếu quyền "cho phép chạy" khi tải về từ mẫu — đã sửa quyền file, nhưng quyết định KHÔNG đưa thay đổi này vào commit hiện tại vì nó không liên quan tới nội dung commit, để dành cho một lần dọn dẹp riêng.

### Phân công & việc đang mở
- Mỗi thành viên tự chạy thử cơ chế ghi log trên máy mình, xác nhận file cấu hình có đủ thông tin.
- Chưa quyết định: làm web app, app di động, hay công cụ dòng lệnh? Sẽ quyết khi nhóm thống nhất ý tưởng sản phẩm.
- Mỗi thành viên giữ một file ghi chú cá nhân riêng (theo mẫu `JOURNAL-<tên>.md`), tách biệt với file ghi quyết định chung này.

---

## Cấu trúc nhánh (branch)

| Nhánh | Mục đích |
|--------|----------|
| `main` | Code ổn định, đã được kiểm tra kỹ |
| `develop` | Nhánh phát triển chung, nơi gộp các tính năng trước khi lên `main` |

---

_Cập nhật file này mỗi khi có quyết định kỹ thuật mới, phân công công việc, hoặc lỗi quan trọng cần ghi nhớ. Viết sao cho người mới đọc vào cũng hiểu được "vì sao" mà không cần đọc code trước._
