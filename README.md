# Phân khúc khách hàng Online Retail II (RFM + Clustering)

Đề tài cuối kỳ môn Máy học — gom cụm khách hàng từ dữ liệu giao dịch bán lẻ trực tuyến (UCI Online Retail II).

## Câu hỏi nghiên cứu

Từ đặc trưng RFM và hành vi mua (kèm tỷ lệ hủy), khách hàng tách thành những nhóm nào, và nhóm nào đáng giữ / kích hoạt lại?

## Cấu trúc thư mục

```
online-retail-ml/
├── README.md
├── requirements.txt
├── bao_cao.md                          # Báo cáo 5 chương
├── slides.html                         # Slide trình bày
├── app.py                              # Demo Streamlit (điểm cộng)
├── online_retail_clustering.ipynb      # Notebook chạy lại được
├── may_hoc.py                          # Script pipeline đầy đủ (DuckDB)
├── figures/                            # Biểu đồ PCA, ROC, so sánh thuật toán
└── outputs/                            # Kết quả Excel khi chạy notebook
```

## Dữ liệu

- Nguồn: [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
- Trích dẫn: Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D
- File Excel mặc định trên máy này: `C:/Users/nguye/Downloads/online+retail+ii/online_retail_II.xlsx`
- Database đã xử lý (tuỳ chọn): `C:/Users/nguye/Downloads/online-retail-ii/retail.duckdb`

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

Chạy lần lượt các cell. Notebook sẽ:

1. Đọc Excel (hoặc DuckDB nếu đã có bảng `purchases`)
2. Làm sạch → bảng mua / hủy
3. EDA ngắn
4. Feature RFM + hành vi
5. Baseline RFM ngũ phân vị
6. K-Means và Hierarchical + Silhouette / Davies–Bouldin
7. PCA và xuất file vào `outputs/`

### Script đầy đủ

```powershell
python may_hoc.py
```

Lần chạy đầu đọc lại Excel khá lâu (~1–2 phút). Các lần sau có thể mở `retail.duckdb` nếu bảng đã có sẵn.

### Demo Streamlit (điểm cộng)

Cần có sẵn `outputs/customer_clusters_k4.xlsx` (đã có nếu chạy pipeline trước đó).

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
| Feature | Recency, Frequency, Monetary, avg_order, n_products, tenure, cancel_* |
| Baseline | Điểm RFM theo ngũ phân vị |
| Mô hình | K-Means, Hierarchical (Ward); hỗ trợ PCA |
| Metric | Silhouette (↑), Davies–Bouldin (↓) |
| Output | Nhãn cụm + hồ sơ khách (VIP, thường xuyên, một lần rồi bỏ, rủi ro hủy) |

## Kết quả chính (tóm tắt)

- **K-Means k=4** được chọn để diễn giải (Silhouette 0.261, DB 1.228; tốt hơn Hierarchical cùng k).
- Bốn nhóm: VIP trung thành (~71% doanh thu), thường xuyên, một lần rồi bỏ, rủi ro hay hủy.
- Điểm cộng: Logistic Regression dự đoán mua lại 90 ngày, AUC ≈ 0.79.

## Ghi nhận hỗ trợ

Có sử dụng Cursor / trợ lý AI để hỗ trợ viết pipeline, làm sạch SQL và soạn thảo báo cáo; kết quả số liệu tái lập từ mã nguồn và dữ liệu UCI nêu trên.
