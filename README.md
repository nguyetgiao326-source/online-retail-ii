# Phân khúc khách hàng Online Retail II (RFM + Clustering)

Đề tài cuối kỳ môn Máy học — gom cụm khách hàng từ dữ liệu giao dịch bán lẻ trực tuyến (UCI Online Retail II).

## Câu hỏi nghiên cứu

Từ đặc trưng RFM và hành vi mua (kèm tỷ lệ hủy), khách hàng tách thành những nhóm nào, và nhóm nào đáng giữ / kích hoạt lại?

## Cấu trúc thư mục

```
online-retail-ml/
├── README.md
├── requirements.txt
├── slides.html                         # Slide trình bày
├── app.py                              # Demo Streamlit (điểm cộng)
├── online_retail_clustering.ipynb      # Notebook chạy phân cụm và xuất báo cáo
├── analysis_pipeline.py                # Mã nguồn pipeline thực nghiệm trong notebook
├── may_hoc.py                          # Script pipeline đầy đủ (DuckDB)
├── outputs/                            # Dữ liệu đặc trưng và kết quả Excel
└── figures/                            # Hình phân tích
```

Các bảng Excel đầu vào và kết quả được lưu trong `outputs/`; hình phân tích trong
`figures/`. Báo cáo Word được lưu ngoài repo tại
`%USERPROFILE%/Downloads/OnlineRetailII_artifacts/`. Đặt `RETAIL_OUTPUTS_DIR`
để đổi thư mục Excel hoặc `RETAIL_ARTIFACTS_DIR` để đổi thư mục artifact báo cáo.

## Dữ liệu

- Nguồn: [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
- Trích dẫn: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D
- File Excel mặc định: `%USERPROFILE%/Downloads/online+retail+ii/online_retail_II.xlsx`
- Database đã xử lý (tuỳ chọn): `%USERPROFILE%/Downloads/OnlineRetailII_artifacts/retail.duckdb`

Đặt biến môi trường `RETAIL_XLSX` nếu file nằm chỗ khác.

## Cài đặt

```powershell
python -m pip install -r requirements.txt
```

## Chạy

### Notebook (khuyến nghị khi nộp)

```powershell
jupyter notebook online_retail_clustering.ipynb
```

Chạy lần lượt các cell từ thư mục gốc repo. Notebook phần thực nghiệm đọc `outputs/customer_features.xlsx` (không làm lại bước
làm sạch/EDA), rồi xuất bảng Excel vào `outputs/`, hình vào `figures/` và báo cáo
Word bên ngoài repo.

Có thể chạy toàn bộ pipeline và tái tạo notebook/báo cáo bằng:

```powershell
python analysis_pipeline.py
```

Đầu vào `outputs/customer_features.xlsx` phải có sẵn; để chạy lại từ dữ liệu giao dịch,
dùng riêng script `may_hoc.py` với đường dẫn nguồn đã cấu hình trong môi trường.

### Script đầy đủ

```powershell
python may_hoc.py
```

Lần chạy đầu đọc lại Excel khá lâu (~1–2 phút). Các lần sau có thể mở `retail.duckdb` nếu bảng đã có sẵn.

### Demo Streamlit (điểm cộng)

Cần có sẵn `outputs/customer_clusters_final.xlsx` (kết quả mới); app sẽ tự
dùng `customer_clusters_k4.xlsx` nếu file kết quả mới chưa có.

```powershell
python -m pip install streamlit plotly
streamlit run app.py
```

Trình duyệt mở trang demo: lọc theo cụm, PCA tương tác, tra cứu Customer ID, so sánh K-Means / Hierarchical, gợi ý hành động marketing theo nhóm.

## Pipeline tóm tắt

| Bước | Nội dung |
|------|----------|
| Input | Dòng mặt hàng trên hóa đơn |
| Làm sạch | Bỏ thiếu Customer ID, giá ≤ 0, mã phí (POST/DOT/…); tách đơn hủy |
| Feature | RFM, avg_order, n_products, tenure, cancel_* và đặc trưng suy ra |
| Baseline | Luật RFM ngũ phân vị |
| Mô hình | K-Means, Hierarchical Ward, GMM; DBSCAN mở rộng |
| Metric | Silhouette, Davies–Bouldin, Calinski–Harabasz; AIC/BIC cho GMM |
| Output | Bảng so sánh, hồ sơ cụm, độ ổn định ARI, PCA và báo cáo Word |

## Kết quả chính (tóm tắt)

- **K-Means k=5** được chọn để diễn giải (Silhouette 0.3039, DB 1.2195, CH 2.241,8; cụm nhỏ nhất 157 khách).
- Năm nhóm: VIP trung thành (70,7% doanh thu), thường xuyên, một lần rồi bỏ, mua thưa thớt giá trị trung bình, rủi ro hay hủy.
- Điểm cộng: Logistic Regression dự đoán mua lại 90 ngày, AUC ≈ 0.79.

## Ghi nhận hỗ trợ

Có sử dụng Cursor / trợ lý AI để hỗ trợ viết pipeline, làm sạch SQL và soạn thảo báo cáo; kết quả số liệu tái lập từ mã nguồn và dữ liệu UCI nêu trên.
