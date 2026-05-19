from pathlib import Path

from scripts.ingest_index.clean_articles import clean_articles


def test_clean_articles_filters_invalid_and_duplicates(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "clean.jsonl"
    input_path.write_text(
        "\n".join(
            [
                '{"id":"1","title":"Giá vàng hôm nay","summary":"A","content":"Nội dung","author":"A","category":"Kinh tế","tags":["giá vàng"],"published_at":"2026-05-19T08:00:00+07:00","updated_at":"2026-05-19T09:00:00+07:00","url":"https://example.com/post?utm_source=abc","status":"published"}',
                '{"id":"2","title":"Giá vàng hôm nay","summary":"B","content":"Nội dung","author":"A","category":"Kinh tế","tags":["giá vàng"],"published_at":"2026-05-19T08:00:00+07:00","updated_at":"2026-05-19T09:00:00+07:00","url":"https://example.com/post","status":"published"}',
                '{"id":"3","title":"","summary":"B","content":"Thiếu title","author":"A","category":"Kinh tế","tags":["giá vàng"],"published_at":"2026-05-19T08:00:00+07:00","updated_at":"2026-05-19T09:00:00+07:00","url":"https://example.com/post-2","status":"published"}',
            ]
        ),
        encoding="utf-8",
    )

    summary = clean_articles(input_path, output_path)

    assert summary == {"input": 3, "cleaned": 1, "invalid": 1, "duplicates": 1}
    contents = output_path.read_text(encoding="utf-8")
    assert "utm_source" not in contents
    assert "https://example.com/post" in contents

