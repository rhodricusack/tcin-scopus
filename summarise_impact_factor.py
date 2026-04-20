import argparse
import pickle
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml


IMPACT_BAND_ORDER = ["0", "0-2", "2-4", "4-8", "8-16", "16-32", "32+", "unmatched"]
DISPLAY_IMPACT_BAND_ORDER = ["0-2", "2-4", "4-8", "8-16", "16-32", "32+"]


def normalise_journal_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    cleaned = re.sub(r"\s+", " ", name.strip().lower())
    return cleaned


def normalise_issn(value: str) -> str:
    if not isinstance(value, str):
        return ""
    digits = re.sub(r"[^0-9xX]", "", value)
    return digits.upper()


def detect_column(columns: list[str], candidates: list[str]) -> str | None:
    lowered = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def load_author_lookup(yaml_path: Path) -> dict[str, str]:
    with yaml_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    lookup: dict[str, str] = {}
    for group in data.get("groups", []):
        for entry in group.get("entries", []):
            lookup[str(entry["scopus_id"]).strip()] = str(entry["name"])
    return lookup


def load_publications(pickle_path: Path, author_lookup: dict[str, str]) -> pd.DataFrame:
    with pickle_path.open("rb") as handle:
        allpubs = pickle.load(handle)

    rows = []
    for scopus_id, papers in allpubs.items():
        author = author_lookup.get(str(scopus_id).strip(), "Unknown")
        for paper in papers:
            if "prism:url" not in paper:
                continue
            rows.append(
                {
                    "author_scopus_id": str(scopus_id).strip(),
                    "tcin_author": author,
                    "title": paper.get("dc:title"),
                    "url": paper.get("prism:url"),
                    "cover_date": paper.get("prism:coverDate"),
                    "citations": pd.to_numeric(paper.get("citedby-count"), errors="coerce"),
                    "journal": paper.get("prism:publicationName"),
                    "issn": paper.get("prism:issn"),
                    "eissn": paper.get("prism:eIssn"),
                }
            )

    publications = pd.DataFrame(rows)
    if publications.empty:
        return publications

    publications = publications.drop_duplicates(subset=["url"])
    publications["citations"] = publications["citations"].fillna(0).astype(int)
    publications["journal_norm"] = publications["journal"].map(normalise_journal_name)
    publications["issn_norm"] = publications["issn"].map(normalise_issn)
    publications["eissn_norm"] = publications["eissn"].map(normalise_issn)
    return publications


def load_impact_factors(impact_csv_path: Path) -> pd.DataFrame:
    impact = pd.read_csv(impact_csv_path)
    if impact.empty:
        raise ValueError("Impact-factor CSV is empty.")

    impact_col = detect_column(list(impact.columns), ["impact_factor", "if", "impact factor"])
    if impact_col is None:
        raise ValueError(
            "Impact-factor CSV must contain one of these columns: impact_factor, if, impact factor"
        )

    journal_col = detect_column(
        list(impact.columns),
        ["journal", "journal_name", "source_title", "title", "publication_name"],
    )
    issn_col = detect_column(list(impact.columns), ["issn", "print_issn"])
    eissn_col = detect_column(list(impact.columns), ["eissn", "e_issn", "electronic_issn"])

    if journal_col is None and issn_col is None and eissn_col is None:
        raise ValueError(
            "Impact-factor CSV needs at least one identifier column: journal/journal_name/source_title or issn/eissn"
        )

    impact = impact.rename(columns={impact_col: "impact_factor"})
    impact["impact_factor"] = pd.to_numeric(impact["impact_factor"], errors="coerce")
    impact = impact.dropna(subset=["impact_factor"]).copy()

    impact["journal_norm"] = (
        impact[journal_col].map(normalise_journal_name) if journal_col else ""
    )
    impact["issn_norm"] = impact[issn_col].map(normalise_issn) if issn_col else ""
    impact["eissn_norm"] = impact[eissn_col].map(normalise_issn) if eissn_col else ""

    return impact[["impact_factor", "journal_norm", "issn_norm", "eissn_norm"]]


def merge_impact_factors(publications: pd.DataFrame, impact: pd.DataFrame) -> pd.DataFrame:
    if publications.empty:
        return publications

    by_eissn = (
        impact[impact["eissn_norm"].astype(str) != ""]
        .sort_values("impact_factor", ascending=False)
        .drop_duplicates(subset=["eissn_norm"])
        [["eissn_norm", "impact_factor"]]
    )
    by_issn = (
        impact[impact["issn_norm"].astype(str) != ""]
        .sort_values("impact_factor", ascending=False)
        .drop_duplicates(subset=["issn_norm"])
        [["issn_norm", "impact_factor"]]
    )
    by_journal = (
        impact[impact["journal_norm"].astype(str) != ""]
        .sort_values("impact_factor", ascending=False)
        .drop_duplicates(subset=["journal_norm"])
        [["journal_norm", "impact_factor"]]
    )

    merged = publications.merge(by_eissn, how="left", on="eissn_norm")
    merged = merged.rename(columns={"impact_factor": "impact_from_eissn"})
    merged = merged.merge(by_issn, how="left", on="issn_norm")
    merged = merged.rename(columns={"impact_factor": "impact_from_issn"})
    merged = merged.merge(by_journal, how="left", on="journal_norm")
    merged = merged.rename(columns={"impact_factor": "impact_from_journal"})

    merged["impact_factor"] = (
        merged["impact_from_eissn"]
        .combine_first(merged["impact_from_issn"])
        .combine_first(merged["impact_from_journal"])
    )

    merged["impact_match_source"] = "unmatched"
    merged.loc[merged["impact_from_eissn"].notna(), "impact_match_source"] = "eissn"
    merged.loc[
        merged["impact_from_eissn"].isna() & merged["impact_from_issn"].notna(),
        "impact_match_source",
    ] = "issn"
    merged.loc[
        merged["impact_from_eissn"].isna()
        & merged["impact_from_issn"].isna()
        & merged["impact_from_journal"].notna(),
        "impact_match_source",
    ] = "journal"

    return merged


def add_if_band(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        df["impact_band"] = pd.Series(dtype="string")
        return df

    df["impact_band"] = "unmatched"

    has_if = df["impact_factor"].notna()
    df.loc[has_if & (df["impact_factor"] <= 0), "impact_band"] = "0"
    df.loc[has_if & (df["impact_factor"] > 0) & (df["impact_factor"] < 2), "impact_band"] = "0-2"
    df.loc[has_if & (df["impact_factor"] >= 2) & (df["impact_factor"] < 4), "impact_band"] = "2-4"
    df.loc[has_if & (df["impact_factor"] >= 4) & (df["impact_factor"] < 8), "impact_band"] = "4-8"
    df.loc[has_if & (df["impact_factor"] >= 8) & (df["impact_factor"] < 16), "impact_band"] = "8-16"
    df.loc[has_if & (df["impact_factor"] >= 16) & (df["impact_factor"] < 32), "impact_band"] = "16-32"
    df.loc[has_if & (df["impact_factor"] >= 32), "impact_band"] = "32+"

    return df


def write_outputs(merged: pd.DataFrame, output_prefix: str) -> None:
    publications_out = Path(f"{output_prefix}-publications.csv")
    author_summary_out = Path(f"{output_prefix}-by-author.csv")
    overall_summary_out = Path(f"{output_prefix}-overall.csv")
    by_year_bands_out = Path(f"{output_prefix}-impact-bands-by-year.csv")
    by_year_bands_plot_out = Path(f"{output_prefix}-impact-bands-by-year.png")

    merged = add_if_band(merged)
    merged.to_csv(publications_out, index=False)

    by_author = (
        merged.groupby("tcin_author", dropna=False)
        .agg(
            publications=("url", "count"),
            matched_if=("impact_factor", lambda x: int(x.notna().sum())),
            avg_if=("impact_factor", "mean"),
            median_if=("impact_factor", "median"),
            total_citations=("citations", "sum"),
            weighted_avg_if=(
                "impact_factor",
                lambda x: (x.fillna(0) * merged.loc[x.index, "citations"]).sum()
                / max(merged.loc[x.index, "citations"].sum(), 1),
            ),
        )
        .reset_index()
        .sort_values(["matched_if", "avg_if"], ascending=[False, False])
    )
    by_author.to_csv(author_summary_out, index=False)

    overall = pd.DataFrame(
        {
            "metric": [
                "publications_total",
                "publications_with_if",
                "publications_without_if",
                "match_rate",
                "mean_if",
                "median_if",
                "weighted_mean_if_by_citations",
            ],
            "value": [
                len(merged),
                int(merged["impact_factor"].notna().sum()),
                int(merged["impact_factor"].isna().sum()),
                float(merged["impact_factor"].notna().mean()),
                float(merged["impact_factor"].mean()) if len(merged) else 0,
                float(merged["impact_factor"].median()) if len(merged) else 0,
                float((merged["impact_factor"].fillna(0) * merged["citations"]).sum())
                / max(float(merged["citations"].sum()), 1.0),
            ],
        }
    )

    bands = (
        merged.groupby("impact_band", dropna=False)
        .agg(publications=("url", "count"), total_citations=("citations", "sum"))
        .reset_index()
    )
    bands["impact_band"] = pd.Categorical(
        bands["impact_band"], categories=IMPACT_BAND_ORDER, ordered=True
    )
    bands = bands.sort_values("impact_band").reset_index(drop=True)

    merged["pub_year"] = pd.to_datetime(merged["cover_date"], errors="coerce").dt.year

    def sample_journals(series: pd.Series, n: int = 3) -> str:
        journals = sorted(
            {
                str(value).strip()
                for value in series.dropna()
                if str(value).strip() and str(value).strip().lower() != "nan"
            }
        )
        if not journals:
            return ""
        if len(journals) <= n:
            return " | ".join(journals)
        sampled = pd.Series(journals).sample(n=n, random_state=42, replace=False).tolist()
        return " | ".join(sampled)

    by_year_bands = (
        merged.groupby(["pub_year", "impact_band"], dropna=False)
        .agg(
            publications=("url", "count"),
            total_citations=("citations", "sum"),
            avg_if=("impact_factor", "mean"),
            journal_examples=("journal", sample_journals),
        )
        .reset_index()
    )
    by_year_bands = by_year_bands[by_year_bands["impact_band"].isin(DISPLAY_IMPACT_BAND_ORDER)].copy()
    by_year_bands["impact_band"] = pd.Categorical(
        by_year_bands["impact_band"], categories=DISPLAY_IMPACT_BAND_ORDER, ordered=True
    )
    by_year_bands = by_year_bands.sort_values(["pub_year", "impact_band"], na_position="last")

    plot_df = (
        by_year_bands.pivot(index="pub_year", columns="impact_band", values="publications")
        .reindex(columns=DISPLAY_IMPACT_BAND_ORDER)
        .fillna(0)
    )
    if not plot_df.empty:
        fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
        plot_df.plot(kind="bar", stacked=True, ax=ax)
        ax.set_title("Publications by Year and Impact Band")
        ax.set_xlabel("Publication Year")
        ax.set_ylabel("Number of Publications")
        ax.legend(title="Impact Band", bbox_to_anchor=(1.02, 1), loc="upper left")
        plt.tight_layout()
        fig.savefig(by_year_bands_plot_out)
        plt.close(fig)

    overall.to_csv(overall_summary_out, index=False)
    bands.to_csv(Path(f"{output_prefix}-impact-bands.csv"), index=False)
    by_year_bands.to_csv(by_year_bands_out, index=False)

    print(f"Wrote: {publications_out}")
    print(f"Wrote: {author_summary_out}")
    print(f"Wrote: {overall_summary_out}")
    print(f"Wrote: {output_prefix}-impact-bands.csv")
    print(f"Wrote: {by_year_bands_out}")
    print(f"Wrote: {by_year_bands_plot_out}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarise TCIN publications by journal impact factor."
    )
    parser.add_argument(
        "--pickle",
        default="allpubs-2026.pickle",
        help="Path to publications pickle generated by tcinscan.py",
    )
    parser.add_argument(
        "--authors-yaml",
        default="edie_scopus_ids.yaml",
        help="Path to YAML with Scopus author IDs",
    )
    parser.add_argument(
        "--impact-csv",
        default="impact_factors.csv",
        help="CSV mapping journals/ISSN to impact factors",
    )
    parser.add_argument(
        "--output-prefix",
        default="impact-summary-2026",
        help="Prefix for output CSV files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    author_lookup = load_author_lookup(Path(args.authors_yaml))
    publications = load_publications(Path(args.pickle), author_lookup)

    if publications.empty:
        raise ValueError("No publications found in pickle.")

    impact = load_impact_factors(Path(args.impact_csv))
    merged = merge_impact_factors(publications, impact)
    write_outputs(merged, args.output_prefix)


if __name__ == "__main__":
    main()
