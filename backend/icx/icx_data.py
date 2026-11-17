from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
import re
from typing import Literal

import numpy as np
import pandas as pd

Perspective = Literal["provider", "customer"]
AnalysisLevel = Literal[
    "groups",
    "service_clusters",
    "division_only",
    "division_territory",
    "territory_only",
]
BlueQueueSortMode = Literal["band_default", "ascending", "descending"]

APP_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = APP_ROOT
ROOT_DIR = APP_ROOT
MASTER_CSV = APP_ROOT / "data" / "demo.csv"
SERVICE_CATALOGUE_CSV = APP_ROOT / "data" / "service_catalogue.csv"
XFN_DIVISION_CSV = APP_ROOT / "data" / "division_reference.csv"
TERRITORY_ONLY_CSV = APP_ROOT / "data" / "territory_reference.csv"
TERRITORY_SCATTER_METRICS_CSV = APP_ROOT / "data" / "territory_metrics.csv"
CLUSTER_MAPPING_CSV = APP_ROOT / "backend" / "icx" / "service_cluster_mapping.csv"
CLUSTER_MAPPING_TEMPLATE_CSV = APP_ROOT / "backend" / "icx" / "service_cluster_mapping_template.csv"

ALL_GROUPS_LABEL = "All Groups"
INSUFFICIENT_CLUSTER = "N/A - Insufficient Information"
UNMAPPED_SERVICE_CLUSTER = "Unmapped / No Service Cluster"
EXCLUDED_PROVIDER_GROUPS: set[str] = set()
PROVIDER_SCORE_EXCLUDED_CSV_LINES = ()
PROVIDER_SCORE_EXCLUDED_RATING_IDS = set()
PROVIDER_SCORE_EXCLUDED_GROUP = "__no_excluded_provider__"
SMALL_N_THRESHOLD = 30
NPS_THRESHOLD = 70
CRITICALITY_THRESHOLD = 3.5
BLUE_SCORE_BANDS = {
    "Busted": (-100, -1),
    "Leveled": (0, 29),
    "Uplifted": (30, 69),
    "Exceptional": (70, 100),
}
BLUE_QUEUE_ORDER = ["Exceptional", "Uplifted", "Leveled", "Busted"]

BLUE_ORDER = ["Busted", "Leveled", "Uplifted", "Exceptional"]

MASTER_COLUMN_ALIASES = {"Service": "Service Cluster", "Group RATED": "Group Rated"}

                                                                            
                                                                          
                                                                        
INVALID_PROVIDER_SERVICE_CLUSTERS = set()

PROVIDER_GROUP_COL = "Group Rated"
CUSTOMER_GROUP_COL = "Group"

GROUP_ABBREVIATIONS = {}

GROUP_CODE_ABBREVIATIONS = {}
TERRITORY_GROUP_LABEL_ORDER = []
TERRITORY_LABEL_ORDER = []
TERRITORY_GROUP_LABELS = {}
XFN_PROVIDER = "Cross-Functional Teams"
XFN_PROVIDER_ALIASES = {XFN_PROVIDER, "Cross-Functional Teams*"}
OP_PROVIDER = "Executive Services"
HR_PROVIDER = "People Services"
HR_REMAPPED_DIVISION_COL = "Provider Division Override"
HR_TERRITORY_DIVISION_SUFFIX = r"\s+serving\s+Territory\s+\d+\s*$"
TERRITORY_DIVISION_PATTERN = r"\bserving\s+Territory\b"
HR_DIVISION_COMPENSATION = "Rewards"
HR_DIVISION_BUSINESS_PARTNERSHIP = "People Operations"
HR_DIVISION_PEOPLE_EXPERIENCE = "Employee Services"
HR_DIVISION_STRATEGY = "People Planning"
HR_DIVISION_TALENT = "Learning Services"
HR_DIVISION_WHOLE_GROUP = "Served by Whole Group"
HR_TERRITORY_ROLLUP = "People Services Territories"
XFN_SELECTED_SHEET_ROWS = []
XFN_FILTERED_DIVISION_REMAP = {}
XFN_UNSPECIFIED_VALUES = {"", "na", "n/a", "n/a - new hire", "none", "nan"}
DIVISION_LABEL_REMAP = {}

FREQUENCY_ORDER = [
    "Annual",
    "Quarterly",
    "Monthly",
    "Weekly",
    "Daily",
    "Ad hoc / Upon request",
    "Other / Missing",
]
FREQUENCY_REPORT_ORDER = [
    "Daily",
    "Weekly",
    "Monthly",
    "Quarterly",
    "Annual",
    "Ad hoc / Upon request",
]
FREQUENCY_RANK = {name: idx + 1 for idx, name in enumerate(FREQUENCY_ORDER)}
FREQUENCY_REPORT_RANK = {name: idx + 1 for idx, name in enumerate(FREQUENCY_REPORT_ORDER)}
FREQUENCY_CODE = {
    "Annual": "AN",
    "Quarterly": "Q",
    "Monthly": "M",
    "Weekly": "W",
    "Daily": "D",
    "Ad hoc / Upon request": "AH",
    "Other / Missing": "NA",
}

CRITICALITY_REPORT_ORDER = [
    "Very Critical",
    "Critical",
    "Somewhat Critical",
    "Not Critical",
]
CRITICALITY_REPORT_RANK = {
    name: idx + 1 for idx, name in enumerate(CRITICALITY_REPORT_ORDER)
}


@dataclass(frozen=True)
class GuardrailReport:
    rows_ok: bool
    blue_counts_ok: bool
    nps_ok: bool
    service_cluster_ok: bool
    rows: int
    blue_counts: dict[str, int]
    overall_nps: float
    service_cluster_non_null: int
    service_cluster_missing: int
    service_cluster_unique: int

    @property
    def ok(self) -> bool:
        return (
            self.rows_ok
            and self.blue_counts_ok
            and self.nps_ok
            and self.service_cluster_ok
        )


def blue_from_rating(value: object) -> str:
    text = str(value).upper()
    if text.startswith("BUSTED"):
        return "Busted"
    if text.startswith("LEVELED"):
        return "Leveled"
    if text.startswith("UPLIFTED"):
        return "Uplifted"
    if text.startswith("EXCEPTIONAL"):
        return "Exceptional"
    return "Unknown"


def normalize_frequency(value: object) -> str:
    text = " ".join(str(value).strip().split())
    lowered = text.lower()
    if lowered in {"annual", "annually"}:
        return "Annual"
    if lowered == "quarterly":
        return "Quarterly"
    if lowered == "monthly":
        return "Monthly"
    if lowered == "weekly":
        return "Weekly"
    if lowered == "daily":
        return "Daily"
    if "ad hoc" in lowered or "upon request" in lowered:
        return "Ad hoc / Upon request"
    return "Other / Missing"


def normalize_criticality(value: object) -> str:
    text = " ".join(str(value).strip().split()).lower()
    if text == "very critical":
        return "Very Critical"
    if text == "critical":
        return "Critical"
    if text == "somewhat critical":
        return "Somewhat Critical"
    if text == "not critical":
        return "Not Critical"
    return "Other / Missing"


def safe_abbreviation(label: object) -> str:
    text = str(label)
    if text in GROUP_ABBREVIATIONS:
        return GROUP_ABBREVIATIONS[text]
    words = [part for part in text.replace("&", " ").replace("/", " ").split() if part]
    if not words:
        return "NA"
    if len(words) == 1:
        return words[0][:8].upper()
    return "".join(word[0] for word in words[:5]).upper()


def clean_xfn_division_label(value: object) -> str:
    text = " ".join(str(value).strip().split())
    lowered = text.lower()
    if lowered in XFN_UNSPECIFIED_VALUES or not text:
        return "Unspecified"
    if lowered in XFN_FILTERED_DIVISION_REMAP:
        return XFN_FILTERED_DIVISION_REMAP[lowered]
    if text == text.lower():
        return text.title()
    return text


def group_code_abbreviation(label: object) -> str:
    text = str(label)
    if text in GROUP_CODE_ABBREVIATIONS:
        return GROUP_CODE_ABBREVIATIONS[text]
    return safe_abbreviation(text).replace(" ", "")


def normalize_territory_grouping(value: object) -> str:
    if pd.isna(value):
        return ""
    text = " ".join(str(value).strip().split())
    if not text or text.lower() in {"nan", "none", "null", "<na>"}:
        return ""
    return TERRITORY_GROUP_LABELS.get(text, text)


def normalize_territory(value: object) -> str:
    text = " ".join(str(value).strip().split())
    if not text or text.lower() in {"nan", "none", "null"}:
        return "Not provided"
    return text


def normalize_hr_provider_division(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def frequency_code(label: object) -> str:
    return FREQUENCY_CODE.get(str(label), "NA")


def nps_from_counts(busted: int, uplifted: int, exceptional: int, total: int) -> float:
    if total == 0:
        return np.nan
    return (uplifted + exceptional - busted) / total * 100


def normalize_service_cluster(value: object) -> str:
    if pd.isna(value):
        return UNMAPPED_SERVICE_CLUSTER
    text = " ".join(str(value).strip().split())
    if not text or text.lower() in {"nan", "none", "null"}:
        return UNMAPPED_SERVICE_CLUSTER
    return text


def is_low_info_service_cluster(value: object) -> bool:
    text = normalize_service_cluster(value)
    lowered = text.lower()
    return (
        text == UNMAPPED_SERVICE_CLUSTER
        or lowered.startswith("n/a")
        or "insufficient" in lowered
        or "unmapped" in lowered
    )


def _service_cluster_metadata(df: pd.DataFrame) -> pd.DataFrame:
    counts = (
        df.groupby(["provider_group", "service_cluster"], dropna=False)
        .size()
        .reset_index(name="cluster_ratings")
    )
    counts["provider_abbr"] = counts["provider_group"].map(group_code_abbreviation)
    counts["service_cluster_is_low_info"] = counts["service_cluster"].map(
        is_low_info_service_cluster
    )
    counts["_cluster_sort"] = counts["service_cluster"].astype(str).str.lower()
    counts = counts.sort_values(
        ["provider_group", "cluster_ratings", "_cluster_sort"],
        ascending=[True, False, True],
    )
    counts["service_cluster_rank"] = pd.NA
    valid_mask = ~counts["service_cluster_is_low_info"]
    valid_counts = counts[valid_mask].copy()
    valid_counts["service_cluster_rank"] = (
        valid_counts.groupby("provider_group").cumcount() + 1
    )
    counts.loc[valid_counts.index, "service_cluster_rank"] = valid_counts[
        "service_cluster_rank"
    ]
    counts["service_cluster_rank"] = counts["service_cluster_rank"].astype("Int64")
    counts["service_cluster_code"] = np.where(
        counts["service_cluster_is_low_info"],
        counts["provider_abbr"] + " N/A",
        counts["provider_abbr"] + " " + counts["service_cluster_rank"].astype(str),
    )
    counts["service_cluster_display"] = (
        counts["service_cluster_code"] + " (" + counts["service_cluster"].astype(str) + ")"
    )
    counts["service_cluster_key"] = (
        counts["provider_group"].astype(str) + " | " + counts["service_cluster"].astype(str)
    )
    return counts.drop(columns=["_cluster_sort"])


def _add_service_cluster_identity(df: pd.DataFrame) -> pd.DataFrame:
    if "Service Cluster" not in df.columns:
        df["Service Cluster"] = pd.NA
    df["service_cluster_raw"] = df["Service Cluster"].map(normalize_service_cluster)
    invalid_pairs = pd.MultiIndex.from_tuples(
        INVALID_PROVIDER_SERVICE_CLUSTERS,
        names=["provider_group", "service_cluster_raw"],
    )
    row_pairs = pd.MultiIndex.from_frame(
        df[["provider_group", "service_cluster_raw"]].astype(str)
    )
    invalid_mask = row_pairs.isin(invalid_pairs)
    df["service_cluster_is_invalid_for_provider"] = invalid_mask
    df["service_cluster"] = df["service_cluster_raw"].where(
        ~df["service_cluster_is_invalid_for_provider"],
        UNMAPPED_SERVICE_CLUSTER,
    )
    metadata = _service_cluster_metadata(df)
    return df.merge(
        metadata[
            [
                "provider_group",
                "service_cluster",
                "provider_abbr",
                "service_cluster_rank",
                "service_cluster_code",
                "service_cluster_display",
                "service_cluster_key",
                "service_cluster_is_low_info",
            ]
        ],
        on=["provider_group", "service_cluster"],
        how="left",
        validate="many_to_one",
    )


def canonical_master_column(column: str) -> str:
    canonical = "Timestamp|Email Address|Employee ID|Role|Band|Tenure|Tenure Category|Age Range|Work Location|Group|Division|Department|Section|Last Name|First Name|Middle Name|Group Rated|Service Received|Division Rated|Department(s) Rated|Team(s)/Member(s) Rated|Frequency|Frequency Category|Criticality|Criticality Score|Rating|Feedback|Sentiment|Main Bucket|Key|Service Cluster|Functional Cluster|Territory|Territory Grouping|Cleaned Feedback|Intra or Inter|Response Number".split("|")
    lookup = {name.casefold(): name for name in canonical}
    lookup.update({key.casefold(): value for key, value in MASTER_COLUMN_ALIASES.items()})
    text = str(column).strip().lstrip("\ufeff")
    return lookup.get(text.casefold(), text)


def load_icx_master(path: Path | str = MASTER_CSV) -> pd.DataFrame:
    header = pd.read_csv(path, nrows=0)
    identifiers = {column: "string" for column in header.columns if canonical_master_column(column) in {"Employee ID", "Email Address"}}
    df = pd.read_csv(path, dtype=identifiers)
    df.columns = [canonical_master_column(column) for column in df.columns]
    if df.columns.duplicated().any():
        raise ValueError("Master CSV contains duplicate or ambiguous column headings.")
    required_columns = {
        PROVIDER_GROUP_COL,
        CUSTOMER_GROUP_COL,
        "Rating",
        "Frequency Category",
        "Criticality Score",
    }
    missing_columns = sorted(required_columns.difference(df.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Master CSV is missing required column(s): {missing}")
    df = df.copy()
    df["rating_id"] = np.arange(1, len(df) + 1)
    df["exclude_from_provider_group_scores"] = (
        df[PROVIDER_GROUP_COL]
        .astype("string")
        .str.strip()
        .eq(PROVIDER_SCORE_EXCLUDED_GROUP)
    )
    for column in [PROVIDER_GROUP_COL, CUSTOMER_GROUP_COL]:
        df[column] = df[column].astype("string").str.strip().replace("", pd.NA)
    df["provider_group"] = df[PROVIDER_GROUP_COL].astype("string")
    df["customer_group"] = df[CUSTOMER_GROUP_COL].astype("string")
    raw_provider_division = df.get(
        "Division Rated",
        pd.Series(pd.NA, index=df.index, dtype="string"),
    ).astype("string").str.strip()
    raw_provider_division = raw_provider_division.mask(raw_provider_division.eq(""))
    df["provider_division_raw"] = raw_provider_division
    df["provider_division"] = raw_provider_division
    df["provider_division_is_hr_remapped"] = False
    df["provider_division_is_hr_territory"] = False
    hr_rows = df["provider_group"].eq(HR_PROVIDER)
    if HR_REMAPPED_DIVISION_COL in df.columns:
        hr_division = df[HR_REMAPPED_DIVISION_COL].astype("string").str.strip()
        hr_division = hr_division.mask(hr_division.eq(""))
    else:
        hr_division = raw_provider_division
    hr_territory = hr_division.str.contains(
        HR_TERRITORY_DIVISION_SUFFIX,
        case=False,
        regex=True,
        na=False,
    )
    df.loc[hr_rows, "provider_division"] = hr_division.loc[hr_rows].map(
        normalize_hr_provider_division
    )
    df["provider_division_is_hr_remapped"] = (
        hr_rows & df["provider_division"].astype("string").str.strip().ne("")
    )
    df["provider_division_is_hr_territory"] = hr_rows & hr_territory
    df["provider_division"] = df["provider_division"].map(
        lambda value: (
            DIVISION_LABEL_REMAP.get(str(value).strip().lower(), value)
            if pd.notna(value)
            else value
        )
    )
    df["blue_rating"] = df["Rating"].map(blue_from_rating)
    df["frequency_normalized"] = df["Frequency Category"].map(normalize_frequency)
    df["frequency_rank"] = df["frequency_normalized"].map(FREQUENCY_RANK)
    df["criticality_score"] = pd.to_numeric(df["Criticality Score"], errors="coerce")

    for rating in BLUE_ORDER:
        df[f"is_{rating.lower()}"] = df["blue_rating"].eq(rating)
    df["is_uplifted_exceptional"] = df["is_uplifted"] | df["is_exceptional"]
    df["is_intra"] = df["provider_group"].eq(df["customer_group"])
    df = _add_service_cluster_identity(df)
    return df


def load_service_catalogue(path: Path | str = SERVICE_CATALOGUE_CSV) -> pd.DataFrame:
    """Optional reference loading; the application derives charts from active rows."""
    return pd.read_csv(path)


def load_territory_only(path: Path | str = TERRITORY_ONLY_CSV) -> pd.DataFrame:
    rows = pd.read_csv(path).copy()
    rows["rating_id"] = np.arange(1, len(rows) + 1)
    rows["provider_group"] = rows[PROVIDER_GROUP_COL].astype("string")
    rows["customer_group"] = rows[CUSTOMER_GROUP_COL].astype("string")
    rows["blue_rating"] = rows["Rating"].map(blue_from_rating)

    frequency_source = rows.get("Frequency Category", pd.Series(pd.NA, index=rows.index))
    frequency_source = frequency_source.where(frequency_source.notna(), rows.get("Frequency"))
    rows["frequency_normalized"] = frequency_source.map(normalize_frequency)
    rows["frequency_rank"] = rows["frequency_normalized"].map(FREQUENCY_RANK)
    rows["criticality_score"] = pd.to_numeric(rows["Criticality Score"], errors="coerce")
    rows["territory"] = rows["Territory"].map(normalize_territory)
    rows["territory_grouping_raw"] = rows["Territory Grouping"].astype("string")
    rows["territory_group"] = rows["territory_grouping_raw"].map(normalize_territory_grouping)

    for rating in BLUE_ORDER:
        rows[f"is_{rating.lower()}"] = rows["blue_rating"].eq(rating)
    rows["is_uplifted_exceptional"] = rows["is_uplifted"] | rows["is_exceptional"]
    rows["is_intra"] = rows["provider_group"].eq(rows["customer_group"])
    return rows


def run_guardrails(df: pd.DataFrame) -> GuardrailReport:
    """Validate the active dataset structurally without fixed survey baselines."""
    counts = {rating: int(df["blue_rating"].eq(rating).sum()) for rating in BLUE_ORDER}
    score = round(nps_from_counts(counts["Busted"], counts["Uplifted"], counts["Exceptional"], len(df)), 2)
    clusters = df.get("Service Cluster", pd.Series(pd.NA, index=df.index))
    criticality = df["criticality_score"].dropna()
    return GuardrailReport(
        rows_ok=len(df) > 0,
        blue_counts_ok=sum(counts.values()) == len(df),
        nps_ok=bool(np.isfinite(score) and -100 <= score <= 100),
        service_cluster_ok=bool(criticality.isin([1, 2, 3, 4]).all()),
        rows=len(df), blue_counts=counts, overall_nps=score,
        service_cluster_non_null=int(clusters.notna().sum()),
        service_cluster_missing=int(clusters.isna().sum()),
        service_cluster_unique=int(clusters.nunique(dropna=True)),
    )


def classify_icx_score_band(nps: float) -> str | None:
    if pd.isna(nps):
        return None
    score = float(nps)
    if score < 0:
        return "Busted"
    if score < 30:
        return "Leveled"
    if score < NPS_THRESHOLD:
        return "Uplifted"
    if score <= 100:
        return "Exceptional"
    return "Exceptional"


def attention_score_blue(
    nps: pd.Series,
    ratings: pd.Series,
    avg_criticality: pd.Series,
) -> pd.Series:
    criticality_weight = (
        avg_criticality.fillna(CRITICALITY_THRESHOLD).clip(lower=0) / 4
    )
    return (
        (100 - nps).clip(lower=0)
        * np.log1p(ratings.clip(lower=1))
        * criticality_weight
    )


def attention_score_frequency(
    nps: pd.Series,
    ratings: pd.Series,
    avg_criticality: pd.Series,
) -> pd.Series:
    criticality_weight = (
        avg_criticality.fillna(CRITICALITY_THRESHOLD).clip(lower=0) / 4
    )
    return (
        (NPS_THRESHOLD - nps).clip(lower=0)
        * np.sqrt(ratings.clip(lower=1))
        * criticality_weight
    )


def split_blue_attention_queues(
    summary: pd.DataFrame,
    sort_mode: BlueQueueSortMode = "band_default",
) -> dict[str, pd.DataFrame]:
    if sort_mode not in {"band_default", "ascending", "descending"}:
        raise ValueError(f"Unknown BLUE queue sort mode: {sort_mode}")

    visible = summary.dropna(subset=["avg_criticality"]).copy()
    queues = {band: summary.iloc[0:0].copy() for band in BLUE_QUEUE_ORDER}
    if visible.empty:
        return queues

    visible["attention_score"] = attention_score_blue(
        visible["nps"],
        visible["ratings"],
        visible["avg_criticality"],
    ).round(0)
    visible["icx_score_band"] = visible["nps"].map(classify_icx_score_band)
    for band in BLUE_QUEUE_ORDER:
        queue = visible[visible["icx_score_band"].eq(band)].copy()
        if sort_mode == "ascending":
            attention_ascending = True
        elif sort_mode == "descending":
            attention_ascending = False
        else:
            attention_ascending = band in {"Exceptional", "Uplifted"}
        queue = queue.sort_values(
            ["attention_score", "ratings", "nps"],
            ascending=[attention_ascending, False, True],
        )
        queues[band] = queue.reset_index(drop=True)
    return queues


def group_options(
    df: pd.DataFrame,
    perspective: Perspective | None = None,
) -> list[str]:
    if perspective == "provider":
        groups = set(provider_score_rows(df)["provider_group"].dropna().astype(str))
    elif perspective == "customer":
        groups = set(analysis_rows(df)["customer_group"].dropna().astype(str))
    else:
        groups = set(provider_score_rows(df)["provider_group"].dropna().astype(str))
        groups.update(analysis_rows(df)["customer_group"].dropna().astype(str))
    return [ALL_GROUPS_LABEL] + sorted(groups)


def analysis_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows eligible for dashboard analysis after reporting exclusions."""
    if not EXCLUDED_PROVIDER_GROUPS:
        return df.copy()
    return df[~df["provider_group"].astype(str).isin(EXCLUDED_PROVIDER_GROUPS)].copy()


def provider_score_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows eligible for provider-side group and service-cluster scoring."""
    rows = analysis_rows(df)
    if "exclude_from_provider_group_scores" not in rows.columns:
        return rows
    exclusion = rows["exclude_from_provider_group_scores"].fillna(False).astype(bool)
    return rows.loc[~exclusion].copy()


def _score_rows(df: pd.DataFrame, perspective: Perspective) -> pd.DataFrame:
    if perspective == "provider":
        return provider_score_rows(df)
    return analysis_rows(df)


def _mode_group_col(perspective: Perspective) -> str:
    if perspective == "provider":
        return "provider_group"
    if perspective == "customer":
        return "customer_group"
    raise ValueError(f"Unknown perspective: {perspective}")


def _opposite_group_col(perspective: Perspective) -> str:
    return "customer_group" if perspective == "provider" else "provider_group"


def _context_rows(
    df: pd.DataFrame,
    perspective: Perspective,
    selected_group: str = ALL_GROUPS_LABEL,
) -> pd.DataFrame:
    df = _score_rows(df, perspective)
    if selected_group == ALL_GROUPS_LABEL:
        return df
    mode_col = _mode_group_col(perspective)
    return df[df[mode_col].astype(str).eq(selected_group)].copy()


def _dominant_frequency(values: pd.Series) -> str:
    clean = values.dropna()
    if clean.empty:
        return "Other / Missing"
    counts = clean.value_counts()
    ranked_counts = sorted(
        counts.items(),
        key=lambda item: (-int(item[1]), FREQUENCY_RANK.get(str(item[0]), 999)),
    )
    return str(ranked_counts[0][0])


def _summarize(df: pd.DataFrame, by: str, label_col_name: str) -> pd.DataFrame:
    if df.empty:
        return _empty_summary(label_col_name)

    grouped = df.groupby(by, dropna=False)
    summary = grouped.agg(
        ratings=("rating_id", "size"),
        busted=("is_busted", "sum"),
        leveled=("is_leveled", "sum"),
        uplifted=("is_uplifted", "sum"),
        exceptional=("is_exceptional", "sum"),
        avg_criticality=("criticality_score", "mean"),
        dominant_frequency=("frequency_normalized", _dominant_frequency),
    ).reset_index(names=label_col_name)

    summary["nps"] = summary.apply(
        lambda row: nps_from_counts(
            int(row["busted"]),
            int(row["uplifted"]),
            int(row["exceptional"]),
            int(row["ratings"]),
        ),
        axis=1,
    )
    summary["nps"] = summary["nps"].round(2)
    summary["avg_criticality"] = summary["avg_criticality"].round(2)
    summary["label_full"] = summary[label_col_name].astype(str)
    summary["label_short"] = summary["label_full"].map(safe_abbreviation)
    summary["frequency_rank"] = summary["dominant_frequency"].map(FREQUENCY_RANK)
    summary["small_n"] = summary["ratings"] < SMALL_N_THRESHOLD
    summary["attention_score"] = attention_score_blue(
        summary["nps"],
        summary["ratings"],
        summary["avg_criticality"],
    ).round(0)
    return summary.sort_values(["nps", "ratings"], ascending=[True, False]).reset_index(drop=True)


def _summarize_frequency_slices(
    df: pd.DataFrame,
    by: str,
    label_col_name: str,
) -> pd.DataFrame:
    if df.empty:
        return _empty_frequency_summary(label_col_name)

    usable = df[df["frequency_normalized"].isin(FREQUENCY_ORDER)].copy()
    if usable.empty:
        return _empty_frequency_summary(label_col_name)

    grouped = usable.groupby([by, "frequency_normalized"], dropna=False)
    summary = grouped.agg(
        ratings=("rating_id", "size"),
        busted=("is_busted", "sum"),
        leveled=("is_leveled", "sum"),
        uplifted=("is_uplifted", "sum"),
        exceptional=("is_exceptional", "sum"),
        avg_criticality=("criticality_score", "mean"),
    ).reset_index(names=[label_col_name, "frequency_normalized"])

    summary["nps"] = summary.apply(
        lambda row: nps_from_counts(
            int(row["busted"]),
            int(row["uplifted"]),
            int(row["exceptional"]),
            int(row["ratings"]),
        ),
        axis=1,
    )
    summary["nps"] = summary["nps"].round(2)
    summary["avg_criticality"] = summary["avg_criticality"].round(2)
    summary["label_full"] = summary[label_col_name].astype(str)
    summary["slice_full"] = (
        summary["label_full"] + " | " + summary["frequency_normalized"].astype(str)
    )
    summary["label_short"] = summary["label_full"].map(safe_abbreviation)
    summary["dominant_frequency"] = summary["frequency_normalized"]
    summary["frequency_rank"] = summary["frequency_normalized"].map(FREQUENCY_RANK)
    summary["small_n"] = summary["ratings"] < SMALL_N_THRESHOLD
    summary["stable_n"] = summary["ratings"] >= SMALL_N_THRESHOLD
    criticality_weight = (
        summary["avg_criticality"].fillna(CRITICALITY_THRESHOLD).clip(lower=0) / 4
    )
    summary["attention_score"] = (
        (NPS_THRESHOLD - summary["nps"]).clip(lower=0)
        * np.sqrt(summary["ratings"].clip(lower=1))
        * criticality_weight
    ).round(2)
    summary["risk_score"] = summary["attention_score"]
    summary["action_bucket"] = np.select(
        [
            ~summary["stable_n"],
            summary["nps"].lt(NPS_THRESHOLD),
            summary["nps"].ge(85),
        ],
        ["Investigate", "Below BLUE target", "Exceptional"],
        default="Watch",
    )
    return summary.sort_values(
        ["frequency_rank", "nps", "ratings"], ascending=[True, True, False]
    ).reset_index(drop=True)


def _empty_summary(label_col_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            label_col_name,
            "provider_group",
            "service_cluster",
            "provider_abbr",
            "service_cluster_rank",
            "service_cluster_code",
            "service_cluster_display",
            "service_cluster_is_low_info",
            "ratings",
            "busted",
            "leveled",
            "uplifted",
            "exceptional",
            "avg_criticality",
            "dominant_frequency",
            "nps",
            "label_full",
            "label_short",
            "frequency_rank",
            "small_n",
            "stable_n",
            "attention_score",
            "risk_score",
            "action_bucket",
        ]
    )


def _empty_frequency_summary(label_col_name: str) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            label_col_name,
            "provider_group",
            "service_cluster",
            "provider_abbr",
            "service_cluster_rank",
            "service_cluster_code",
            "service_cluster_display",
            "service_cluster_is_low_info",
            "frequency_normalized",
            "ratings",
            "busted",
            "leveled",
            "uplifted",
            "exceptional",
            "avg_criticality",
            "nps",
            "label_full",
            "slice_full",
            "label_short",
            "dominant_frequency",
            "frequency_rank",
            "small_n",
            "attention_score",
        ]
    )


def _empty_frequency_criticality_summary() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "criticality_normalized",
            "frequency_normalized",
            "responses",
            "busted",
            "leveled",
            "uplifted",
            "exceptional",
            "avg_criticality",
            "nps",
            "small_n",
            "criticality_rank",
            "frequency_report_rank",
        ]
    )


def _empty_frequency_gap_summary() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "label_full",
            "label_short",
            "frequency_a",
            "frequency_b",
            "nps_a",
            "nps_b",
            "responses_a",
            "responses_b",
            "avg_criticality_a",
            "avg_criticality_b",
            "gap_points",
        ]
    )


def _empty_all_frequency_gap_summary() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "label_full",
            "label_short",
            "frequency_a",
            "frequency_b",
            "nps_a",
            "nps_b",
            "responses_a",
            "responses_b",
            "avg_criticality_a",
            "avg_criticality_b",
            "combined_responses",
            "lower_nps",
            "gap_points",
        ]
    )


def summarize_groups(df: pd.DataFrame, perspective: Perspective) -> pd.DataFrame:
    df = _score_rows(df, perspective)
    group_col = _mode_group_col(perspective)
    return _summarize(df, group_col, "group")


def _clean_text_label(value: object) -> str:
    if pd.isna(value):
        return ""
    text = " ".join(str(value).strip().split())
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _division_col(perspective: Perspective) -> str:
    if perspective == "provider":
        return "provider_division"
    if perspective == "customer":
        return "Division"
    raise ValueError(f"Unknown perspective: {perspective}")


def _valid_division_label(value: object) -> bool:
    text = _clean_text_label(value)
    if not text:
        return False
    lowered = text.lower()
    invalid_fragments = [
        "serving territory",
        "receive service from the entire group",
        "don't know which division",
        "do not know which division",
    ]
    return not any(fragment in lowered for fragment in invalid_fragments)


def _clean_division_label(value: object) -> str:
    text = _clean_text_label(value)
    if not text:
        return ""
    return DIVISION_LABEL_REMAP.get(text.lower(), text)


def _division_universe(df: pd.DataFrame) -> set[str]:
    if "Division" not in df.columns:
        return set()
    values = df["Division"].map(_clean_division_label)
    values = values[values.map(_valid_division_label)]
    return set(values.dropna().astype(str))


def _provider_division_universe_mask(
    rows: pd.DataFrame,
    division_universe: set[str],
) -> pd.Series:
    allowed = rows["division_label"].isin(division_universe)
    if "provider_division_is_hr_remapped" in rows.columns:
        allowed |= rows["provider_division_is_hr_remapped"].fillna(False).astype(bool)
    return allowed


def _division_rows(
    df: pd.DataFrame,
    perspective: Perspective,
    selected_group: str = ALL_GROUPS_LABEL,
) -> pd.DataFrame:
    return _context_rows(df, perspective, selected_group)


def _with_full_length_labels(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    summary = summary.copy()
    summary["label_short"] = summary["label_full"]
    return summary


def summarize_divisions(
    df: pd.DataFrame,
    perspective: Perspective,
    selected_group: str = ALL_GROUPS_LABEL,
) -> pd.DataFrame:
    rows = _division_rows(df, perspective, selected_group)
    division_col = _division_col(perspective)
    rows = rows.assign(division_label=rows[division_col].map(_clean_division_label))
    rows = rows[rows["division_label"].map(_valid_division_label)].copy()

                                                                          
                                                                           
                                                                      
                                                                            
    if selected_group == ALL_GROUPS_LABEL:
        group_col = _mode_group_col(perspective)
        rows["division_group"] = rows[group_col].map(_clean_text_label)
        rows = rows[rows["division_group"].ne("")].copy()
        rows["division_key"] = (
            rows["division_group"] + " | " + rows["division_label"]
        )
        summary = _summarize(rows, "division_key", "division_key")
        metadata = rows[
            ["division_key", "division_group", "division_label"]
        ].drop_duplicates("division_key")
        summary = summary.merge(metadata, on="division_key", how="left")
        summary["division"] = summary["division_label"]
        summary["group_name"] = summary["division_group"]
        summary["label_full"] = (
            summary["division_group"] + " | " + summary["division_label"]
        )
        summary["label_short"] = (
            summary["division_group"].map(safe_abbreviation)
            + " | "
            + summary["division_label"]
        )
        return summary.drop(
            columns=["division_key", "division_group", "division_label"]
        )

    summary = _summarize(rows, "division_label", "division")
    return _with_full_length_labels(summary)


def summarize_division_territory(
    df: pd.DataFrame,
    perspective: Perspective,
    selected_group: str = ALL_GROUPS_LABEL,
) -> pd.DataFrame:
    division_summary = summarize_divisions(df, perspective, selected_group)
    if not division_summary.empty:
        division_summary = division_summary.copy()
        division_summary["point_type"] = "Division"
        division_summary["is_territory_point"] = False

    if perspective == "provider" and selected_group == HR_PROVIDER:
        territory_summary = _summarize_hr_territory_rollup(df)
    else:
        territory_summary = summarize_territory_groupings(
            df,
            perspective,
            selected_group,
        )
    if not territory_summary.empty:
        territory_summary = territory_summary.copy()
        territory_summary["point_type"] = "Territory"
        territory_summary["is_territory_point"] = True

    combined = pd.concat([division_summary, territory_summary], ignore_index=True)
    if combined.empty:
        return combined
    return combined.sort_values(
        ["point_type", "nps", "ratings"], ascending=[True, True, False]
    ).reset_index(drop=True)


def _territory_rows(
    df: pd.DataFrame,
    perspective: Perspective = "provider",
    selected_group: str = ALL_GROUPS_LABEL,
) -> pd.DataFrame:
    rows = _context_rows(df, perspective, selected_group)
    division_source = rows.get(
        "provider_division_raw",
        rows.get(
            "Division Rated",
            pd.Series(pd.NA, index=rows.index, dtype="string"),
        ),
    )
    rows = rows.assign(
        territory_division_label=division_source.map(_clean_text_label),
        territory_group_owner=rows["provider_group"].map(_clean_text_label),
    )
    territory_mask = rows["territory_division_label"].str.contains(
        TERRITORY_DIVISION_PATTERN,
        case=False,
        regex=True,
        na=False,
    )
    rows = rows[
        territory_mask
        & rows["territory_division_label"].ne("")
        & rows["territory_group_owner"].ne("")
    ].copy()
    return rows


def _summarize_hr_territory_rollup(df: pd.DataFrame) -> pd.DataFrame:
    rows = _territory_rows(df, "provider", HR_PROVIDER)
    if rows.empty:
        return _empty_summary("territory")
    rows = rows.assign(territory_rollup=HR_TERRITORY_ROLLUP)
    summary = _summarize(rows, "territory_rollup", "territory")
    summary["group_name"] = HR_PROVIDER
    summary["territory_count"] = int(rows["territory_division_label"].nunique())
    summary["label_full"] = HR_TERRITORY_ROLLUP
    summary["label_short"] = HR_TERRITORY_ROLLUP
    return summary


def summarize_territory_groupings(
    df: pd.DataFrame,
    perspective: Perspective = "provider",
    selected_group: str = ALL_GROUPS_LABEL,
) -> pd.DataFrame:
    rows = _territory_rows(df, perspective, selected_group)
    if rows.empty:
        return _empty_summary("territory")

    if selected_group == ALL_GROUPS_LABEL:
                                                                       
                                                                        
                                                                       
                                                                     
        summary = _summarize(
            rows,
            "territory_group_owner",
            "territory",
        )
        territory_counts = (
            rows.groupby("territory_group_owner", dropna=False)[
                "territory_division_label"
            ]
            .nunique()
            .rename("territory_count")
            .reset_index()
        )
        summary = summary.merge(
            territory_counts,
            left_on="territory",
            right_on="territory_group_owner",
            how="left",
            validate="one_to_one",
        )
        summary["group_name"] = summary["territory_group_owner"]
        summary["label_full"] = summary["territory_group_owner"]
        summary["label_short"] = summary["territory_group_owner"].map(
            safe_abbreviation
        )
        summary = summary.drop(columns=["territory_group_owner"])
    elif perspective == "customer":
        rows["territory_key"] = (
            rows["territory_group_owner"]
            + " | "
            + rows["territory_division_label"]
        )
        summary = _summarize(rows, "territory_key", "territory")
        metadata = rows[
            ["territory_key", "territory_group_owner", "territory_division_label"]
        ].drop_duplicates("territory_key")
        summary = summary.merge(
            metadata,
            left_on="territory",
            right_on="territory_key",
            how="left",
            validate="one_to_one",
        )
        summary["group_name"] = summary["territory_group_owner"]
        summary["territory_count"] = 1
        summary["label_full"] = summary["territory"]
        summary["label_short"] = (
            summary["territory_group_owner"].map(safe_abbreviation)
            + " | "
            + summary["territory_division_label"]
        )
        summary = summary.drop(
            columns=[
                "territory_key",
                "territory_group_owner",
                "territory_division_label",
            ]
        )
    else:
        summary = _summarize(rows, "territory_division_label", "territory")
        summary["group_name"] = selected_group
        summary["territory_count"] = 1
        summary["label_full"] = summary["territory"].astype(str)
        summary["label_short"] = summary["label_full"]
    summary["point_type"] = "Territory"
    summary["is_territory_point"] = True
    summary["is_low_volume_point"] = summary["ratings"].lt(5)
    return summary.sort_values(
        ["label_full", "ratings"], ascending=[True, False]
    ).reset_index(drop=True)


def summarize_requested_territory_scatter(df: pd.DataFrame, metrics_path: Path | str = TERRITORY_SCATTER_METRICS_CSV, use_reference_scores: bool = False) -> pd.DataFrame:
    """Calculate territory scores from the current CSV; no fixed reference values."""
    rows = provider_score_rows(df).copy()
    grouping = rows.get("Territory Grouping", pd.Series(pd.NA, index=rows.index)).astype("string").str.strip()
    rows = rows.assign(territory_label=grouping)
    rows = rows[rows["territory_label"].notna() & rows["territory_label"].ne("")]
    if rows.empty:
        return _empty_summary("territory")
    summary = _summarize(rows, "territory_label", "territory")
    summary["label_full"] = summary["territory"]
    summary["label_short"] = summary["territory"]
    summary["score_source"] = "Active CSV"
    summary["blue_counts_reconciled"] = True
    summary["point_type"] = "Territory"
    summary["is_territory_point"] = True
    return summary


def summarize_group_frequency_slices(
    df: pd.DataFrame,
    perspective: Perspective,
    selected_group: str = ALL_GROUPS_LABEL,
) -> pd.DataFrame:
    if selected_group == ALL_GROUPS_LABEL:
        df = _score_rows(df, perspective)
        return _summarize_frequency_slices(df, _mode_group_col(perspective), "group")

    df = provider_score_rows(df)
    mode_col = _mode_group_col(perspective)
    opposite_col = _opposite_group_col(perspective)
    filtered = df[df[mode_col].astype(str).eq(selected_group)]
    return _summarize_frequency_slices(filtered, opposite_col, "group")


def summarize_frequency_criticality(
    df: pd.DataFrame,
    perspective: Perspective,
    selected_group: str = ALL_GROUPS_LABEL,
) -> pd.DataFrame:
    filtered = _context_rows(df, perspective, selected_group)
    usable = filtered[filtered["frequency_normalized"].isin(FREQUENCY_REPORT_ORDER)].copy()
    if usable.empty:
        return _empty_frequency_criticality_summary()

    usable["criticality_normalized"] = usable["Criticality"].map(normalize_criticality)
    usable = usable[
        usable["criticality_normalized"].isin(CRITICALITY_REPORT_ORDER)
    ].copy()
    if usable.empty:
        return _empty_frequency_criticality_summary()

    grouped = usable.groupby(
        ["criticality_normalized", "frequency_normalized"],
        dropna=False,
    )
    summary = grouped.agg(
        responses=("rating_id", "size"),
        busted=("is_busted", "sum"),
        leveled=("is_leveled", "sum"),
        uplifted=("is_uplifted", "sum"),
        exceptional=("is_exceptional", "sum"),
        avg_criticality=("criticality_score", "mean"),
    ).reset_index()
    summary["nps"] = summary.apply(
        lambda row: nps_from_counts(
            int(row["busted"]),
            int(row["uplifted"]),
            int(row["exceptional"]),
            int(row["responses"]),
        ),
        axis=1,
    ).round(2)
    summary["avg_criticality"] = summary["avg_criticality"].round(2)
    summary["small_n"] = summary["responses"] < SMALL_N_THRESHOLD
    summary["criticality_rank"] = summary["criticality_normalized"].map(
        CRITICALITY_REPORT_RANK
    )
    summary["frequency_report_rank"] = summary["frequency_normalized"].map(
        FREQUENCY_REPORT_RANK
    )
    return summary.sort_values(
        ["criticality_rank", "frequency_report_rank"]
    ).reset_index(drop=True)


def summarize_frequency_attention(frequency_summary: pd.DataFrame) -> pd.DataFrame:
    if frequency_summary.empty:
        return _empty_frequency_summary("group")

    summary = frequency_summary[
        frequency_summary["frequency_normalized"].isin(FREQUENCY_REPORT_ORDER)
    ].copy()
    if summary.empty:
        return summary

    summary["attention_score"] = attention_score_frequency(
        summary["nps"],
        summary["ratings"],
        summary["avg_criticality"],
    ).round(0)
    summary["sample_label"] = np.where(
        summary["ratings"].lt(SMALL_N_THRESHOLD),
        "Small",
        "Stable",
    )
    summary["icx_score_band"] = summary["nps"].map(classify_icx_score_band)
    summary["frequency_report_rank"] = summary["frequency_normalized"].map(
        FREQUENCY_REPORT_RANK
    )
    return summary.sort_values(
        ["attention_score", "ratings", "nps"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def summarize_frequency_gaps(
    frequency_summary: pd.DataFrame,
    frequency_a: str,
    frequency_b: str,
    min_responses_per_side: int | None = 10,
) -> pd.DataFrame:
    if frequency_summary.empty or frequency_a == frequency_b:
        return _empty_frequency_gap_summary()

    usable = frequency_summary[
        frequency_summary["frequency_normalized"].isin([frequency_a, frequency_b])
    ].copy()
    if usable.empty:
        return _empty_frequency_gap_summary()

    key_cols = ["label_full", "label_short"]
    value_cols = ["nps", "ratings", "avg_criticality"]
    indexed = usable[key_cols + ["frequency_normalized"] + value_cols].set_index(
        key_cols + ["frequency_normalized"]
    )
    wide = indexed.unstack("frequency_normalized")
    if frequency_a not in wide["nps"].columns or frequency_b not in wide["nps"].columns:
        return _empty_frequency_gap_summary()

    result = pd.DataFrame(
        {
            "label_full": wide.index.get_level_values("label_full"),
            "label_short": wide.index.get_level_values("label_short"),
            "frequency_a": frequency_a,
            "frequency_b": frequency_b,
            "nps_a": wide["nps"][frequency_a].to_numpy(),
            "nps_b": wide["nps"][frequency_b].to_numpy(),
            "responses_a": wide["ratings"][frequency_a].to_numpy(),
            "responses_b": wide["ratings"][frequency_b].to_numpy(),
            "avg_criticality_a": wide["avg_criticality"][frequency_a].to_numpy(),
            "avg_criticality_b": wide["avg_criticality"][frequency_b].to_numpy(),
        }
    )
    result = result.dropna(subset=["nps_a", "nps_b", "responses_a", "responses_b"])
    if min_responses_per_side is not None:
        result = result[
            result["responses_a"].ge(min_responses_per_side)
            & result["responses_b"].ge(min_responses_per_side)
        ].copy()
    if result.empty:
        return _empty_frequency_gap_summary()

    result["gap_points"] = (result["nps_a"] - result["nps_b"]).abs().round(2)
    result["responses_a"] = result["responses_a"].astype(int)
    result["responses_b"] = result["responses_b"].astype(int)
    return result.sort_values(
        ["gap_points", "responses_a", "responses_b"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def summarize_all_frequency_gaps(
    frequency_summary: pd.DataFrame,
    min_responses_per_side: int | None = 10,
) -> pd.DataFrame:
    if frequency_summary.empty:
        return _empty_all_frequency_gap_summary()

    usable = frequency_summary[
        frequency_summary["frequency_normalized"].isin(FREQUENCY_REPORT_ORDER)
    ].copy()
    if usable.empty:
        return _empty_all_frequency_gap_summary()

    records: list[dict[str, object]] = []
    for (label_full, label_short), group_df in usable.groupby(
        ["label_full", "label_short"],
        dropna=False,
    ):
        clean_group = group_df.dropna(subset=["frequency_normalized", "nps", "ratings"])
        if clean_group.empty:
            continue
        rows_by_frequency = {
            str(row.frequency_normalized): row
            for row in clean_group.itertuples(index=False)
        }
        for frequency_a, frequency_b in combinations(FREQUENCY_REPORT_ORDER, 2):
            if frequency_a not in rows_by_frequency or frequency_b not in rows_by_frequency:
                continue
            row_a = rows_by_frequency[frequency_a]
            row_b = rows_by_frequency[frequency_b]
            responses_a = int(row_a.ratings)
            responses_b = int(row_b.ratings)
            if min_responses_per_side is not None and (
                responses_a < min_responses_per_side or responses_b < min_responses_per_side
            ):
                continue
            nps_a = float(row_a.nps)
            nps_b = float(row_b.nps)
            records.append(
                {
                    "label_full": str(label_full),
                    "label_short": str(label_short),
                    "frequency_a": frequency_a,
                    "frequency_b": frequency_b,
                    "nps_a": nps_a,
                    "nps_b": nps_b,
                    "responses_a": responses_a,
                    "responses_b": responses_b,
                    "avg_criticality_a": float(row_a.avg_criticality),
                    "avg_criticality_b": float(row_b.avg_criticality),
                    "combined_responses": responses_a + responses_b,
                    "lower_nps": min(nps_a, nps_b),
                    "gap_points": round(abs(nps_a - nps_b), 2),
                }
            )

    if not records:
        return _empty_all_frequency_gap_summary()

    result = pd.DataFrame.from_records(records)
    return result.sort_values(
        ["gap_points", "combined_responses", "lower_nps", "label_full"],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)


def summarize_selected_group_drilldown(
    df: pd.DataFrame,
    selected_group: str,
    perspective: Perspective,
) -> pd.DataFrame:
    df = _score_rows(df, perspective)
    mode_col = _mode_group_col(perspective)
    opposite_col = _opposite_group_col(perspective)
    filtered = df[df[mode_col].astype(str).eq(selected_group)]
    return _summarize(filtered, opposite_col, "group")


def _service_cluster_context_rows(
    df: pd.DataFrame,
    perspective: Perspective,
    selected_group: str,
) -> pd.DataFrame:
                                                                          
                                                                       
                                                                         
    clustered = _score_rows(df, perspective)
    if selected_group == ALL_GROUPS_LABEL:
        return clustered
    group_col = _mode_group_col(perspective)
    return clustered[clustered[group_col].astype(str).eq(selected_group)].copy()


def _service_cluster_metadata_columns(clustered: pd.DataFrame) -> pd.DataFrame:
    metadata_cols = [
        "service_cluster_key",
        "provider_group",
        "service_cluster",
        "provider_abbr",
        "service_cluster_rank",
        "service_cluster_code",
        "service_cluster_display",
        "service_cluster_is_low_info",
    ]
    if clustered.empty:
        return pd.DataFrame(columns=metadata_cols)
    return clustered[metadata_cols].drop_duplicates(subset=["service_cluster_key"])


def _with_service_cluster_labels(
    summary: pd.DataFrame,
    clustered: pd.DataFrame,
    is_frequency_summary: bool = False,
) -> pd.DataFrame:
    metadata = _service_cluster_metadata_columns(clustered)
    drop_cols = [
        "label_full",
        "label_short",
        "slice_full",
        "provider_group",
        "service_cluster",
        "provider_abbr",
        "service_cluster_rank",
        "service_cluster_code",
        "service_cluster_display",
        "service_cluster_is_low_info",
    ]
    summary = summary.drop(columns=[col for col in drop_cols if col in summary.columns])

    if summary.empty:
        for col in metadata.columns:
            if col not in summary.columns:
                summary[col] = pd.Series(dtype=metadata[col].dtype)
        summary["label_full"] = pd.Series(dtype="string")
        summary["label_short"] = pd.Series(dtype="string")
        if is_frequency_summary:
            summary["slice_full"] = pd.Series(dtype="string")
        return summary

    summary = summary.merge(metadata, on="service_cluster_key", how="left")
    summary["label_full"] = summary["service_cluster_display"].fillna(
        summary["service_cluster_key"].astype(str)
    )
    summary["label_short"] = summary["service_cluster_code"].fillna(
        summary["service_cluster_key"].map(safe_abbreviation)
    )
    if is_frequency_summary:
        summary["slice_full"] = (
            summary["label_full"] + " | " + summary["frequency_normalized"].astype(str)
        )
    return summary


def load_validated_cluster_mapping(
    mapping_path: Path | str = CLUSTER_MAPPING_CSV,
) -> pd.DataFrame:
    path = Path(mapping_path)
    required = {"rating_id", "provider_group", "customer_group", "service_cluster", "validated"}
    if not path.exists():
        return pd.DataFrame(columns=sorted(required))

    mapping = pd.read_csv(path)
    missing = required.difference(mapping.columns)
    if missing:
        raise ValueError(
            f"Service cluster mapping is missing required columns: {', '.join(sorted(missing))}"
        )

    validated = mapping["validated"].astype(str).str.strip().str.lower().isin(
        {"true", "yes", "y", "1", "validated"}
    )
    mapping = mapping[validated].copy()
    mapping["rating_id"] = pd.to_numeric(mapping["rating_id"], errors="coerce")
    mapping = mapping.dropna(subset=["rating_id", "service_cluster"])
    mapping["rating_id"] = mapping["rating_id"].astype(int)
    mapping["service_cluster"] = mapping["service_cluster"].astype(str).str.strip()
    mapping = mapping[mapping["service_cluster"].ne("")]
    return mapping.drop_duplicates(subset=["rating_id", "service_cluster"])


def attach_service_clusters(
    df: pd.DataFrame,
    mapping: pd.DataFrame,
) -> pd.DataFrame:
    if mapping.empty:
        return pd.DataFrame(columns=list(df.columns) + ["service_cluster"])
    merged = df.merge(
        mapping[["rating_id", "service_cluster"]],
        on="rating_id",
        how="inner",
        validate="one_to_many",
    )
    merged["service_cluster"] = merged["service_cluster"].astype(str)
    return merged


def summarize_service_clusters(
    df: pd.DataFrame,
    perspective: Perspective,
    selected_group: str = ALL_GROUPS_LABEL,
    mapping_path: Path | str = CLUSTER_MAPPING_CSV,
) -> tuple[pd.DataFrame, bool]:
    del mapping_path
    clustered = _service_cluster_context_rows(df, perspective, selected_group)
    if clustered.empty or "service_cluster_key" not in clustered.columns:
        return _empty_summary("service_cluster_key"), False

    summary = _summarize(clustered, "service_cluster_key", "service_cluster_key")
    return _with_service_cluster_labels(summary, clustered), True


def summarize_service_cluster_frequency_slices(
    df: pd.DataFrame,
    perspective: Perspective,
    selected_group: str = ALL_GROUPS_LABEL,
    mapping_path: Path | str = CLUSTER_MAPPING_CSV,
) -> tuple[pd.DataFrame, bool]:
    del mapping_path
    clustered = _service_cluster_context_rows(df, perspective, selected_group)
    if clustered.empty or "service_cluster_key" not in clustered.columns:
        return _empty_frequency_summary("service_cluster_key"), False

    summary = _summarize_frequency_slices(
        clustered,
        "service_cluster_key",
        "service_cluster_key",
    )
    return _with_service_cluster_labels(summary, clustered, is_frequency_summary=True), True


def _load_xfn_division_rows(fallback_df: pd.DataFrame, xfn_path: Path | str = XFN_DIVISION_CSV) -> pd.DataFrame:
    rows = analysis_rows(fallback_df)
    return rows[rows["provider_group"].astype(str).eq(XFN_PROVIDER)].copy().reset_index(drop=True)


def summarize_cross_functional_teams(
    df: pd.DataFrame,
) -> dict[str, pd.DataFrame | float | int | str]:
    rows = _load_xfn_division_rows(df)
    if rows.empty:
        return {
            "provider_group": XFN_PROVIDER,
            "ratings": 0,
            "nps": float("nan"),
            "avg_criticality": float("nan"),
            "xfn_division_mix": pd.DataFrame(
                columns=["label_full", "label_short", "ratings", "pct"]
            ),
            "xfn_division_summary": _empty_summary("xfn_division"),
        }

    rows["xfn_division"] = rows["Division Rated"].map(clean_xfn_division_label)
    overall = _summarize(rows, "provider_group", "provider_group").iloc[0]
    division_summary = _summarize(rows, "xfn_division", "xfn_division")
    division_summary["share_pct"] = ((division_summary["ratings"] / len(rows)) * 100).round(2)
    division_summary["share_label"] = (
        division_summary["ratings"].astype(int).astype(str)
        + "/"
        + str(len(rows))
        + " ("
        + division_summary["share_pct"].round(0).astype(int).astype(str)
        + "%)"
    )
    division_summary["label_short"] = division_summary["label_full"]
    division_summary = division_summary.sort_values(
        ["ratings", "nps", "label_full"],
        ascending=[False, True, True],
    ).reset_index(drop=True)

    pie_source = division_summary[["label_full", "label_short", "ratings", "share_pct"]].copy()
    pie_source = pie_source.rename(columns={"share_pct": "pct"})

    return {
        "provider_group": XFN_PROVIDER,
        "ratings": int(overall["ratings"]),
        "nps": float(overall["nps"]),
        "avg_criticality": float(overall["avg_criticality"]),
        "xfn_division_mix": pie_source,
        "xfn_division_summary": division_summary,
    }


def selected_context_summary(
    df: pd.DataFrame,
    selected_group: str,
    perspective: Perspective,
) -> pd.DataFrame:
    if selected_group == ALL_GROUPS_LABEL:
        return summarize_groups(df, perspective)
    summary = summarize_groups(df, perspective)
    return summary[summary["label_full"].eq(selected_group)].copy()
