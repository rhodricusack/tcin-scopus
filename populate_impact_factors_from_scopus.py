import argparse
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests


def normalise_issn(value: str) -> str:
    if not isinstance(value, str):
        return ""
    digits = re.sub(r"[^0-9Xx]", "", value).upper()
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    return digits


def read_api_key(config_path: Path) -> str:
    with config_path.open(encoding="utf-8") as handle:
        return json.load(handle)["apikey"]


def fetch_citescore(apikey: str, issn: str, session: requests.Session) -> tuple[float | None, str | None, str | None]:
    url = f"https://api.elsevier.com/content/serial/title/issn/{issn}?view=ENHANCED"
    response = session.get(
        url,
        headers={"X-ELS-APIKey": apikey, "Accept": "application/json"},
        timeout=30,
    )
    if response.status_code != 200:
        return None, None, f"HTTP {response.status_code}"

    data = response.json()
    entries = data.get("serial-metadata-response", {}).get("entry", [])
    if not entries:
        return None, None, "No entry"

    entry = entries[0]
    cs = entry.get("citeScoreYearInfoList", {})
    score = cs.get("citeScoreCurrentMetric")
    year = cs.get("citeScoreCurrentMetricYear")
    if score in (None, ""):
        return None, None, "No CiteScore"

    try:
        return float(score), str(year) if year is not None else None, None
    except ValueError:
        return None, None, f"Invalid CiteScore: {score}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate impact_factors_template.csv impact_factor column using Scopus CiteScore by ISSN/eISSN."
    )
    parser.add_argument("--csv", default="impact_factors_template.csv")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between API calls in seconds")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing non-empty impact_factor values")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    config_path = Path(args.config)
    cache_path = csv_path.with_suffix(".scopus_cache.json")

    df = pd.read_csv(csv_path)
    for col in ["journal", "issn", "eissn", "impact_factor"]:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    if "impact_source" not in df.columns:
        df["impact_source"] = ""
    if "impact_year" not in df.columns:
        df["impact_year"] = ""

    df["impact_source"] = df["impact_source"].astype("object")
    df["impact_year"] = df["impact_year"].astype("object")

    apikey = read_api_key(config_path)

    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        cache = {}

    session = requests.Session()

    updated = 0
    skipped_existing = 0
    unresolved = 0

    for idx, row in df.iterrows():
        existing_raw = row.get("impact_factor", "")
        if pd.isna(existing_raw):
            existing = ""
        else:
            existing = str(existing_raw).strip()
        if existing and not args.overwrite:
            skipped_existing += 1
            continue

        issn_candidates = []
        eissn = normalise_issn(str(row.get("eissn", "")))
        issn = normalise_issn(str(row.get("issn", "")))
        if eissn:
            issn_candidates.append(eissn)
        if issn and issn not in issn_candidates:
            issn_candidates.append(issn)

        score = None
        year = None
        err = None

        for key in issn_candidates:
            if key in cache:
                cached = cache[key]
                score = cached.get("score")
                year = cached.get("year")
                err = cached.get("error")
            else:
                score, year, err = fetch_citescore(apikey, key, session)
                cache[key] = {"score": score, "year": year, "error": err}
                time.sleep(max(args.delay, 0.0))

            if score is not None:
                break

        if score is not None:
            df.at[idx, "impact_factor"] = score
            df.at[idx, "impact_source"] = "Scopus CiteScore"
            if year:
                df.at[idx, "impact_year"] = year
            updated += 1
        else:
            unresolved += 1

        if (idx + 1) % 50 == 0:
            print(f"Processed {idx + 1}/{len(df)} rows; updated={updated}, unresolved={unresolved}")

    df.to_csv(csv_path, index=False)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Done")
    print(f"Updated rows: {updated}")
    print(f"Skipped existing: {skipped_existing}")
    print(f"Unresolved rows: {unresolved}")
    print(f"Cache file: {cache_path}")


if __name__ == "__main__":
    main()
