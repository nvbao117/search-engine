# Future Development Guide

Tài liệu này mô tả lộ trình phát triển hệ thống hiện tại từ MVP nhỏ thành một search engine báo tiếng Việt đầy đủ hơn, có:

- crawl từ nhiều nguồn
- làm sạch dữ liệu mạnh hơn
- lexical search tốt
- hybrid retrieval
- NER / entity enrichment
- reranker
- evaluation bài bản

Mục tiêu của tài liệu:

- chỉ ra thứ tự phát triển đúng
- tránh làm quá nhiều phần “AI nâng cao” quá sớm
- giúp mở rộng hệ thống mà không phá cấu trúc đang có

---

## 1. Nguyên tắc phát triển

Thứ tự đúng nên là:

1. Crawl ổn định
2. Làm sạch dữ liệu tốt
3. Dedup tốt
4. Lexical search mạnh
5. Evaluation rõ ràng
6. Hybrid retrieval
7. Reranker
8. NER / entity layer

Không nên làm theo thứ tự ngược lại.

Lý do:

- Nếu dữ liệu bẩn, hybrid và reranker vẫn cho ra kết quả bẩn.
- Nếu không có evaluation, không biết mô hình mới có tốt hơn thật hay không.
- Nếu crawl không ổn định, search quality không thể ổn định.

---

## 2. Mục tiêu tổng thể

Đích đến dài hạn là xây một hệ thống có khả năng:

- crawl được nhiều trang báo tiếng Việt
- chuẩn hóa và làm sạch nội dung tự động
- index được dữ liệu lớn hơn nhiều so với MVP
- phục vụ search nhanh và ổn định
- hỗ trợ search có dấu / không dấu
- hỗ trợ hybrid search
- hỗ trợ reranker cho top results
- hỗ trợ entity-aware search
- đo được chất lượng bằng metrics và bộ query chuẩn

---

## 3. Kiến trúc mục tiêu

Kiến trúc gợi ý:

`Source Registry -> Scheduler -> Fetcher -> Raw Storage -> Parser -> Cleaner -> Dedup -> Enrichment -> Indexer -> OpenSearch/Vector -> API -> UI -> Logs/Evaluation`

Các lớp nên tách rõ:

- `connectors/`
  - code riêng cho từng nguồn báo
- `crawl/`
  - scheduler, fetcher, retry, queue
- `raw_storage/`
  - lưu HTML gốc và metadata fetch
- `cleaning/`
  - normalize text, remove boilerplate
- `dedup/`
  - exact dup + near-dup
- `enrichment/`
  - folded text, embeddings, entities
- `indexing/`
  - article index, suggestion index, vector index
- `serving/`
  - API search và UI
- `evaluation/`
  - judged queries, metrics, reports

---

## 4. Giai đoạn 1 — Củng cố nền tảng hiện tại

### Mục tiêu

Biến hệ thống MVP hiện tại thành một baseline ổn định, dễ mở rộng.

### Việc cần làm

#### 4.1 Chuẩn hóa cấu trúc repo

Mục tiêu:

- tách rõ phần ingest, API, UI, infra
- chuẩn bị đường đi cho crawler và enrichment

Nên thêm hoặc chuẩn hóa:

- `apps/api`
- `apps/web`
- `scripts/ingest_index`
- `data/raw`
- `data/clean`
- `services/opensearch`
- `docs/`
- `future/` hoặc `pipelines/` cho giai đoạn sau

#### 4.2 Tăng độ rõ của config

Mục tiêu:

- mọi thành phần đọc config rõ ràng từ env/config file

Cần bổ sung:

- file cấu hình index names
- batch size ingest
- synonym path
- source configs
- crawl rate limit

#### 4.3 Cải thiện runtime local/dev

Mục tiêu:

- developer chạy hệ thống nhanh, ít lỗi môi trường

Cần có:

- Docker Compose ổn định
- API auto-reload
- hướng dẫn bootstrap index rõ
- scripts chạy phổ biến

### Kết quả mong muốn

- repo dễ đọc
- quy trình chạy local rõ ràng
- không còn phụ thuộc vào thao tác thủ công mơ hồ

---

## 5. Giai đoạn 2 — Thu thập dữ liệu thật từ nhiều nguồn

### Mục tiêu

Xây pipeline crawl thật, thay vì chỉ dựa vào JSONL mẫu.

### Phạm vi

Bắt đầu từ 2–3 nguồn trước:

- `vnexpress`
- `thanhnien`
- `tuoitre`

Không nên crawl quá nhiều nguồn ngay từ đầu.

### Việc cần làm

#### 5.1 Tạo source registry

Mục tiêu:

- mỗi báo là một source có config và parser riêng

Mỗi source nên có:

- `name`
- `base_url`
- `rss_urls`
- `sitemap_urls`
- `allowed_domains`
- `rate_limit`
- `parser_strategy`

### 5.2 Xây fetcher chung

Mục tiêu:

- tải HTML ổn định, retry được, không trùng lặp request

Fetcher nên có:

- timeout
- retry
- user-agent hợp lý
- redirect handling
- logging theo URL
- lưu HTTP status

### 5.3 Tách raw storage

Mục tiêu:

- lưu lại HTML gốc để debug parser và clean pipeline

Mỗi raw record nên lưu:

- `source`
- `fetch_url`
- `final_url`
- `canonical_url`
- `fetched_at`
- `http_status`
- `html_path` hoặc `html_blob_ref`
- `raw_hash`

### 5.4 Tạo parser riêng cho từng báo

Mục tiêu:

- extract article content chính xác cho từng site

Parser phải lấy được:

- title
- summary
- content
- author
- category
- tags
- published_at
- updated_at
- canonical_url

### 5.5 Tôn trọng legal và vận hành

Mục tiêu:

- không crawl sai phép hoặc quá tải nguồn

Phải kiểm tra:

- `robots.txt`
- terms of use
- crawl interval
- volume mỗi ngày

### Kết quả mong muốn

- crawl được vài nghìn bài thật
- raw HTML được lưu
- article parser chạy ổn định theo từng nguồn

---

## 6. Giai đoạn 3 — Làm sạch dữ liệu nghiêm túc

### Mục tiêu

Tạo một clean dataset đáng tin cậy, vì đây là nền của mọi bước sau.

### Việc cần làm

#### 6.1 Chuẩn hóa URL

Mục tiêu:

- cùng một bài chỉ có một URL chuẩn

Cần làm:

- bỏ `utm_*`, tracking params
- xử lý trailing slash
- lấy canonical URL nếu có
- normalize host/path

#### 6.2 Loại boilerplate

Mục tiêu:

- content chỉ còn nội dung bài viết

Loại bỏ:

- quảng cáo
- box “xem thêm”
- bài liên quan
- social share
- footer/header
- đoạn legal lặp lại

#### 6.3 Chuẩn hóa text

Mục tiêu:

- text nhất quán cho indexing

Cần làm:

- Unicode NFC
- trim và collapse whitespace
- chuẩn hóa line breaks
- giữ text gốc có dấu
- sinh thêm text folded không dấu

#### 6.4 Chuẩn hóa ngày giờ

Mục tiêu:

- filter thời gian hoạt động đúng

Cần:

- parse timezone rõ
- convert về `Asia/Ho_Chi_Minh`
- lưu `published_at`
- lưu `updated_at`

#### 6.5 Gắn quality flags

Mục tiêu:

- phát hiện các record khó xử lý

Ví dụ flag:

- `is_gallery`
- `is_liveblog`
- `is_video_post`
- `content_too_short`
- `parse_quality_score`

### Kết quả mong muốn

- clean JSONL hoặc clean table đủ tin cậy để index
- có quality score cơ bản cho từng bài

---

## 7. Giai đoạn 4 — Dedup và near-duplicate

### Mục tiêu

Loại hoặc gom nhóm các bài trùng / gần trùng.

### Việc cần làm

#### 7.1 Exact duplicate

Mục tiêu:

- loại cùng URL hoặc cùng nội dung y hệt

Rule:

- same canonical URL -> duplicate
- same `title + content hash` -> duplicate

#### 7.2 Near-duplicate

Mục tiêu:

- xử lý bài update nhỏ, syndicated content, bài sao chép

Kỹ thuật có thể dùng:

- shingling
- simhash
- minhash
- cosine similarity trên sparse features

#### 7.3 Duplicate policy

Mục tiêu:

- biết giữ bài nào, bỏ bài nào

Cần quy định:

- giữ canonical record nào
- có gom cluster duplicate không
- có index tất cả source hay chỉ primary source

### Kết quả mong muốn

- duplicate rate thấp
- không còn nhiều bài gần như giống nhau trong top results

---

## 8. Giai đoạn 5 — Nâng cấp lexical search

### Mục tiêu

Làm cho search truyền thống đủ mạnh trước khi thêm vector.

### Việc cần làm

#### 8.1 Cải tiến mapping

Mục tiêu:

- tối ưu field types và scoring

Nên có:

- `title`
- `summary`
- `content`
- `tags_text`
- `*_folded`
- metadata keywords

#### 8.2 Tăng chất lượng analyzer

Mục tiêu:

- xử lý tiếng Việt tốt hơn nhưng vẫn đơn giản

Làm trước:

- lowercase
- asciifolding/folded fields
- synonyms thủ công

Làm sau nếu cần:

- tokenization tiếng Việt nâng cao
- custom analyzer sâu hơn

#### 8.3 Tuning relevance

Mục tiêu:

- kết quả lexical phải tốt với query thật

Tuning:

- `title^5`
- `tags^3`
- `summary^2`
- `content^1`
- recency boost nhẹ
- popularity boost nhẹ nếu có

#### 8.4 Query understanding cơ bản

Mục tiêu:

- query ngắn, có dấu / không dấu đều hoạt động ổn

Làm:

- folded search
- manual synonyms
- abbreviation expansion

### Kết quả mong muốn

- lexical baseline tốt đủ để làm mốc so sánh
- nhiều query thật ra kết quả đúng mà chưa cần vector

---

## 9. Giai đoạn 6 — Logging, analytics và quan sát chất lượng

### Mục tiêu

Biến search thành hệ có thể đo đạc, không còn cảm tính.

### Việc cần làm

#### 9.1 Search log đầy đủ

Mục tiêu:

- biết người dùng tìm gì và hệ trả gì

Log nên có:

- raw query
- normalized query
- filters
- sort
- top result ids
- latency
- total results
- zero-result flag

#### 9.2 Click log

Mục tiêu:

- biết kết quả nào được click

Log nên có:

- query
- article_id
- rank
- timestamp
- session id ẩn danh nếu có

#### 9.3 Dashboard chất lượng cơ bản

Mục tiêu:

- có nơi xem vấn đề thực tế

Nên xem được:

- top queries
- zero-result queries
- query chậm
- click position
- CTR theo query

### Kết quả mong muốn

- có dữ liệu thật để tuning
- không phải đo search bằng cảm giác

---

## 10. Giai đoạn 7 — Evaluation offline bài bản

### Mục tiêu

Tạo bộ đo chất lượng chính thức cho search.

### Việc cần làm

#### 10.1 Tạo query set

Mục tiêu:

- có bộ query đại diện cho nhu cầu người dùng

Phân loại query:

- navigational
- topical
- entity-based
- recency-based
- paraphrase / natural language
- no-accent queries

#### 10.2 Gắn relevance judgments

Mục tiêu:

- mỗi query có nhãn đánh giá rõ

Scale gợi ý:

- `0` = không liên quan
- `1` = liên quan
- `2` = rất liên quan

#### 10.3 Tính metrics

Mục tiêu:

- đo được thay đổi ranking

Metric nên dùng:

- `Precision@10`
- `nDCG@10`
- `MRR@10`
- `Recall@50`
- `Zero-result rate`

#### 10.4 Chia nhóm đánh giá

Mục tiêu:

- biết hệ yếu ở loại query nào

Slice nên có:

- có dấu vs không dấu
- tên người / tổ chức / địa danh
- query ngắn vs query dài
- query thời sự nóng
- query mơ hồ

### Kết quả mong muốn

- có baseline chính thức
- mọi thay đổi relevance đều đo được

---

## 11. Giai đoạn 8 — Vector embeddings và hybrid retrieval

### Mục tiêu

Bổ sung semantic retrieval nhưng không phá lexical baseline.

### Việc cần làm

#### 11.1 Chọn embedding model tiếng Việt

Mục tiêu:

- biểu diễn semantic tốt cho bài báo tiếng Việt

Cần đánh giá:

- chất lượng semantic
- tốc độ embedding
- chi phí inference

#### 11.2 Tạo vector pipeline

Mục tiêu:

- sinh embedding cho document

Nên quyết định:

- embed `title + summary`
- hoặc `title + summary + content excerpt`

#### 11.3 Tạo vector index

Mục tiêu:

- truy hồi semantic top-k

Options:

- OpenSearch vector index
- vector DB riêng nếu scale lớn hơn

#### 11.4 Fusion lexical + vector

Mục tiêu:

- lấy ưu điểm của cả hai

Khuyến nghị:

- lexical top 100
- vector top 100
- merge bằng `RRF`

Không nên bắt đầu bằng weighted sum phức tạp.

### Kết quả mong muốn

- hybrid thắng lexical trên tập query semantic hoặc paraphrase
- latency vẫn chấp nhận được

---

## 12. Giai đoạn 9 — Reranker

### Mục tiêu

Cải thiện chất lượng top results, đặc biệt top 3–5.

### Việc cần làm

#### 12.1 Chọn reranker

Mục tiêu:

- chấm relevance tốt ở mức query-document pair

Input hợp lý:

- query
- title
- summary
- đoạn content rút gọn

#### 12.2 Chỉ rerank shortlist

Mục tiêu:

- giữ latency hợp lý

Rule:

- retrieve top 20–50
- rerank số này thôi

#### 12.3 So sánh với baseline

Mục tiêu:

- chỉ bật reranker nếu nó thắng rõ

So sánh:

- lexical only
- hybrid only
- hybrid + reranker

### Kết quả mong muốn

- top results tốt hơn rõ trên evaluation set
- không làm p95 latency tăng quá mức

---

## 13. Giai đoạn 10 — NER và entity enrichment

### Mục tiêu

Biến hệ search thành hệ có hiểu biết entity tốt hơn.

### Việc cần làm

#### 13.1 NER pipeline

Mục tiêu:

- trích thực thể từ title/summary/content

Thực thể chính:

- person
- organization
- location
- event

#### 13.2 Entity normalization

Mục tiêu:

- cùng một thực thể có cùng id logic

Ví dụ:

- `TPHCM`
- `TP HCM`
- `Thành phố Hồ Chí Minh`

phải được gom về một canonical entity.

#### 13.3 Entity-aware search

Mục tiêu:

- tận dụng entity để tăng chất lượng search

Ứng dụng:

- facet theo entity
- boost bài có entity đúng
- trang tổng hợp theo entity
- related coverage

### Kết quả mong muốn

- query entity cho kết quả chắc hơn
- có thể mở rộng sang topic pages / knowledge features

---

## 14. Giai đoạn 11 — Dữ liệu làm giàu và signals bổ sung

### Mục tiêu

Bổ sung các tín hiệu phụ để ranking tốt hơn.

### Có thể thêm

- popularity score
- freshness score
- source authority
- category-specific boosts
- author consistency
- topic clusters

### Ví dụ ứng dụng

- bài cực mới có boost nhẹ
- bài được đọc nhiều có boost nhẹ
- nhưng không được đẩy bài kém liên quan lên đầu

### Kết quả mong muốn

- ranking ổn định hơn ở môi trường thực tế

---

## 15. Giai đoạn 12 — Production hardening

### Mục tiêu

Biến hệ thống thành dịch vụ chạy lâu dài được.

### Việc cần làm

#### 15.1 Data reliability

Mục tiêu:

- không mất dữ liệu raw / clean / logs

Cần:

- backup
- retention policy
- versioned storage

#### 15.2 Job reliability

Mục tiêu:

- crawl và index không bị silent failure

Cần:

- retries
- dead-letter strategy
- alerts
- job status tracking

#### 15.3 Search reliability

Mục tiêu:

- API ổn định

Cần:

- healthchecks
- readiness checks
- latency monitoring
- index readiness checks

#### 15.4 Release process

Mục tiêu:

- cập nhật search logic an toàn

Cần:

- dev/staging/prod
- reindex strategy
- alias-based rollout
- rollback plan

### Kết quả mong muốn

- hệ không chỉ chạy được, mà còn vận hành được

---

## 16. Mục tiêu cụ thể theo từng chặng

### Chặng A — Crawl thật

Mục tiêu:

- crawl được 2–3 báo
- parse được title/content/date ổn định

Definition of done:

- ít nhất 10k bài raw
- parser accuracy cao trên sample kiểm tra tay

### Chặng B — Clean + dedup

Mục tiêu:

- dữ liệu đủ sạch để index

Definition of done:

- invalid rate thấp
- duplicate rate thấp
- content sạch, ít boilerplate

### Chặng C — Lexical baseline

Mục tiêu:

- search keyword tốt trên query thật

Definition of done:

- query có dấu / không dấu hoạt động
- filter hoạt động
- highlight hoạt động
- evaluation baseline ổn

### Chặng D — Evaluation

Mục tiêu:

- có mốc chất lượng chính thức

Definition of done:

- có query set
- có judgments
- có báo cáo metrics

### Chặng E — Hybrid

Mục tiêu:

- semantic retrieval tốt hơn cho query paraphrase

Definition of done:

- hybrid thắng lexical trên subset semantic

### Chặng F — Reranker

Mục tiêu:

- top-k chính xác hơn

Definition of done:

- nDCG/MRR tăng rõ
- latency vẫn chấp nhận được

### Chặng G — NER

Mục tiêu:

- entity search và enrichment hoạt động

Definition of done:

- entity extraction usable
- canonicalization đủ tốt
- entity facets hoặc entity boosts chạy được

---

## 17. KPI gợi ý

### Dữ liệu

- valid clean docs > 95%
- duplicate rate < 3–5%
- parser quality ổn định theo source

### Search

- lexical baseline `Precision@10` đủ ổn
- zero-result rate thấp dần theo tuning
- query có dấu / không dấu có behavior tương đương

### Performance

- search p95 trong ngưỡng mục tiêu
- suggest latency thấp
- indexing throughput đủ cho refresh cadence mong muốn

### Evaluation

- mỗi thay đổi ranking đều có before/after report

---

## 18. Thứ tự triển khai khuyến nghị

### Đợt 1

- source registry
- crawler cơ bản
- raw storage
- parser cho 2 nguồn

### Đợt 2

- cleaner mạnh hơn
- dedup
- lexical index production-like

### Đợt 3

- logs
- evaluation set
- tuning lexical

### Đợt 4

- embeddings
- vector index
- hybrid fusion

### Đợt 5

- reranker
- offline/online comparison

### Đợt 6

- NER
- entity normalization
- entity features trong search

---

## 19. Việc nên tránh

- thêm vector trước khi lexical baseline đủ tốt
- thêm reranker khi chưa có judged queries
- crawl quá nhiều nguồn trước khi parser 1–2 nguồn ổn
- trộn nhiều chiến lược tokenization mà không đo được lợi ích
- không lưu raw HTML
- thay đổi ranking mà không đo metrics

---

## 20. Hướng phát triển trực tiếp từ repo hiện tại

Từ codebase hiện tại, bước hợp lý tiếp theo là:

1. Thêm thư mục crawler mới
2. Thêm raw storage schema
3. Nâng `clean_articles.py` thành pipeline nhiều bước
4. Tách synonym config khỏi hardcoded analyzer body
5. Thêm evaluation dataset format
6. Thêm index bootstrap rõ ràng hơn
7. Thêm docs cho ingestion lifecycle

Nếu đi theo hướng này, repo hiện tại vẫn tận dụng được:

- `SearchService`
- models API
- cleaner cơ bản
- indexer cơ bản
- UI search

---

## 21. Kết luận

Muốn xây một search engine báo tiếng Việt đầy đủ, trọng tâm thật sự không nằm ở “thêm model” trước tiên.

Trọng tâm đúng là:

- crawl đáng tin
- dữ liệu sạch
- dedup tốt
- lexical baseline mạnh
- evaluation rõ ràng

Sau đó mới đến:

- hybrid
- reranker
- NER

Làm đúng thứ tự này thì hệ thống sẽ mở rộng chắc, dễ debug, và mọi bước nâng cấp đều đo được hiệu quả thật.

