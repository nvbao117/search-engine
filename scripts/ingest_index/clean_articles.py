import argparse
from pathlib import Path

from .common import read_jsonl, transform_record, write_jsonl


def clean_articles(input_path: Path, output_path: Path) -> dict[str, int]:
    raw_records = read_jsonl(input_path)
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    cleaned: list[dict] = []
    invalid = 0
    duplicates = 0

    for record in raw_records:
        transformed = transform_record(record)
        if transformed is None:
            invalid += 1
            continue
        dedupe_hash = transformed.pop("dedupe_hash")
        if transformed["url"] in seen_urls or dedupe_hash in seen_hashes:
            duplicates += 1
            continue
        seen_urls.add(transformed["url"])
        seen_hashes.add(dedupe_hash)
        cleaned.append(transformed)

    write_jsonl(output_path, cleaned)
    return {
        "input": len(raw_records),
        "cleaned": len(cleaned),
        "invalid": invalid,
        "duplicates": duplicates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    summary = clean_articles(Path(args.input), Path(args.output))
    print(summary)


if __name__ == "__main__":
    main()

