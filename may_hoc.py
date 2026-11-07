import duckdb

con = duckdb.connect(r"C:\Users\nguye\Downloads\online-retail-ii\retail.duckdb")
con.execute("INSTALL excel;")
con.execute("LOAD excel;")

xlsx = "C:/Users/nguye/Downloads/online+retail+ii/online_retail_II.xlsx"

con.execute(f"""
    CREATE OR REPLACE TABLE retail AS
    SELECT
        Invoice AS invoice,
        StockCode AS stock_code,
        NULLIF(Description, '') AS description,
        TRY_CAST(Quantity AS INTEGER) AS quantity,
        CAST('1899-12-30' AS TIMESTAMP)
            + TRY_CAST(InvoiceDate AS DOUBLE) * INTERVAL 1 DAY AS invoice_date,
        TRY_CAST(Price AS DOUBLE) AS price,
        TRY_CAST(NULLIF(TRIM("Customer ID"), '') AS BIGINT) AS customer_id,
        Country AS country
    FROM (
        SELECT * FROM read_xlsx('{xlsx}', sheet = 'Year 2009-2010', all_varchar = true)
        UNION ALL
        SELECT * FROM read_xlsx('{xlsx}', sheet = 'Year 2010-2011', all_varchar = true)
    )
""")

print(con.execute("SELECT COUNT(*) AS raw_rows FROM retail").df())
print(con.execute("SELECT * FROM retail LIMIT 5").df())

print(con.execute("""
    SELECT COUNT(*) AS missing_customer
    FROM retail
    WHERE customer_id IS NULL
""").df())

print(con.execute("""
    SELECT COUNT(*) AS cancel_invoice
    FROM retail
    WHERE invoice LIKE 'C%'
""").df())

print(con.execute("""
    SELECT COUNT(*) AS negative_qty
    FROM retail
    WHERE quantity < 0
""").df())

print(con.execute("""
    SELECT COUNT(*) AS bad_price
    FROM retail
    WHERE price <= 0
""").df())

print(con.execute("""
    SELECT SUM(n - 1) AS extra_duplicate_rows
    FROM (
        SELECT COUNT(*) AS n
        FROM retail
        GROUP BY invoice, stock_code, description, quantity, invoice_date, price, customer_id, country
        HAVING COUNT(*) > 1
    )
""").df())

print(con.execute("""
    SELECT UPPER(stock_code) AS stock_code, COUNT(*) AS n
    FROM retail
    WHERE UPPER(stock_code) IN ('POST', 'DOT', 'M', 'D', 'S', 'B')
    GROUP BY UPPER(stock_code)
    ORDER BY n DESC
""").df())

con.execute("""
    CREATE OR REPLACE TABLE purchases AS
    SELECT DISTINCT
        invoice,
        stock_code,
        description,
        quantity,
        invoice_date,
        price,
        customer_id,
        country,
        quantity * price AS line_revenue
    FROM retail
    WHERE customer_id IS NOT NULL
      AND quantity > 0
      AND price > 0
      AND invoice NOT LIKE 'C%'
      AND UPPER(stock_code) NOT IN ('POST', 'DOT', 'M', 'D', 'S', 'B')
""")

con.execute("""
    CREATE OR REPLACE TABLE cancellations AS
    SELECT DISTINCT
        invoice,
        stock_code,
        quantity,
        invoice_date,
        price,
        customer_id
    FROM retail
    WHERE customer_id IS NOT NULL
      AND (invoice LIKE 'C%' OR quantity < 0)
""")

print(con.execute("""
    SELECT
        (SELECT COUNT(*) FROM retail) AS raw_rows,
        (SELECT COUNT(*) FROM purchases) AS purchase_rows,
        (SELECT COUNT(*) FROM cancellations) AS cancel_rows
""").df())
print(con.execute("SHOW TABLES").df())
print(con.execute("SELECT * FROM purchases LIMIT 5").df())
print(con.execute("SELECT * FROM cancellations LIMIT 5").df())

# EDA trên bảng purchases
print(con.execute("""
    SELECT
        COUNT(*) AS sum_rows,
        COUNT(DISTINCT customer_id) AS so_khach,
        COUNT(DISTINCT invoice) AS so_hoa_don,
        COUNT(DISTINCT stock_code) AS so_ma_hang,
        MIN(invoice_date) AS ngay_dau,
        MAX(invoice_date) AS ngay_cuoi,
        ROUND(SUM(line_revenue), 2) AS tong_doanh_thu
    FROM purchases
""").df())

print(con.execute("""
    SELECT
        STRFTIME(invoice_date, '%Y-%m') AS thang,
        COUNT(DISTINCT invoice) AS hoa_don_thang,
        ROUND(SUM(line_revenue), 2) AS doanh_thu_thang
    FROM purchases
    GROUP BY thang
    ORDER BY thang
""").df())

print(con.execute("""
    SELECT
        country,
        COUNT(DISTINCT customer_id) AS so_khach_qg,
        ROUND(SUM(line_revenue), 2) AS doanh_thu_qg
    FROM purchases
    GROUP BY country
    ORDER BY doanh_thu_qg DESC
""").df())

print(con.execute("""
    SELECT
        MIN(quantity) AS min_qty,
        MEDIAN(quantity) AS median_qty,
        QUANTILE_CONT(quantity, 0.95) AS p95_qty,
        MAX(quantity) AS max_qty,
        MIN(price) AS min_price,
        MEDIAN(price) AS median_price,
        QUANTILE_CONT(price, 0.95) AS p95_price,
        MAX(price) AS max_price,
        MIN(line_revenue) AS min_revenue,
        MEDIAN(line_revenue) AS median_revenue,
        QUANTILE_CONT(line_revenue, 0.95) AS p95_revenue,
        MAX(line_revenue) AS max_revenue
    FROM purchases
""").df())

print(con.execute("""
    SELECT 
        COUNT(*) AS tong_dong,
        COUNT( DISTINCT customer_id) AS so_khach,
        COUNT( DISTINCT invoice) AS so_hoa_don,
        COUNT( DISTINCT stock_code) AS so_ma_hang, 
        MIN( invoice_date) AS ngay_dau,
        MAX( invoice_date) AS ngay_cuoi,
        SUM(ABS(quantity)*price) AS tong_huy
    FROM cancellations

""").df())

print(con.execute("""
    SELECT 
        STRFTIME(invoice_date, '%Y-%m') AS thang,
        SUM(ABS(quantity)*price) AS huy_thang,
        COUNT( DISTINCT invoice) AS hoa_don_thang
    FROM cancellations
    GROUP BY thang
    ORDER BY thang
    
""").df())

print(con.execute("""
    SELECT
        stock_code,
        COUNT(invoice) AS dong_huy,
        SUM(ABS(quantity)*price) AS tong_huy_ma
    FROM cancellations
    GROUP BY stock_code
    ORDER BY SUM(ABS(quantity)*price) DESC
    LIMIT 10
    
""").df())

print(con.execute("""
    SELECT 
        MIN(ABS(quantity)) AS gtnn_quantity,
        MAX(ABS(quantity)) AS gtln_quantity,
        MEDIAN(ABS(quantity)) AS trung_vi_quantity,
        QUANTILE_CONT(ABS(quantity),0.95) AS phan_vi_quantity,
        MIN(price) AS gtnn_price,
        MAX(price) AS gtln_price,
        MEDIAN(price) AS trung_vi_price,
        QUANTILE_CONT(price,0.95) AS phan_vi_price,
        MIN(ABS(quantity)*price) AS gtnn_gtri_huy,
        MAX(ABS(quantity)*price) AS gtln_gtri_huy,
        MEDIAN(ABS(quantity)*price) AS trung_vi_gtri_huy,
        QUANTILE_CONT(ABS(quantity)*price, 0.95) AS phan_vi_gtri_huy
    FROM cancellations    
""").df())

# ---------------------------------------------------------------------------
# Bước tiếp: bảng đặc trưng khách hàng + K-means
# ---------------------------------------------------------------------------
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

SNAPSHOT = "2011-12-10"
OUT_DIR = Path(r"C:\Users\nguye\OneDrive\Pictures\Documents")

con.execute(f"""
    CREATE OR REPLACE TABLE customer_features AS
    WITH purchase_agg AS (
        SELECT
            customer_id,
            DATE_DIFF('day', MAX(invoice_date), TIMESTAMP '{SNAPSHOT}') AS recency,
            COUNT(DISTINCT invoice) AS frequency,
            ROUND(SUM(line_revenue), 2) AS monetary,
            ROUND(SUM(line_revenue) / COUNT(DISTINCT invoice), 2) AS avg_order,
            COUNT(DISTINCT stock_code) AS n_products,
            DATE_DIFF('day', MIN(invoice_date), MAX(invoice_date)) AS tenure_days,
            MODE(country) AS country
        FROM purchases
        GROUP BY customer_id
    ),
    cancel_agg AS (
        SELECT
            customer_id,
            ROUND(SUM(ABS(quantity) * price), 2) AS cancel_value,
            COUNT(DISTINCT invoice) AS cancel_invoices
        FROM cancellations
        GROUP BY customer_id
    )
    SELECT
        p.customer_id,
        p.recency,
        p.frequency,
        p.monetary,
        p.avg_order,
        p.n_products,
        p.tenure_days,
        COALESCE(c.cancel_value, 0) AS cancel_value,
        COALESCE(c.cancel_invoices, 0) AS cancel_invoices,
        ROUND(
            COALESCE(c.cancel_value, 0)
            / NULLIF(p.monetary + COALESCE(c.cancel_value, 0), 0),
            4
        ) AS cancel_rate,
        p.country
    FROM purchase_agg p
    LEFT JOIN cancel_agg c USING (customer_id)
""")

print(con.execute("""
    SELECT
        COUNT(*) AS so_khach,
        ROUND(AVG(recency), 1) AS avg_recency,
        ROUND(AVG(frequency), 1) AS avg_frequency,
        ROUND(AVG(monetary), 1) AS avg_monetary,
        ROUND(AVG(cancel_rate), 4) AS avg_cancel_rate
    FROM customer_features
""").df())
print(con.execute("SELECT * FROM customer_features LIMIT 5").df())

features = con.execute("""
    SELECT
        customer_id,
        recency,
        frequency,
        monetary,
        avg_order,
        n_products,
        tenure_days,
        cancel_value,
        cancel_invoices,
        cancel_rate,
        country
    FROM customer_features
    ORDER BY customer_id
""").df()

# Log giúp kéo doanh thu / tần suất / hủy về dạng bớt lệch
log_cols = ["frequency", "monetary", "avg_order", "n_products", "cancel_value", "cancel_invoices"]
X = features[["recency", "tenure_days", "cancel_rate"] + log_cols].copy()
for col in log_cols:
    X[col] = np.log1p(X[col])

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

def summarize_clusters(df):
    stats = (
        df.groupby("cluster")
        .agg(
            so_khach=("customer_id", "count"),
            median_recency=("recency", "median"),
            median_frequency=("frequency", "median"),
            median_monetary=("monetary", "median"),
            median_cancel_rate=("cancel_rate", "median"),
            tong_doanh_thu=("monetary", "sum"),
        )
        .reset_index()
    )
    return stats


silhouette_rows = []
for k in range(2, 8):
    labels = KMeans(n_clusters=k, random_state=42, n_init=20).fit_predict(X_scaled)
    score = silhouette_score(X_scaled, labels)
    silhouette_rows.append({"k": k, "silhouette": round(score, 4)})
    print(f"k={k} silhouette={score:.4f}")

print(pd.DataFrame(silhouette_rows))
# Silhouette cao nhất ở k=2; k=4 dùng để diễn giải nghiệp vụ chi tiết hơn
print("Dùng k=2 (best silhouette) và k=4 (phân khúc chi tiết)")

# Tên cố định theo kết quả đã kiểm tra với random_state=42
NAMES_K2 = {
    0: "khach_tich_cuc_gia_tri_cao",
    1: "khach_it_mua_lau_khong_quay_lai",
}
NAMES_K4 = {
    0: "khach_mot_lan_roi_bo",
    1: "khach_thuong_xuyen",
    2: "khach_vip_trung_thanh",
    3: "khach_rui_ro_hay_huy",
}

clusters_k2 = features.copy()
clusters_k2["cluster"] = KMeans(n_clusters=2, random_state=42, n_init=20).fit_predict(X_scaled)
clusters_k2["ten_cum"] = clusters_k2["cluster"].map(NAMES_K2)
summary_k2 = summarize_clusters(clusters_k2)
summary_k2["ten_cum"] = summary_k2["cluster"].map(NAMES_K2)

clusters_k4 = features.copy()
clusters_k4["cluster"] = KMeans(n_clusters=4, random_state=42, n_init=20).fit_predict(X_scaled)
clusters_k4["ten_cum"] = clusters_k4["cluster"].map(NAMES_K4)
summary_k4 = summarize_clusters(clusters_k4)
summary_k4["ten_cum"] = summary_k4["cluster"].map(NAMES_K4)

con.register("clusters_k2_df", clusters_k2)
con.execute("CREATE OR REPLACE TABLE customer_clusters AS SELECT * FROM clusters_k2_df")
con.register("clusters_k4_df", clusters_k4)
con.execute("CREATE OR REPLACE TABLE customer_clusters_k4 AS SELECT * FROM clusters_k4_df")

print("\n=== Tóm tắt k=2 ===")
print(summary_k2.sort_values("so_khach", ascending=False).to_string(index=False))
print("\n=== Tóm tắt k=4 ===")
print(summary_k4.sort_values("tong_doanh_thu", ascending=False).to_string(index=False))
print("\n=== Trung vị k=4 ===")
print(
    clusters_k4.groupby(["cluster", "ten_cum"])[
        ["recency", "frequency", "monetary", "avg_order", "n_products", "tenure_days", "cancel_rate"]
    ]
    .median()
    .round(2)
    .reset_index()
    .to_string(index=False)
)

feat_path = OUT_DIR / "customer_features.xlsx"
cluster_path = OUT_DIR / "customer_clusters.xlsx"
summary_path = OUT_DIR / "cluster_summary.xlsx"
cluster_k4_path = OUT_DIR / "customer_clusters_k4.xlsx"
summary_k4_path = OUT_DIR / "cluster_summary_k4.xlsx"

features.to_excel(feat_path, index=False)
clusters_k2.to_excel(cluster_path, index=False)
summary_k2.to_excel(summary_path, index=False)
clusters_k4.to_excel(cluster_k4_path, index=False)
summary_k4.to_excel(summary_k4_path, index=False)
print(
    f"\nĐã lưu:\n- {feat_path}\n- {cluster_path}\n- {summary_path}"
    f"\n- {cluster_k4_path}\n- {summary_k4_path}"
)

# ---------------------------------------------------------------------------
# PCA 2D + dự đoán khách còn mua lại (90 ngày sau 2011-09-01)
# ---------------------------------------------------------------------------
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split

pca = PCA(n_components=2, random_state=42)
pca_xy = pca.fit_transform(X_scaled)
clusters_k4 = clusters_k4.copy()
clusters_k4["pca1"] = pca_xy[:, 0]
clusters_k4["pca2"] = pca_xy[:, 1]
print(
    f"PCA explained variance: "
    f"{pca.explained_variance_ratio_[0]:.3f}, {pca.explained_variance_ratio_[1]:.3f} "
    f"(tổng {pca.explained_variance_ratio_.sum():.3f})"
)

fig, ax = plt.subplots(figsize=(8, 6))
for cluster_id, name in NAMES_K4.items():
    part = clusters_k4[clusters_k4["cluster"] == cluster_id]
    ax.scatter(part["pca1"], part["pca2"], s=12, alpha=0.55, label=name)
ax.set_xlabel("PCA 1")
ax.set_ylabel("PCA 2")
ax.set_title("K-means k=4 trên mặt phẳng PCA")
ax.legend(fontsize=8, markerscale=2)
fig.tight_layout()
pca_path = OUT_DIR / "pca_clusters_k4.png"
fig.savefig(pca_path, dpi=150)
plt.close(fig)
print(f"Đã lưu PCA: {pca_path}")

CUTOFF = "2011-09-01"
HORIZON_DAYS = 90

con.execute(f"""
    CREATE OR REPLACE TABLE repurchase_dataset AS
    WITH buyers AS (
        SELECT DISTINCT customer_id
        FROM purchases
        WHERE invoice_date < TIMESTAMP '{CUTOFF}'
    ),
    feat AS (
        SELECT
            p.customer_id,
            DATE_DIFF('day', MAX(p.invoice_date), TIMESTAMP '{CUTOFF}') AS recency,
            COUNT(DISTINCT p.invoice) AS frequency,
            ROUND(SUM(p.line_revenue), 2) AS monetary,
            ROUND(SUM(p.line_revenue) / COUNT(DISTINCT p.invoice), 2) AS avg_order,
            COUNT(DISTINCT p.stock_code) AS n_products,
            DATE_DIFF('day', MIN(p.invoice_date), MAX(p.invoice_date)) AS tenure_days
        FROM purchases p
        INNER JOIN buyers b USING (customer_id)
        WHERE p.invoice_date < TIMESTAMP '{CUTOFF}'
        GROUP BY p.customer_id
    ),
    cancel_feat AS (
        SELECT
            c.customer_id,
            ROUND(SUM(ABS(c.quantity) * c.price), 2) AS cancel_value,
            COUNT(DISTINCT c.invoice) AS cancel_invoices
        FROM cancellations c
        INNER JOIN buyers b USING (customer_id)
        WHERE c.invoice_date < TIMESTAMP '{CUTOFF}'
        GROUP BY c.customer_id
    ),
    labels AS (
        SELECT
            b.customer_id,
            MAX(
                CASE
                    WHEN p.invoice_date >= TIMESTAMP '{CUTOFF}'
                     AND p.invoice_date < TIMESTAMP '{CUTOFF}' + INTERVAL {HORIZON_DAYS} DAY
                    THEN 1 ELSE 0
                END
            ) AS bought_again
        FROM buyers b
        LEFT JOIN purchases p USING (customer_id)
        GROUP BY b.customer_id
    )
    SELECT
        f.customer_id,
        f.recency,
        f.frequency,
        f.monetary,
        f.avg_order,
        f.n_products,
        f.tenure_days,
        COALESCE(c.cancel_value, 0) AS cancel_value,
        COALESCE(c.cancel_invoices, 0) AS cancel_invoices,
        ROUND(
            COALESCE(c.cancel_value, 0)
            / NULLIF(f.monetary + COALESCE(c.cancel_value, 0), 0),
            4
        ) AS cancel_rate,
        l.bought_again
    FROM feat f
    LEFT JOIN cancel_feat c USING (customer_id)
    INNER JOIN labels l USING (customer_id)
""")

repurchase = con.execute("SELECT * FROM repurchase_dataset ORDER BY customer_id").df()
print(repurchase["bought_again"].value_counts().rename("count").to_frame())
print(
    con.execute("""
        SELECT
            COUNT(*) AS so_khach,
            ROUND(AVG(bought_again), 3) AS ty_le_mua_lai
        FROM repurchase_dataset
    """).df()
)

feature_cols = [
    "recency",
    "frequency",
    "monetary",
    "avg_order",
    "n_products",
    "tenure_days",
    "cancel_value",
    "cancel_invoices",
    "cancel_rate",
]
Xr = repurchase[feature_cols].copy()
for col in ["frequency", "monetary", "avg_order", "n_products", "cancel_value", "cancel_invoices"]:
    Xr[col] = np.log1p(Xr[col])
yr = repurchase["bought_again"].astype(int)

X_train, X_test, y_train, y_test = train_test_split(
    Xr, yr, test_size=0.25, random_state=42, stratify=yr
)
scaler_clf = StandardScaler()
X_train_s = scaler_clf.fit_transform(X_train)
X_test_s = scaler_clf.transform(X_test)

clf = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
clf.fit(X_train_s, y_train)
proba = clf.predict_proba(X_test_s)[:, 1]
pred = (proba >= 0.5).astype(int)
auc = roc_auc_score(y_test, proba)
print(f"\nLogisticRegression AUC={auc:.4f}")
print(classification_report(y_test, pred, digits=3))
print("Confusion matrix:\n", confusion_matrix(y_test, pred))

coef = pd.DataFrame({"feature": feature_cols, "coef": clf.coef_[0]}).sort_values(
    "coef", key=abs, ascending=False
)
print("\nHệ số (ảnh hưởng tới xác suất mua lại):")
print(coef.to_string(index=False))

fpr, tpr, _ = roc_curve(y_test, proba)
fig, ax = plt.subplots(figsize=(6, 5))
ax.plot(fpr, tpr, label=f"AUC = {auc:.3f}")
ax.plot([0, 1], [0, 1], linestyle="--", color="gray")
ax.set_xlabel("False Positive Rate")
ax.set_ylabel("True Positive Rate")
ax.set_title("ROC — dự đoán mua lại trong 90 ngày")
ax.legend()
fig.tight_layout()
roc_path = OUT_DIR / "roc_repurchase.png"
fig.savefig(roc_path, dpi=150)
plt.close(fig)

scored = repurchase.copy()
Xr_all = Xr.copy()
scored["prob_buy_again"] = clf.predict_proba(scaler_clf.transform(Xr_all))[:, 1]
scored["pred_buy_again"] = (scored["prob_buy_again"] >= 0.5).astype(int)

con.register("repurchase_scored_df", scored)
con.execute("CREATE OR REPLACE TABLE repurchase_scored AS SELECT * FROM repurchase_scored_df")

repurchase_path = OUT_DIR / "repurchase_predictions.xlsx"
coef_path = OUT_DIR / "repurchase_coefficients.xlsx"
scored.to_excel(repurchase_path, index=False)
coef.to_excel(coef_path, index=False)
print(f"\nĐã lưu:\n- {roc_path}\n- {repurchase_path}\n- {coef_path}")

# ---------------------------------------------------------------------------
# Baseline RFM ngũ phân vị + Hierarchical + so sánh Davies–Bouldin
# ---------------------------------------------------------------------------
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import davies_bouldin_score

rfm = features[["customer_id", "recency", "frequency", "monetary"]].copy()
# Recency: điểm cao = mua gần đây hơn → đảo thứ tự xếp hạng
rfm["R"] = pd.qcut(rfm["recency"], 5, labels=[5, 4, 3, 2, 1]).astype(int)
rfm["F"] = pd.qcut(rfm["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["M"] = pd.qcut(rfm["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
rfm["RFM_score"] = rfm["R"] + rfm["F"] + rfm["M"]


def name_rfm_segment(row):
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

rfm_summary = (
    rfm.groupby("rfm_segment")
    .agg(
        so_khach=("customer_id", "count"),
        median_recency=("recency", "median"),
        median_frequency=("frequency", "median"),
        median_monetary=("monetary", "median"),
        mean_RFM_score=("RFM_score", "mean"),
        tong_doanh_thu=("monetary", "sum"),
    )
    .reset_index()
    .sort_values("tong_doanh_thu", ascending=False)
)
print("\n=== Baseline RFM (ngũ phân vị) ===")
print(rfm_summary.to_string(index=False))

con.register("rfm_df", rfm)
con.execute("CREATE OR REPLACE TABLE rfm_baseline AS SELECT * FROM rfm_df")

# So sánh K-Means vs Hierarchical trên cùng X_scaled, k=2..7
compare_rows = []
for k in range(2, 8):
    km_labels = KMeans(n_clusters=k, random_state=42, n_init=20).fit_predict(X_scaled)
    # Ward cần khoảng Euclidean; dữ liệu đã StandardScaler
    hier_labels = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X_scaled)
    compare_rows.append(
        {
            "k": k,
            "kmeans_silhouette": round(silhouette_score(X_scaled, km_labels), 4),
            "kmeans_db": round(davies_bouldin_score(X_scaled, km_labels), 4),
            "hier_silhouette": round(silhouette_score(X_scaled, hier_labels), 4),
            "hier_db": round(davies_bouldin_score(X_scaled, hier_labels), 4),
        }
    )
    print(
        f"k={k} | KMeans sil={compare_rows[-1]['kmeans_silhouette']:.4f} "
        f"DB={compare_rows[-1]['kmeans_db']:.4f} | "
        f"Hier sil={compare_rows[-1]['hier_silhouette']:.4f} "
        f"DB={compare_rows[-1]['hier_db']:.4f}"
    )

compare_df = pd.DataFrame(compare_rows)
print("\n=== So sánh K-Means vs Hierarchical ===")
print(compare_df.to_string(index=False))
print("(Silhouette càng cao càng tốt; Davies–Bouldin càng thấp càng tốt)")

# Chọn k=4 cho cả hai để đối chiếu hồ sơ cụm với phần trước
hier4 = AgglomerativeClustering(n_clusters=4, linkage="ward").fit_predict(X_scaled)
km4_labels = KMeans(n_clusters=4, random_state=42, n_init=20).fit_predict(X_scaled)

hier_df = features.copy()
hier_df["cluster"] = hier4
hier_summary = (
    hier_df.groupby("cluster")
    .agg(
        so_khach=("customer_id", "count"),
        median_recency=("recency", "median"),
        median_frequency=("frequency", "median"),
        median_monetary=("monetary", "median"),
        median_cancel_rate=("cancel_rate", "median"),
        tong_doanh_thu=("monetary", "sum"),
    )
    .reset_index()
)

# Đặt tên Hierarchical theo cùng logic ngưỡng trung vị
o_r = features["recency"].median()
o_f = features["frequency"].median()
o_m = features["monetary"].median()
o_c = features["cancel_rate"].median()


def name_hier(row):
    tags = []
    tags.append("moi_mua" if row["median_recency"] <= o_r else "lau_khong_mua")
    tags.append("mua_nhieu" if row["median_frequency"] >= o_f else "mua_it")
    tags.append("chi_cao" if row["median_monetary"] >= o_m else "chi_thap")
    if row["median_cancel_rate"] > max(o_c, 0.05):
        tags.append("hay_huy")
    return "_".join(tags)


hier_summary["ten_cum"] = hier_summary.apply(name_hier, axis=1)
hier_df["ten_cum"] = hier_df["cluster"].map(
    dict(zip(hier_summary["cluster"], hier_summary["ten_cum"]))
)

print("\n=== Hierarchical k=4 ===")
print(hier_summary.sort_values("tong_doanh_thu", ascending=False).to_string(index=False))

con.register("hier_df_reg", hier_df)
con.execute("CREATE OR REPLACE TABLE customer_clusters_hier_k4 AS SELECT * FROM hier_df_reg")

# PCA so sánh cạnh nhau: K-Means k=4 vs Hierarchical k=4
pca_xy_cmp = PCA(n_components=2, random_state=42).fit_transform(X_scaled)
fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharex=True, sharey=True)
for ax, labels, title in [
    (axes[0], km4_labels, "K-Means k=4"),
    (axes[1], hier4, "Hierarchical (Ward) k=4"),
]:
    for cid in sorted(set(labels)):
        mask = labels == cid
        ax.scatter(pca_xy_cmp[mask, 0], pca_xy_cmp[mask, 1], s=10, alpha=0.5, label=f"cụm {cid}")
    ax.set_title(title)
    ax.set_xlabel("PCA 1")
    ax.set_ylabel("PCA 2")
    ax.legend(fontsize=7, markerscale=2)
fig.suptitle("So sánh hai thuật toán gom cụm")
fig.tight_layout()
cmp_path = OUT_DIR / "compare_kmeans_hierarchical_pca.png"
fig.savefig(cmp_path, dpi=150)
plt.close(fig)

rfm_path = OUT_DIR / "rfm_baseline.xlsx"
rfm_sum_path = OUT_DIR / "rfm_baseline_summary.xlsx"
hier_path = OUT_DIR / "customer_clusters_hier_k4.xlsx"
hier_sum_path = OUT_DIR / "cluster_summary_hier_k4.xlsx"
cmp_xlsx = OUT_DIR / "cluster_algorithm_comparison.xlsx"

rfm.to_excel(rfm_path, index=False)
rfm_summary.to_excel(rfm_sum_path, index=False)
hier_df.to_excel(hier_path, index=False)
hier_summary.to_excel(hier_sum_path, index=False)
compare_df.to_excel(cmp_xlsx, index=False)
print(
    f"\nĐã lưu:\n- {rfm_path}\n- {rfm_sum_path}\n- {hier_path}\n- {hier_sum_path}"
    f"\n- {cmp_xlsx}\n- {cmp_path}"
)
