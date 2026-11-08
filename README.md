# Phân khúc khách hàng Online Retail II

Đồ án cuối kỳ môn **Máy học** tại Trường Đại học Sài Gòn. Dự án sử dụng dữ liệu giao dịch bán lẻ trực tuyến để phân khúc khách hàng theo RFM và hành vi mua/hủy, sau đó so sánh các thuật toán phân cụm và xây dựng ứng dụng minh họa kết quả.

## Câu hỏi nghiên cứu

Từ lịch sử mua hàng, giá trị giao dịch và hành vi hủy, khách hàng có thể được chia thành những nhóm nào? Nhóm nào cần được giữ chân, nuôi dưỡng hoặc kích hoạt mua lại?

## Dữ liệu

- **Nguồn:** [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
- **Trích dẫn:** Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D
- File Excel gốc không được lưu trong repository. Theo mặc định, `may_hoc.py` tìm file tại `%USERPROFILE%/Downloads/online+retail+ii/online_retail_II.xlsx`.
- Theo kết quả phân tích của đồ án: dữ liệu có 1.067.371 dòng thô; sau làm sạch còn 776.920 dòng mua hợp lệ, 5.862 khách hàng và 18.390 dòng thuộc hóa đơn hủy.

## Cấu trúc đồ án

```text
README.md
requirements.txt
may_hoc.py                          # Đọc dữ liệu gốc, làm sạch và tạo đặc trưng khách hàng
analysis_pipeline.py                # So sánh mô hình, chọn cụm cuối và xuất báo cáo
app.py                              # Ứng dụng demo Streamlit
online_retail_clustering.ipynb      # Notebook phân tích và thực nghiệm
slides.html                         # Slide trình bày
outputs/                            # Bảng đặc trưng và kết quả Excel
figures/                            # Biểu đồ phân tích
```

Các tài liệu Word/báo cáo do pipeline tạo được lưu ngoài repository trong `%USERPROFILE%/Downloads/OnlineRetailII_artifacts/` theo mặc định.

## Quy trình phân tích

| Bước | Nội dung |
|---|---|
| Làm sạch | Loại khách thiếu Customer ID, giá không dương, dòng trùng và mã hàng/dịch vụ không phải sản phẩm; nhận diện riêng hóa đơn hủy |
| Đặc trưng | Tính Recency, Frequency, Monetary cùng giá trị đơn trung bình, số sản phẩm, thời gian hoạt động và các đặc trưng hủy |
| Tiền xử lý | Biến đổi `log1p` cho các đặc trưng lệch và chuẩn hóa bằng `StandardScaler` trong pipeline phân cụm |
| So sánh | Đối chiếu baseline RFM với K-Means, Hierarchical Ward, Gaussian Mixture Model (GMM) và DBSCAN |
| Đánh giá | Dùng Silhouette, Davies–Bouldin, Calinski–Harabasz; đánh giá độ ổn định K-Means bằng ARI qua nhiều random seed |
| Diễn giải | Xem hồ sơ từng cụm và biểu diễn PCA; ứng dụng demo hỗ trợ tra cứu khách hàng và gợi ý hành động marketing |

## Kết quả chính

K-Means với **k=5** được chọn làm mô hình phân khúc cuối để cân bằng chất lượng phân cụm, độ ổn định và khả năng diễn giải.

| Mô hình | Cấu hình | Silhouette | Davies–Bouldin | Calinski–Harabasz |
|---|---|---:|---:|---:|
| K-Means | k=5, k-means++ | 0,3039 | 1,2195 | 2.241,8 |
| Hierarchical Ward | k=3 | 0,2596 | 1,2829 | 2.343,6 |
| GMM | k=4, covariance=full | 0,2808 | 1,3440 | 2.320,6 |
| DBSCAN | eps ≈ 1,776; min_samples=10 | 0,5282* | 0,4926* | 68,5* |

`*` DBSCAN loại 137 điểm nhiễu, độ phủ 97,66%; do đó các chỉ số của DBSCAN không thể so sánh trực tiếp với các mô hình gán cụm cho toàn bộ khách hàng. ARI trung bình của K-Means qua 7 random seed xấp xỉ **0,9995**.

| Cụm | Phân khúc | Số khách | Tỷ trọng doanh thu |
|---:|---|---:|---:|
| 0 | Một lần rồi bỏ | 1.649 | 3,02% |
| 1 | VIP trung thành | 1.192 | 70,67% |
| 2 | Thường xuyên | 1.862 | 16,49% |
| 3 | Mua thưa thớt, giá trị trung bình | 1.002 | 6,39% |
| 4 | Rủi ro hay hủy | 157 | 3,44% |

Thử nghiệm phụ dùng Logistic Regression để dự đoán khách có mua lại trong 90 ngày hay không đạt AUC khoảng **0,788**. Đây là bài toán phân loại riêng, không phải mô hình phân cụm.

## Cài đặt

Yêu cầu Python 3. Cài các thư viện trong môi trường ảo (khuyến nghị) hoặc môi trường Python hiện có:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Chạy đồ án

### 1. Tạo bảng đặc trưng từ Excel gốc (tùy chọn)

Tải `online_retail_II.xlsx` từ UCI, sau đó cấu hình đường dẫn nếu file không nằm ở vị trí mặc định:

```powershell
$env:RETAIL_XLSX = "C:\duong-dan\online_retail_II.xlsx"
python .\may_hoc.py
```

Lệnh này tạo/cập nhật `outputs/customer_features.xlsx` và cơ sở dữ liệu DuckDB. Lần đầu có thể cần kết nối mạng để DuckDB tải extension đọc Excel. Đặt biến môi trường trước khi chạy nếu muốn thay đổi vị trí đầu ra hoặc cơ sở dữ liệu:

```powershell
$env:RETAIL_OUTPUTS_DIR = "C:\duong-dan\outputs"
$env:RETAIL_ARTIFACTS_DIR = "C:\duong-dan\OnlineRetailII_artifacts"
$env:RETAIL_DB = "C:\duong-dan\retail.duckdb"
```

### 2. Chạy thực nghiệm phân cụm

Pipeline cần có sẵn `outputs/customer_features.xlsx`. Có thể chạy script:

```powershell
python .\analysis_pipeline.py
```

Hoặc mở notebook và chạy lần lượt các cell:

```powershell
jupyter notebook .\online_retail_clustering.ipynb
```

Notebook tập trung vào phân tích và so sánh mô hình từ bảng đặc trưng đã có; để làm lại bước đọc/làm sạch dữ liệu gốc, chạy `may_hoc.py` trước. Pipeline thực nghiệm xuất các bảng Excel vào `outputs/`, hình vào `figures/` và báo cáo Word/JSON vào thư mục artifact bên ngoài repository. Các tệp kết quả có thể bị ghi đè khi chạy lại, vì vậy hãy sao lưu nếu cần giữ bản cũ.

### 3. Chạy ứng dụng demo

Ứng dụng cần `outputs/customer_clusters_final.xlsx`. Nếu không có kết quả k=5, ứng dụng sẽ thử dùng `customer_clusters_k4.xlsx`:

```powershell
python -m streamlit run .\app.py
```

Giao diện hỗ trợ lọc và tra cứu khách hàng theo cụm, xem biểu đồ PCA tương tác, so sánh kết quả phân cụm và tham khảo gợi ý hành động marketing.

## Các tệp kết quả nên xem

- `outputs/customer_features.xlsx`: đặc trưng ở mức khách hàng.
- `outputs/candidate_model_comparison.xlsx`, `outputs/model_metrics_by_k.xlsx`: so sánh và chỉ số mô hình.
- `outputs/customer_clusters_final.xlsx`, `outputs/cluster_profiles_final.xlsx`: nhãn cụm cuối và hồ sơ cụm.
- `outputs/stability_ari_summary.xlsx`, `outputs/stability_ari_by_seed.xlsx`: đánh giá độ ổn định.
- `figures/final_clusters_pca.png`, `figures/model_selection.png`, `figures/feature_space_comparison.png`: hình minh họa kết quả.
- `slides.html`: slide trình bày đồ án.

## Hạn chế

Dữ liệu có khách hàng thiếu mã định danh và tập trung nhiều vào thị trường Anh; nhóm khách sỉ cũng có thể ảnh hưởng đến đặc trưng giá trị. Nhãn cụm là kết quả không giám sát, chưa có nhãn thật để xác nhận. Vì vậy, tên cụm và gợi ý marketing chỉ là diễn giải từ dữ liệu, chưa chứng minh hiệu quả kinh doanh nếu chưa được kiểm nghiệm thực tế/A-B test.

## Ghi nhận hỗ trợ

Trong quá trình thực hiện đồ án, nhóm có sử dụng các công cụ AI, bao gồm **Cursor** và **ChatGPT**, để hỗ trợ viết và rà soát mã nguồn, xử lý dữ liệu, gỡ lỗi và soạn thảo nội dung báo cáo. Nhóm chịu trách nhiệm kiểm tra, chỉnh sửa và xác nhận các nội dung cũng như kết quả cuối cùng. Số liệu phân tích được tạo từ mã nguồn của đồ án trên bộ dữ liệu UCI Online Retail II.

**Repository tham chiếu:** https://github.com/nguyetgiao326-source/online-retail-ii
