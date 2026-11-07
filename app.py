"""Demo Streamlit — phân khúc khách hàng Online Retail II (K-Means k=5)."""

from pathlib import Path
import os

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get("RETAIL_OUTPUTS_DIR", str(ROOT / "outputs"))).expanduser()
FIG = ROOT / "figures"

SEGMENT_ACTIONS = {
    "khach_vip_trung_thanh": {
        "label": "VIP trung thành",
        "action": "Giữ chân: ưu đãi riêng, CSKH ưu tiên, chương trình loyalty.",
        "color": "#0ea5e9",
    },
    "khach_thuong_xuyen": {
        "label": "Thường xuyên",
        "action": "Nuôi dưỡng / upsell: gợi ý combo, tăng tần suất mua.",
        "color": "#22c55e",
    },
    "khach_mot_lan_roi_bo": {
        "label": "Một lần rồi bỏ",
        "action": "Win-back: email kích hoạt, voucher đơn tiếp theo.",
        "color": "#f59e0b",
    },
    "khach_rui_ro_hay_huy": {
        "label": "Rủi ro hay hủy",
        "action": "Giảm ma sát hoàn trả: kiểm tra mô tả SP, chính sách đổi trả.",
        "color": "#ef4444",
    },
    "khach_mua_thua_thot_gia_tri_trung_binh": {
        "label": "Mua thưa thớt, giá trị trung bình",
        "action": "Theo dõi giảm hoạt động; nhắc mua lại phù hợp lịch sử mua.",
        "color": "#a78bfa",
    },
}


@st.cache_data
def load_clusters() -> pd.DataFrame:
    path = OUT / "customer_clusters_final.xlsx"
    if not path.exists():
        path = OUT / "customer_clusters_k4.xlsx"
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {OUT / 'customer_clusters_final.xlsx'} hoặc "
            f"{OUT / 'customer_clusters_k4.xlsx'}. "
            "Chạy analysis_pipeline.py hoặc đặt RETAIL_ARTIFACTS_DIR tới thư mục dữ liệu."
        )
    df = pd.read_excel(path)
    df["model_label"] = "K-Means k=5" if path.name == "customer_clusters_final.xlsx" else "K-Means k=4"
    if "ten_cum" not in df.columns and "cluster" in df.columns:
        # fallback nếu chỉ có số cụm
        names = {
            0: "khach_mot_lan_roi_bo",
            1: "khach_thuong_xuyen",
            2: "khach_vip_trung_thanh",
            3: "khach_rui_ro_hay_huy",
        }
        df["ten_cum"] = df["cluster"].map(names)
    return df


@st.cache_data
def load_optional(name: str) -> pd.DataFrame | None:
    path = OUT / name
    if not path.exists():
        return None
    return pd.read_excel(path)


@st.cache_data
def add_pca(df: pd.DataFrame) -> pd.DataFrame:
    derived = df.copy()
    if "avg_interpurchase_days" not in derived.columns:
        derived["avg_interpurchase_days"] = np.where(
            derived["frequency"] > 1,
            derived["tenure_days"] / (derived["frequency"] - 1),
            0.0,
        )
    if "cancel_invoice_share" not in derived.columns:
        denominator = derived["frequency"] + derived["cancel_invoices"]
        derived["cancel_invoice_share"] = (
            derived["cancel_invoices"] / denominator.replace(0, np.nan)
        ).fillna(0.0)

    log_cols = [
        "frequency",
        "monetary",
        "avg_order",
        "n_products",
        "cancel_value",
        "cancel_invoices",
        "cancel_rate",
        "avg_interpurchase_days",
        "cancel_invoice_share",
    ]
    cols = [
        "recency",
        "frequency",
        "monetary",
        "avg_order",
        "n_products",
        "tenure_days",
        "cancel_value",
        "cancel_invoices",
        "cancel_rate",
        "avg_interpurchase_days",
        "cancel_invoice_share",
    ]
    missing = [c for c in cols if c not in derived.columns]
    if missing:
        out = derived
        out["pca1"] = np.nan
        out["pca2"] = np.nan
        return out

    X = derived[cols].copy()
    for c in log_cols:
        if X[c].skew() > 1:
            X[c] = np.log1p(X[c])
    scaled = StandardScaler().fit_transform(X)
    xy = PCA(n_components=2, random_state=42).fit_transform(scaled)
    out = derived
    out["pca1"] = xy[:, 0]
    out["pca2"] = xy[:, 1]
    return out


def segment_profile(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("ten_cum", as_index=False)
        .agg(
            so_khach=("customer_id", "count"),
            median_recency=("recency", "median"),
            median_frequency=("frequency", "median"),
            median_monetary=("monetary", "median"),
            median_cancel_rate=("cancel_rate", "median"),
            tong_doanh_thu=("monetary", "sum"),
        )
        .sort_values("tong_doanh_thu", ascending=False)
    )


def main() -> None:
    st.set_page_config(
        page_title="Online Retail — Phân khúc khách",
        page_icon="📊",
        layout="wide",
    )

    st.title("Phân khúc khách hàng Online Retail II")
    try:
        raw = load_clusters()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

    df = add_pca(raw)
    st.caption(
        f"Demo {raw['model_label'].iloc[0]} · RFM + hành vi mua/hủy · "
        "Điểm cộng Streamlit cho đề tài Máy học"
    )
    profile = segment_profile(df)
    total_rev = float(df["monetary"].sum())
    total_cust = len(df)

    # Sidebar filters
    st.sidebar.header("Bộ lọc")
    segments = sorted(df["ten_cum"].dropna().unique().tolist())
    nice = {s: SEGMENT_ACTIONS.get(s, {}).get("label", s) for s in segments}
    chosen = st.sidebar.multiselect(
        "Nhóm khách",
        options=segments,
        default=segments,
        format_func=lambda s: nice.get(s, s),
    )
    max_recency = int(df["recency"].max())
    recency_range = st.sidebar.slider(
        "Recency (ngày từ lần mua cuối)",
        0,
        max_recency,
        (0, max_recency),
    )
    query_id = st.sidebar.text_input("Tìm Customer ID", placeholder="vd. 18102")

    view = df[df["ten_cum"].isin(chosen)].copy()
    view = view[
        (view["recency"] >= recency_range[0]) & (view["recency"] <= recency_range[1])
    ]

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Khách (lọc)", f"{len(view):,}".replace(",", "."))
    c2.metric("Tổng khách", f"{total_cust:,}".replace(",", "."))
    c3.metric("Doanh thu lọc", f"£{view['monetary'].sum():,.0f}")
    c4.metric("Tỷ lệ DT / toàn bộ", f"{100 * view['monetary'].sum() / total_rev:.1f}%")

    tab_overview, tab_pca, tab_lookup, tab_compare = st.tabs(
        ["Tổng quan cụm", "PCA", "Tra cứu khách", "So sánh thuật toán"]
    )

    with tab_overview:
        left, right = st.columns([1.2, 1])
        with left:
            show = profile.copy()
            show["nhom"] = show["ten_cum"].map(
                lambda s: SEGMENT_ACTIONS.get(s, {}).get("label", s)
            )
            show["hanh_dong"] = show["ten_cum"].map(
                lambda s: SEGMENT_ACTIONS.get(s, {}).get("action", "")
            )
            show["share_dt_%"] = (100 * show["tong_doanh_thu"] / total_rev).round(1)
            st.subheader(
                f"Hồ sơ {profile['ten_cum'].nunique()} cụm "
                f"({raw['model_label'].iloc[0]})"
            )
            st.dataframe(
                show[
                    [
                        "nhom",
                        "so_khach",
                        "median_recency",
                        "median_frequency",
                        "median_monetary",
                        "median_cancel_rate",
                        "tong_doanh_thu",
                        "share_dt_%",
                        "hanh_dong",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        with right:
            pie = profile.copy()
            pie["nhom"] = pie["ten_cum"].map(
                lambda s: SEGMENT_ACTIONS.get(s, {}).get("label", s)
            )
            fig_pie = px.pie(
                pie,
                names="nhom",
                values="tong_doanh_thu",
                title="Tỷ trọng doanh thu theo cụm",
                color="ten_cum",
                color_discrete_map={
                    k: v["color"] for k, v in SEGMENT_ACTIONS.items()
                },
            )
            fig_pie.update_layout(margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Gợi ý hành động nhanh")
        cols = st.columns(min(5, max(1, len(SEGMENT_ACTIONS))))
        for col, (key, meta) in zip(cols, SEGMENT_ACTIONS.items()):
            n = int((df["ten_cum"] == key).sum())
            with col:
                st.markdown(f"**{meta['label']}** · {n} khách")
                st.write(meta["action"])

        rfm_sum = load_optional("rfm_baseline_summary.xlsx")
        if rfm_sum is not None:
            with st.expander("Baseline RFM (ngũ phân vị)"):
                st.dataframe(rfm_sum, use_container_width=True, hide_index=True)

    with tab_pca:
        st.subheader("Khách trên mặt phẳng PCA")
        plot_df = view.dropna(subset=["pca1", "pca2"]).copy()
        plot_df["nhom"] = plot_df["ten_cum"].map(
            lambda s: SEGMENT_ACTIONS.get(s, {}).get("label", s)
        )
        if plot_df.empty:
            st.warning("Không vẽ được PCA (thiếu cột đặc trưng).")
        else:
            fig = px.scatter(
                plot_df,
                x="pca1",
                y="pca2",
                color="nhom",
                hover_data={
                    "customer_id": True,
                    "recency": True,
                    "frequency": True,
                    "monetary": True,
                    "cancel_rate": True,
                    "pca1": False,
                    "pca2": False,
                },
                color_discrete_map={
                    v["label"]: v["color"] for v in SEGMENT_ACTIONS.values()
                },
                opacity=0.65,
                title="PCA 2D — màu theo cụm K-Means",
            )
            fig.update_traces(marker=dict(size=7))
            fig.update_layout(height=520)
            st.plotly_chart(fig, use_container_width=True)

        img = FIG / "final_clusters_pca.png"
        if img.exists():
            with st.expander("Ảnh PCA tĩnh từ pipeline"):
                st.image(str(img), use_container_width=True)

    with tab_lookup:
        st.subheader("Tra cứu một khách")
        hit = pd.DataFrame()
        if query_id.strip():
            try:
                cid = int(float(query_id.strip()))
                hit = df[df["customer_id"] == cid]
            except ValueError:
                st.warning("Customer ID phải là số.")
        else:
            st.info("Nhập Customer ID ở thanh bên, hoặc chọn ngẫu nhiên bên dưới.")

        if st.button("Lấy 1 khách ngẫu nhiên trong bộ lọc"):
            if len(view):
                hit = view.sample(1, random_state=None)
            else:
                st.warning("Bộ lọc đang trống.")

        if len(hit):
            row = hit.iloc[0]
            key = row["ten_cum"]
            meta = SEGMENT_ACTIONS.get(key, {"label": key, "action": ""})
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Customer ID", int(row["customer_id"]))
            m2.metric("Nhóm", meta["label"])
            m3.metric("Recency (ngày)", int(row["recency"]))
            m4.metric("Monetary", f"£{row['monetary']:,.0f}")
            st.write(
                f"**Frequency:** {int(row['frequency'])} · "
                f"**Avg order:** £{row['avg_order']:,.2f} · "
                f"**Sản phẩm:** {int(row['n_products'])} · "
                f"**Cancel rate:** {row['cancel_rate']:.2%}"
            )
            st.success(meta["action"])
            st.dataframe(hit, use_container_width=True, hide_index=True)

        st.subheader("Bảng khách (theo bộ lọc)")
        cols_show = [
            c
            for c in [
                "customer_id",
                "ten_cum",
                "recency",
                "frequency",
                "monetary",
                "avg_order",
                "n_products",
                "cancel_rate",
            ]
            if c in view.columns
        ]
        st.dataframe(
            view[cols_show].sort_values("monetary", ascending=False).head(500),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Hiển thị tối đa 500 khách có monetary cao nhất trong bộ lọc.")

    with tab_compare:
        cmp = load_optional("candidate_model_comparison.xlsx")
        if cmp is None:
            st.info("Chưa có file candidate_model_comparison.xlsx trong outputs/.")
        else:
            st.subheader("So sánh mô hình trên RFM + hành vi")
            st.dataframe(cmp, use_container_width=True, hide_index=True)
            st.caption(
                "DBSCAN tính metric trên điểm không nhiễu; không so trực tiếp "
                "với mô hình gán toàn bộ khách."
            )

        cmp_img = FIG / "model_selection.png"
        if cmp_img.exists():
            st.image(str(cmp_img), caption="Elbow K-Means và BIC/AIC GMM")

    st.divider()
    st.caption(
        "Nguồn dữ liệu: Chen, D. (2012). Online Retail II — UCI. "
        "Demo đọc kết quả từ thư mục outputs/."
    )


if __name__ == "__main__":
    main()
