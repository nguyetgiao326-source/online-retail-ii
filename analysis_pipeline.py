from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler


if "__file__" in globals():
    ROOT = Path(__file__).resolve().parent
else:
    ROOT = Path.cwd().resolve()
    while not (ROOT / "analysis_pipeline.py").is_file() and ROOT != ROOT.parent:
        ROOT = ROOT.parent

ARTIFACT_ROOT = Path(
    os.environ.get(
        "RETAIL_ARTIFACTS_DIR",
        str(Path.home() / "Downloads" / "OnlineRetailII_artifacts"),
    )
).expanduser()
OUT = Path(
    os.environ.get("RETAIL_OUTPUTS_DIR", str(ROOT / "outputs"))
).expanduser()
FIG = ROOT / "figures"
FEATURE_FILE = OUT / "customer_features.xlsx"
OUT.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)

if not FEATURE_FILE.is_file():
    raise FileNotFoundError(
        f"Không tìm thấy bảng đặc trưng: {FEATURE_FILE}. "
        "Đặt outputs/customer_features.xlsx trong repo hoặc cấu hình "
        "RETAIL_OUTPUTS_DIR."
    )

RANDOM_STATE = 42
SILHOUETTE_SAMPLE = 2000
MIN_CLUSTER_SIZE = 6
K_VALUES = range(2, 8)
REPEAT_SEEDS = [42, 0, 1, 7, 21, 99, 2026]

features = pd.read_excel(FEATURE_FILE)
required = {
    "customer_id",
    "recency",
    "frequency",
    "monetary",
    "avg_order",
    "n_products",
    "tenure_days",
    "cancel_value",
    "cancel_invoices",
    "cancel_rate",
}
missing = sorted(required.difference(features.columns))
if missing:
    raise ValueError(f"Bảng đặc trưng thiếu cột bắt buộc: {missing}")
if features["customer_id"].duplicated().any():
    raise ValueError("customer_id bị trùng; yêu cầu mỗi khách một dòng.")
if features[list(required.difference({"customer_id"}))].isna().any().any():
    raise ValueError("Các trường số bắt buộc có giá trị thiếu; cần xử lý trước khi phân cụm.")

features = features.sort_values("customer_id").reset_index(drop=True)
features["avg_interpurchase_days"] = np.where(
    features["frequency"] > 1,
    features["tenure_days"] / (features["frequency"] - 1),
    0.0,
)
features["cancel_invoice_share"] = features["cancel_invoices"] / (
    features["frequency"] + features["cancel_invoices"]
).replace(0, np.nan)
features["cancel_invoice_share"] = features["cancel_invoice_share"].fillna(0.0)

rfm_features = ["recency", "frequency", "monetary"]
behavior_features = [
    "avg_order",
    "n_products",
    "tenure_days",
    "cancel_value",
    "cancel_invoices",
    "cancel_rate",
    "avg_interpurchase_days",
    "cancel_invoice_share",
]
all_features = rfm_features + behavior_features
raw_matrix = features[all_features].astype(float)
if (raw_matrix < 0).any().any():
    bad = raw_matrix.columns[(raw_matrix < 0).any()].tolist()
    raise ValueError(f"log1p không áp dụng được cho giá trị âm: {bad}")

feature_audit = pd.DataFrame(
    [
        ("recency", "Có sẵn", "Ngày từ lần mua cuối đến mốc tham chiếu", "RFM"),
        ("frequency", "Có sẵn", "Số hóa đơn mua phân biệt", "RFM"),
        ("monetary", "Có sẵn", "Tổng giá trị mua", "RFM"),
        ("avg_order", "Có sẵn", "Monetary / số hóa đơn mua", "Giá trị đơn trung bình"),
        ("n_products", "Có sẵn", "Số mã hàng phân biệt", "Sản phẩm khác nhau"),
        ("avg_interpurchase_days", "Suy ra được", "tenure_days / (frequency - 1), nếu frequency > 1; ngược lại 0", "Khoảng cách ngày trung bình; độ phân giải ngày"),
        ("cancel_rate", "Có sẵn", "Tỷ trọng giá trị hủy trên tổng giá trị mua và hủy", "Proxy theo giá trị, không phải tỷ lệ theo số lượng"),
        ("cancel_invoice_share", "Suy ra được", "cancel_invoices / (frequency + cancel_invoices)", "Tỷ trọng hóa đơn hủy trong tổng sự kiện hóa đơn"),
        ("average_quantity_per_order", "Thiếu dữ liệu", "Cần tổng Quantity mua / số hóa đơn từ giao dịch gốc", "Không có Quantity trong customer_features.xlsx"),
        ("return_rate_by_units_or_lines", "Thiếu dữ liệu", "Cần số lượng/dòng mua và hoàn trả gốc", "Không thể suy ra từ cancel_value"),
    ],
    columns=["feature", "status", "formula_or_definition", "note"],
)
feature_audit.to_excel(OUT / "feature_audit.xlsx", index=False)

skew_rows = []
transformed = raw_matrix.copy()
log_features = []
for col in all_features:
    before = float(raw_matrix[col].skew())
    apply_log = before > 1.0
    if apply_log:
        transformed[col] = np.log1p(raw_matrix[col])
        log_features.append(col)
    skew_rows.append(
        {
            "feature": col,
            "skew_before": before,
            "transformation": "log1p" if apply_log else "none",
            "skew_after": float(transformed[col].skew()),
        }
    )
skewness = pd.DataFrame(skew_rows)
skewness.to_excel(OUT / "skewness_log1p.xlsx", index=False)

scaler_behavior = StandardScaler()
X_behavior = scaler_behavior.fit_transform(transformed[all_features])
scaler_rfm = StandardScaler()
X_rfm = scaler_rfm.fit_transform(transformed[rfm_features])


def metrics_for(
    X: np.ndarray,
    labels: np.ndarray,
    noise_label: int | None = None,
) -> dict:
    labels = np.asarray(labels)
    mask = np.ones(len(labels), dtype=bool)
    if noise_label is not None:
        mask = labels != noise_label
    assigned = labels[mask]
    assigned_X = X[mask]
    counts = pd.Series(assigned).value_counts()
    n_clusters = int(counts.size)
    min_size = int(counts.min()) if n_clusters else 0
    result = {
        "n_clusters": n_clusters,
        "min_cluster_size": min_size,
        "noise_count": int((~mask).sum()),
        "coverage": float(mask.mean()),
        "silhouette": np.nan,
        "davies_bouldin": np.nan,
        "calinski_harabasz": np.nan,
    }
    if n_clusters < 2 or len(assigned) <= n_clusters:
        return result
    sample_size = min(SILHOUETTE_SAMPLE, len(assigned))
    result["silhouette"] = float(
        silhouette_score(
            assigned_X,
            assigned,
            sample_size=sample_size,
            random_state=RANDOM_STATE,
        )
    )
    result["davies_bouldin"] = float(davies_bouldin_score(assigned_X, assigned))
    result["calinski_harabasz"] = float(calinski_harabasz_score(assigned_X, assigned))
    return result


def eligible(metrics: dict, converged: bool = True) -> bool:
    return (
        converged
        and 2 <= metrics["n_clusters"] <= 7
        and metrics["min_cluster_size"] >= MIN_CLUSTER_SIZE
        and np.isfinite(metrics["silhouette"])
    )


def metric_row(algorithm: str, params: dict, scores: dict, **extra) -> dict:
    row = {"algorithm": algorithm, **params, **scores, **extra}
    row["eligible"] = eligible(
        scores,
        bool(row.get("converged", True)),
    )
    return row


def rank_quality(frame: pd.DataFrame) -> pd.DataFrame:
    ranked = frame.copy()
    ranked["rank_silhouette"] = ranked["silhouette"].rank(ascending=False, method="min")
    ranked["rank_davies_bouldin"] = ranked["davies_bouldin"].rank(
        ascending=True, method="min"
    )
    ranked["rank_calinski_harabasz"] = ranked["calinski_harabasz"].rank(
        ascending=False, method="min"
    )
    ranked["mean_metric_rank"] = ranked[
        ["rank_silhouette", "rank_davies_bouldin", "rank_calinski_harabasz"]
    ].mean(axis=1)
    return ranked


# Baseline luật RFM ngũ phân vị — giữ đúng cách chia của báo cáo hiện có.
rfm = features[["customer_id", "recency", "frequency", "monetary"]].copy()
rfm["R"] = pd.qcut(rfm["recency"], 5, labels=[5, 4, 3, 2, 1]).astype(int)
rfm["F"] = pd.qcut(
    rfm["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]
).astype(int)
rfm["M"] = pd.qcut(
    rfm["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]
).astype(int)


def name_rfm_segment(row: pd.Series) -> str:
    if row["R"] >= 4 and row["F"] >= 4 and row["M"] >= 4:
        return "VIP_trung_thanh"
    if row["R"] >= 4 and row["F"] <= 2:
        return "khach_moi_tiem_nang"
    if row["R"] >= 3 and row["F"] >= 3 and row["M"] >= 3:
        return "khach_trung_thanh"
    if row["R"] <= 2 and row["F"] >= 4 and row["M"] >= 4:
        return "sap_roi_gia_tri_cao"
    if row["R"] <= 2 and row["F"] <= 2:
        return "nguy_co_mat"
    if row["R"] >= 4:
        return "moi_mua_gan_day"
    if row["R"] <= 2:
        return "lau_khong_mua"
    return "trung_binh"


rfm["rfm_segment"] = rfm.apply(name_rfm_segment, axis=1)
rfm_labels = rfm["rfm_segment"].astype("category").cat.codes.to_numpy()
baseline_scores = metrics_for(X_behavior, rfm_labels)
baseline_comparison = pd.DataFrame(
    [
        {
            "model": "Baseline luật RFM ngũ phân vị",
            "feature_space": "RFM + hành vi",
            **baseline_scores,
            "eligible_for_model_selection": False,
            "note": "8 phân khúc luật; đo trên cùng ma trận đặc trưng mở rộng",
        }
    ]
)
baseline_comparison.to_excel(OUT / "baseline_comparison.xlsx", index=False)

# Tinh chỉnh init K-Means tại k=4; chỉ dùng tham số có cụm nhỏ nhất >= 6.
init_rows = []
for init in ["k-means++", "random"]:
    model = KMeans(
        n_clusters=4,
        init=init,
        n_init=20,
        random_state=RANDOM_STATE,
    )
    labels = model.fit_predict(X_behavior)
    init_rows.append(
        {
            "parameter": "init",
            "value": init,
            **metrics_for(X_behavior, labels),
            "inertia": float(model.inertia_),
        }
    )
init_tuning = pd.DataFrame(init_rows)
init_valid = init_tuning[init_tuning["min_cluster_size"] >= MIN_CLUSTER_SIZE]
if init_valid.empty:
    selected_init = "k-means++"
else:
    init_ranked = rank_quality(init_valid)
    selected_init = str(
        init_ranked.sort_values(
            ["mean_metric_rank", "silhouette", "davies_bouldin"],
            ascending=[True, False, True],
        ).iloc[0]["value"]
    )

metric_rows = []
kmeans_models: dict[int, KMeans] = {}
kmeans_labels: dict[int, np.ndarray] = {}
for k in K_VALUES:
    model = KMeans(
        n_clusters=k,
        init=selected_init,
        n_init=20,
        random_state=RANDOM_STATE,
    )
    labels = model.fit_predict(X_behavior)
    kmeans_models[k] = model
    kmeans_labels[k] = labels
    metric_rows.append(
        metric_row(
            "K-Means",
            {"k": k, "init": selected_init},
            metrics_for(X_behavior, labels),
            inertia=float(model.inertia_),
        )
    )

ward_labels: dict[int, np.ndarray] = {}
for k in K_VALUES:
    labels = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(
        X_behavior
    )
    ward_labels[k] = labels
    metric_rows.append(
        metric_row(
            "Hierarchical Ward",
            {"k": k, "linkage": "ward"},
            metrics_for(X_behavior, labels),
        )
    )

# GMM: lưu cả AIC/BIC cho mọi covariance và k; chọn covariance theo BIC trong từng k.
gmm_tuning_rows = []
gmm_selected: dict[int, tuple[GaussianMixture, np.ndarray, dict]] = {}
for k in K_VALUES:
    candidates = []
    for covariance_type in ["full", "tied", "diag", "spherical"]:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = GaussianMixture(
                n_components=k,
                covariance_type=covariance_type,
                random_state=RANDOM_STATE,
                n_init=2,
                max_iter=300,
                reg_covar=1e-5,
            )
            labels = model.fit_predict(X_behavior)
        scores = metrics_for(X_behavior, labels)
        row = {
            "k": k,
            "covariance_type": covariance_type,
            **scores,
            "bic": float(model.bic(X_behavior)),
            "aic": float(model.aic(X_behavior)),
            "converged": bool(model.converged_),
            "n_iter": int(model.n_iter_),
            "warnings": " | ".join(str(w.message) for w in caught),
        }
        row["eligible"] = eligible(scores, bool(model.converged_))
        gmm_tuning_rows.append(row)
        candidates.append((model.bic(X_behavior), model, labels, row))
    _, model, labels, row = min(candidates, key=lambda x: x[0])
    gmm_selected[k] = (model, labels, row)
    metric_rows.append(
        metric_row(
            "GMM",
            {"k": k, "covariance_type": row["covariance_type"]},
            metrics_for(X_behavior, labels),
            bic=row["bic"],
            aic=row["aic"],
            converged=row["converged"],
        )
    )
gmm_tuning = pd.DataFrame(gmm_tuning_rows)

# Linkage sensitivity at k=4; Ward remains the hierarchical baseline.
linkage_rows = []
for linkage in ["ward", "complete", "average"]:
    labels = AgglomerativeClustering(n_clusters=4, linkage=linkage).fit_predict(
        X_behavior
    )
    linkage_rows.append(
        {
            "parameter": "linkage",
            "value": linkage,
            **metrics_for(X_behavior, labels),
        }
    )
linkage_tuning = pd.DataFrame(linkage_rows)

# DBSCAN eps grid is data-derived from the 5th/10th/20th-neighbor distances.
dbscan_rows = []
dbscan_labels: dict[tuple[int, float], np.ndarray] = {}
dbscan_models: dict[tuple[int, float], DBSCAN] = {}
for min_samples in [5, 10, 20]:
    nn = NearestNeighbors(n_neighbors=min_samples, metric="euclidean", n_jobs=-1)
    nn.fit(X_behavior)
    distances, _ = nn.kneighbors(X_behavior)
    kth_dist = distances[:, -1]
    eps_candidates = sorted(
        {
            round(float(np.quantile(kth_dist, q)), 8)
            for q in [0.90, 0.95, 0.98, 0.99]
        }
    )
    for eps in eps_candidates:
        model = DBSCAN(eps=eps, min_samples=min_samples, n_jobs=-1)
        labels = model.fit_predict(X_behavior)
        scores = metrics_for(X_behavior, labels, noise_label=-1)
        row = metric_row(
            "DBSCAN",
            {"eps": eps, "min_samples": min_samples},
            scores,
        )
        dbscan_rows.append(row)
        dbscan_labels[(min_samples, eps)] = labels
        dbscan_models[(min_samples, eps)] = model
dbscan_tuning = pd.DataFrame(dbscan_rows)

model_metrics = pd.DataFrame(metric_rows)
model_metrics.to_excel(OUT / "model_metrics_by_k.xlsx", index=False)
gmm_tuning.to_excel(OUT / "gmm_covariance_tuning.xlsx", index=False)
init_tuning.to_excel(OUT / "kmeans_init_tuning.xlsx", index=False)
linkage_tuning.to_excel(OUT / "hierarchical_linkage_tuning.xlsx", index=False)
dbscan_tuning.to_excel(OUT / "dbscan_parameter_tuning.xlsx", index=False)

# Compare feature spaces independently; silhouette values from different spaces
# are reported side by side but are not interpreted as directly comparable.
feature_comparison_rows = []
for space_name, X in [("RFM", X_rfm), ("RFM + hành vi", X_behavior)]:
    for k in K_VALUES:
        km_labels = (
            kmeans_labels[k]
            if space_name == "RFM + hành vi"
            else KMeans(
                n_clusters=k,
                init=selected_init,
                n_init=20,
                random_state=RANDOM_STATE,
            ).fit_predict(X)
        )
        feature_comparison_rows.append(
            {
                "feature_space": space_name,
                "algorithm": "K-Means",
                "k": k,
                **metrics_for(X, km_labels),
            }
        )
        if space_name == "RFM + hành vi":
            hi_labels = ward_labels[k]
        else:
            hi_labels = AgglomerativeClustering(
                n_clusters=k, linkage="ward"
            ).fit_predict(X)
        feature_comparison_rows.append(
            {
                "feature_space": space_name,
                "algorithm": "Hierarchical Ward",
                "k": k,
                **metrics_for(X, hi_labels),
            }
        )
feature_comparison = pd.DataFrame(feature_comparison_rows)
feature_comparison.to_excel(OUT / "feature_set_comparison.xlsx", index=False)

# One eligible candidate per model in the interpretable 3–5 cluster range.
candidate_rows = []
for algorithm in ["K-Means", "Hierarchical Ward", "GMM"]:
    subset = model_metrics[
        (model_metrics["algorithm"] == algorithm)
        & model_metrics["k"].between(3, 5)
        & model_metrics["eligible"]
    ].copy()
    if algorithm == "GMM":
        subset = subset.sort_values(["k", "bic"]).drop_duplicates("k")
    if subset.empty:
        continue
    ranked = rank_quality(subset)
    candidate_rows.append(
        ranked.sort_values(
            ["mean_metric_rank", "silhouette", "davies_bouldin"],
            ascending=[True, False, True],
        ).iloc[0]
    )
candidate_comparison = pd.DataFrame(candidate_rows)
if candidate_comparison.empty:
    fallback = model_metrics[model_metrics["eligible"]].copy()
    if fallback.empty:
        raise RuntimeError(
            "Không có cấu hình nào đạt tối thiểu 2 cụm, mỗi cụm >= 6 khách."
        )
    candidate_comparison = rank_quality(fallback).sort_values(
        ["mean_metric_rank", "silhouette", "davies_bouldin"],
        ascending=[True, False, True],
    ).groupby("algorithm", as_index=False).first()

# DBSCAN is compared only when it has 2–7 non-noise groups, no tiny group,
# and its metric is defined. Metrics exclude noise; coverage is reported.
db_valid = dbscan_tuning[dbscan_tuning["eligible"]].copy()
if not db_valid.empty:
    db_valid = rank_quality(db_valid)
    db_best = db_valid.sort_values(
        ["mean_metric_rank", "silhouette", "davies_bouldin", "coverage"],
        ascending=[True, False, True, False],
    ).iloc[0]
    candidate_comparison = pd.concat(
        [candidate_comparison, pd.DataFrame([db_best])],
        ignore_index=True,
        sort=False,
    )
else:
    db_best = None
    defined_db = dbscan_tuning[np.isfinite(dbscan_tuning["silhouette"])].copy()
    if not defined_db.empty:
        db_best = defined_db.sort_values(
            ["silhouette", "coverage", "davies_bouldin"],
            ascending=[False, False, True],
        ).iloc[0]
        db_best["selection_note"] = (
            "Không có cấu hình DBSCAN đạt điều kiện cỡ cụm tối thiểu / số cụm."
        )
    else:
        db_best = dbscan_tuning.iloc[0].copy()
        db_best["selection_note"] = "Silhouette không xác định cho các cấu hình DBSCAN."
    candidate_comparison = pd.concat(
        [candidate_comparison, pd.DataFrame([db_best])],
        ignore_index=True,
        sort=False,
    )

# Assess stability on the selected candidate for each model, using ARI against seed 42.
stability_rows = []
for _, candidate in candidate_comparison.iterrows():
    algorithm = str(candidate["algorithm"])
    k_value = candidate.get("k", np.nan)
    k = int(k_value) if pd.notna(k_value) else 0
    reference_labels = None
    for seed in REPEAT_SEEDS:
        if algorithm == "K-Means":
            labels = KMeans(
                n_clusters=k,
                init=str(candidate.get("init", selected_init)),
                n_init=20,
                random_state=seed,
            ).fit_predict(X_behavior)
        elif algorithm == "GMM":
            labels = GaussianMixture(
                n_components=k,
                covariance_type=str(candidate["covariance_type"]),
                random_state=seed,
                n_init=2,
                max_iter=300,
                reg_covar=1e-5,
            ).fit_predict(X_behavior)
        elif algorithm == "Hierarchical Ward":
            labels = AgglomerativeClustering(
                n_clusters=k, linkage="ward"
            ).fit_predict(X_behavior)
        else:
            min_samples = int(candidate["min_samples"])
            eps = float(candidate["eps"])
            labels = DBSCAN(
                eps=eps,
                min_samples=min_samples,
                n_jobs=-1,
            ).fit_predict(X_behavior)
        if seed == RANDOM_STATE:
            reference_labels = labels
            ari = 1.0
        else:
            ari = float(adjusted_rand_score(reference_labels, labels))
        stability_rows.append(
            {
                "algorithm": algorithm,
                "k": k if k else np.nan,
                "seed": seed,
                "ari_vs_seed_42": ari,
            }
        )
stability = pd.DataFrame(stability_rows)
stability_summary = (
    stability.groupby("algorithm")
    .agg(
        ari_mean=("ari_vs_seed_42", "mean"),
        ari_min=("ari_vs_seed_42", "min"),
        ari_std=("ari_vs_seed_42", "std"),
    )
    .reset_index()
)
candidate_comparison = candidate_comparison.merge(
    stability_summary, on="algorithm", how="left"
)

# Final model: among complete-assignment methods with 3–5 interpretable groups,
# require stable labels and prioritize silhouette/DB; CH remains a reported
# complementary criterion rather than deciding the model alone.
selection_pool = candidate_comparison[
    candidate_comparison["algorithm"].isin(
        ["K-Means", "Hierarchical Ward", "GMM"]
    )
].copy()
selection_pool = selection_pool[
    selection_pool["k"].between(3, 5)
    & (selection_pool["ari_mean"] >= 0.99)
    & selection_pool["eligible"].fillna(False)
]
if selection_pool.empty:
    raise RuntimeError(
        "Không có ứng viên gán đầy đủ 3–5 cụm, đủ kích thước và ARI trung bình >= 0.99."
    )
final_row = selection_pool.sort_values(
    ["silhouette", "davies_bouldin", "calinski_harabasz", "ari_mean"],
    ascending=[False, True, False, False],
).iloc[0]
final_algorithm = str(final_row["algorithm"])
final_k = int(final_row["k"])
final_init_value = final_row.get("init", selected_init)
final_init = str(final_init_value) if pd.notna(final_init_value) else selected_init
final_covariance_value = final_row.get("covariance_type", "")
final_covariance = (
    str(final_covariance_value)
    if pd.notna(final_covariance_value)
    else ""
)
final_labels = None
if final_algorithm == "K-Means":
    final_labels = kmeans_labels[final_k]
elif final_algorithm == "Hierarchical Ward":
    final_labels = ward_labels[final_k]
elif final_algorithm == "GMM":
    final_labels = gmm_selected[final_k][1]
else:
    final_min_samples = int(final_row["min_samples"])
    final_eps = float(final_row["eps"])
    final_labels = dbscan_labels[(final_min_samples, final_eps)]

clustered = features.copy()
clustered["cluster"] = final_labels
overall_medians = features[
    ["recency", "frequency", "monetary", "cancel_rate"]
].median()
profile = (
    clustered.groupby("cluster")
    .agg(
        so_khach=("customer_id", "size"),
        median_recency=("recency", "median"),
        median_frequency=("frequency", "median"),
        median_monetary=("monetary", "median"),
        median_avg_order=("avg_order", "median"),
        median_n_products=("n_products", "median"),
        median_tenure_days=("tenure_days", "median"),
        median_cancel_rate=("cancel_rate", "median"),
        tong_doanh_thu=("monetary", "sum"),
    )
    .reset_index()
)
profile["share_customers"] = profile["so_khach"] / len(clustered)
profile["share_revenue"] = profile["tong_doanh_thu"] / profile["tong_doanh_thu"].sum()
profile["ten_cum"] = "khach_trung_binh"
used_names: set[str] = set()
vip_cluster = profile.loc[profile["median_monetary"].idxmax(), "cluster"]
for i, row in profile.iterrows():
    if row["cluster"] == vip_cluster and row["median_recency"] <= overall_medians["recency"]:
        name = "khach_vip_trung_thanh"
    elif row["median_cancel_rate"] >= max(0.05, overall_medians["cancel_rate"]):
        name = "khach_rui_ro_hay_huy"
    elif (
        row["median_frequency"] <= 1
        and row["median_recency"] > overall_medians["recency"]
    ):
        name = "khach_mot_lan_roi_bo"
    elif (
        row["median_frequency"] >= overall_medians["frequency"]
        and row["median_recency"] <= overall_medians["recency"]
    ):
        name = "khach_thuong_xuyen"
    elif row["median_frequency"] >= overall_medians["frequency"]:
        name = "khach_mua_thua_thot_gia_tri_trung_binh"
    else:
        name = "khach_gia_tri_trung_binh"
    if name in used_names:
        name = f"{name}_cum_{int(row['cluster'])}"
    used_names.add(name)
    profile.loc[i, "ten_cum"] = name
name_map = dict(zip(profile["cluster"], profile["ten_cum"]))
clustered["ten_cum"] = clustered["cluster"].map(name_map)

clustered.to_excel(OUT / "customer_clusters_final.xlsx", index=False)
profile.to_excel(OUT / "cluster_profiles_final.xlsx", index=False)
candidate_comparison.to_excel(OUT / "candidate_model_comparison.xlsx", index=False)
stability.to_excel(OUT / "stability_ari_by_seed.xlsx", index=False)
stability_summary.to_excel(OUT / "stability_ari_summary.xlsx", index=False)
dbscan_tuning.to_excel(OUT / "dbscan_parameter_tuning.xlsx", index=False)

# Business profiles at the selected k for both feature spaces. Numeric cluster
# IDs are local to each fit and are not matched across spaces.
rfm_selected_labels = KMeans(
    n_clusters=final_k,
    init=selected_init,
    n_init=20,
    random_state=RANDOM_STATE,
).fit_predict(X_rfm)
feature_profile_rows = []
for space_name, labels in [
    ("RFM", rfm_selected_labels),
    ("RFM + hành vi", final_labels if final_algorithm == "K-Means" else kmeans_labels[final_k]),
]:
    comparison_frame = features.copy()
    comparison_frame["cluster"] = labels
    space_profile = (
        comparison_frame.groupby("cluster")
        .agg(
            so_khach=("customer_id", "size"),
            median_recency=("recency", "median"),
            median_frequency=("frequency", "median"),
            median_monetary=("monetary", "median"),
            median_avg_order=("avg_order", "median"),
            median_cancel_rate=("cancel_rate", "median"),
            tong_doanh_thu=("monetary", "sum"),
        )
        .reset_index()
    )
    space_profile.insert(0, "feature_space", space_name)
    feature_profile_rows.extend(space_profile.to_dict(orient="records"))
feature_set_profiles = pd.DataFrame(feature_profile_rows)
feature_set_profiles.to_excel(OUT / "feature_set_profiles.xlsx", index=False)

# Model selection figures.
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
km_curve = model_metrics[model_metrics["algorithm"] == "K-Means"].sort_values("k")
axes[0].plot(km_curve["k"], km_curve["inertia"], marker="o", label="Inertia")
axes[0].set_xlabel("Số cụm k")
axes[0].set_ylabel("Inertia")
axes[0].set_title("Elbow — K-Means")
ax2 = axes[0].twinx()
ax2.plot(
    km_curve["k"],
    km_curve["silhouette"],
    marker="s",
    color="tab:orange",
    label="Silhouette",
)
ax2.set_ylabel("Silhouette")
gmm_curve = (
    gmm_tuning[gmm_tuning["covariance_type"].isin(["full", "tied", "diag", "spherical"])]
    .sort_values(["k", "bic"])
    .drop_duplicates("k")
)
axes[1].plot(gmm_curve["k"], gmm_curve["bic"], marker="o", label="BIC")
axes[1].plot(gmm_curve["k"], gmm_curve["aic"], marker="s", label="AIC")
axes[1].set_xlabel("Số cụm k")
axes[1].set_title("GMM — BIC/AIC (covariance tốt nhất theo BIC)")
axes[1].legend()
fig.tight_layout()
fig.savefig(FIG / "model_selection.png", dpi=160)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharex=True)
for ax, algorithm in zip(axes, ["K-Means", "Hierarchical Ward"]):
    part = feature_comparison[feature_comparison["algorithm"] == algorithm]
    for space in ["RFM", "RFM + hành vi"]:
        subset = part[part["feature_space"] == space]
        ax.plot(subset["k"], subset["silhouette"], marker="o", label=space)
    ax.set_title(algorithm)
    ax.set_xlabel("Số cụm k")
    ax.set_ylabel("Silhouette trong không gian tương ứng")
    ax.legend()
fig.suptitle("So sánh bộ đặc trưng — đọc riêng từng không gian")
fig.tight_layout()
fig.savefig(FIG / "feature_space_comparison.png", dpi=160)
plt.close(fig)

sample_idx = np.arange(len(X_behavior))
if len(sample_idx) > 3500:
    rng = np.random.default_rng(RANDOM_STATE)
    sample_idx = np.sort(rng.choice(sample_idx, size=3500, replace=False))
pca = PCA(n_components=2, random_state=RANDOM_STATE)
xy = pca.fit_transform(X_behavior[sample_idx])
plot_labels = np.asarray(final_labels)[sample_idx]
fig, ax = plt.subplots(figsize=(8, 6))
for cluster_id in sorted(np.unique(plot_labels)):
    mask = plot_labels == cluster_id
    ax.scatter(
        xy[mask, 0],
        xy[mask, 1],
        s=12,
        alpha=0.55,
        label=f"Cụm {cluster_id}",
    )
ax.set_xlabel(f"PCA 1 ({pca.explained_variance_ratio_[0]:.1%})")
ax.set_ylabel(f"PCA 2 ({pca.explained_variance_ratio_[1]:.1%})")
ax.set_title(f"{final_algorithm} — k={final_k} (mẫu tối đa 3.500 khách)")
ax.legend(fontsize=8, markerscale=1.5)
fig.tight_layout()
fig.savefig(FIG / "final_clusters_pca.png", dpi=160)
plt.close(fig)


def fmt(value, digits: int = 3) -> str:
    return "—" if pd.isna(value) else f"{float(value):.{digits}f}"


def add_table(doc: Document, frame: pd.DataFrame, columns: list[str], formats=None):
    table = doc.add_table(rows=1, cols=len(columns))
    table.style = "Table Grid"
    for cell, label in zip(table.rows[0].cells, columns):
        cell.text = str(label)
    formats = formats or {}
    for _, row in frame.iterrows():
        cells = table.add_row().cells
        for cell, col in zip(cells, columns):
            value = row.get(col, "")
            if col in formats and pd.notna(value):
                value = formats[col](value)
            elif isinstance(value, (float, np.floating)):
                value = fmt(value)
            cell.text = str(value)
    return table


doc = Document()
normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(12)
normal._element.rPr.rFonts.set(
    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia",
    "Times New Roman",
)
for style_name in ["Heading 1", "Heading 2", "Heading 3", "Caption"]:
    style = doc.styles[style_name]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)
    style._element.rPr.rFonts.set(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia",
        "Times New Roman",
    )

doc.add_heading("3.3. Xây dựng đặc trưng RFM và hành vi", level=2)
doc.add_paragraph(
    f"Bảng đặc trưng đầu vào có {len(features):,} khách hàng và {len(features.columns)} cột "
    "(bao gồm mã khách và quốc gia). Ba biến RFM là recency, frequency và monetary. "
    "Bảng đã có giá trị đơn trung bình (avg_order), số mã hàng khác nhau (n_products), "
    "tenure_days, cancel_value, cancel_invoices và cancel_rate."
)
doc.add_paragraph(
    "Bổ sung hai biến tính được từ bảng hiện có: (i) avg_interpurchase_days = "
    "tenure_days/(frequency−1) với khách có từ hai hóa đơn mua, đặt bằng 0 khi chỉ có "
    "một hóa đơn (frequency vẫn giữ để phân biệt trường hợp này); (ii) cancel_invoice_share "
    "= cancel_invoices/(frequency + cancel_invoices). Đây là tỷ trọng hóa đơn hủy theo "
    "số hóa đơn, không phải tỷ lệ hoàn trả theo đơn vị hàng. cancel_rate hiện có là tỷ trọng "
    "giá trị hủy."
)
doc.add_paragraph(
    "Không thể tính số lượng trung bình mỗi đơn hoặc tỷ lệ hoàn trả theo số lượng/dòng hàng: "
    "customer_features.xlsx không chứa Quantity mua, lượng trả, hoặc số dòng hóa đơn. "
    "Muốn tính đúng các chỉ số này cần dữ liệu giao dịch gốc và quy tắc ghép giao dịch hoàn trả."
)
doc.add_paragraph("Bảng 3.1. Đối chiếu đặc trưng theo đề cương")
add_table(
    doc,
    feature_audit,
    ["feature", "status", "formula_or_definition", "note"],
)

doc.add_heading("3.4. Thiết kế thực nghiệm", level=2)
doc.add_paragraph(
    f"Các biến số không âm có skewness ban đầu lớn hơn 1 được biến đổi log1p "
    f"({', '.join(log_features) if log_features else 'không có biến nào'}); "
    "sau đó StandardScaler được fit riêng cho không gian RFM và RFM + hành vi. "
    "customer_id và country chỉ dùng nhận dạng/diễn giải, không đưa vào khoảng cách."
)
doc.add_paragraph(
    "Trên cùng ma trận RFM + hành vi, K-Means và Hierarchical Ward được khảo sát với "
    "k=2..7; GMM thử covariance_type ∈ {full, tied, diag, spherical} và k=2..7, "
    "ghi nhận thêm AIC/BIC; DBSCAN dò eps từ phân vị khoảng cách láng giềng gần nhất "
    "với min_samples ∈ {5, 10, 20}. Tinh chỉnh riêng init của K-Means tại k=4 và linkage "
    "(ward, complete, average) tại k=4. Cấu hình có cụm nhỏ nhất dưới 6 khách bị đánh dấu "
    "không đủ điều kiện chọn mô hình."
)
average_link = linkage_tuning[linkage_tuning["value"] == "average"].iloc[0]
if int(average_link["min_cluster_size"]) < MIN_CLUSTER_SIZE:
    doc.add_paragraph(
        f"Trong thử nghiệm linkage tại k=4, average cho Silhouette "
        f"{fmt(average_link['silhouette'], 4)} nhưng cụm nhỏ nhất chỉ có "
        f"{int(average_link['min_cluster_size'])} khách, nên bị loại khỏi lựa chọn "
        "theo ngưỡng đã đặt trước."
    )
doc.add_paragraph(
    f"Silhouette được ước lượng trên mẫu cố định tối đa {SILHOUETTE_SAMPLE:,} khách "
    "(seed=42) để giảm chi phí tính toán; Davies–Bouldin và Calinski–Harabasz dùng toàn bộ "
    "khách được gán cụm. Với DBSCAN, ba chỉ số tính trên điểm không nhiễu và báo cáo thêm "
    "coverage/noise. Baseline luật RFM ngũ phân vị được chấm trên cùng không gian mở rộng. "
    "Độ ổn định được kiểm tra bằng ARI so với seed 42 trên bảy seed."
)
doc.add_paragraph("Bảng 3.2. Skewness trước và sau biến đổi")
add_table(
    doc,
    skewness,
    ["feature", "skew_before", "transformation", "skew_after"],
)

doc.add_heading("4.2. So sánh mô hình và lựa chọn", level=2)
doc.add_paragraph(
    "Bảng 4.1 so sánh baseline luật RFM với đại diện đủ điều kiện của K-Means, Ward và "
    "GMM trong khoảng 3–5 cụm; DBSCAN là kết quả mở rộng. Với ba thuật toán gán nhãn đầy "
    "đủ, xếp hạng lựa chọn xem đồng thời Silhouette, Davies–Bouldin, Calinski–Harabasz và "
    "độ ổn định; không chọn theo một chỉ số đơn lẻ. Covariance của GMM được chọn theo BIC "
    "trong từng k. Kết quả DBSCAN phải đọc cùng coverage vì chỉ số loại điểm nhiễu; do đó "
    "không xếp hạng trực tiếp cùng mô hình gán nhãn toàn bộ."
)
comparison_rows = [
    {
        "model": row["algorithm"],
        "k": row.get("k", np.nan),
        "silhouette": row.get("silhouette", np.nan),
        "davies_bouldin": row.get("davies_bouldin", np.nan),
        "calinski_harabasz": row.get("calinski_harabasz", np.nan),
        "min_cluster_size": row.get("min_cluster_size", np.nan),
        "ari_mean": row.get("ari_mean", np.nan),
        "bic": row.get("bic", np.nan),
    }
    for _, row in candidate_comparison.iterrows()
]
comparison_rows.append(
    {
        "model": "Baseline luật RFM ngũ phân vị",
        "k": baseline_scores["n_clusters"],
        "silhouette": baseline_scores["silhouette"],
        "davies_bouldin": baseline_scores["davies_bouldin"],
        "calinski_harabasz": baseline_scores["calinski_harabasz"],
        "min_cluster_size": baseline_scores["min_cluster_size"],
        "ari_mean": np.nan,
        "bic": np.nan,
    }
)
comparison_doc = pd.DataFrame(comparison_rows)
doc.add_paragraph("Bảng 4.1. So sánh mô hình trên không gian RFM + hành vi")
add_table(
    doc,
    comparison_doc,
    [
        "model",
        "k",
        "silhouette",
        "davies_bouldin",
        "calinski_harabasz",
        "min_cluster_size",
        "ari_mean",
        "bic",
    ],
    formats={
        "silhouette": lambda x: fmt(x, 4),
        "davies_bouldin": lambda x: fmt(x, 4),
        "calinski_harabasz": lambda x: fmt(x, 1),
        "ari_mean": lambda x: fmt(x, 3),
        "bic": lambda x: fmt(x, 1),
    },
)
doc.add_paragraph(
    f"Trong các phương pháp gán nhãn đầy đủ có 3–5 cụm, đủ kích thước và ARI trung bình "
    f"ít nhất 0,99, mô hình được chọn là {final_algorithm} (k={final_k}"
    f"{', covariance_type=' + final_covariance if final_covariance else ''}"
    f"{', init=' + final_init if final_algorithm == 'K-Means' else ''}). "
    f"Cụm nhỏ nhất có {int(profile['so_khach'].min())} khách; ARI trung bình qua các seed "
    f"là {fmt(float(final_row['ari_mean']), 3)}. Kết quả có {len(profile)} cụm, "
    "cần diễn giải cùng quy mô và hồ sơ cụm, không chỉ dựa vào điểm số."
)
km_k2 = model_metrics[
    (model_metrics["algorithm"] == "K-Means") & (model_metrics["k"] == 2)
].iloc[0]
doc.add_paragraph(
    f"K-Means k=2 có Silhouette {fmt(km_k2['silhouette'], 4)} cao hơn, nhưng chỉ tạo "
    "hai nhóm lớn; để có phân khúc hành động chi tiết hơn, k được chọn trong khoảng 3–5. "
    f"Mô hình cuối {final_algorithm} k={final_k} đạt Silhouette "
    f"{fmt(final_row['silhouette'], 4)}, "
    f"Davies–Bouldin {fmt(final_row['davies_bouldin'], 4)} và Calinski–Harabasz "
    f"{fmt(final_row['calinski_harabasz'], 1)}. Cấu hình có cụm nhỏ nhất "
    f"{int(profile['so_khach'].min())} khách, không rơi vào trường hợp cụm 1–5 khách."
)
if db_best is not None:
    doc.add_paragraph(
        f"DBSCAN cho Silhouette {fmt(db_best.get('silhouette', np.nan), 4)} trên "
        f"{float(db_best.get('coverage', 0)):.1%} điểm được gán (loại "
        f"{int(db_best.get('noise_count', 0))} điểm nhiễu), với "
        f"{int(db_best.get('n_clusters', 0))} cụm và cụm nhỏ nhất "
        f"{int(db_best.get('min_cluster_size', 0))} khách. Vì chỉ số DBSCAN loại nhiễu "
        "nên không xếp hạng trực tiếp cùng mô hình gán nhãn toàn bộ; kết quả dùng như "
        "phân tích mở rộng, không phải lý do duy nhất để chọn mô hình cuối."
    )
gmm_best = candidate_comparison[candidate_comparison["algorithm"] == "GMM"]
if not gmm_best.empty:
    row = gmm_best.iloc[0]
    doc.add_paragraph(
        f"Với GMM tại k={int(row['k'])}, covariance_type={row['covariance_type']} có "
        f"BIC {fmt(row['bic'], 1)} và AIC {fmt(row['aic'], 1)}. BIC/AIC chỉ dùng so sánh "
        "cấu hình GMM trên cùng dữ liệu và số biến; không đối chiếu trực tiếp với K-Means."
    )
doc.add_paragraph(
    "Bảng 4.2. Hồ sơ cụm của mô hình được chọn "
    "(giá trị trung vị; doanh thu và tỷ trọng tính từ bảng đặc trưng)"
)
add_table(
    doc,
    profile.sort_values("cluster"),
    [
        "cluster",
        "ten_cum",
        "so_khach",
        "median_recency",
        "median_frequency",
        "median_monetary",
        "median_cancel_rate",
        "share_revenue",
    ],
    formats={"share_revenue": lambda x: f"{float(x):.1%}"},
)
doc.add_paragraph(
    f"Bảng 4.3. Hồ sơ kinh doanh tại k={final_k} theo bộ đặc trưng "
    "(nhãn cụm là cục bộ, không ghép theo số cụm giữa hai không gian)"
)
add_table(
    doc,
    feature_set_profiles.sort_values(["feature_space", "cluster"]),
    [
        "feature_space",
        "cluster",
        "so_khach",
        "median_recency",
        "median_frequency",
        "median_monetary",
        "median_avg_order",
        "median_cancel_rate",
    ],
)
doc.add_paragraph(
    "Không so sánh trực tiếp Silhouette giữa RFM và RFM + hành vi vì số chiều và hình học "
    "không gian khác nhau; đối chiếu thêm kích thước và hồ sơ kinh doanh trong bảng trên."
)
doc.add_paragraph(
    "Bảng 4.4. ARI theo seed so với seed 42"
)
add_table(
    doc,
    stability_summary,
    ["algorithm", "ari_mean", "ari_min", "ari_std"],
    formats={
        "ari_mean": lambda x: fmt(x, 3),
        "ari_min": lambda x: fmt(x, 3),
        "ari_std": lambda x: fmt(x, 3),
    },
)

for caption, image_path, width in [
    ("Hình 4.1. Elbow K-Means và BIC/AIC của GMM", FIG / "model_selection.png", 6.2),
    ("Hình 4.2. Silhouette theo không gian đặc trưng (không so trực tiếp giữa hai không gian)", FIG / "feature_space_comparison.png", 6.2),
    ("Hình 4.3. Chiếu PCA hai chiều của mô hình được chọn", FIG / "final_clusters_pca.png", 5.8),
]:
    doc.add_picture(str(image_path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph(caption)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER

# Keep the requested report outside the source repository with other artifacts.
docx_path = ARTIFACT_ROOT / "bao_cao_3.3_3.4_4.2_Vu_Thuy_Nhung.docx"
# Capture existing report artifacts before using them to explain discrepancies.
legacy_comparison_path = OUT / "cluster_algorithm_comparison.xlsx"
legacy_k4 = None
if legacy_comparison_path.is_file():
    legacy_comparison = pd.read_excel(legacy_comparison_path)
    legacy_rows = legacy_comparison[legacy_comparison["k"] == 4]
    if not legacy_rows.empty:
        legacy_k4 = legacy_rows.iloc[0].to_dict()
legacy_profile_path = OUT / "cluster_summary_k4.xlsx"
legacy_profile = (
    pd.read_excel(legacy_profile_path).to_dict(orient="records")
    if legacy_profile_path.is_file()
    else []
)
legacy_profile_text = ", ".join(
    f"{row.get('ten_cum', row.get('cluster', ''))}: {int(row['so_khach'])}"
    for row in legacy_profile
)
doc.add_paragraph(
    "Đối chiếu với bộ kết quả k=4 đã có trước phân tích này: "
    + (
        f"bảng cũ ghi K-Means k=4 với Silhouette {float(legacy_k4['kmeans_silhouette']):.4f} "
        f"và Davies–Bouldin {float(legacy_k4['kmeans_db']):.4f}; báo cáo cũ còn dùng "
        f"các quy mô cụm {legacy_profile_text}. "
        if legacy_k4 is not None
        else "không tìm thấy bảng so sánh k=4 trước đó để đối chiếu. "
    )
    + f"Những số liệu này thuộc ma trận cũ; phân tích hiện tại thêm hai biến suy ra và "
    f"biến đổi log1p theo skewness, nên không thể giữ đồng thời. Kết quả mới chọn "
    f"{final_algorithm} k={final_k}; cần thay các số và tên cụm cũ ở mục 3.3, 3.4, "
    "4.2–4.4 và 5.1 của báo cáo chính."
)
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(12)
                    run._element.get_or_add_rPr().rFonts.set(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia",
                        "Times New Roman",
                    )
doc.save(docx_path)

# Save a concise summary for the Markdown report update and final verification.
summary = {
    "n_customers": int(len(features)),
    "n_features_behavior": int(len(all_features)),
    "log1p_features": log_features,
    "final_algorithm": final_algorithm,
    "final_k": final_k,
    "final_covariance_type": final_covariance,
    "final_init": final_init,
    "final_silhouette": float(final_row["silhouette"]),
    "final_davies_bouldin": float(final_row["davies_bouldin"]),
    "final_calinski_harabasz": float(final_row["calinski_harabasz"]),
    "min_cluster_size": int(profile["so_khach"].min()),
    "stability_ari_mean": float(final_row["ari_mean"]),
    "profile": profile.to_dict(orient="records"),
    "candidate_comparison": candidate_comparison.to_dict(orient="records"),
    "baseline": baseline_scores,
    "legacy_k4_metrics": legacy_k4,
    "legacy_k4_profile": legacy_profile,
}
(ARTIFACT_ROOT / "analysis_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, default=float),
    encoding="utf-8",
)

print("Khách hàng:", len(features))
print("Đặc trưng log1p:", ", ".join(log_features))
print("Tuning init:", init_tuning[["value", "silhouette", "davies_bouldin", "min_cluster_size"]].to_string(index=False))
print("So sánh mô hình:")
print(candidate_comparison[["algorithm", "k", "silhouette", "davies_bouldin", "calinski_harabasz", "min_cluster_size", "ari_mean", "bic"]].to_string(index=False))
print("Mô hình cuối:", final_algorithm, "k=", final_k, "profile smallest=", int(profile["so_khach"].min()))
print("Hồ sơ cụm:")
print(profile[["cluster", "ten_cum", "so_khach", "median_recency", "median_frequency", "median_monetary", "median_cancel_rate", "share_revenue"]].to_string(index=False))
print("Đã lưu DOCX:", docx_path)

# NOTEBOOK BUILDER ONLY: excluded from the notebook cell when embedding this source.
notebook_source = Path(__file__).read_text(encoding="utf-8").split(
    "# NOTEBOOK BUILDER ONLY:"
)[0]
notebook = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Phân khúc khách hàng Online Retail II — phần thực nghiệm Thùy Nhung\n\n",
                "Đọc bảng đã làm sạch tại `outputs/customer_features.xlsx` trong repo; chạy cell dưới để tái tạo các bảng Excel trong `outputs/` và hình trong `figures/`; báo cáo Word lưu ngoài repo trong `~/Downloads/OnlineRetailII_artifacts`. Có thể đặt `RETAIL_OUTPUTS_DIR` để đổi thư mục Excel. Không chạy lại làm sạch/EDA.\n\n",
                "Giới hạn: số lượng trung bình mỗi đơn và tỷ lệ hoàn trả theo lượng/dòng cần giao dịch gốc; khoảng cách ngày giữa các hóa đơn suy ra được từ `tenure_days / (frequency - 1)`.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": notebook_source.splitlines(keepends=True),
        },
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
(ROOT / "online_retail_clustering.ipynb").write_text(
    json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
    encoding="utf-8",
)
