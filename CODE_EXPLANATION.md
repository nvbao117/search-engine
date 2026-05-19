# Code Explanation

Tài liệu này giải thích chi tiết cách hệ thống hoạt động, đi từ dữ liệu đầu vào đến OpenSearch, API và UI.

## 1. Tổng quan kiến trúc

Hệ thống được chia thành 4 khối chính:

- `scripts/ingest_index/`
  - Chuẩn hóa dữ liệu JSONL
  - Tạo index OpenSearch
  - Bulk insert bài viết và suggestion
- `apps/api/app/`
  - FastAPI backend
  - Xây query OpenSearch
  - Trả dữ liệu cho UI
- `apps/web/app/`
  - Next.js UI cho search page
  - Gọi `/search`, `/suggest`, `/filters`
- `services/opensearch/`
  - Lưu synonym source để tune dần

Luồng chính:

`raw JSONL -> cleaner -> clean JSONL -> indexer -> OpenSearch -> FastAPI -> Next.js UI`

---

## 2. Dữ liệu và chuẩn hóa

### 2.1 Schema article

Mỗi article có các field chính:

- `id`
- `title`
- `summary`
- `content`
- `author`
- `category`
- `tags`
- `published_at`
- `updated_at`
- `url`
- `status`

Ngoài ra hệ thống sinh thêm:

- `tags_text`
- `title_folded`
- `summary_folded`
- `content_folded`
- `tags_text_folded`

Các field `*_folded` là bản không dấu, dùng để search query không dấu.

### 2.2 `scripts/ingest_index/common.py`

File này là nền tảng của pipeline ingest.

#### `normalize_url()`

Mục đích:

- Chuẩn hóa URL
- Loại bỏ tracking params như:
  - `utm_*`
  - `fbclid`
  - `gclid`
  - `mc_*`
  - `ref`

Ý nghĩa:

- Tránh duplicate giả do cùng một bài nhưng khác query string tracking.

#### `normalize_datetime()`

Mục đích:

- Parse ngày giờ từ input
- Nếu input không có timezone thì mặc định `Asia/Ho_Chi_Minh`
- Convert toàn bộ về cùng timezone

Ý nghĩa:

- Filter theo ngày hoạt động ổn định
- Không bị lệch timezone giữa nguồn dữ liệu

#### `article_signature()`

Mục đích:

- Tạo hash từ `title + content`
- Dùng để phát hiện bài trùng nội dung

#### `transform_record()`

Đây là hàm quan trọng nhất của bước ingest.

Nó làm các việc:

- Chuẩn hóa text Unicode
- Chuẩn hóa URL
- Chuẩn hóa datetime
- Gán giá trị mặc định cho `author`, `category`
- Kiểm tra field bắt buộc
- Tạo `tags_text`
- Tạo tất cả field `*_folded`
- Tạo `dedupe_hash`

Nếu thiếu một trong các field bắt buộc:

- `id`
- `title`
- `content`
- `published_at`
- `url`
- `status`

thì record bị loại.

### 2.3 `scripts/ingest_index/clean_articles.py`

File này đọc dữ liệu raw rồi xuất ra `clean_articles.jsonl`.

Luồng:

1. Đọc tất cả dòng JSONL
2. Gọi `transform_record()` cho từng record
3. Loại record invalid
4. Loại duplicate theo:
   - URL đã normalize
   - `dedupe_hash`
5. Ghi output thành JSONL sạch

Output là dữ liệu chuẩn để index vào OpenSearch.

---

## 3. OpenSearch indexer

### 3.1 `scripts/ingest_index/index_articles.py`

File này chịu trách nhiệm:

- Tạo index article
- Tạo index suggestion
- Bulk insert dữ liệu
- Gắn alias cho article index

### 3.2 `ARTICLE_INDEX_BODY`

Đây là cấu hình index chính cho bài viết.

#### Analyzer

Hệ thống dùng analyzer MVP:

- `standard` tokenizer
- `lowercase`
- `asciifolding`
- `vi_synonyms`

Ý nghĩa:

- Hỗ trợ search không phân biệt hoa thường
- Hỗ trợ query không dấu
- Có synonym thủ công cho một số cụm tiếng Việt quan trọng

#### Mapping

- `title`, `summary`, `content`: `text`
- `title_folded`, `summary_folded`, `content_folded`: `text`
- `author`, `category`, `tags`, `url`, `status`: `keyword`
- `published_at`, `updated_at`: `date`
- `tags_text`, `tags_text_folded`: dùng cho search theo tags

### 3.3 `SUGGESTION_INDEX_BODY`

Index suggestion đơn giản hơn.

Field:

- `text`
- `text_folded`
- `type`
- `weight`

### 3.4 `ensure_index()`

Mục đích:

- Nếu cần `recreate`, xóa index cũ
- Nếu index chưa tồn tại, tạo index mới

### 3.5 `swap_alias()`

Mục đích:

- Alias `news_articles_current` luôn trỏ đến article index đang active

Ý nghĩa:

- Reindex xong có thể swap alias mà không cần đổi code API

### 3.6 `build_article_actions()`

Tạo danh sách bulk action để insert article vào OpenSearch.

Mỗi action gồm:

- `_index`
- `_id`
- `_source`

### 3.7 `build_suggestion_actions()`

Tạo suggestion từ:

- `title`
- `tags`

Logic:

- Title được `weight = 100`
- Tag được `weight = 60`
- Khử duplicate bằng key `casefold()`

### 3.8 `bulk_index()`

Dùng `helpers.streaming_bulk()` để insert theo batch.

Theo dõi:

- `success`
- `failed`

### 3.9 `index_articles()`

Đây là entrypoint chính của indexer.

Luồng:

1. Tạo OpenSearch client
2. Đọc `clean_articles.jsonl`
3. Tạo article index
4. Tạo suggestion index
5. Bulk insert article
6. Bulk insert suggestion
7. Refresh index
8. Swap alias
9. In report kết quả

---

## 4. FastAPI backend

### 4.1 `apps/api/app/config.py`

File này định nghĩa `Settings`.

Mục đích:

- Đọc cấu hình từ env hoặc `.env`
- Giữ mọi giá trị cấu hình ở một chỗ

Các cấu hình chính:

- `opensearch_url`
- `opensearch_username`
- `opensearch_password`
- `article_index_alias`
- `article_index_name`
- `suggestion_index_name`
- `search_log_path`
- `click_log_path`
- `default_page_size`
- `max_page_size`
- `max_page`
- `max_query_length`
- `suggest_limit`

### 4.2 `apps/api/app/opensearch_client.py`

File này tạo OpenSearch client duy nhất cho app.

Đặc điểm:

- Dùng `@lru_cache(maxsize=1)` để cache client
- Nếu có username thì dùng auth
- Nếu không thì để `auth = None`

Ý nghĩa:

- Không tạo connection mới cho mỗi request

### 4.3 `apps/api/app/models.py`

Đây là nơi định nghĩa toàn bộ schema API.

#### `SortOption`

Enum:

- `relevance`
- `newest`

#### `ArticleDocument`

Schema chuẩn của document article.

Validator:

- Chuẩn hóa text
- Chuẩn hóa tags

#### `SearchParams`

Schema cho query params của `/search`.

Field:

- `q`
- `category`
- `author`
- `from_date`
- `to_date`
- `sort`
- `page`
- `page_size`

Validation:

- `q <= 200`
- `page` từ `1..100`
- `page_size` từ `1..50`

Date normalization:

- `from_date` được chuẩn hóa về đầu ngày
- `to_date` được chuẩn hóa về cuối ngày
- timezone mặc định là `Asia/Ho_Chi_Minh`

#### Response models

- `HighlightBlock`
- `SearchResult`
- `SearchResponse`
- `SuggestItem`
- `SuggestResponse`
- `FiltersResponse`
- `ClickEvent`

Ý nghĩa:

- API response có shape ổn định
- UI có thể dựa vào contract rõ ràng

### 4.4 `apps/api/app/logging_utils.py`

Chỉ có một việc:

- ghi log JSONL ra file bằng `append_jsonl()`

Mỗi record log được thêm:

- `timestamp`

và phần payload của event.

---

## 5. SearchService

### 5.1 Vai trò

`apps/api/app/search_service.py` là lớp nghiệp vụ chính.

Nó chịu trách nhiệm:

- build query OpenSearch
- chạy search
- chạy suggest
- map response OpenSearch sang response API
- ghi log search/click

### 5.2 `search()`

Luồng:

1. Bắt đầu đo thời gian
2. Build query bằng `_build_search_query()`
3. Gọi OpenSearch
4. Nếu index chưa tồn tại:
   - trả response rỗng
   - không ném `500`
5. Nếu thành công:
   - đọc `hits`
   - lấy `total`
   - parse `facets`
   - map từng hit thành `SearchResult`
6. Ghi log search
7. Trả `SearchResponse`

Điểm quan trọng:

- Hệ thống đã được vá để thiếu index không làm API chết

### 5.3 `suggest()`

Luồng:

1. Trim query
2. Sinh bản `folded` không dấu
3. Build query `match_phrase_prefix`
4. Tìm trên:
   - `text`
   - `text_folded`
5. Sort theo `weight desc`
6. Nếu suggestion index chưa tồn tại:
   - trả danh sách rỗng
7. Khử duplicate suggestion
8. Trả `SuggestResponse`

### 5.4 `get_article()`

Mục đích:

- Lấy một article theo `id`

Nếu index chưa được tạo hoặc document không tồn tại:

- trả `404`

### 5.5 `get_filters()`

Mục đích:

- Lấy facet cho:
  - `category`
  - `author`

Nếu index chưa tồn tại:

- trả facet rỗng

### 5.6 `log_click()`

Ghi click event ra `clicks.jsonl`.

Payload:

- `article_id`
- `query`
- `position`
- `clicked_at`

### 5.7 `_build_search_query()`

Đây là phần quan trọng nhất của logic search.

#### Filter

Nếu có:

- `category` -> `term` filter
- `author` -> `term` filter
- `from_date`, `to_date` -> `range` filter trên `published_at`

#### Sort

- Mặc định sort theo `published_at desc`
- Nếu query có nội dung và sort = `relevance`
  - sort theo `_score`
  - rồi mới sort theo `published_at desc`

#### Highlight

Trả highlight cho:

- `title`
- `summary`
- `content`

#### Khi `q` rỗng

Không chạy full-text search.

Chỉ lấy bài:

- `status = published`
- áp filter nếu có
- sort theo ngày mới nhất

#### Khi `q` có nội dung

Query gồm 2 nhánh:

1. Nhánh có dấu:
   - `title^5`
   - `tags_text^3`
   - `summary^2`
   - `content^1`
2. Nhánh không dấu:
   - `title_folded^5`
   - `tags_text_folded^3`
   - `summary_folded^2`
   - `content_folded^1`

`minimum_should_match = 1`

Ý nghĩa:

- Người dùng gõ có dấu hoặc không dấu đều có cơ hội match
- Title được ưu tiên mạnh nhất
- Tags quan trọng hơn summary và content

### 5.8 `_to_search_result()`

Map một hit OpenSearch thành object API:

- `id`
- `title`
- `summary`
- `url`
- `category`
- `author`
- `published_at`
- `highlight`

### 5.9 `_parse_facets()`

Biến aggregation buckets của OpenSearch thành JSON gọn hơn cho UI:

- `[{ value, count }]`

### 5.10 `_log_search_event()`

Ghi search log JSONL với:

- `query`
- `filters`
- `total`
- `top_result_ids`
- `latency_ms`
- `zero_result`
- `index_ready`

---

## 6. FastAPI routes

### `apps/api/app/main.py`

File này chỉ làm nhiệm vụ wiring.

#### `get_search_service()`

- Tạo `SearchService` từ OpenSearch client

#### Routes

- `GET /health`
  - kiểm tra API sống
- `GET /search`
  - gọi `service.search()`
- `GET /suggest`
  - gọi `service.suggest()`
- `GET /articles/{id}`
  - gọi `service.get_article()`
- `GET /filters`
  - gọi `service.get_filters()`
- `POST /events/click`
  - gọi `service.log_click()`

Thiết kế ở đây cố ý mỏng:

- route không chứa business logic
- mọi phần phức tạp đẩy vào `SearchService`

---

## 7. Frontend Next.js

### 7.1 `apps/web/app/page.tsx`

Đây là search page chính.

### 7.2 Types

File định nghĩa type cho:

- `FacetItem`
- `SearchResult`
- `SearchResponse`
- `SuggestResponse`

Mục tiêu:

- giữ contract giữa UI và API rõ ràng

### 7.3 State chính

- `query`
  - nội dung user đang gõ
- `submittedQuery`
  - query đã submit thật
- `category`
- `author`
- `fromDate`
- `toDate`
- `sort`
- `page`
- `results`
- `loading`
- `suggestions`

### 7.4 Suggest flow

`useEffect` theo dõi `query`.

Luồng:

1. Tạo debounce 180ms
2. Nếu query rỗng:
   - xóa suggestion
3. Nếu có query:
   - gọi `/suggest?q=...`
4. Nếu lỗi:
   - set suggestion rỗng

Ý nghĩa:

- Autocomplete cập nhật theo lúc người dùng gõ

### 7.5 Search flow

`runSearch()`:

- build URL `/search`
- gắn:
  - `q`
  - `page`
  - `page_size`
  - `sort`
  - `category`
  - `author`
  - `from_date`
  - `to_date`
- fetch API
- cập nhật `results`

### 7.6 Submit

`submitSearch()`:

- lưu query đã submit
- reset page về 1
- chạy search

### 7.7 Click tracking

`trackClick()` dùng `navigator.sendBeacon()`

Mục đích:

- gửi click log nhẹ
- không chặn việc mở link article

### 7.8 Highlight render

`renderHighlight()` ưu tiên:

1. `title` highlight
2. `summary` highlight
3. `content` highlight
4. fallback về `summary`

### 7.9 Render UI

Trang gồm:

- hero panel
- search box
- suggestion pills
- filter panel
- results panel
- pagination

Khi không có kết quả:

- hiển thị empty state

### 7.10 Vấn đề encoding hiện tại

Một số chuỗi tiếng Việt trong file đang bị lỗi encoding kiểu:

- `TÃ¬m bÃ i bÃ¡o...`

Đây là lỗi encoding file, không phải lỗi logic.

Nó cần được sửa bằng cách lưu file UTF-8 chuẩn.

---

## 8. Logging

### Search log

File:

- `logs/search.jsonl`

Nội dung:

- query
- filters
- total
- top_result_ids
- latency
- zero_result
- index_ready

### Click log

File:

- `logs/clicks.jsonl`

Nội dung:

- article_id
- query
- position
- clicked_at

Ý nghĩa:

- đủ để làm phân tích MVP:
  - top queries
  - zero-result queries
  - CTR cơ bản

---

## 9. Docker và runtime

### `docker-compose.yml`

Hiện stack có 3 service:

- `opensearch`
- `api`
- `web`

API được cấu hình để:

- chạy `uvicorn`
- mount code source `./apps/api/app:/app/app`
- dùng `--reload`

Ý nghĩa:

- sửa Python code trên host thì container API reload lại
- tránh tình trạng code mới nhưng container vẫn chạy image cũ

---

## 10. Vì sao trước đó search không ra kết quả

Nguyên nhân gốc:

- `data/clean/clean_articles.jsonl` chỉ nằm trên disk
- OpenSearch chưa được tạo:
  - `news_articles_v1`
  - `news_suggestions_v1`
- alias `news_articles_current` chưa được gắn

Nên:

- `/search` trả rỗng hoặc từng bị `500`
- `/suggest` trả rỗng hoặc từng bị `500`

Sau khi vá:

- thiếu index không còn làm API chết
- nhưng vẫn phải chạy indexer để có dữ liệu thật

---

## 11. Điểm tốt trong thiết kế hiện tại

- Tách rõ ingest, API, UI
- Có schema Pydantic rõ ràng
- Có support search có dấu / không dấu
- Có alias để reindex an toàn
- Có logging cơ bản cho MVP
- Có graceful fallback khi index chưa tồn tại

---

## 12. Hạn chế hiện tại

- Chưa tự bootstrap index sau `docker compose up`
- Suggest bị gọi khá nhiều khi người dùng gõ
- Chưa có spell correction thực sự
- Synonym hiện được hardcode trong index body
- File synonym riêng chưa được nạp động
- UI còn lỗi encoding tiếng Việt

---

## 13. Thứ tự chạy hệ thống

1. Chạy Docker:

```bash
rtk docker compose up -d --build
```

2. Cài dependency backend nếu chạy indexer từ conda env:

```bash
rtk conda run -n searchengine pip install -e apps/api
```

3. Tạo index và nạp dữ liệu:

```bash
rtk conda run -n searchengine python -m scripts.ingest_index.index_articles --input data/clean/clean_articles.jsonl --recreate --batch-size 500
```

4. Test:

```bash
rtk curl "http://localhost:8000/search?q=gia%20vang"
rtk curl "http://localhost:8000/suggest?q=gia"
```

---

## 14. File nên đọc đầu tiên nếu muốn hiểu code nhanh

Theo thứ tự:

1. `apps/api/app/search_service.py`
2. `apps/api/app/models.py`
3. `scripts/ingest_index/common.py`
4. `scripts/ingest_index/index_articles.py`
5. `apps/api/app/main.py`
6. `apps/web/app/page.tsx`

Nếu bạn cần đào sâu logic search, file quan trọng nhất là:

- `apps/api/app/search_service.py`

Nếu bạn cần đào sâu ingest/index:

- `scripts/ingest_index/common.py`
- `scripts/ingest_index/index_articles.py`

