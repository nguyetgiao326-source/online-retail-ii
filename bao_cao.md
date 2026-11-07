# BÁO CÁO ĐỀ TÀI CUỐI KỲ MÔN MÁY HỌC

**Đề tài:** Phân khúc khách hàng Online Retail II bằng RFM và gom cụm  
**Loại bài toán:** Học không giám sát (Clustering)  
**Nhóm:** _(điền họ tên / MSSV)_  
**Nguồn dữ liệu:** Chen, D. (2012). Online Retail II. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D

---

## Chương 1. Giới thiệu

### 1.1. Bối cảnh và ý nghĩa

Doanh nghiệp bán lẻ trực tuyến thường có hàng trăm nghìn giao dịch nhưng thiếu chân dung khách hàng rõ ràng. Không phải mọi khách đều quan trọng như nhau: một nhóm nhỏ có thể đóng góp phần lớn doanh thu, trong khi nhiều khách chỉ mua một lần rồi biến mất. Phân khúc giúp ưu tiên chăm sóc, giảm chi phí marketing và phát hiện sớm rủi ro rời bỏ.

Bộ dữ liệu Online Retail II ghi nhận giao dịch của một cửa hàng quà tặng trực tuyến tại Anh (12/2009–12/2011), khách hàng chủ yếu là nhà bán sỉ. Mỗi dòng là một mặt hàng trong hóa đơn, không phải một khách hàng. Do đó cần gom giao dịch theo `Customer ID` trước khi phân nhóm.

### 1.2. Mục tiêu / câu hỏi nghiên cứu

**Câu hỏi:** Từ đặc trưng RFM và hành vi mua (kèm tỷ lệ hủy), khách hàng tách thành những nhóm nào, và nhóm nào đáng giữ hoặc kích hoạt lại?

**Mục tiêu cụ thể:**

1. Làm sạch và khám phá dữ liệu giao dịch.
2. Xây đặc trưng một dòng / một khách (RFM + hành vi).
3. Xây baseline theo điểm RFM ngũ phân vị.
4. So sánh ít nhất hai thuật toán gom cụm và chọn mô hình có căn cứ.
5. Diễn giải hồ sơ từng cụm theo góc nhìn kinh doanh.

### 1.3. Xác định bài toán

| Hạng mục | Nội dung |
|----------|----------|
| Loại bài toán | Gom cụm (không giám sát) |
| Input | Đặc trưng khách: Recency, Frequency, Monetary, avg_order, n_products, tenure_days, cancel_value, cancel_invoices, cancel_rate |
| Output | Nhãn cụm + hồ sơ mô tả từng nhóm |
| Phạm vi | Khách có `Customer ID`; không phân khúc giao dịch ẩn danh |

### 1.4. Hướng tiếp cận liên quan

RFM là phương pháp phân tích khách hàng cổ điển trong marketing. Học máy bổ sung bằng cách tìm cấu trúc nhóm trên không gian đặc trưng đã chuẩn hóa, thay vì chỉ cắt theo ngưỡng điểm. PCA hỗ trợ trực quan hóa; không dùng làm mục tiêu chính.

---

## Chương 2. Cơ sở lý thuyết và nghiên cứu liên quan

### 2.1. RFM

- **Recency (R):** số ngày từ lần mua cuối đến mốc quan sát.  
- **Frequency (F):** số hóa đơn khác nhau.  
- **Monetary (M):** tổng doanh thu.  

Baseline chia mỗi chỉ số thành ngũ phân vị (1–5), cộng điểm, đặt tên nhóm nghiệp vụ (VIP, nguy cơ mất, …). Đây là mốc so sánh trước khi dùng thuật toán học máy.

### 2.2. K-Means

Phân dữ liệu thành \(k\) cụm bằng cách tối thiểu hóa tổng bình phương khoảng cách tới tâm cụm. Ưu điểm: nhanh, dễ hiểu. Hạn chế: giả định cụm lồi, cần chọn \(k\), nhạy với scale và điểm ngoại lệ. Vì phân phối doanh thu lệch mạnh, bài này dùng `log1p` rồi `StandardScaler`.

### 2.3. Hierarchical Clustering (Ward)

Gộp dần các điểm theo tiêu chí Ward (giảm phương sai trong cụm). Ưu điểm: không cần khởi tạo tâm ngẫu nhiên; có dendrogram. Hạn chế: chi phí cao hơn K-Means với tập lớn; kết quả phụ thuộc linkage. Với ~5.8 nghìn khách, Ward vẫn khả thi.

### 2.4. Độ đo và PCA

- **Silhouette** (↑ càng tốt): mức gắn kết trong cụm so với cụm gần nhất.  
- **Davies–Bouldin** (↓ càng tốt): tỷ lệ phân tán trong cụm / khoảng cách giữa cụm.  
- **PCA:** chiếu xuống 2 chiều để quan sát; hai thành phần chính giải thích khoảng 70.5% phương sai.

### 2.5. Lý do lựa chọn

Bài toán không có nhãn nhóm sẵn → phù hợp clustering. Chọn K-Means (chuẩn mực, dễ tinh chỉnh \(k\)) và Hierarchical (đối chứng không phụ thuộc khởi tạo). Không dùng DBSCAN làm mô hình chính vì mật độ khách rất không đều (nhiều khách mua một lần), dễ sinh nhiều nhiễu khó diễn giải nghiệp vụ.

---

## Chương 3. Dữ liệu và phương pháp

### 3.1. Mô tả dữ liệu

| Thuộc tính | Ý nghĩa |
|------------|---------|
| Invoice | Mã hóa đơn; bắt đầu bằng `C` là đơn hủy |
| StockCode | Mã hàng |
| Description | Mô tả |
| Quantity | Số lượng |
| InvoiceDate | Thời điểm |
| Price | Đơn giá |
| Customer ID | Mã khách |
| Country | Quốc gia |

- Số dòng thô: **1.067.371** (2 sheet: 2009–2010 và 2010–2011).  
- Sau lọc mua hợp lệ (`purchases`): **776.920** dòng, **5.862** khách, doanh thu ~**£17.09M**.  
- Bảng hủy (`cancellations`): **18.390** dòng, **2.572** khách.

### 3.2. EDA và tiền xử lý

**Các vấn đề phát hiện và xử lý:**

| Vấn đề | Số lượng (ước lượng / đếm) | Cách xử lý | Lý do |
|--------|---------------------------|------------|-------|
| Thiếu Customer ID | 243.007 | Loại khỏi phân khúc | Không gắn được khách |
| Hóa đơn `C%` / qty < 0 | ~19k–23k | Tách bảng `cancellations` | Phản ánh hành vi hủy, không cộng doanh thu mua |
| Giá ≤ 0 | 6.207 | Loại khỏi `purchases` | Không phải doanh thu hàng |
| Trùng hoàn toàn | 12.133 dòng thừa | `SELECT DISTINCT` | Tránh nhân đôi doanh thu |
| Mã phí POST, DOT, M, D, S, B | Theo mã | Loại khỏi `purchases` | Không phải sản phẩm |

Anh chiếm ~83.7% doanh thu và đa số khách; `country` dùng mô tả, không đưa vào vector gom cụm để tránh cụm chỉ tách “UK / không UK”.

### 3.3. Feature engineering

Mốc quan sát: **2011-12-10** (ngày sau hóa đơn cuối).

| Đặc trưng | Công thức |
|-----------|-----------|
| recency | Ngày từ lần mua cuối → mốc |
| frequency | Số invoicedistinct |
| monetary | Σ line_revenue |
| avg_order | monetary / frequency |
| n_products | Số stock_code khác nhau |
| tenure_days | Ngày từ hóa đơn đầu → cuối |
| cancel_value / cancel_invoices / cancel_rate | Từ bảng hủy |

Trước gom cụm: `log1p` với các biến lệch (frequency, monetary, …) và `StandardScaler`.

### 3.4. Thiết kế thực nghiệm

- **Baseline:** điểm RFM ngũ phân vị (không học máy).  
- **Mô hình:** K-Means và AgglomerativeClustering (Ward), \(k \in \{2,\ldots,7\}\).  
- **Tinh chỉnh:** chọn \(k\) theo Silhouette và Davies–Bouldin; ưu tiên \(k=4\) khi cần diễn giải nghiệp vụ.  
- **Công bằng so sánh:** cùng ma trận đặc trưng đã scale, cùng metric.  
- **Data leakage:** không dùng nhãn tương lai trong đặc trưng cụm. Phần dự đoán mua lại (điểm cộng) cắt đặc trưng trước 2011-09-01, nhãn = có mua trong 90 ngày sau.

---

## Chương 4. Thực nghiệm, kết quả và thảo luận

### 4.1. Baseline RFM

| Phân khúc RFM | Số khách | Recency median | Frequency median | Monetary median | Doanh thu |
|---------------|----------|----------------|------------------|-----------------|-----------|
| VIP_trung_thanh | 1.284 | 17 | 11 | 3.902 | 11.64M |
| khach_trung_thanh | 1.136 | 68 | 5 | 1.291 | 2.51M |
| nguy_co_mat | 1.515 | 433 | 1 | 273 | 0.62M |
| sap_roi_gia_tri_cao | 227 | 330 | 7 | 2.243 | 1.00M |
| … | … | … | … | … | … |

Baseline đã chỉ ra nhóm VIP và nhóm nguy cơ mất — phù hợp trực giác kinh doanh, nhưng ranh giới cứng theo ngũ phân vị, chưa tận dụng đồng thời nhiều đặc trưng hành vi (hủy, tenure, đa dạng sản phẩm).

### 4.2. So sánh K-Means và Hierarchical

| k | KMeans Silhouette↑ | KMeans DB↓ | Hier Silhouette↑ | Hier DB↓ |
|---|--------------------|------------|------------------|----------|
| 2 | **0.337** | 1.176 | 0.326 | **1.056** |
| 3 | 0.243 | 1.387 | 0.172 | 1.480 |
| 4 | **0.261** | **1.228** | 0.197 | 1.335 |
| 5 | 0.250 | 1.353 | 0.155 | 1.650 |

- Silhouette cao nhất ở **k=2** (tách “khách tích cực giá trị cao” / “ít mua, lâu không quay lại”).  
- Với **k=4**, K-Means vượt Hierarchical trên cả hai metric → chọn **K-Means k=4** làm mô hình diễn giải chính.  
- Hình so sánh PCA: `figures/compare_kmeans_hierarchical_pca.png`.

### 4.3. Hồ sơ K-Means k=4

| Cụm | Tên | Số khách | Recency | Frequency | Monetary | Cancel rate | Ý nghĩa |
|-----|-----|----------|---------|-----------|----------|-------------|---------|
| 2 | VIP trung thành | 1.270 | 25 | 12 | 4.389 | ~0.02 | ~71% doanh thu — ưu tiên giữ |
| 1 | Thường xuyên | 2.222 | 58 | 4 | 1.122 | 0 | Upsell / nuôi dưỡng |
| 0 | Một lần rồi bỏ | 2.152 | 391 | 1 | 272 | 0 | Win-back hàng loạt |
| 3 | Rủi ro hay hủy | 218 | 276 | 3 | 705 | ~0.25 | Chăm sóc / giảm ma sát hoàn trả |

PCA 2D: `figures/pca_clusters_k4.png` (2 trục giải thích ~70.5% phương sai).

### 4.4. Thảo luận / trả lời câu hỏi nghiên cứu

Khách tách thành bốn nhóm có hành vi khác rõ. Nhóm đáng giữ nhất là VIP trung thành (mua gần, mua nhiều, chi tiêu cao). Nhóm cần kích hoạt lại là “một lần rồi bỏ” và một phần “rủi ro hay hủy”. Hierarchical cho cấu trúc tương tự nhưng metric kém hơn ở k=4, nên không thay K-Means.

Overfitting theo nghĩa học có giám sát không áp dụng trực tiếp; thay vào đó theo dõi độ ổn định qua hai thuật toán và qua khoảng \(k\). k=2 cho metric đẹp hơn nhưng quá thô cho hành động marketing.

### 4.5. Thực nghiệm bổ sung (điểm cộng)

Logistic Regression dự đoán có mua lại trong 90 ngày sau 2011-09-01: **AUC ≈ 0.788**, accuracy ≈ 0.716. Hệ số mạnh nhất: recency (âm), frequency và monetary (dương). ROC: `figures/roc_repurchase.png`.

---

## Chương 5. Kết luận và hướng phát triển

### 5.1. Kết quả chính và mô hình chọn

- Pipeline làm sạch → RFM/hành vi → baseline → K-Means & Hierarchical đã trả lời được câu hỏi phân khúc.  
- **Mô hình cuối:** K-Means với **k=4** (cân bằng metric và khả năng diễn giải).  
- VIP (~1.3k khách) đóng góp phần lớn doanh thu; hơn 2k khách gần như chỉ mua một lần.

### 5.2. Hạn chế

- Dữ liệu lệch mạnh về UK và khách sỉ; khó tổng quát hóa sang B2C khác.  
- Không có nhãn “chân lý” cho cụm; đánh giá dựa metric nội tại và diễn giải nghiệp vụ.  
- Ward trên toàn bộ đặc trưng vẫn nhạy với scale dù đã chuẩn hóa.  
- Mốc thời gian cố định; không mô hình hóa theo mùa vụ chi tiết.

### 5.3. Hướng cải tiến

- Thử DBSCAN / HDBSCAN trên không gian PCA hoặc tập con.  
- Thêm đặc trưng mùa vụ, danh mục sản phẩm.  
- Pipeline dự đoán churn / next-purchase operational hóa (scoring định kỳ).  
- Demo Streamlit (`app.py`) đã có: lọc cụm, PCA tương tác, tra cứu khách, gợi ý chiến dịch.

---

## Tài liệu tham khảo

1. Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D  
2. Pedregosa et al. (2011). Scikit-learn: Machine Learning in Python. *JMLR*.  
3. Đề cương đề tài cuối kỳ môn Máy học (file `ML - De tai cuoi ky - Final.pdf`).
