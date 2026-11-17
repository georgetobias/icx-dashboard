from __future__ import annotations

from functools import lru_cache
import io
import csv
import hashlib
from pathlib import Path
from uuid import uuid4
from typing import Literal

import pandas as pd

from .settings import (
    clear_persisted_master_csv,
    APP_ROOT,
    default_master_csv_path,
    master_csv_path,
    persisted_master_csv_path,
    runtime_master_csv_path,
    set_runtime_master_csv,
    app_data_directory,
)
from .schemas import records
from ..icx import icx_data as icx


Perspective = Literal["provider", "customer"]
AnalysisLevel = Literal[
    "groups",
    "service_clusters",
    "division_only",
    "division_territory",
    "territory_only",
]
BlueBreakdownLevel = Literal["groups", "service", "division", "territory"]

DATA_GROUP_LABEL = "Data Group (Special)"
DATA_GROUP_CODE = "DG"
DATA_GROUP_METRICS_FILENAME = "optional_group_metrics.csv"
DATA_GROUP_PROFILE_NOTE = "Optional user-provided aggregate metrics, separate from the active dataset."

                                                                           
                                                                           
                                                                               
                                                                        
                                             
DISPLAY_EXCLUDED_GROUPS: set[str] = set()

BLUE_PERCENT_COLUMNS = {
    "busted": "busted_pct",
    "leveled": "leveled_pct",
    "uplifted": "uplifted_pct",
    "exceptional": "exceptional_pct",
}
FREQUENCY_COLUMNS = [
    "Daily",
    "Weekly",
    "Monthly",
    "Quarterly",
    "Annual",
    "Ad hoc / Upon request",
    "Other / Missing",
]
CRITICALITY_COLUMNS = [
    "Very Critical",
    "Critical",
    "Somewhat Critical",
    "Not Critical",
    "Other / Missing",
]

DEMOGRAPHIC_SPECS = (
    ("band", "By Band", "Band", ()),
    ("role", "By Role", "Role", ("Individual Contributor", "People Manager")),
    (
        "tenure",
        "By Tenure",
        "Tenure Category",
        ("Less than 3 years", "3 to 5 years", "6 to 10 years", "11 to 15 years", "16 to 20 years", "More than 20 years"),
    ),
    (
        "age",
        "By Age Group",
        "Age Range",
        ("20 - 30 years old", "31 - 40 years old", "41 - 50 years old", "51 - 59 years old", "60 and above"),
    ),
)


def _demographic_chart(rows: pd.DataFrame, key: str, title: str, column: str, order: tuple[str, ...]) -> dict[str, object]:
    total = int(len(rows))
    if total == 0:
        return {"key": key, "title": title, "column": column, "total": 0, "rows": []}

    values = rows[column].astype("string").str.strip()
    values = values.mask(values.isna() | values.eq(""), "Not Provided")
    counts = values.value_counts(dropna=False)
    order_rank = {label: index for index, label in enumerate((*order, "Not Provided"))}
    labels = sorted(
        [str(label) for label in counts.index],
        key=lambda label: (-int(counts[label]), order_rank.get(label, len(order_rank))),
    )
    return {
        "key": key,
        "title": title,
        "column": column,
        "total": total,
        "rows": [
            {
                "label": label,
                "count": int(counts[label]),
                "pct": round(int(counts[label]) / total * 100, 1),
            }
            for label in labels
        ],
    }


def _group_demographics(df: pd.DataFrame, group_name: str) -> list[dict[str, object]]:
                                                                               
                                                                               
                                                                               
                                             
    employee_key = df.get("Employee ID", pd.Series(pd.NA, index=df.index, dtype="string")).astype("string").str.strip()
    email_key = df.get("Email Address", pd.Series(pd.NA, index=df.index, dtype="string")).astype("string").str.strip().str.casefold()
    respondent_key = employee_key.mask(employee_key.isna() | employee_key.eq(""), email_key)
    rows = (
        df.assign(_respondent_key=respondent_key)
        .dropna(subset=["_respondent_key"])
        .drop_duplicates("_respondent_key")
        .drop(columns=["_respondent_key"])
    )
    if group_name != icx.ALL_GROUPS_LABEL:
        rows = rows[rows["Group"].astype(str).eq(group_name)].copy()
    return [_demographic_chart(rows, key, title, column, order) for key, title, column, order in DEMOGRAPHIC_SPECS]
def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


@lru_cache(maxsize=4)
def load_master_cached(path_text: str, mtime: float) -> pd.DataFrame:
    del mtime
    return icx.load_icx_master(Path(path_text))


def source_path() -> Path:
    return master_csv_path()


def app_settings() -> dict:
    current = source_path()
    default = default_master_csv_path()
    override = runtime_master_csv_path()
    return {
        "csv_source_path": str(current),
        "default_csv_source_path": str(default),
        "runtime_override": str(override) if override is not None else None,
        "csv_exists": bool(current.exists()),
    }


def update_csv_source_path(path_text: str | None) -> dict:
    set_runtime_master_csv(path_text)
    load_master_cached.cache_clear()
    return app_settings()


def load_master() -> pd.DataFrame:
    path = source_path()
    if not path.exists():
        raise FileNotFoundError(f"Missing master CSV: {path}")
    return load_master_cached(str(path), _mtime(path))


def display_rows(df: pd.DataFrame | None = None) -> pd.DataFrame:
    source = load_master() if df is None else df
    provider = source["provider_group"].astype(str)
    customer = source["customer_group"].astype(str)
    return source[
        ~provider.isin(DISPLAY_EXCLUDED_GROUPS)
        & ~customer.isin(DISPLAY_EXCLUDED_GROUPS)
    ].copy()


def data_status() -> dict:
    path = source_path()
    if not path.exists():
        return {
            "ok": False,
            "source": str(path),
            "message": "Master CSV not found. Set ICX_MASTER_CSV in .env or place the CSV in data/.",
        }
    source_df = load_master()
    df = display_rows(source_df)
    guardrails = icx.run_guardrails(source_df)
    visible_blue_counts = {
        rating: int(df["blue_rating"].eq(rating).sum())
        for rating in icx.BLUE_ORDER
    }
    visible_overall = round(
        icx.nps_from_counts(
            visible_blue_counts["Busted"],
            visible_blue_counts["Uplifted"],
            visible_blue_counts["Exceptional"],
            len(df),
        ),
        2,
    )
    return {
        "ok": all(_integrity_checks(source_df).values()),
        "baseline_matches": bool(guardrails.ok),
        "source": str(path),
        "source_mtime": _mtime(path),
        "rows": int(len(df)),
        "source_rows": int(guardrails.rows),
        "overall_nps": float(visible_overall),
        "source_overall_nps": float(guardrails.overall_nps),
        "blue_counts": visible_blue_counts,
        "source_blue_counts": guardrails.blue_counts,
        "service_cluster_non_null": int(df["Service Cluster"].notna().sum()) if "Service Cluster" in df.columns else 0,
        "service_cluster_missing": int(df["Service Cluster"].isna().sum()) if "Service Cluster" in df.columns else len(df),
        "service_cluster_unique": int(df["Service Cluster"].nunique(dropna=True)) if "Service Cluster" in df.columns else 0,
        "source_service_cluster_non_null": int(guardrails.service_cluster_non_null),
        "source_service_cluster_missing": int(guardrails.service_cluster_missing),
        "source_service_cluster_unique": int(guardrails.service_cluster_unique),
        "checks": _integrity_checks(source_df),
    }


def _perspective_rows(df: pd.DataFrame, perspective: Perspective) -> tuple[pd.DataFrame, str]:
    df = display_rows(df)
    if perspective == "provider":
        return icx.provider_score_rows(df), "provider_group"
    return icx.analysis_rows(df), "customer_group"


def _percent_columns(grouped: pd.core.groupby.generic.DataFrameGroupBy, column: str, order: list[str]) -> pd.DataFrame:
    counts = grouped[column].value_counts(dropna=False).unstack(fill_value=0)
    for label in order:
        if label not in counts.columns:
            counts[label] = 0
    counts = counts[order]
    totals = counts.sum(axis=1).replace(0, pd.NA)
    return counts.div(totals, axis=0).mul(100).round(1)


def _service_counts(rows: pd.DataFrame, group_col: str) -> pd.DataFrame:
    raw = rows.assign(
        _service_received=rows["Service Received"].astype("string").str.strip()
    )
    raw["_usable_service_received"] = raw["_service_received"].where(
        raw["_service_received"].notna() & raw["_service_received"].ne("")
    )
    raw_counts = raw.groupby(group_col).agg(
        raw_service_rows=("_usable_service_received", "count"),
        unique_raw_service_texts=("_usable_service_received", lambda values: int(values.dropna().nunique())),
    )
    real_clusters = rows[~rows["service_cluster_is_low_info"].fillna(True).astype(bool)]
    cluster_counts = real_clusters.groupby(group_col)["service_cluster"].nunique().rename("defined_service_clusters")
    return raw_counts.join(cluster_counts, how="left").fillna({"defined_service_clusters": 0})


def home_summary(perspective: Perspective = "provider") -> dict:
    source_df = load_master()
    df = display_rows(source_df)
    rows, group_col = _perspective_rows(df, perspective)
    summary = icx.summarize_groups(df, perspective).copy()
    if summary.empty:
        return {"status": data_status(), "perspective": perspective, "rows": [], "tiles": {}}

    summary = summary.rename(columns={"label_full": "group_name", "label_short": "group_code"})
    service_counts = _service_counts(rows, group_col)
    summary = summary.merge(service_counts, left_on="group_name", right_index=True, how="left")
    summary[["raw_service_rows", "unique_raw_service_texts", "defined_service_clusters"]] = summary[
        ["raw_service_rows", "unique_raw_service_texts", "defined_service_clusters"]
    ].fillna(0).astype(int)

    for count_col, pct_col in BLUE_PERCENT_COLUMNS.items():
        summary[pct_col] = (summary[count_col] / summary["ratings"] * 100).round(1)

    grouped = rows.groupby(group_col, dropna=False)
    freq_pct = _percent_columns(grouped, "frequency_normalized", FREQUENCY_COLUMNS)
    freq_pct.columns = [f"frequency_pct_{col}" for col in freq_pct.columns]
    criticality_source = rows.assign(criticality_normalized=rows["Criticality"].map(icx.normalize_criticality))
    crit_pct = _percent_columns(
        criticality_source.groupby(group_col, dropna=False),
        "criticality_normalized",
        CRITICALITY_COLUMNS,
    )
    crit_pct.columns = [f"criticality_pct_{col}" for col in crit_pct.columns]
    summary = summary.merge(freq_pct, left_on="group_name", right_index=True, how="left")
    summary = summary.merge(crit_pct, left_on="group_name", right_index=True, how="left")
    pct_cols = [col for col in summary.columns if "_pct_" in col or col.endswith("_pct")]
    summary[pct_cols] = summary[pct_cols].fillna(0)

    summary["rank"] = summary["nps"].rank(method="first", ascending=False).astype(int)
    summary["open_path"] = "/group/" + summary["group_name"].astype(str)
    summary = summary.sort_values(["nps", "ratings"], ascending=[False, False])

    tiles = {
                                                                              
                                                                              
                                                                 
        "overall_icx": round(
            icx.nps_from_counts(
                int(rows["is_busted"].sum()),
                int(rows["is_uplifted"].sum()),
                int(rows["is_exceptional"].sum()),
                int(len(rows)),
            ),
            2,
        ),
        "total_ratings": int(len(rows)),
        "groups": int(len(summary)),
        "small_n_groups": int(summary["small_n"].sum()),
        "lowest_group": str(summary.sort_values(["nps", "ratings"], ascending=[True, False]).iloc[0]["group_name"]),
        "highest_attention": str(summary.sort_values(["attention_score", "ratings"], ascending=[False, False]).iloc[0]["group_name"]),
    }
    return {"status": data_status(), "perspective": perspective, "tiles": tiles, "rows": records(summary)}


def group_profile(group_name: str) -> dict:
    df = display_rows(load_master())
    provider_summary = icx.summarize_groups(df, "provider")
    customer_summary = icx.summarize_groups(df, "customer")
    provider_row = provider_summary[provider_summary["label_full"].astype(str).eq(group_name)]
    customer_row = customer_summary[customer_summary["label_full"].astype(str).eq(group_name)]
    comparison = group_comparison(group_name, "provider")

    received = None if provider_row.empty else provider_row.iloc[0].to_dict()
    gave = None if customer_row.empty else customer_row.iloc[0].to_dict()
    disparity = None
    if received and gave:
        disparity = round(float(received["nps"]) - float(gave["nps"]), 2)
    inter_intra = group_inter_intra_detail(group_name, df)
    return {
        "status": data_status(),
        "group_name": group_name,
        "received": {key: value for key, value in (received or {}).items() if key not in {"group"}},
        "gave": {key: value for key, value in (gave or {}).items() if key not in {"group"}},
        "disparity": disparity,
        "inter_intra": inter_intra,
        "comparison": comparison["rows"],
    }


def group_inter_intra_detail(group_name: str, df: pd.DataFrame | None = None) -> dict:
    source = display_rows(load_master()) if df is None else df
    rows = icx.provider_score_rows(source)
    group_rows = rows[rows["provider_group"].astype(str).eq(group_name)].copy()
    total = int(len(group_rows))
    intra = group_rows[group_rows["is_intra"]]
    inter = group_rows[~group_rows["is_intra"]]
    intra_n = int(len(intra))
    inter_n = int(len(inter))
    intra_nps = _nps_for_rows(intra)
    inter_nps = _nps_for_rows(inter)
    return {
        "total": total,
        "intra_n": intra_n,
        "inter_n": inter_n,
        "intra_pct": round(intra_n / total * 100, 1) if total else None,
        "inter_pct": round(inter_n / total * 100, 1) if total else None,
        "intra_nps": round(intra_nps, 2) if pd.notna(intra_nps) else None,
        "inter_nps": round(inter_nps, 2) if pd.notna(inter_nps) else None,
        "gap": round(inter_nps - intra_nps, 2)
        if pd.notna(intra_nps) and pd.notna(inter_nps)
        else None,
    }


def groups(perspective: Perspective = "provider") -> list[str]:
    values = icx.group_options(display_rows(load_master()), perspective)
    if perspective == "provider" and data_group_metrics_path().exists():
        values = [*values, DATA_GROUP_LABEL]
    return values


def summary_for_analysis(
    perspective: Perspective,
    analysis: AnalysisLevel,
    selected_group: str = icx.ALL_GROUPS_LABEL,
    min_ratings: int = 1,
    include_low_info: bool = False,
) -> pd.DataFrame:
    df = display_rows(load_master())
    if analysis == "groups":
        summary = icx.summarize_groups(df, perspective)
    elif analysis == "service_clusters":
        summary, _ = icx.summarize_service_clusters(df, perspective, selected_group)
        if not include_low_info and "service_cluster_is_low_info" in summary.columns:
            summary = summary[~summary["service_cluster_is_low_info"].fillna(False).astype(bool)]
    elif analysis == "division_only":
        summary = icx.summarize_divisions(df, perspective, selected_group)
    elif analysis == "division_territory":
        summary = icx.summarize_division_territory(df, perspective, selected_group)
    elif analysis == "territory_only":
        summary = (
            icx.summarize_requested_territory_scatter(df)
            if perspective == "provider" and selected_group == icx.ALL_GROUPS_LABEL
            else icx.summarize_territory_groupings(df, perspective, selected_group)
        )
    else:
        raise ValueError(f"Unknown analysis level: {analysis}")
    if "ratings" in summary.columns:
        summary = summary[summary["ratings"].fillna(0).astype(float).ge(min_ratings)]
    return summary.reset_index(drop=True)


def group_comparison(
    selected_group: str,
    perspective: Perspective = "provider",
) -> dict:
    summary = icx.summarize_groups(display_rows(load_master()), perspective).copy()
    if summary.empty:
        return {"selected_group": selected_group, "rows": []}
    selected = summary[summary["label_full"].astype(str).eq(selected_group)]
    selected_nps = None if selected.empty else float(selected.iloc[0]["nps"])
    summary["selected"] = summary["label_full"].astype(str).eq(selected_group)
    summary["gap_vs_selected"] = (
        summary["nps"].astype(float) - selected_nps
        if selected_nps is not None
        else pd.NA
    )
    summary = summary.sort_values(["nps", "ratings"], ascending=[False, False])
    return {"selected_group": selected_group, "rows": records(summary)}


def received_gave_summary(selected_group: str | None = None) -> dict:
    df = display_rows(load_master())
    provider = icx.summarize_groups(df, "provider")[["label_full", "label_short", "ratings", "nps", "avg_criticality"]]
    customer = icx.summarize_groups(df, "customer")[["label_full", "ratings", "nps", "avg_criticality"]]
    merged = provider.merge(customer, on="label_full", suffixes=("_received", "_gave"))
    merged["gap"] = (merged["nps_received"] - merged["nps_gave"]).round(2)
    merged["selected"] = merged["label_full"].astype(str).eq(selected_group or "")
    merged = merged.sort_values(["gap", "ratings_received"], ascending=[False, False])
    return {"selected_group": selected_group, "rows": records(merged)}


def _nps_for_rows(rows: pd.DataFrame) -> float:
    if rows.empty:
        return float("nan")
    return float(
        icx.nps_from_counts(
            int(rows["is_busted"].sum()),
            int(rows["is_uplifted"].sum()),
            int(rows["is_exceptional"].sum()),
            int(len(rows)),
        )
    )


def inter_intra_summary(selected_group: str | None = None) -> dict:
    df = icx.provider_score_rows(display_rows(load_master()))
    records_out: list[dict[str, object]] = []
    for provider_group, group_df in df.groupby("provider_group", dropna=False):
        intra = group_df[group_df["is_intra"]]
        inter = group_df[~group_df["is_intra"]]
        intra_nps = _nps_for_rows(intra)
        inter_nps = _nps_for_rows(inter)
        records_out.append(
            {
                "label_full": str(provider_group),
                "label_short": icx.safe_abbreviation(provider_group),
                "intra_n": int(len(intra)),
                "inter_n": int(len(inter)),
                "intra_nps": round(intra_nps, 2) if pd.notna(intra_nps) else None,
                "inter_nps": round(inter_nps, 2) if pd.notna(inter_nps) else None,
                "gap": round(inter_nps - intra_nps, 2)
                if pd.notna(intra_nps) and pd.notna(inter_nps)
                else None,
                "selected": str(provider_group) == str(selected_group or ""),
            }
        )
    result = pd.DataFrame.from_records(records_out)
    if not result.empty:
        result = result.sort_values(["gap", "inter_n"], ascending=[False, False], na_position="last")
    return {"selected_group": selected_group, "rows": records(result)}


def blue_breakdown(perspective: Perspective = "provider", selected_group: str = icx.ALL_GROUPS_LABEL) -> dict:
    summary = home_summary(perspective)["rows"]
    if selected_group != icx.ALL_GROUPS_LABEL:
        summary = [row for row in summary if row["group_name"] == selected_group]
    return {"perspective": perspective, "selected_group": selected_group, "rows": summary}


def blue_service_queues(selected_group: str, perspective: Perspective = "provider") -> dict:
    df = display_rows(load_master())
    clusters, _ = icx.summarize_service_clusters(df, perspective, selected_group)
    if clusters.empty:
        return {"selected_group": selected_group, "queues": {}}
    queues = icx.split_blue_attention_queues(clusters)
    return {
        "selected_group": selected_group,
        "queues": {band: records(queue) for band, queue in queues.items()},
    }


def service_blue_breakdown(selected_group: str, perspective: Perspective = "provider") -> dict:
    df = display_rows(load_master())
    clusters, _ = icx.summarize_service_clusters(df, perspective, selected_group)
    if clusters.empty:
        return {"selected_group": selected_group, "rows": []}
    if "service_cluster_is_low_info" in clusters.columns:
        clusters = clusters[~clusters["service_cluster_is_low_info"].fillna(False).astype(bool)].copy()
    rows = _service_cluster_context_rows(df, perspective, selected_group)
    if rows.empty:
        return {"selected_group": selected_group, "rows": records(clusters)}
    freq_pct = _percent_columns(rows.groupby("service_cluster_key", dropna=False), "frequency_normalized", FREQUENCY_COLUMNS)
    freq_pct.columns = [f"frequency_pct_{col}" for col in freq_pct.columns]
    criticality_source = rows.assign(criticality_normalized=rows["Criticality"].map(icx.normalize_criticality))
    crit_pct = _percent_columns(
        criticality_source.groupby("service_cluster_key", dropna=False),
        "criticality_normalized",
        CRITICALITY_COLUMNS,
    )
    crit_pct.columns = [f"criticality_pct_{col}" for col in crit_pct.columns]
    clusters = clusters.merge(freq_pct, left_on="service_cluster_key", right_index=True, how="left")
    clusters = clusters.merge(crit_pct, left_on="service_cluster_key", right_index=True, how="left")
    pct_cols = [col for col in clusters.columns if "_pct_" in col or col.endswith("_pct")]
    clusters[pct_cols] = clusters[pct_cols].fillna(0)
    clusters = clusters.sort_values(["ratings", "nps", "label_full"], ascending=[False, True, True])
    return {"selected_group": selected_group, "rows": records(clusters)}


def _service_cluster_context_rows(
    df: pd.DataFrame,
    perspective: Perspective,
    selected_group: str,
) -> pd.DataFrame:
    rows = (
        icx.provider_score_rows(df)
        if perspective == "provider"
        else icx.analysis_rows(df)
    )
    if selected_group == icx.ALL_GROUPS_LABEL:
        return rows
    group_col = "provider_group" if perspective == "provider" else "customer_group"
    return rows[rows[group_col].astype(str).eq(selected_group)].copy()


def data_qa() -> dict:
    df = display_rows(load_master())
    status = data_status()
    source_columns = [icx.canonical_master_column(column) for column in pd.read_csv(source_path(), nrows=0).columns]
    missing = df[[column for column in source_columns if column in df]].isna().sum().sort_values(ascending=False)
    public_missing = missing.drop(labels=["Email Address", "Employee ID", "Last Name", "First Name", "Middle Name"], errors="ignore")
    return {
        "status": status,
        "missing_values": [{"column": str(col), "missing": int(value)} for col, value in public_missing.items()],
        "privacy_note": "Normal UI suppresses emails, IDs, respondent names, member/team names, and raw feedback.",
    }

def _mtime(path: Path) -> float:
    return path.stat().st_mtime_ns if path.exists() else 0


@lru_cache(maxsize=4)
def load_master_cached(path_text: str, mtime: float) -> pd.DataFrame:
    del mtime
    return icx.load_icx_master(Path(path_text))


@lru_cache(maxsize=2)
def load_service_catalogue_cached(path_text: str, mtime: float) -> pd.DataFrame:
    del mtime
    return icx.load_service_catalogue(Path(path_text))


@lru_cache(maxsize=2)
def load_data_group_metrics_cached(path_text: str, mtime: float) -> pd.DataFrame:
    del mtime
    return pd.read_csv(path_text)


def source_path() -> Path:
    return master_csv_path()


def app_settings() -> dict:
    current = source_path()
    default = default_master_csv_path()
    override = runtime_master_csv_path()
    managed = persisted_master_csv_path()
    return {
        "csv_source_path": str(current),
        "default_csv_source_path": str(default),
        "runtime_override": str(override) if override is not None else None,
        "csv_exists": bool(current.exists()),
        "source_is_managed_copy": current == managed and managed.exists(),
        "app_data_directory": str(app_data_directory()),
        "source_revision": source_revision()["revision"],
    }


class CsvSourceValidationError(ValueError):
    pass


def source_revision() -> dict:
    path = source_path()
    stat = path.stat() if path.exists() else None
    signature = f"{path}:{stat.st_mtime_ns}:{stat.st_size}" if stat else f"{path}:missing"
    return {"revision": hashlib.sha256(signature.encode()).hexdigest()[:24]}


def _integrity_checks(df: pd.DataFrame) -> dict[str, bool]:
    raw_criticality = df["Criticality Score"].astype("string").str.strip()
    has_criticality = raw_criticality.notna() & raw_criticality.ne("")
    return {
        "rows": len(df) > 0,
        "blue_counts": bool(df["blue_rating"].isin(icx.BLUE_ORDER).all()),
        "groups": bool(df[["provider_group", "customer_group"]].notna().all().all()),
        "criticality": bool(df.loc[has_criticality, "criticality_score"].isin([1, 2, 3, 4]).all()),
        "service_clusters": "Service Cluster" in df.columns,
    }


def _expected_master_columns() -> set[str]:
    path = default_master_csv_path()
    if not path.exists():
        path = source_path()
    return {str(column).strip().casefold() for column in pd.read_csv(path, nrows=0).columns}


def validate_master_csv_path(path: Path) -> pd.DataFrame:
    if path.suffix.casefold() != ".csv":
        raise CsvSourceValidationError("The selected file must be a .csv file.")
    if not path.exists() or not path.is_file():
        raise CsvSourceValidationError("The selected CSV file does not exist.")
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            raw_header = next(csv.reader(stream))
        columns = [icx.canonical_master_column(column) for column in raw_header]
    except Exception as exc:
        raise CsvSourceValidationError("The selected CSV could not be read. Export a UTF-8 comma-separated CSV from the master sheet.") from exc
    if len(columns) != len(set(columns)):
        raise CsvSourceValidationError("Duplicate or ambiguous column headings. Keep one column for each master field.")
    required = {"Group", "Group Rated", "Rating", "Frequency Category", "Criticality Score", "Criticality", "Band", "Role", "Tenure Category", "Age Range", "Division", "Division Rated", "Service Cluster", "Service Received", "Territory", "Territory Grouping"}
    missing = sorted(required - set(columns))
    if missing:
        raise CsvSourceValidationError(
            "The selected CSV has the wrong structure. Missing columns: " + ", ".join(missing) + "."
        )
    if not {"Employee ID", "Email Address"}.intersection(columns):
        raise CsvSourceValidationError("Include Employee ID or Email Address for unique-respondent demographics.")
    try:
        df = icx.load_icx_master(path)
    except Exception as exc:
        raise CsvSourceValidationError("The CSV contains malformed rows. Export the complete master as a UTF-8 CSV, not a summary table.") from exc
    failed = [key for key, valid in _integrity_checks(df).items() if not valid]
    if failed:
        raise CsvSourceValidationError("Master-sheet validation failed: " + ", ".join(failed) + ". Use non-empty rows, BLUE rating labels, both groups, and criticality scores from 1 to 4 (or blank). The previous source is unchanged.")
    identities = df[[column for column in ["Employee ID", "Email Address"] if column in df]].astype("string").apply(lambda col: col.str.strip().replace("", pd.NA))
    if identities.isna().all(axis=1).any():
        raise CsvSourceValidationError("Every rating row needs an Employee ID or Email Address to calculate unique-respondent demographics. The previous source is unchanged.")
    employee = identities.get("Employee ID", pd.Series(pd.NA, index=df.index, dtype="string"))
    email = identities.get("Email Address", pd.Series(pd.NA, index=df.index, dtype="string")).str.casefold()
    identity = employee.fillna(email)
    demographic_fields = ["Group", "Band", "Role", "Tenure Category", "Age Range"]
    consistency = df[demographic_fields].astype("string").apply(lambda col: col.str.strip().replace("", pd.NA)).groupby(identity).nunique(dropna=False)
    if consistency.gt(1).any().any():
        raise CsvSourceValidationError("Some respondents have conflicting group or demographic values across their rating rows. Make each respondent’s Group, Band, Role, Tenure Category and Age Range consistent before uploading. The previous source is unchanged.")
    return df


def update_csv_source_path(path_text: str | None) -> dict:
    if path_text is None or not str(path_text).strip():
        clear_persisted_master_csv()
        set_runtime_master_csv(default_master_csv_path())
    else:
        path = Path(path_text).expanduser()
        validate_master_csv_path(path)
        set_runtime_master_csv(path)
    load_master_cached.cache_clear()
    load_service_catalogue_cached.cache_clear()
    return app_settings()


def import_csv_source(content: bytes, filename: str | None = None) -> dict:
    if len(content) > 50 * 1024 * 1024:
        raise CsvSourceValidationError("The selected CSV exceeds the 50 MB import limit.")
    imported_name = Path(filename or "").name
    if not imported_name or Path(imported_name).suffix.casefold() != ".csv":
        raise CsvSourceValidationError("The selected file must be a .csv file.")
    destination = persisted_master_csv_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.stem}.{uuid4().hex}.csv")
    try:
        temporary.write_bytes(content)
        validated = validate_master_csv_path(temporary)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    set_runtime_master_csv(None)
    load_master_cached.cache_clear()
    load_service_catalogue_cached.cache_clear()
    return {
        **app_settings(),
        "source_is_managed_copy": True,
        "imported_filename": imported_name,
        "imported_rows": int(len(validated)),
    }


def load_master() -> pd.DataFrame:
    path = source_path()
    if not path.exists():
        raise FileNotFoundError(f"Missing master CSV: {path}")
    return load_master_cached(str(path), _mtime(path))


def load_service_catalogue() -> pd.DataFrame:
    path = default_master_csv_path().parent / "service_catalogue.csv"
    return load_service_catalogue_cached(str(path), _mtime(path)).copy()


def data_group_metrics_path() -> Path:
    return default_master_csv_path().parent / DATA_GROUP_METRICS_FILENAME


def territory_scatter_metrics_path() -> Path:
    return APP_ROOT / "backend" / "icx" / "territory_scatter_metrics.csv"


def load_data_group_metrics() -> pd.DataFrame:
    path = data_group_metrics_path()
    if not path.exists():
        raise FileNotFoundError(f"Missing Data Group metrics: {path}")
    return load_data_group_metrics_cached(str(path), _mtime(path)).copy()


def is_data_group(group_name: str | None) -> bool:
    return str(group_name or "").strip() == DATA_GROUP_LABEL


def groups(perspective: Perspective = "provider") -> list[str]:
    values = icx.group_options(display_rows(load_master()), perspective)
    if perspective == "provider" and data_group_metrics_path().exists():
        values = [*values, DATA_GROUP_LABEL]
    return values


def _data_group_summary(analysis: str, min_ratings: int) -> pd.DataFrame:
    source = load_data_group_metrics()
    metric_analysis = "service" if analysis == "service_clusters" else "division"
    rows = source[source["analysis"].astype(str).eq(metric_analysis)].copy()
    rows["ratings"] = pd.to_numeric(rows["ratings"], errors="coerce").astype(int)
    rows["busted"] = pd.to_numeric(rows["busted"], errors="coerce").astype(int)
    rows["leveled"] = pd.to_numeric(rows["leveled"], errors="coerce").astype(int)
    rows["uplifted"] = pd.to_numeric(rows["uplifted"], errors="coerce").astype(int)
    rows["exceptional"] = pd.to_numeric(rows["exceptional"], errors="coerce").astype(int)
    rows["avg_criticality"] = pd.to_numeric(rows["avg_criticality"], errors="coerce")
    rows["nps"] = pd.to_numeric(rows["nps"], errors="coerce")
    rows["provider_group"] = DATA_GROUP_LABEL
    rows["provider_abbr"] = DATA_GROUP_CODE
    rows["service_cluster"] = rows["label_full"]
    rows["service_cluster_is_low_info"] = rows["service_cluster_is_low_info"].fillna(False).astype(bool)
    rows["dominant_frequency"] = rows["dominant_frequency"].fillna("Other / Missing")
    rows["small_n"] = rows["ratings"].lt(icx.SMALL_N_THRESHOLD)
    rows["stable_n"] = ~rows["small_n"]
    rows["attention_score"] = icx.attention_score_blue(
        rows["nps"], rows["ratings"], rows["avg_criticality"]
    ).round(0)
    rows["label_short"] = rows["label_short"].astype(str)
    rows["point_type"] = "Division" if metric_analysis == "division" else "Service"
    rows["is_territory_point"] = False
    rows["score_source"] = rows["score_source"].astype(str)
    rows["label_full"] = rows["label_full"].astype(str)
    rows = rows[rows["ratings"].ge(min_ratings)]
    return rows.reset_index(drop=True)


def summary_for_analysis(
    perspective: Perspective,
    analysis: AnalysisLevel,
    selected_group: str = icx.ALL_GROUPS_LABEL,
    min_ratings: int = 1,
    include_low_info: bool = False,
) -> pd.DataFrame:
    if is_data_group(selected_group):
        if perspective != "provider":
            return pd.DataFrame()
        summary = _data_group_summary(analysis, min_ratings)
        if not include_low_info and "service_cluster_is_low_info" in summary.columns:
            summary = summary[~summary["service_cluster_is_low_info"]].copy()
        return summary.reset_index(drop=True)
    df = display_rows(load_master())
    if analysis == "groups":
        summary = icx.summarize_groups(df, perspective)
    elif analysis == "service_clusters":
        summary, _ = icx.summarize_service_clusters(df, perspective, selected_group)
        if not include_low_info and "service_cluster_is_low_info" in summary.columns:
            summary = summary[~summary["service_cluster_is_low_info"].fillna(False).astype(bool)]
    elif analysis == "division_only":
        summary = icx.summarize_divisions(df, perspective, selected_group)
    elif analysis == "division_territory":
        summary = icx.summarize_division_territory(df, perspective, selected_group)
    elif analysis == "territory_only":
        summary = (
            icx.summarize_requested_territory_scatter(
                df,
                territory_scatter_metrics_path(),
                use_reference_scores=source_path() == default_master_csv_path(),
            )
            if perspective == "provider" and selected_group == icx.ALL_GROUPS_LABEL
            else icx.summarize_territory_groupings(df, perspective, selected_group)
        )
    else:
        raise ValueError(f"Unknown analysis level: {analysis}")
    if "ratings" in summary.columns:
        summary = summary[summary["ratings"].fillna(0).astype(float).ge(min_ratings)]
    return summary.reset_index(drop=True)


def _aggregate_score(rows: pd.DataFrame) -> dict[str, object]:
    total = int(len(rows))
    busted = int(rows["is_busted"].sum()) if total else 0
    leveled = int(rows["is_leveled"].sum()) if total else 0
    uplifted = int(rows["is_uplifted"].sum()) if total else 0
    exceptional = int(rows["is_exceptional"].sum()) if total else 0
    return {
        "ratings": total,
        "busted": busted,
        "leveled": leveled,
        "uplifted": uplifted,
        "exceptional": exceptional,
        "nps": round(float(icx.nps_from_counts(busted, uplifted, exceptional, total)), 2) if total else None,
        "avg_criticality": round(float(rows["criticality_score"].mean()), 2) if total else None,
        "services": int(rows["service_cluster"].nunique()) if "service_cluster" in rows else 0,
        "divisions": int(rows["provider_division"].nunique()) if "provider_division" in rows else 0,
    }


def group_comparison(
    selected_group: str,
    perspective: Perspective = "provider",
) -> dict:
    summary = icx.summarize_groups(display_rows(load_master()), perspective).copy()
    if summary.empty:
        return {"selected_group": selected_group, "rows": []}
    if selected_group == icx.ALL_GROUPS_LABEL:
        total_rows = icx.provider_score_rows(display_rows(load_master())) if perspective == "provider" else icx.analysis_rows(display_rows(load_master()))
        overall = _aggregate_score(total_rows)["nps"]
        summary["selected"] = False
        summary["gap_vs_selected"] = summary["nps"].astype(float) - float(overall)
    else:
        selected = summary[summary["label_full"].astype(str).eq(selected_group)]
        selected_nps = None if selected.empty else float(selected.iloc[0]["nps"])
        summary["selected"] = summary["label_full"].astype(str).eq(selected_group)
        summary["gap_vs_selected"] = (
            summary["nps"].astype(float) - selected_nps if selected_nps is not None else pd.NA
        )
    summary = summary.sort_values(["nps", "ratings"], ascending=[False, False])
    return {"selected_group": selected_group, "rows": records(summary)}


def group_profile(group_name: str) -> dict:
    if is_data_group(group_name):
        rows = _data_group_summary("service_clusters", 1)
        real = rows[~rows["service_cluster_is_low_info"]]
        return {
            "status": data_status(),
            "group_name": DATA_GROUP_LABEL,
            "is_synthetic": True,
            "profile_note": DATA_GROUP_PROFILE_NOTE,
            "demographics": [],
            "received": {
                "ratings": int(rows["ratings"].sum()),
                "nps": float((rows["nps"] * rows["ratings"]).sum() / rows["ratings"].sum()) if rows["ratings"].sum() else None,
                "avg_criticality": float((rows["avg_criticality"] * rows["ratings"]).sum() / rows["ratings"].sum()) if rows["ratings"].sum() else None,
                "services": int(len(real)),
                "divisions": int(len(_data_group_summary("division_only", 1))),
            },
            "gave": None,
            "disparity": None,
            "inter_intra": {},
            "comparison": [],
        }
    if group_name == icx.ALL_GROUPS_LABEL:
        df = display_rows(load_master())
        received = _aggregate_score(icx.provider_score_rows(df))
        gave = _aggregate_score(icx.analysis_rows(df))
        all_rows = icx.provider_score_rows(df)
        intra = all_rows[all_rows["is_intra"]]
        inter = all_rows[~all_rows["is_intra"]]
        inter_intra = {
            "total": int(len(all_rows)),
            "intra_n": int(len(intra)),
            "inter_n": int(len(inter)),
            "intra_pct": round(len(intra) / len(all_rows) * 100, 1) if len(all_rows) else None,
            "inter_pct": round(len(inter) / len(all_rows) * 100, 1) if len(all_rows) else None,
            "intra_nps": round(_nps_for_rows(intra), 2) if len(intra) else None,
            "inter_nps": round(_nps_for_rows(inter), 2) if len(inter) else None,
            "gap": round(_nps_for_rows(inter) - _nps_for_rows(intra), 2) if len(intra) and len(inter) else None,
        }
        return {
            "status": data_status(),
            "group_name": group_name,
            "demographics": _group_demographics(df, group_name),
            "received": received,
            "gave": gave,
            "disparity": round(float(received["nps"]) - float(gave["nps"]), 2),
            "inter_intra": inter_intra,
            "comparison": group_comparison(group_name, "provider")["rows"],
        }
    df = display_rows(load_master())
    provider_summary = icx.summarize_groups(df, "provider")
    customer_summary = icx.summarize_groups(df, "customer")
    provider_row = provider_summary[provider_summary["label_full"].astype(str).eq(group_name)]
    customer_row = customer_summary[customer_summary["label_full"].astype(str).eq(group_name)]
    comparison = group_comparison(group_name, "provider")
    received = None if provider_row.empty else provider_row.iloc[0].to_dict()
    gave = None if customer_row.empty else customer_row.iloc[0].to_dict()
    disparity = None
    if received and gave:
        disparity = round(float(received["nps"]) - float(gave["nps"]), 2)
    inter_intra = group_inter_intra_detail(group_name, df)
    return {
        "status": data_status(),
        "group_name": group_name,
        "demographics": _group_demographics(df, group_name),
        "received": {key: value for key, value in (received or {}).items() if key not in {"group"}},
        "gave": {key: value for key, value in (gave or {}).items() if key not in {"group"}},
        "disparity": disparity,
        "inter_intra": inter_intra,
        "comparison": comparison["rows"],
    }


def blue_breakdown(
    perspective: Perspective = "provider",
    selected_group: str = icx.ALL_GROUPS_LABEL,
    analysis: BlueBreakdownLevel = "groups",
) -> dict:
    if is_data_group(selected_group):
        rows = _data_group_summary("service_clusters" if analysis == "service" else "division", 1)
        return {"perspective": perspective, "selected_group": selected_group, "analysis": analysis, "rows": records(rows)}
    if analysis == "groups":
        rows = home_summary(perspective)["rows"]
    elif analysis == "service":
        rows = service_blue_breakdown(selected_group, perspective)["rows"]
    elif analysis == "division":
        summary = summary_for_analysis(perspective, "division_only", selected_group, min_ratings=1)
        rows = []
        group_rows = _selected_perspective_rows(display_rows(load_master()), perspective, selected_group)
        for _, item in summary.iterrows():
            row = item.to_dict()
            if perspective == "provider":
                selected = group_rows[group_rows["provider_division"].astype(str).eq(str(item.get("division")))]
            else:
                selected = group_rows[group_rows["Division"].astype(str).eq(str(item.get("division")))]
            row.update(_aggregate_score(selected))
            row["division"] = item.get("division", item.get("label_full"))
            row["overall_icx"] = row.get("nps")
            row["intra_icx"] = _nps_for_rows(selected[selected["is_intra"]])
            row["inter_icx"] = _nps_for_rows(selected[~selected["is_intra"]])
            rows.append(row)
        whole = _aggregate_score(group_rows)
        for column in ("ratings", "busted", "leveled", "uplifted", "exceptional"):
            whole[column] = 0
        whole["division"] = "Served by Whole Group"
        whole["overall_icx"] = whole["nps"]
        whole["intra_icx"] = _nps_for_rows(group_rows[group_rows["is_intra"]])
        whole["inter_icx"] = _nps_for_rows(group_rows[~group_rows["is_intra"]])
        if not any(row.get("division") == whole["division"] for row in rows):
            rows.append(whole)
    elif analysis == "territory":
        summary = summary_for_analysis(perspective, "territory_only", selected_group, min_ratings=1)
        rows = []
        group_rows = _selected_perspective_rows(display_rows(load_master()), perspective, selected_group)
        parent = _aggregate_score(group_rows)["nps"]
        for _, item in summary.iterrows():
            row = item.to_dict()
            row["territory"] = item.get("territory", item.get("label_full"))
            row["territory_group"] = selected_group
            row["group_icx"] = parent
            row["territory_icx"] = row.get("nps")
            rows.append(row)
    else:
        raise ValueError(f"Unknown breakdown analysis: {analysis}")
    return {"perspective": perspective, "selected_group": selected_group, "analysis": analysis, "rows": records(pd.DataFrame(rows))}


def _selected_perspective_rows(df: pd.DataFrame, perspective: Perspective, selected_group: str) -> pd.DataFrame:
    rows = icx.provider_score_rows(df) if perspective == "provider" else icx.analysis_rows(df)
    if selected_group != icx.ALL_GROUPS_LABEL:
        group_col = "provider_group" if perspective == "provider" else "customer_group"
        rows = rows[rows[group_col].astype(str).eq(selected_group)]
    return rows.copy()
