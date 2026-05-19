"use client";

import { useEffect, useMemo, useState } from "react";

type FacetItem = {
  value: string;
  count: number;
};

type SearchResult = {
  id: string;
  title: string;
  summary: string;
  url: string;
  category: string;
  author: string;
  published_at: string;
  highlight?: {
    title?: string[];
    summary?: string[];
    content?: string[];
  };
};

type SearchResponse = {
  query: string;
  total: number;
  page: number;
  page_size: number;
  latency_ms: number;
  results: SearchResult[];
  facets: {
    category: FacetItem[];
    author: FacetItem[];
  };
};

type SuggestResponse = {
  suggestions: Array<{
    text: string;
    type: string;
    weight: number;
  }>;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const INITIAL_SEARCH_RESPONSE: SearchResponse = {
  query: "",
  total: 0,
  page: 1,
  page_size: 10,
  latency_ms: 0,
  results: [],
  facets: {
    category: [],
    author: [],
  },
};

const QUICK_QUERIES = [
  "giá vàng",
  "TPHCM",
  "chứng khoán",
  "bóng đá việt nam",
  "thời tiết hà nội",
];

function formatDate(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderHighlight(result: SearchResult) {
  const highlight =
    result.highlight?.title?.[0] ||
    result.highlight?.summary?.[0] ||
    result.highlight?.content?.[0] ||
    escapeHtml(result.summary);

  return { __html: highlight };
}

function buildActiveFilters(
  category: string,
  author: string,
  fromDate: string,
  toDate: string,
) {
  const items: string[] = [];
  if (category) items.push(`Chuyên mục: ${category}`);
  if (author) items.push(`Tác giả: ${author}`);
  if (fromDate) items.push(`Từ ngày: ${fromDate}`);
  if (toDate) items.push(`Đến ngày: ${toDate}`);
  return items;
}

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [category, setCategory] = useState("");
  const [author, setAuthor] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [sort, setSort] = useState<"relevance" | "newest">("relevance");
  const [page, setPage] = useState(1);
  const [results, setResults] = useState<SearchResponse>(INITIAL_SEARCH_RESPONSE);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(results.total / results.page_size));
  }, [results.total, results.page_size]);

  const activeFilters = useMemo(
    () => buildActiveFilters(category, author, fromDate, toDate),
    [category, author, fromDate, toDate],
  );

  useEffect(() => {
    const trimmedQuery = query.trim();
    const controller = new AbortController();
    const timeout = setTimeout(async () => {
      if (trimmedQuery.length < 2) {
        setSuggestions([]);
        return;
      }

      const url = new URL(`${API_BASE_URL}/suggest`);
      url.searchParams.set("q", trimmedQuery);

      try {
        const response = await fetch(url, { signal: controller.signal });
        const data = (await response.json()) as SuggestResponse;
        setSuggestions(data.suggestions.map((item) => item.text));
      } catch {
        setSuggestions([]);
      }
    }, 280);

    return () => {
      controller.abort();
      clearTimeout(timeout);
    };
  }, [query]);

  useEffect(() => {
    void runSearch();
  }, [page, category, author, fromDate, toDate, sort]);

  async function runSearch(nextPage = page, nextQuery = submittedQuery) {
    setLoading(true);
    const url = new URL(`${API_BASE_URL}/search`);
    url.searchParams.set("q", nextQuery);
    url.searchParams.set("page", String(nextPage));
    url.searchParams.set("page_size", "10");
    url.searchParams.set("sort", sort);
    if (category) url.searchParams.set("category", category);
    if (author) url.searchParams.set("author", author);
    if (fromDate) url.searchParams.set("from_date", fromDate);
    if (toDate) url.searchParams.set("to_date", toDate);

    try {
      const response = await fetch(url.toString(), { cache: "no-store" });
      const data = (await response.json()) as SearchResponse;
      setResults(data);
    } finally {
      setLoading(false);
    }
  }

  async function submitSearch(nextQuery: string) {
    const trimmedQuery = nextQuery.trim();
    setSubmittedQuery(trimmedQuery);
    setPage(1);
    await runSearch(1, trimmedQuery);
  }

  function resetFilters() {
    setCategory("");
    setAuthor("");
    setFromDate("");
    setToDate("");
    setSort("relevance");
    setPage(1);
  }

  function trackClick(articleId: string, position: number) {
    const payload = new Blob(
      [
        JSON.stringify({
          article_id: articleId,
          query: submittedQuery,
          position,
        }),
      ],
      { type: "application/json" },
    );
    navigator.sendBeacon(`${API_BASE_URL}/events/click`, payload);
  }

  return (
    <main className="page-shell">
      <section className="hero-panel">
        <div className="hero-copy-wrap">
          <p className="eyebrow">Vietnamese News Search</p>
          <h1>Tìm bài báo nhanh hơn, rõ hơn và ít phải đoán hơn.</h1>
          <p className="hero-copy">
            Tìm theo từ khóa, lọc theo chuyên mục hoặc tác giả, và đọc nhanh phần
            nội dung được highlight ngay trên trang kết quả.
          </p>
        </div>

        <form
          className="search-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submitSearch(query);
          }}
        >
          <label className="search-box">
            <span className="search-label">Từ khóa tìm kiếm</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ví dụ: giá vàng, bóng đá việt nam, TPHCM"
            />
          </label>
          <button type="submit" className="primary-button">
            Tìm kiếm
          </button>
        </form>

        <div className="hero-footer">
          <div className="quick-query-block">
            <span className="subtle-label">Tìm nhanh</span>
            <div className="suggestion-row">
              {QUICK_QUERIES.map((item) => (
                <button
                  type="button"
                  key={item}
                  className="suggestion-pill"
                  onClick={() => {
                    setQuery(item);
                    void submitSearch(item);
                  }}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>

          <div className="hero-stats">
            <div className="mini-stat">
              <span className="subtle-label">Tổng kết quả</span>
              <strong>{results.total}</strong>
            </div>
            <div className="mini-stat">
              <span className="subtle-label">Độ trễ</span>
              <strong>{results.latency_ms} ms</strong>
            </div>
            <div className="mini-stat">
              <span className="subtle-label">Chế độ</span>
              <strong>{submittedQuery ? "Search" : "Mới nhất"}</strong>
            </div>
          </div>
        </div>

        {suggestions.length > 0 ? (
          <div className="autocomplete-panel">
            <span className="subtle-label">Gợi ý</span>
            <div className="suggestion-row">
              {suggestions.slice(0, 6).map((item) => (
                <button
                  type="button"
                  key={item}
                  className="suggestion-pill ghost"
                  onClick={() => {
                    setQuery(item);
                    void submitSearch(item);
                  }}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="content-grid">
        <aside className="filter-panel">
          <div className="filter-header">
            <div>
              <div className="panel-title">Bộ lọc</div>
              <p className="panel-note">Thu hẹp kết quả theo ngữ cảnh bạn cần.</p>
            </div>
            <button type="button" className="text-button" onClick={resetFilters}>
              Xóa lọc
            </button>
          </div>

          <label>
            <span>Chuyên mục</span>
            <select
              value={category}
              onChange={(event) => {
                setCategory(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Tất cả chuyên mục</option>
              {results.facets.category.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.value} ({item.count})
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Tác giả</span>
            <select
              value={author}
              onChange={(event) => {
                setAuthor(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Tất cả tác giả</option>
              {results.facets.author.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.value} ({item.count})
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Sắp xếp</span>
            <select
              value={sort}
              onChange={(event) => {
                setSort(event.target.value as "relevance" | "newest");
                setPage(1);
              }}
            >
              <option value="relevance">Liên quan nhất</option>
              <option value="newest">Mới nhất</option>
            </select>
          </label>

          <div className="date-grid">
            <label>
              <span>Từ ngày</span>
              <input
                type="date"
                value={fromDate}
                onChange={(event) => {
                  setFromDate(event.target.value);
                  setPage(1);
                }}
              />
            </label>
            <label>
              <span>Đến ngày</span>
              <input
                type="date"
                value={toDate}
                onChange={(event) => {
                  setToDate(event.target.value);
                  setPage(1);
                }}
              />
            </label>
          </div>

          {activeFilters.length > 0 ? (
            <div className="active-filter-block">
              <span className="subtle-label">Đang áp dụng</span>
              <div className="active-filter-list">
                {activeFilters.map((item) => (
                  <span key={item} className="active-filter-chip">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </aside>

        <section className="results-panel">
          <div className="results-toolbar">
            <div>
              <div className="panel-title">Kết quả</div>
              <p className="results-meta">
                {submittedQuery
                  ? `Đang hiển thị kết quả cho “${submittedQuery}”`
                  : "Đang hiển thị các bài mới nhất"}
              </p>
            </div>
            <div className="page-badge">
              Trang {results.page}/{totalPages}
            </div>
          </div>

          {loading ? (
            <div className="status-card">
              <h2>Đang truy vấn dữ liệu</h2>
              <p>Hệ thống đang tổng hợp kết quả phù hợp nhất cho bạn.</p>
            </div>
          ) : null}

          {!loading && results.results.length === 0 ? (
            <div className="status-card">
              <h2>Không có kết quả phù hợp.</h2>
              <p>
                Hãy thử rút ngắn câu tìm kiếm, bỏ bớt bộ lọc hoặc đổi giữa có dấu
                và không dấu.
              </p>
            </div>
          ) : null}

          {!loading && results.results.length > 0 ? (
            <div className="summary-strip">
              <span>{results.total} kết quả</span>
              <span>{results.latency_ms} ms</span>
              <span>{sort === "relevance" ? "Ưu tiên liên quan" : "Ưu tiên mới nhất"}</span>
            </div>
          ) : null}

          <div className="result-list">
            {results.results.map((result, index) => (
              <article className="result-card" key={result.id}>
                <div className="result-topline">
                  <span>{result.category}</span>
                  <span>{result.author}</span>
                  <span>{formatDate(result.published_at)}</span>
                </div>

                <a
                  href={result.url}
                  target="_blank"
                  rel="noreferrer"
                  className="result-title"
                  onClick={() => trackClick(result.id, index + 1)}
                >
                  {result.title}
                </a>

                <p className="result-summary">{result.summary}</p>

                <p
                  className="result-snippet"
                  dangerouslySetInnerHTML={renderHighlight(result)}
                />

                <div className="result-footer">
                  <span className="result-rank">#{index + 1}</span>
                  <a
                    href={result.url}
                    target="_blank"
                    rel="noreferrer"
                    className="result-link"
                  >
                    Mở bài viết
                  </a>
                </div>
              </article>
            ))}
          </div>

          <div className="pagination">
            <button
              type="button"
              className="secondary-button"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page <= 1}
            >
              Trang trước
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                setPage((current) => Math.min(totalPages, current + 1))
              }
              disabled={page >= totalPages}
            >
              Trang sau
            </button>
          </div>
        </section>
      </section>
    </main>
  );
}
