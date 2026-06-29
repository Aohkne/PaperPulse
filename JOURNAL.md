# JOURNAL — G069

> Ghi chú cá nhân của từng thành viên: việc đã làm, bug gặp phải, học được gì, quyết định riêng trong ngày.
> Quyết định chung của cả nhóm xem ở `WORKLOG.md`. File này viết để người mới đọc cũng hiểu được đang làm gì, không cần biết trước code.

---

## 2026-06-26 — Sửa lỗi: trả lời sai ngôn ngữ sau khi gộp code - Lê Hữu Khoa

### Việc đã làm
- Khôi phục lại quy tắc "trả lời cùng ngôn ngữ với câu hỏi của người dùng" (đặc biệt với câu hỏi tiếng Anh ngắn hoặc viết tắt) — quy tắc này đã bị mất khi gộp các nhánh code của nhóm lại.

### Bug / fix gặp phải
- **Hệ thống trả lời nhầm sang tiếng Trung/Nhật/Hàn khi người dùng hỏi câu tiếng Anh ngắn** — nguyên nhân là một phần code xử lý an toàn (chặn nội dung không phù hợp) được tách ra từ một bản cũ hơn, trước khi quy tắc ngôn ngữ được sửa — khi gộp lại vào nhánh chung, phần quy tắc ngôn ngữ bị ghi đè trở lại bản cũ.
- Đã sửa lại đúng quy tắc ở cả hai chỗ liên quan, không đổi gì khác trong logic phân loại ý định người dùng.

### Tiếp theo
- Thêm vài câu hỏi kiểm tra ngắn riêng cho quy tắc ngôn ngữ vào bộ kiểm tra tự động — để tránh lặp lại lỗi này ở lần gộp code song song kế tiếp.

---

## 2026-06-23 — PDF Agent: tính năng đọc & kiểm tra PDF/.tex có sẵn - Lê Hữu Khoa

### Việc đã làm
- Xây tính năng mới hoàn toàn độc lập với phần viết bài tổng quan hiện có — chỉ dùng lại các phần tra cứu bài báo đã có sẵn, không sửa gì trong phần đang chạy ổn.
- Nhận diện file người dùng tải lên thuộc loại nào (PDF / file LaTeX trần / file zip có kèm ảnh) để xử lý đúng nhánh.
- Viết phần đọc nội dung theo từng loại file:
  - File PDF: dùng công cụ chuyển đổi riêng (MinerU) để tách thành các phần văn bản + hình ảnh + danh sách trích dẫn thô (rồi dùng AI dọn lại danh sách trích dẫn cho sạch).
  - File LaTeX trần: tự phân tích cấu trúc văn bản, lấy ra từng phần + các chỗ trích dẫn + các chỗ chèn ảnh.
  - File zip: giải nén an toàn (có kiểm tra chặn đường dẫn độc hại trước khi giải nén), tự tìm ra file chính trong số nhiều file.
- Ghép lại thành một file LaTeX hoàn chỉnh có thể chỉnh sửa, kèm thư mục ảnh — đóng gói thành 1 file zip để người dùng tải về hoặc tiếp tục sửa ngay trên web.
- Chạy đồng thời 3 việc kiểm tra: (1) một AI riêng nhận xét văn phong từng phần (rõ ràng, thống nhất thuật ngữ, mạch lạc, có lặp ý không), (2) kiểm tra từng trích dẫn có thật không (tra nhiều nguồn, so khớp nhiều trường thông tin, AI phân xử cho các trường hợp không chắc chắn), (3) kiểm tra các đường link trong bài còn truy cập được không.
- Ghép 3 kết quả kiểm tra trên thành các "góp ý" gắn vào đúng vị trí trong văn bản, dùng cách neo vị trí theo nội dung xung quanh (không theo số thứ tự ký tự) để góp ý không bị lệch khi người dùng sửa đoạn khác.
- Làm 3 nút hành động khi người dùng bôi đen một đoạn: Giải thích, Viết lại, Áp dụng (chỉ Áp dụng mới ghi thật vào văn bản, và phải kiểm tra đoạn gốc chưa bị đổi trước khi ghi).
- Làm phần lưu kết quả vào đúng chỗ lưu các bài tổng quan đã viết trước đó, chỉ thêm một vài trường đánh dấu đây là tài liệu người dùng tự tải lên.
- Làm giao diện: khung tải file lên, trình soạn LaTeX có đánh dấu góp ý ngay trong văn bản, thẻ hiển thị từng góp ý, thanh công cụ khi bôi đen, khung xem trước đoạn viết lại.
- Đóng gói công cụ chuyển đổi PDF (MinerU) thành một dịch vụ chạy riêng, tách khỏi dịch vụ chính — vì công cụ này khá nặng, không nên làm chậm cả hệ thống.

### Bug / fix gặp phải
- **Công cụ chuyển đổi PDF cần dung lượng lưu trữ riêng khá lớn** — không gộp chung vào dịch vụ chính (sẽ làm dịch vụ chính nặng theo không cần thiết). Sửa: tách thành dịch vụ riêng.
- **Phần tra cứu trích dẫn cũ chỉ hỗ trợ "tìm theo từ khoá"** chưa có cách "tra theo mã định danh có sẵn" (DOI/ID) — phải viết thêm, kiểm tra kỹ để không ảnh hưởng tới phần viết bài đang chạy ổn.
- **Ban đầu hệ thống vô tình cho phép "Đồng ý" với cả cảnh báo trích dẫn giả** — soát lại yêu cầu ban đầu (không có "bản sửa đúng" cho citation giả nên không nên có nút Đồng ý) → đã thêm chặn.
- **Việc áp dụng đoạn viết lại ban đầu ghi đè thẳng vào văn bản, không kiểm tra đoạn gốc còn khớp hay không** — nếu người dùng vừa tự sửa tay đúng lúc AI đang trả lời, bản viết lại có thể ghi đè sai chỗ. Đã thêm bước kiểm tra khớp chính xác trước khi cho ghi, báo lỗi rõ nếu lệch.

### Quyết định kỹ thuật
- Quy trình PDF Agent chạy liền một lượt từ đầu tới cuối, không có điểm dừng nào để chờ người dùng duyệt giữa đường — khác với phần viết bài tổng quan (cần dừng để người dùng duyệt dàn ý/luận điểm). Lý do: mọi tương tác của người dùng với PDF Agent (đồng ý/từ chối/bỏ qua/áp dụng) đều xảy ra SAU khi việc đọc + kiểm tra đã xong hết, không có bước nào cần người dùng quyết định trước thì mới chạy tiếp được.
- Lưu trữ tiến trình của PDF Agent tách riêng khỏi tiến trình của phần viết bài tổng quan — hai việc khác nhau (một bên là phiên nghiên cứu, một bên là tài liệu người dùng tải lên), tách ra để không bị lẫn dữ liệu.
- Mọi góp ý bắt buộc neo theo nội dung xung quanh, không theo số thứ tự ký tự — để góp ý không bị trôi sai vị trí khi người dùng sửa đoạn khác.

### Tiếp theo
- Đo chi phí thật khi xử lý một tài liệu có nhiều trích dẫn/nhiều phần, so với ước tính ban đầu.
- Thử kiểm tra lại độ an toàn của bước giải nén zip với một file zip có đường dẫn độc hại thật, xác nhận có bị chặn đúng không.
- Có một thiếu sót (không phải của PDF Agent) cần sửa ở phần viết bài tổng quan: phần Mở đầu/Kết luận được viết SAU bước kiểm tra luận điểm, nên các trích dẫn trong đó chưa từng qua kiểm tra.

---

## 2026-06-21 — Thêm bước duyệt kế hoạch tìm kiếm + tìm đa nguồn + Sơ đồ tri thức - Lê Hữu Khoa

### Việc đã làm
- **Thêm bước "Duyệt kế hoạch nghiên cứu"**: ngay sau khi hệ thống hiểu ý định người dùng và lên kế hoạch tìm kiếm, hệ thống dừng lại hiển thị kế hoạch (các câu hỏi sẽ tìm, nguồn sẽ tìm) cho người dùng xem/sửa trước khi gọi bất kỳ API tìm kiếm thật nào — tránh tốn công tìm theo hướng sai.
- Viết một thuật toán chọn bài đa dạng (tên thuật toán: MMR — chọn bài vừa liên quan tới câu hỏi vừa khác với những bài đã chọn trước đó, tránh chọn toàn bài giống nhau) — dùng cho cả bước lên dàn ý và bước tìm bài riêng cho từng chủ đề.
- Nối thêm các nguồn tìm kiếm thật khác ngoài Semantic Scholar: arXiv, OpenAlex, và PubMed (cho chủ đề y sinh) — hệ thống tự chọn nguồn phù hợp theo kế hoạch đã được duyệt ở bước trên.
- Cải thiện cách lưu trữ vector cho việc tìm kiếm khi số lượng bài báo lớn hơn (sau bước lan rộng theo trích dẫn, có thể lên tới 600-900 bài).
- Xây tính năng **Sơ đồ tri thức** (Knowledge Graph):
  - Sửa lại bước "lan rộng tìm kiếm theo trích dẫn" để giữ lại thông tin "bài nào trích dẫn bài nào" — trước đây bước này chỉ giữ danh sách bài báo, bỏ qua hoàn toàn quan hệ trích dẫn giữa các bài.
  - Viết phần ráp sơ đồ: 1 điểm gốc duy nhất là chủ đề nghiên cứu → các nhóm ý chính (theme) → các bài báo thật sự được dùng trong bài viết (không phải toàn bộ bài đã quét qua) → các luận điểm, với 2 loại đường nối riêng (một loại trung tính chỉ để biết luận điểm lấy từ bài nào, một loại mang ý nghĩa ủng hộ/phản bác/mở rộng để biết luận điểm đó đứng ở phía nào so với nhóm ý chính).
  - Thêm 1 chỗ trong API để frontend lấy sơ đồ đã ráp xong, đọc lại từ tiến trình đã lưu, báo lỗi nếu sơ đồ chưa được tạo.
  - Làm phần hiển thị sơ đồ ở giao diện: vẽ sơ đồ, thẻ chi tiết khi bấm vào từng loại điểm (chủ đề/nhóm ý/bài báo/luận điểm), bố cục dạng vòng tròn đồng tâm (giống hệ mặt trời) để dễ định hướng, và một khung riêng để mở sơ đồ ra (không phải tab cố định).
- Làm thêm một trang Quản trị để chạy thử trực tiếp phần viết bài tổng quan, giúp debug nhanh từng bước mà không cần qua giao diện chat chính.

### Bug / fix gặp phải
- **Bước lan rộng tìm kiếm theo trích dẫn đổi cách trả kết quả** (trả thêm cả danh sách quan hệ trích dẫn, không chỉ danh sách bài) — phải sửa luôn chỗ nhận kết quả này để đọc đúng cả hai phần, nếu không hệ thống sẽ hiểu nhầm dữ liệu.
- **Sơ đồ bị lỗi hiển thị (crash) ở phía người dùng** vì có đường nối trích dẫn chỉ tới bài báo nằm ngoài phạm vi bài viết (bị loại sau khi lọc/lên dàn ý) — sửa bằng cách chỉ vẽ đường nối khi cả hai đầu đều đã có mặt trong sơ đồ.
- **Tên trường dữ liệu không khớp nhau** giữa phần xử lý dữ liệu (Python) và phần hiển thị (giao diện web) — viết thêm một bước chuyển đổi nhỏ ở giữa.
- **Một số luận điểm tham chiếu tới bài báo nằm ngoài phạm vi bài viết** (bị loại sau khi lọc/lên dàn ý) — nếu không kiểm tra sẽ tạo ra các điểm "mồ côi" trong sơ đồ. Sửa bằng cách bỏ qua có chủ đích các luận điểm này.

### Quyết định kỹ thuật
- Sơ đồ tri thức hiển thị trong một khung riêng có thể mở ra, không phải tab cố định cạnh trình soạn văn bản — vì sơ đồ cần không gian rộng để bố cục dạng vòng tròn không bị bóp méo.
- Mặc định không hiện chữ/tên trên các điểm trong sơ đồ khi có nhiều điểm cùng lúc (dễ rối mắt) — thông tin chi tiết chuyển hết vào thẻ hiển thị khi bấm vào.
- Hiệu ứng chuyển động (sơ đồ tự xoay) là tuỳ chọn, mặc định tắt, và tự tắt nếu máy người dùng có cài đặt "giảm chuyển động" — ưu tiên người dễ bị chóng mặt khi nhìn hình xoay liên tục hơn là hiệu ứng đẹp mắt (theo khuyến nghị tiêu chuẩn khả năng truy cập web WCAG).

### Tiếp theo
- Bắt đầu làm tính năng PDF Agent — đọc kỹ tài liệu thiết kế trước, vì đây là tính năng hoàn toàn độc lập, có entry point riêng, không nối sau phần viết bài tổng quan.
- Đo số lượng bài báo thật sự xuất hiện trong sơ đồ sau khi chạy với dữ liệu thật — xác nhận có đúng khoảng 60-150 bài như ước tính không.

---

## 2026-06-20 — Viết lại "bộ não" Research Agent theo dạng quy trình có thể dừng/tiếp tục - Lê Hữu Khoa

### Việc đã làm
- Xây một package mới cho phần viết bài tổng quan, thay cho 4 chức năng tách rời cũ (tìm kiếm / lan rộng theo trích dẫn / kiểm tra / duyệt) — gộp lại thành một quy trình duy nhất, có thể dừng ở một số điểm để chờ người dùng xác nhận rồi tiếp tục, giống một bản nhạc có những đoạn nghỉ định trước.
- Định nghĩa rõ luồng đi qua từng bước: hiểu ý định người dùng → (trả lời thường nếu là chào hỏi, hoặc tiếp tục tìm kiếm nếu là yêu cầu nghiên cứu) → lan rộng tìm kiếm theo trích dẫn → tạo vector tìm kiếm → lên dàn ý → viết nội dung theo từng nhóm ý → trích luận điểm → kiểm tra luận điểm → phân loại kết quả → xuất bài.
- Viết các bước nhỏ tương ứng với từng giai đoạn trên, mỗi bước chỉ là một lớp bao mỏng gọi tới phần xử lý nghiệp vụ thật — để phần xử lý nghiệp vụ có thể kiểm tra độc lập, không phụ thuộc vào cách quy trình tổng được chạy.
- Viết lại chỗ nhận yêu cầu từ giao diện để truyền tiến trình từng bước (đang làm gì, xong bước nào) ngay khi đang chạy, không phải chờ xong hết mới trả kết quả.
- Bổ sung các phần tìm kiếm còn thiếu cho việc tìm đa nguồn: tìm trên arXiv, tìm trên OpenAlex, lọc trùng giữa các nguồn (ưu tiên theo mã định danh chuẩn trước, rồi mới so tên bài gần giống nếu không có mã).
- Sắp xếp lại tên gọi cho rõ ràng: tách phần "gọi AI" ra khỏi phần "điều phối/xử lý dữ liệu" để dễ phân biệt vai trò.
- Cập nhật phần hiển thị tiến trình ở giao diện để khớp với cách quy trình mới báo tiến trình.
- Chuyển một tính năng cũ (phát hiện khoảng trống nghiên cứu) sang cùng cách tổ chức package mới cho đồng bộ, không đổi logic.

### Bug / fix gặp phải
- **Tổ chức lại 2 phần lớn cùng lúc trong một lần thay đổi** (phần viết bài tổng quan mới + chuyển tính năng phát hiện khoảng trống nghiên cứu) — dễ sót file cũ không còn dùng nếu không kiểm tra kỹ trước khi lưu lại.
- **Chỗ quyết định "đi tiếp bước nào sau khi hiểu ý định"** ban đầu viết hơi cứng, chưa tính tới việc sẽ có thêm bước "duyệt kế hoạch nghiên cứu" chèn vào sau (thêm sau đó vài ngày) — phải sửa lại để dễ mở rộng thêm bước mới mà không phải đổi cấu trúc.
- **Theo dõi tiến trình bị thiếu sự kiện** cho các bước chạy đồng thời (viết nội dung nhiều nhóm ý cùng lúc, kiểm tra nhiều luận điểm cùng lúc) — phải nâng cấp cách lắng nghe sự kiện mới bắt đủ.

### Quyết định kỹ thuật
- Mỗi bước nhỏ trong quy trình chỉ là lớp bao mỏng, toàn bộ logic thật nằm ở phần xử lý nghiệp vụ riêng — để có thể kiểm tra phần xử lý nghiệp vụ độc lập, không cần chạy cả quy trình lớn.
- Tách việc "trả lời thường" (chào hỏi/làm rõ câu hỏi) ra một bước riêng, không gộp chung với bước "hiểu ý định" — vì hai việc rất khác nhau (một bên là phân loại có cấu trúc, một bên là trả lời tự nhiên), gộp chung sẽ khó debug khi một trong hai bị sai.
- Cách lưu tiến trình được viết theo kiểu chung, chưa gắn cứng vào một công nghệ lưu trữ cụ thể — để sau này đổi sang hệ thống lưu trữ chính thức mà không phải sửa lại toàn bộ quy trình.

### Tiếp theo
- Thêm bước "duyệt kế hoạch nghiên cứu" trước khi tìm kiếm thật — hiện kế hoạch mới chỉ hiển thị, chưa có cách cho người dùng sửa trước khi chạy.
- Nối đầy đủ các nguồn tìm kiếm đa dạng (OpenAlex/PubMed) vào quy trình chính — phần xử lý đã viết nhưng chưa gọi tới hết.
- Sửa bước lan rộng tìm kiếm theo trích dẫn để giữ lại quan hệ "bài nào trích dẫn bài nào" trước khi làm Sơ đồ tri thức — hiện chỉ trả về danh sách bài, thiếu thông tin này sẽ làm sơ đồ thiếu đường nối.

---

## 2026-06-(15-18) — Cải thiện chất lượng pipeline tìm kiếm/viết bài, làm trang Quản trị, gộp code nhóm - Lê Hữu Khoa

### Việc đã làm
- Viết lại tài liệu thiết kế, ghi nhận 6 cải tiến cho quy trình tìm-viết-kiểm tra sau khi rà soát lại bản thiết kế gốc:
  - **Cải tiến 1 — Chọn bài "hạt giống" công bằng hơn**: chọn cả nhóm bài có nhiều trích dẫn tổng cộng (bài nền tảng) và nhóm bài có tốc độ trích dẫn nhanh gần đây (bài đang nổi), thay vì chỉ chọn theo một tiêu chí.
  - **Cải tiến 2 — Không loại bỏ bài mới vì chưa đủ trích dẫn**: đổi ngưỡng trích dẫn tối thiểu cố định thành ngưỡng linh hoạt theo thời gian, cho bài được đánh dấu "có ảnh hưởng" được giữ lại dù trích dẫn còn thấp.
  - **Cải tiến 3 — Dàn ý từ nguồn bài rộng hơn**: chọn dàn ý từ một tập bài lớn và đa dạng hơn (300-400 bài) thay vì chỉ 100 bài tìm được ban đầu, thêm bước cho người dùng xem/sửa dàn ý trước khi viết nội dung.
  - **Cải tiến 4 — Sửa cách "hiểu" câu hỏi tìm kiếm**: đổi sang phiên bản mô hình AI được tinh chỉnh đúng cho việc so khớp câu hỏi ngắn với nội dung bài báo (mô hình cũ vốn được huấn luyện cho việc khác — so sánh hai bài báo với nhau).
  - **Cải tiến 5 — Kiểm tra trích dẫn đáng tin hơn**: thêm hai lớp kiểm tra dự phòng (đọc toàn văn trên arXiv nếu cách thường không tìm được, rồi mới tới kiểm tra bằng tóm tắt ở mức rất thận trọng) để tăng độ phủ kiểm tra từ ~30% lên cao hơn nhiều.
  - **Cải tiến 6 — Không bỏ qua kiểm tra trích dẫn "ủng hộ"**: bỏ việc bỏ qua kiểm tra kỹ cho các trích dẫn có vẻ đang ủng hộ luận điểm — đây lại chính là nhóm dễ bị sai lệch nhất.
- Làm chỗ nhận yêu cầu mới để truyền tiến trình từng bước của quy trình tìm-viết-kiểm tra ngay khi đang chạy, hiển thị cho người dùng thấy "đang làm gì" theo thời gian thực.
- Làm phần hiển thị tiến trình ở giao diện theo màu/icon riêng cho từng bước, và dữ liệu giả lập để demo giao diện trước khi nối API thật.
- Thêm đường dẫn file PDF (ưu tiên bản miễn phí công khai trước) vào toàn bộ kết quả tìm kiếm để người dùng có thể mở bài báo gốc dễ hơn ở bước cuối.
- Xây trang Quản trị: xem số liệu thống kê, danh sách người dùng, lịch sử hoạt động (đọc trực tiếp từ cơ sở dữ liệu bằng quyền quản trị để không bị chặn bởi quy tắc phân quyền thông thường), và một chỗ kiểm tra "ai có quyền quản trị" dùng cho các trang admin.
- Dọn lại phần đăng nhập/đăng xuất: gộp việc ghi log các sự kiện này vào một chỗ chung, đảm bảo ghi đủ và đúng quyền truy cập.
- Gộp nhiều nhánh code của các thành viên trong nhóm (đồng bộ với nhánh chung, tính năng đăng nhập, lưu bài đã viết, phát hiện khoảng trống nghiên cứu, trang quản trị, cập nhật cấu trúc cơ sở dữ liệu cho chat/tin nhắn/thông báo) vào nhánh phát triển chung — kiểm tra kỹ, xử lý xung đột trước khi gộp.

### Bug / fix gặp phải
- **Thư viện kết nối cơ sở dữ liệu không tương thích với định dạng khóa truy cập mới** khi gọi cho chỗ kiểm tra quyền quản trị — sửa bằng cách gọi trực tiếp tới dịch vụ cơ sở dữ liệu, không qua thư viện trung gian.
- **Hệ thống đăng nhập chỉ chấp nhận hai trong số các kiểu mã hoá token** — dự án đang dùng kiểu thứ ba, khiến đăng nhập báo lỗi sai. Đã thêm hỗ trợ kiểu mã hoá còn thiếu.
- **Ghi log đăng nhập bị âm thầm thất bại** vì quy tắc phân quyền chặn việc ghi, lỗi không hiện ra (do code đang "nuốt" lỗi âm thầm) — chuyển sang cách ghi dùng đúng quyền truy cập.
- **Bước lan rộng tìm kiếm theo trích dẫn gọi tất cả cùng lúc → bị nhà cung cấp tạm khoá vì vượt giới hạn tốc độ gọi** — đổi sang gọi lần lượt, có chờ một khoảng ngắn giữa mỗi lượt.

### Tiếp theo
- Làm phân tích "bài nào cùng được trích dẫn với bài nào khác" (ghi nhận là việc còn thiếu, để dành cho giai đoạn sau).
- Đánh giá có cần làm lan rộng tìm kiếm theo trích dẫn ở lớp thứ hai không, dựa trên dữ liệu thực tế thu được.
- Nối phần hiển thị tiến trình ở giao diện từ dữ liệu giả lập sang API thật khi phần stream ổn định.
- Theo dõi một lỗi nhỏ (Anh Thư ghi nhận khi kiểm tra hôm 06-17) liên quan tới việc một trường thông tin trong kết quả kiểm tra trích dẫn bị hiển thị không khớp với dữ liệu thật.

---

## 2026-06-17 — Kiểm tra thủ công: chống bịa thông tin & kiểm tra trích dẫn - Trần Nguyễn Anh Thư

### Việc đã làm
- Kiểm tra nhanh 4 chức năng cơ bản (kiểm tra sức khoẻ hệ thống, tìm kiếm, chat, duyệt dàn ý) — tất cả đạt trước khi vào phần kiểm tra chính.
- Thiết kế và chạy 6 trường hợp kiểm tra, tập trung vào hai việc: hệ thống có bịa ra bài báo không tồn tại không? Và việc kiểm tra luận điểm có làm đúng quy tắc không?
- TC-01: Hỏi một câu hỏi rất hẹp, kiểm tra 3 bài báo được trả về có tồn tại thật trên Semantic Scholar không — xác nhận không có bài bị bịa.
- TC-02: Hỏi trực tiếp AI mà không cho tra cứu dữ liệu thật (làm mốc so sánh) — xác nhận AI đưa ra trích dẫn có thật nhưng sai chủ đề (đúng mã nhưng nội dung không liên quan). Việc này được ghi nhận là kết quả "fail nhưng có giá trị" — đúng là điều cần chứng minh để thấy việc tra cứu dữ liệu thật là cần thiết, không phải lỗi cần sửa.
- TC-03: Chạy quy trình tìm-viết-kiểm tra đầy đủ với một câu hỏi thật, kiểm tra các bài báo được trích dẫn trong bài viết ra có đúng không. TC-03c kiểm tra kết quả kiểm tra luận điểm có đủ thông tin theo thiết kế không.
- TC-04: Dùng một tên tác giả không tồn tại — xác nhận hệ thống trả về không có bài báo nào, không bịa nội dung.
- TC-05: Hỏi một chủ đề đang gây tranh cãi — xác nhận bài viết có đưa cả góc nhìn ủng hộ và phản bác. TC-05b kiểm tra việc xử lý một luận điểm có ý kiến trái chiều.
- TC-06: Kiểm tra quy tắc "không được khẳng định đúng khi không có bằng chứng" — dùng một bài báo không có đoạn trích dẫn để đối chiếu.
- Tổng hợp toàn bộ kết quả vào một file riêng và lưu lại trong repo.

### Bug / issue gặp phải
- **TC-06 lần đầu không tạo ra được đúng trường hợp cần kiểm tra** — mọi kết quả đều thiếu đoạn bằng chứng đi kèm. Chưa rõ là lỗi hay trường hợp này chưa được làm → báo lại cho dev. Thử lại với bài báo khác → ra đúng kết quả mong đợi → đạt.
- **Một trường thông tin trong kết quả kiểm tra bị hiển thị không khớp với dữ liệu thật** — quy tắc chính vẫn đúng, chỉ là một trường hiển thị gây hiểu lầm. Ghi nhận là lỗi mức độ thấp, báo dev.
- **Một trường hợp ban đầu bị đánh giá "chưa đạt"** vì thiếu một thông tin phụ — sau khi hỏi lại nhóm phát triển mới biết tiêu chí đạt không cần thông tin đó. Đổi lại kết quả thành "đạt".
- **Một lỗi xuất hiện không cố định ở bước lên dàn ý** trong vài lần chạy — không lặp lại được để xác nhận, ghi chú lại nhưng không chặn việc kiểm tra.

### Học được
- **Hỏi rõ tiêu chí đánh giá với nhóm phát triển trước khi tự đánh giá kết quả** — một trường hợp tốn thời gian vì tự đoán tiêu chí từ tài liệu thay vì hỏi sớm.
- **Một kết quả "thất bại" cũng có giá trị** nếu nó chứng minh được lý do một cơ chế an toàn là cần thiết — quan trọng là ghi rõ *tại sao* thất bại, không chỉ ghi kết quả đạt/không đạt.
- **Cách nhanh nhất để xác nhận một bài báo có thật**: tra trực tiếp trên trang Semantic Scholar bằng mã bài báo — không cần đọc cả bài, chỉ cần xác nhận nó tồn tại.
- Kiểm tra một hệ thống AI sinh nội dung khác với kiểm tra API thông thường: kết quả không cố định mỗi lần chạy, nên cần kiểm tra "đặc tính" của kết quả (mã bài báo có thật không, trạng thái có đúng quy tắc không) thay vì so khớp chính xác từng chữ.

### Quyết định kỹ thuật
- Dùng chức năng chạy toàn bộ quy trình (không gọi từng bước riêng) cho TC-01 và TC-04 — để xem được toàn cảnh hành vi hệ thống, không bị bỏ sót trường hợp lạ giữa các bước.
- TC-02 là mốc so sánh, không phải lỗi — ghi rõ trong báo cáo để người đọc hiểu đúng mục đích của cơ chế an toàn.
- Giữ một lỗi nhỏ phát hiện được ở mức độ thấp thay vì báo khẩn — vì quy tắc chính không bị vi phạm, chỉ là một trường hiển thị gây hiểu lầm.

### Tiếp theo
- Lưu báo cáo kiểm tra lên repo.
- Báo nhóm phát triển về lỗi nhỏ đã ghi nhận để xác nhận đây là hành vi mong đợi hay cần sửa.
- Nếu còn thời gian: kiểm tra thêm trường hợp xác minh luận điểm qua mã arXiv để có đủ các trường hợp theo thiết kế.

---

## 2026-06-(14-15) — Dọn khung sườn cũ, tách lớp gọi AI, sửa lỗi khởi động - Lê Hữu Khoa

### Việc đã làm
- Xoá bỏ toàn bộ phần khung sườn cũ không còn dùng tới (vốn dùng cho việc tìm kiếm web nói chung, không phù hợp với dự án).
- Tạo một nhóm 5 phần gọi AI riêng biệt, mỗi phần chịu trách nhiệm một việc: lên dàn ý, viết nội dung, trích luận điểm, kiểm tra luận điểm, chat thông thường.
- Tổ chức lại các phần xử lý nghiệp vụ để chỉ còn vai trò điều phối (lấy dữ liệu, gọi AI, trả kết quả) — không còn phần nào lẫn nội dung "câu lệnh ra lệnh cho AI" (prompt) trong đó nữa.
- Thêm hệ thống đăng nhập (qua Supabase Auth): đăng ký / đăng nhập / đăng xuất / làm mới phiên / xem thông tin tài khoản, cùng phần cơ sở dữ liệu cho tài khoản người dùng.

### Bug / fix gặp phải
- **Lỗi khởi động chương trình** do cách khai báo kiểu dữ liệu không tương thích — sửa bằng một dòng khai báo tương thích ngược.
- **Lệnh khởi động server trỏ sai tên thư mục project** — tên thư mục đã đổi nhưng lệnh khởi động bị sót, chưa cập nhật theo.
- **Thiếu một gói thư viện cần cho phần đăng nhập** trong môi trường máy ảo Python đang dùng — sửa bằng cách bọc phần import đó để không gây lỗi lúc chạy thật khi không cần thiết.
- **Cấu hình kết nối cơ sở dữ liệu ban đầu dùng sai dạng địa chỉ** (dùng dạng dùng cho kết nối trực tiếp Postgres, thay vì dạng API của Supabase).

### Tiếp theo
- Xác nhận đã dọn sạch các gói thư viện của khung sườn cũ khỏi cấu hình dự án.
- Gắn hệ thống đăng nhập vào các chỗ cần bảo vệ.
- Kiểm tra toàn bộ quy trình tìm-viết-kiểm tra với một chủ đề thật.

---

## 2026-06-15 — Hoàn thiện giao diện đăng nhập + hỗ trợ giao diện sáng/tối - Trần Nguyễn Anh Thư

### Việc đã làm
- **Đổi màu cố định thành biến màu theo theme** ở trang đăng nhập/đăng ký — toàn bộ nền, ô nhập, nút, chữ giờ tự đổi theo giao diện sáng/tối, không còn mã màu viết cứng.
- **Logo tự đổi theo theme** ở cả hai trang đăng nhập/đăng ký.
- **Đầu trang chủ sau khi đăng nhập**: đổi cụm nút "Đăng nhập + Bắt đầu" thành một nút "Vào ứng dụng →" khi người dùng đã đăng nhập.
- **Nút ẩn/hiện mật khẩu** ở cả ô mật khẩu trang đăng nhập và hai ô mật khẩu (mật khẩu + xác nhận) ở trang đăng ký.
- **Thêm ô xác nhận mật khẩu** ở trang đăng ký: kiểm tra khớp với ô mật khẩu chính + độ dài tối thiểu trước khi cho gửi.
- **Màn hình xác minh email**: nút mở thẳng tới hộp thư Gmail, kèm nút phụ để quay lại trang đăng nhập nếu cần.
- **Đường dẫn quay lại sau khi xác minh email được tính tự động theo domain đang chạy** — để khi triển khai lên domain thật, người dùng vẫn được đưa về đúng trang đăng nhập của domain đó, không phải sửa tay.
- **Đổi icon trang (favicon)** thành logo chữ "P" của PaperPulse, có hỗ trợ hiển thị khác nhau theo giao diện sáng/tối của trình duyệt.

### Bug / fix gặp phải
- Cách đổi màu viền ô nhập khi focus/rời focus dùng trực tiếp biến màu theo theme — hoạt động đúng vì trình duyệt tự tính toán giá trị thật của biến màu khi áp dụng.
- Phát hiện một trường hợp phản hồi từ server (yêu cầu xác minh email) bị xem nhầm là "thành công" ở phía giao diện — nhưng vì giao diện không thật sự dựa vào kết quả đó để quyết định hiển thị, nên không gây lỗi hiển thị thực tế, không cần sửa.

### Quyết định kỹ thuật
- **Không tách riêng một component cho ô mật khẩu có nút ẩn/hiện** — chỉ dùng ở 3 chỗ, viết trực tiếp đủ gọn, chưa cần tách riêng.
- **Sau khi xác minh email, đưa người dùng về thẳng trang đăng nhập** (không phải trang chủ) — để vào lại đúng luồng đăng nhập ngay.
- **Dùng Gmail làm đường dẫn mở email mặc định** thay vì để trình duyệt tự chọn ứng dụng mail — vì người dùng mục tiêu (sinh viên) không chắc có cài ứng dụng mail riêng trên máy, mở Gmail trên web là lựa chọn chắc chắn hoạt động hơn.

### Tiếp theo
- Thêm một thông báo "Email đã xác minh, vui lòng đăng nhập" hiển thị ở trang đăng nhập sau khi người dùng xác minh xong.
- Cân nhắc thêm đường dẫn quay lại vào danh sách được phép của Supabase khi triển khai lên Railway.

---

## 2026-06-15 — Xây giao diện chính của PaperPulse - Trần Nguyễn Anh Thư

### Việc đã làm
- Đọc qua các trang/luồng đang có trong nhánh phát triển chung để hiểu cách tổ chức hiện tại trước khi code.
- Quyết định thiết kế lại toàn bộ giao diện từ kiểu "tìm kiếm + danh sách kết quả" sang kiểu "giao diện chat" — phù hợp hơn với hướng sản phẩm.
- Xây bảng màu và font chữ riêng cho thương hiệu PaperPulse.
- Dựng các phần chính của giao diện: khung chat tổng, thanh điều hướng bên (có thể thu nhỏ), khung tin nhắn, danh sách tin nhắn, ô nhập tin nhắn.
- Thêm khung hiển thị Sơ đồ tri thức (lúc này còn là dữ liệu giả lập, dạng sơ đồ lực hút-lực đẩy đơn giản) có thể đóng/mở bằng một nút riêng.
- Xây trang chủ, trang đăng nhập, trang đăng ký với phần đăng nhập giả lập (chưa nối hệ thống đăng nhập thật).
- Thiết lập điều hướng giữa các trang: trang chủ, đăng nhập, đăng ký, trang ứng dụng chính (chỉ vào được khi đã đăng nhập).
- Thêm thanh kéo để chỉnh độ rộng giữa 3 khung trong giao diện, tự viết bằng các sự kiện chuột cơ bản (không dùng thư viện có sẵn vì thư viện đó bị lỗi về cách giữ kích thước mặc định).
- Gửi yêu cầu gộp code (pull request) lên nhánh phát triển chung.

### Bug / fix gặp phải
- **Thư viện kéo-resize không giữ đúng kích thước mặc định mong muốn** — thư viện tự tải lại cấu hình cũ đã lưu trước đó, kích thước mới đặt không có tác dụng. Sửa: bỏ thư viện, tự viết tính năng kéo-resize bằng sự kiện chuột cơ bản.
- **Thanh điều hướng bên có chiều rộng cố định viết cứng bên trong nó** — khi khung cha đổi tỉ lệ thì thanh điều hướng không co theo. Sửa: chuyển trạng thái "đang thu nhỏ hay không" lên khung cha quản lý, thanh điều hướng luôn chiếm 100% phần được cấp.
- **Toàn bộ chữ trong app không bôi đen/copy được** vì có cài đặt chặn chọn chữ áp lên toàn trang — chỉ nên áp khi đang kéo resize. Sửa: chỉ chặn chọn chữ trong lúc đang kéo, bật lại ngay sau đó.
- **Nút đóng/mở khung Sơ đồ tri thức tạo ra một khoảng trống thừa** trên giao diện — sửa lại vị trí nút cho hợp lý hơn tuỳ theo khung đang mở hay đóng.
- **Sau khi đăng nhập, người dùng bị đưa thẳng vào phiên chat cũ** thay vì màn hình chào mừng mới — sửa bằng cách luôn tạo phiên mới trước khi chuyển vào app.

### Học được
- Frontend và backend có thể làm song song hoàn toàn nhờ dùng dữ liệu giả lập trước — giao diện định hình sẵn "dữ liệu sẽ trông như thế nào", backend chỉ cần khớp đúng hình dạng đó khi làm xong.
- Dùng AI để viết code rất hiệu quả, nhưng cần hiểu *tại sao* lỗi xảy ra trước khi yêu cầu AI sửa — nếu không sẽ sửa mù và lặp lại vòng lặp không ra kết quả.
- Khi gặp lỗi giao diện phức tạp, nên đơn giản hoá trước (cố định tỉ lệ) rồi mới thêm tính năng nâng cao (cho kéo chỉnh) sau.

### Quyết định kỹ thuật
- **Không dùng thư viện kéo-resize có sẵn** — tự viết bằng sự kiện chuột cơ bản đủ dùng, ít phụ thuộc hơn, không có lỗi ẩn khó kiểm soát.
- **Dùng đăng nhập giả lập trước** thay vì nối hệ thống đăng nhập thật ngay — chờ backend xác nhận xong rồi đổi qua sau.
- **Sơ đồ tri thức ở giai đoạn demo này chỉ dùng hiệu ứng vật lý đơn giản viết tay**, không dùng thư viện vẽ đồ thị chuyên dụng — đủ cho việc demo, giữ dung lượng tải trang nhỏ.

### Tiếp theo
- Khi backend hoàn thành phần tìm kiếm thật, đổi phần gửi tin nhắn giả lập trong giao diện sang gọi API thật.
- Thêm khả năng nhớ lại kích thước khung đã kéo (lưu lại) sau khi bố cục ổn định.
- Nối hệ thống đăng nhập thật vào giao diện khi backend làm xong.

---

## 2026-06-08 — Setup công cụ AI hỗ trợ code trên macOS - Lê Hữu Khoa

### Việc đã làm
- Kiểm tra cấu hình tự động ghi log khi dùng AI hỗ trợ code — xác nhận đã có sẵn, không cần thêm gì.
- Xác nhận cơ chế ghi log chạy đúng ở 3 thời điểm: khi người dùng gửi yêu cầu, sau khi dùng một công cụ hỗ trợ, và khi phiên làm việc kết thúc — cả 3 đều tự động gọi tới script ghi log chung.
- **Sửa quyền chạy cho một file script quan trọng**: file này khi tải về từ mẫu khởi đầu bị thiếu quyền "cho phép chạy" — đã sửa quyền, nhưng quyết định KHÔNG đưa thay đổi quyền file này vào commit hiện tại (không liên quan tới nội dung commit), để dành cho một lần dọn dẹp riêng.

### Quyết định kỹ thuật
- **Dùng lớp "khởi chạy chung" làm chuẩn cho mọi script hỗ trợ** — để không phụ thuộc vào cách máy mỗi người gọi lệnh Python (có máy gọi `python`, có máy gọi `python3`).
- **Mặc định tin tưởng cấu hình có sẵn từ mẫu khởi đầu** — không tự thêm/sửa trừ khi có yêu cầu rõ ràng.

### Bug / fix gặp phải
- **Một file script quan trọng thiếu quyền "cho phép chạy" khi clone từ mẫu trên macOS** — có thể gây lỗi "không có quyền" nếu bị gọi trực tiếp. Sửa bằng cách cấp lại quyền chạy.
- **Việc gửi log lên server bị chặn ở 2 chỗ**: (1) thiếu một gói thư viện cần để đọc file cấu hình môi trường, khiến hệ thống không đọc được địa chỉ server cần gửi tới; (2) máy thiếu chứng chỉ bảo mật cần để kết nối an toàn tới server. Đã cài gói thư viện thiếu và cài đặt lại chứng chỉ bảo mật cho đúng phiên bản Python đang dùng.
- Xác nhận lại: log đã gửi thành công lên server sau khi sửa cả hai vấn đề trên.

### Câu hỏi còn mở
- Nhóm chưa quyết định làm web/di động/công cụ dòng lệnh — sẽ ghi vào `WORKLOG.md` sau khi nhóm thống nhất.
- Có cần thêm các thời điểm ghi log khác không? Hiện 3 thời điểm đang dùng đã đủ cho yêu cầu của khoá học.

### Tiếp theo
- Chờ nhóm thống nhất hướng sản phẩm, sau đó bắt đầu dựng khung dự án trên nhánh riêng.
- Dọn riêng việc sửa quyền file script ở một lần cập nhật khác.

---

## 2026-06-10 — Dựng khung giao diện (Vite + React) + quản lý trạng thái - Lê Hữu Khoa

### Việc đã làm
- Cài công cụ quản lý gói cho giao diện (Bun) — chưa có sẵn trên máy.
- Dựng khung giao diện mới (Vite + React) vào đúng thư mục `frontend/` trong dự án.
- Cài các gói cần dùng: quản lý trạng thái dùng chung cho toàn app, bộ icon, công cụ ghép class CSS có điều kiện, và Tailwind CSS cho việc viết style nhanh.
- Cấu hình Tailwind phiên bản mới — không cần file cấu hình riêng, viết trực tiếp trong file CSS chính.
- Tổ chức lại thư mục theo từng tính năng (components dùng chung / tính năng tìm kiếm / layout / trang / store quản lý trạng thái / hàm dùng chung) — xoá bỏ các file mẫu không dùng tới.
- Cấu hình để giao diện khi chạy thử (`bun dev`) tự chuyển các yêu cầu gọi API sang đúng địa chỉ backend đang chạy local.
- Tạo phần quản lý trạng thái cho tính năng tìm kiếm tài liệu: lưu câu hỏi đang gõ, kết quả tìm được, trạng thái (đang chờ/đang tìm/thành công/lỗi), lịch sử các lần tìm gần nhất.
- Việc gọi API tìm kiếm thật tạm thời được giả lập (chưa nối API thật vì backend chưa có sẵn endpoint này) — chỉ cần đổi 1 chỗ khi backend làm xong.
- Kiểm tra: build thử giao diện chạy thành công; xác nhận cơ chế ghi log AI vẫn hoạt động bình thường trong phiên làm việc này.

### Quyết định kỹ thuật
- **Dùng Tailwind phiên bản mới** thay vì phiên bản cũ — không cần file cấu hình riêng, build nhanh hơn.
- **Viết toàn bộ component theo kiểu hàm (function component)** — theo quy ước chung của dự án.
- **Có một hàm dùng chung để ghép class CSS có điều kiện**, dùng ở mọi nơi cần — để chỉ có một cách làm thống nhất, không mỗi nơi viết kiểu khác nhau.
- **Layout mặc định tự hiển thị trang Tìm kiếm nếu không có trang nào khác được chỉ định** — vì hiện tại chỉ có một trang, nhưng sau này khi thêm điều hướng nhiều trang thì không cần sửa lại layout.
- **Tách riêng từng phần quản lý trạng thái theo từng tính năng** (không gộp chung một chỗ quản lý hết) — để mỗi phần giao diện chỉ theo dõi đúng phần dữ liệu mình cần, dễ mở rộng thêm tính năng khác sau này.
- **Tạm dùng dữ liệu giả lập cho việc tìm kiếm** thay vì gọi API thật ngay — để có thể dựng xong giao diện sớm, không phải chờ backend.

### Bug / fix gặp phải
- **Công cụ dựng khung giao diện không ghi đè được vào thư mục đã có sẵn** (dù thư mục đó đang rỗng) — phải dựng ra một thư mục tạm trước, rồi sao chép nội dung vào đúng thư mục dự án, sau đó xoá thư mục tạm.
- **Một vài lệnh sao chép file ẩn không hoạt động đúng trên terminal đang dùng** — đổi sang công cụ sao chép khác xử lý được cả file ẩn.
- **Một file cấu hình bị báo "đã có ai khác sửa"** trong lúc đang đọc, vì việc cài thêm gói cũng tự cập nhật file đó cùng lúc — đọc lại file mới nhất rồi mới ghi tiếp.

### Câu hỏi còn mở
- Có cần thêm hệ thống điều hướng nhiều trang ngay từ đầu không? Hiện một trang đã đủ, nhưng nếu backend sẽ có nhiều luồng (tìm kiếm, tổng hợp, phát hiện khoảng trống nghiên cứu, xuất file) thì làm sớm sẽ đỡ phải sửa lại sau.
- Việc chuyển tiếp API chỉ hoạt động khi chạy ở máy cá nhân (dev) — khi lên môi trường thật cần backend phục vụ luôn giao diện hoặc cấu hình riêng. Để dành cho bước đóng gói triển khai sau.
- Có cần dùng TypeScript không? Hiện đang quy ước dùng JavaScript thường, nhưng nếu nhóm khác trong dự án dùng TypeScript thì nên thống nhất sớm.

### Tiếp theo
- Viết phần gọi API thật để thay cho phần giả lập trong việc tìm kiếm.
- Gửi phần khung giao diện này lên nhánh đang làm, chia làm 2 lần gửi riêng (1: dựng khung + cài gói, 2: tổ chức lại theo tính năng + phần quản lý trạng thái) để người review dễ xem từng phần.

---

## 2026-06-07 — Khởi tạo repo (tham khảo WORKLOG)

Đã đọc qua hai mục ghi chú setup trong `WORKLOG.md` (máy Windows + máy macOS) để hiểu ngữ cảnh chung của nhóm. Mọi quyết định chung của nhóm được ghi ở `WORKLOG.md`; file ghi chú này chỉ ghi việc cá nhân và lỗi mình tự gặp.

---

_Cập nhật file này mỗi khi có việc setup/sửa lỗi cá nhân, học được điều gì mới, hoặc có quyết định riêng trong ngày. Viết sao cho người mới đọc vào cũng hiểu được đang làm gì, không cần biết trước code._
