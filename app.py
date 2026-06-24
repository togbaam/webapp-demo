import streamlit as st
import pandas as pd
import numpy as np
import io
import json
import uuid
import duckdb

# ==========================================
# CẤU HÌNH TRANG VÀ HÀM PHỤ TRỢ
# ==========================================
st.set_page_config(layout="wide", page_title="A-Score KHDN System")

def load_csv_to_df(csv_str):
    return pd.read_csv(io.StringIO(csv_str))

# Dữ liệu BCTC giả lập (để reset hoặc demo)
bs_template = """Mã_số,Chỉ_tiêu,Năm_2024,Năm_2025
100,TỔNG TÀI SẢN NGẮN HẠN,9000,8500
140,Hàng tồn kho,5000,4500
200,TỔNG TÀI SẢN DÀI HẠN,4000,3500
270,TỔNG TÀI SẢN,13000,12000
300,TỔNG NỢ PHẢI TRẢ,8000,6800
311,Phải trả người bán ngắn hạn,2000,1500
320,Vay và nợ thuê tài chính ngắn hạn,4000,3800
400,TỔNG VỐN CHỦ SỞ HỮU,5000,5200"""

is_template = """Mã_số,Chỉ_tiêu,Năm_2024,Năm_2025
10,Doanh thu thuần,20000,22000
20,Lợi nhuận gộp về bán hàng,5000,5500
22,Chi phí tài chính (Lãi vay),600,550
50,Tổng lợi nhuận kế toán trước thuế,900,950
60,Lợi nhuận sau thuế,720,760"""

cf_template = """Mã_số,Chỉ_tiêu,Năm_2024,Năm_2025
20,Lưu chuyển tiền thuần từ HĐKD,-500,1200"""

# ==========================================
# CÁC HÀM TÍNH TOÁN (Đã build từ trước)
# ==========================================
def calculate_fin_longlist(df_bs, df_is, df_cf):
    def get_val(df, code, year):
        try:
            return float(df[df['Mã_số'].astype(str) == str(code)][year].values[0])
        except:
            return 0.0

    ts_ngan_han = get_val(df_bs, '100', 'Năm_2025')
    hang_ton_kho = get_val(df_bs, '140', 'Năm_2025')
    phai_tra_nguoi_ban = get_val(df_bs, '311', 'Năm_2025')
    vay_ngan_han = get_val(df_bs, '320', 'Năm_2025')
    no_ngan_han = phai_tra_nguoi_ban + vay_ngan_han
    tong_no = get_val(df_bs, '300', 'Năm_2025')
    tong_vcsh = get_val(df_bs, '400', 'Năm_2025')
    tong_tai_san = get_val(df_bs, '270', 'Năm_2025')

    doanh_thu_thuan = get_val(df_is, '10', 'Năm_2025')
    doanh_thu_thuan_prev = get_val(df_is, '10', 'Năm_2024')
    loi_nhuan_gop = get_val(df_is, '20', 'Năm_2025')
    chi_phi_lai_vay = get_val(df_is, '22', 'Năm_2025')
    lntt = get_val(df_is, '50', 'Năm_2025')
    ebit = lntt + chi_phi_lai_vay
    lnst = get_val(df_is, '60', 'Năm_2025')
    cfo = get_val(df_cf, '20', 'Năm_2025')

    features = {'report_id': "REQ_DEMO_001"}
    features['FIN_01_CURRENT_RATIO'] = round(ts_ngan_han / no_ngan_han, 4) if no_ngan_han > 0 else 0
    features['FIN_02_QUICK_RATIO'] = round((ts_ngan_han - hang_ton_kho) / no_ngan_han, 4) if no_ngan_han > 0 else 0
    features['FIN_03_DEBT_TO_EQUITY'] = round(tong_no / tong_vcsh, 4) if tong_vcsh > 0 else 0
    features['FIN_04_INTEREST_COVERAGE'] = round(ebit / chi_phi_lai_vay, 4) if chi_phi_lai_vay > 0 else 0
    features['FIN_05_GROSS_MARGIN'] = round(loi_nhuan_gop / doanh_thu_thuan, 4) if doanh_thu_thuan > 0 else 0
    features['FIN_06_NET_MARGIN'] = round(lnst / doanh_thu_thuan, 4) if doanh_thu_thuan > 0 else 0
    features['FIN_07_ROE'] = round(lnst / tong_vcsh, 4) if tong_vcsh > 0 else 0
    features['FIN_08_ASSET_TURNOVER'] = round(doanh_thu_thuan / tong_tai_san, 4) if tong_tai_san > 0 else 0
    features['FIN_09_CFO_TO_DEBT'] = round(cfo / tong_no, 4) if tong_no > 0 else 0
    features['FIN_10_REVENUE_GROWTH'] = round((doanh_thu_thuan - doanh_thu_thuan_prev) / doanh_thu_thuan_prev, 4) if doanh_thu_thuan_prev > 0 else 0

    return pd.DataFrame([features])

def calculate_cic_longlist_demo():
    # Giả lập kết quả trả về của CIC giống hệt bài toán lúc trước
    features = {
        'report_id': "REQ_DEMO_001",
        'VAR_01_TOTAL_CURRENT_DEBT': 4700000000,
        'VAR_02_NUM_CREDIT_INSTITUTIONS': 1,
        'VAR_03_SHORT_TERM_RATIO': 0.7447,
        'VAR_04_MONTHS_ATTENTION_12M': 3,
        'VAR_05_MAX_ATTENTION_BAL_12M': 500000000,
        'VAR_06_MAX_HIST_DEBT_GROUP': 2,
        'VAR_07_MAX_PAST_DUE_DAYS': 45,
        'VAR_08_LIMIT_UTILIZATION': 0.94,
        'VAR_09_BAD_DEBT_5YR_FLAG': 0,
        'VAR_10_DEBT_TO_COLLATERAL_RATIO': 0.5529
    }
    return pd.DataFrame([features])

# ==========================================
# CÁC HÀM XỬ LÝ CIC (Thêm vào phần đầu file)
# ==========================================
def parse_cic_json_to_dfs(data: dict) -> dict:
    # 1. Sinh khóa ngoại cho lần tra cứu này
    query_time = data.get('report_info', {}).get('query_time', '1970-01-01T')
    report_date_str = query_time[:10].replace("-", "")
    
    unique_id = str(uuid.uuid4())[:8]
    report_id = f"REQ_{report_date_str}_{unique_id}"

    # 2. BẢNG 1: cic_current_debt
    current_debt_list = []
    for d in data.get('current_debts', []):
        current_debt_list.append({
            'report_id': report_id,
            'institution_code': d.get('institution_code'),
            'report_date': d.get('report_date'),
            'short_term_std': d.get('short_term_loans', {}).get('standard', 0),
            'short_term_att': d.get('short_term_loans', {}).get('attention', 0),
            'medium_term_std': d.get('medium_term_loans', {}).get('standard', 0),
            'medium_term_att': d.get('medium_term_loans', {}).get('attention', 0),
            'total_debt': d.get('total_debt', 0)
        })
    df_current_debt = pd.DataFrame(current_debt_list)

    # 3. BẢNG 2: cic_debt_history_12m
    history_dict = {}
    
    # Đọc dư nợ cần chú ý (attention)
    for att in data.get('attention_debt_12_months', []):
        month = att.get('month')
        if month:
            history_dict[month] = {
                'report_id': report_id,
                'report_month': month,
                'attention_balance': att.get('attention_balance', 0),
                'loan_balance': 0 # Giá trị mặc định
            }

    # Đọc dư nợ tổng (loan_balance) và merge vào dict
    for debt in data.get('debt_history_12_months', []):
        month = debt.get('month')
        if month:
            if month not in history_dict:
                history_dict[month] = {
                    'report_id': report_id,
                    'report_month': month,
                    'attention_balance': 0,
                    'loan_balance': debt.get('loan_balance', 0)
                }
            else:
                history_dict[month]['loan_balance'] = debt.get('loan_balance', 0)

    df_debt_history_12m = pd.DataFrame(list(history_dict.values()))

    # 4. BẢNG 3: cic_contract
    contract_list = []
    # Xử lý hợp đồng đang hoạt động
    for c in data.get('detailed_contracts', {}).get('active_loans', []):
        contract_list.append({
            'report_id': report_id,
            'contract_no': c.get('contract_no'),
            'max_debt_group': c.get('max_debt_group'),
            'credit_limit': c.get('credit_limit_vnd', 0),
            'remaining_principal': c.get('remaining_principal_vnd', 0),
            'term': c.get('term'),
            'max_past_due_days': c.get('max_past_due_days_5yr', 0),
            'is_active': 1
        })

    # Xử lý hợp đồng đã đóng (nếu có)
    for c in data.get('detailed_contracts', {}).get('inactive_loans', []):
        contract_list.append({
            'report_id': report_id,
            'contract_no': c.get('contract_no'),
            'max_debt_group': c.get('max_debt_group'),
            'credit_limit': c.get('credit_limit_vnd', 0),
            'remaining_principal': c.get('remaining_principal_vnd', 0),
            'term': c.get('term'),
            'max_past_due_days': c.get('max_past_due_days_5yr', 0),
            'is_active': 0
        })

    df_contract = pd.DataFrame(contract_list)

    # 5. BẢNG 4: cic_bad_debt_5yr
    bad_debt_list = []
    for b in data.get('bad_debt_history_5yr', []):
        bad_debt_list.append({
            'report_id': report_id,
            'last_incurred_date': b.get('last_incurred_date'),
            'debt_group': b.get('debt_group'),
            'past_due_days': b.get('past_due_days', 0),
            'amount_vnd': b.get('amount_vnd', 0)
        })
    df_bad_debt_5yr = pd.DataFrame(bad_debt_list)

    # 6. BẢNG 5: cic_collateral
    collateral_list = []
    for col in data.get('collaterals', []):
        collateral_list.append({
            'report_id': report_id,
            'type': col.get('type'),
            'total_asset_value': col.get('total_asset_value', 0)
        })
    df_collateral = pd.DataFrame(collateral_list)

    # Đóng gói toàn bộ kết quả vào một Dictionary
    return {
        "report_id": report_id,
        "cic_current_debt": df_current_debt,
        "cic_debt_history_12m": df_debt_history_12m,
        "cic_contract": df_contract,
        "cic_bad_debt_5yr": df_bad_debt_5yr,
        "cic_collateral": df_collateral
    }

def calculate_cic_longlist(parsed_tables: dict) -> pd.DataFrame:
    report_id = parsed_tables['report_id']
    df_curr = parsed_tables['cic_current_debt']
    df_hist = parsed_tables['cic_debt_history_12m']
    df_cont = parsed_tables['cic_contract']
    df_bad = parsed_tables['cic_bad_debt_5yr']
    df_coll = parsed_tables['cic_collateral']

    # Khởi tạo dictionary chứa biến
    features = {'report_id': report_id}

    # --- BLOCK 1: Dư nợ hiện thời ---
    if not df_curr.empty:
        features['VAR_01_TOTAL_CURRENT_DEBT'] = df_curr['total_debt'].sum()
        features['VAR_02_NUM_CREDIT_INSTITUTIONS'] = df_curr['institution_code'].nunique()
        total_short_term = df_curr['short_term_std'].sum() + df_curr['short_term_att'].sum()
        features['VAR_03_SHORT_TERM_RATIO'] = round(total_short_term / features['VAR_01_TOTAL_CURRENT_DEBT'], 4) if features['VAR_01_TOTAL_CURRENT_DEBT'] > 0 else 0
    else:
        features['VAR_01_TOTAL_CURRENT_DEBT'] = 0
        features['VAR_02_NUM_CREDIT_INSTITUTIONS'] = 0
        features['VAR_03_SHORT_TERM_RATIO'] = 0

    # --- BLOCK 2: Lịch sử 12 tháng ---
    if not df_hist.empty:
        features['VAR_04_MONTHS_ATTENTION_12M'] = int((df_hist['attention_balance'] > 0).sum())
        features['VAR_05_MAX_ATTENTION_BAL_12M'] = df_hist['attention_balance'].max()
    else:
        features['VAR_04_MONTHS_ATTENTION_12M'] = 0
        features['VAR_05_MAX_ATTENTION_BAL_12M'] = 0

    # --- BLOCK 3: Chi tiết Hợp đồng ---
    if not df_cont.empty:
        features['VAR_06_MAX_HIST_DEBT_GROUP'] = int(df_cont['max_debt_group'].astype(int).max())
        features['VAR_07_MAX_PAST_DUE_DAYS'] = int(df_cont['max_past_due_days'].astype(int).max())
        active_contracts = df_cont[df_cont['is_active'] == 1]
        total_limit = active_contracts['credit_limit'].sum()
        total_remaining = active_contracts['remaining_principal'].sum()
        features['VAR_08_LIMIT_UTILIZATION'] = round(total_remaining / total_limit, 4) if total_limit > 0 else 0
    else:
        features['VAR_06_MAX_HIST_DEBT_GROUP'] = 1 
        features['VAR_07_MAX_PAST_DUE_DAYS'] = 0
        features['VAR_08_LIMIT_UTILIZATION'] = 0

    # --- BLOCK 4: Nợ xấu 5 năm ---
    features['VAR_09_BAD_DEBT_5YR_FLAG'] = 1 if not df_bad.empty else 0

    # --- BLOCK 5: Tài sản bảo đảm ---
    if not df_coll.empty:
        total_collateral = df_coll['total_asset_value'].sum()
        features['VAR_10_DEBT_TO_COLLATERAL_RATIO'] = round(features['VAR_01_TOTAL_CURRENT_DEBT'] / total_collateral, 4) if total_collateral > 0 else 0
    else:
        features['VAR_10_DEBT_TO_COLLATERAL_RATIO'] = -1 

    return pd.DataFrame([features])

# ==========================================
# KHỞI TẠO SESSION STATE
# ==========================================
if 'df_bs' not in st.session_state:
    st.session_state.df_bs = load_csv_to_df(bs_template)
    st.session_state.df_is = load_csv_to_df(is_template)
    st.session_state.df_cf = load_csv_to_df(cf_template)
if 'longlist_fin' not in st.session_state:
    st.session_state.longlist_fin = pd.DataFrame()
if 'longlist_cic' not in st.session_state:
    st.session_state.longlist_cic = pd.DataFrame()
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "Tab 1: Báo Cáo Tài Chính"

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
st.title("Hệ thống Chấm điểm Tín dụng Doanh nghiệp (A-Score)")

# Dùng radio button để giả lập Tabs (giúp việc chuyển tab bằng nút Next dễ dàng hơn)
tabs = ["Tab 1: Báo Cáo Tài Chính", "Tab 2: Dữ liệu CIC", "Tab 3: Cấu hình Model & Score"]
selected_tab = st.radio("Quy trình Đánh giá:", tabs, index=tabs.index(st.session_state.active_tab), horizontal=True)

# ------------------------------------------
# TAB 1: BÁO CÁO TÀI CHÍNH
# ------------------------------------------
if selected_tab == "Tab 1: Báo Cáo Tài Chính":
    st.header("1. Nhập liệu Báo cáo Tài chính")
    st.markdown("Chỉnh sửa trực tiếp trên bảng hoặc click tải dữ liệu Công ty A.")
    
    if st.button("Nạp nhanh dữ liệu Công ty A"):
        st.session_state.df_bs = load_csv_to_df(bs_template)
        st.session_state.df_is = load_csv_to_df(is_template)
        st.session_state.df_cf = load_csv_to_df(cf_template)
        st.rerun()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Cân Đối Kế Toán")
        edited_bs = st.data_editor(st.session_state.df_bs, num_rows="dynamic", key="bs_editor")
    with col2:
        st.subheader("Kết Quả Kinh Doanh")
        edited_is = st.data_editor(st.session_state.df_is, num_rows="dynamic", key="is_editor")
    with col3:
        st.subheader("Lưu Chuyển Tiền Tệ")
        edited_cf = st.data_editor(st.session_state.df_cf, num_rows="dynamic", key="cf_editor")

    if st.button("Tính toán Biến Tài Chính (FIN Longlist) & Tiếp tục"):
        st.session_state.longlist_fin = calculate_fin_longlist(edited_bs, edited_is, edited_cf)
        st.success("Đã tính toán thành công FIN Longlist!")
        st.dataframe(st.session_state.longlist_fin)
        
        # Chuyển tab
        st.session_state.active_tab = "Tab 2: Dữ liệu CIC"
        st.rerun()

# Hãy thêm dòng import này lên đầu file app.py của bạn:
# import duckdb

# ------------------------------------------
# TAB 2: DỮ LIỆU CIC (CẬP NHẬT CHẠY DYNAMIC SQL)
# ------------------------------------------
elif selected_tab == "Tab 2: Dữ liệu CIC":
    st.header("2. Truy vấn dữ liệu CIC & Trích xuất Biến")
    
    st.info("Tải lên file JSON CIC. Hệ thống sẽ tự động Parse thành các bảng con (Temp Tables).")
    
    uploaded_file = st.file_uploader("Chọn file JSON CIC", type=["json"])
    
    if uploaded_file is not None:
        # Load JSON và Parse 1 lần duy nhất, lưu vào Session State để tái sử dụng
        if 'cic_parsed_tables' not in st.session_state or st.session_state.get('last_uploaded_file') != uploaded_file.name:
            import json
            try:
                cic_data = json.load(uploaded_file)
                st.session_state.cic_parsed_tables = parse_cic_json_to_dfs(cic_data)
                st.session_state.last_uploaded_file = uploaded_file.name
                st.success("Đã Parse JSON thành 5 bảng dữ liệu (Sẵn sàng trong bộ nhớ)!")
            except Exception as e:
                st.error(f"Có lỗi khi đọc file JSON: {e}")
                st.stop()
                
        # Khai báo các DataFrame ra biến local. 
        # DuckDB sẽ tự động nhận diện tên các biến này như các bảng (Tables) trong SQL!
        parsed_tables = st.session_state.cic_parsed_tables
        cic_current_debt = parsed_tables['cic_current_debt']
        cic_debt_history_12m = parsed_tables['cic_debt_history_12m']
        cic_contract = parsed_tables['cic_contract']
        cic_bad_debt_5yr = parsed_tables['cic_bad_debt_5yr']
        cic_collateral = parsed_tables['cic_collateral']

        st.write("---")
        # Chọn phương thức trích xuất
        method = st.radio(
            "Cơ chế trích xuất biến vào Longlist:", 
            ["Cách 1: Chạy Logic Python mặc định", "Cách 2: Cấu hình biến bằng SQL (Dynamic)"],
            horizontal=True
        )

        # CÁCH 1: PYTHON LOGIC
        if method == "Cách 1: Chạy Logic Python mặc định":
            if st.button("▶Chạy tính toán (Python Engine)", type="primary"):
                st.session_state.longlist_cic = calculate_cic_longlist(parsed_tables)
                st.success("Trích xuất thành công 10 biến CIC cơ bản!")
                st.dataframe(st.session_state.longlist_cic)

        # CÁCH 2: DYNAMIC SQL
        else:
            st.markdown("Bạn có thể `SELECT`, `JOIN` trực tiếp trên 5 bảng sau: `cic_current_debt`, `cic_debt_history_12m`, `cic_contract`, `cic_bad_debt_5yr`, `cic_collateral`")
            
            with st.expander("Xem 3 mẫu SQL trích xuất biến (Ví dụ)"):
                st.code("""-- MẪU 1: Lấy các biến từ Dư nợ hiện tại
SELECT 
    report_id,
    SUM(total_debt) AS VAR_01_TOTAL_CURRENT_DEBT,
    COUNT(DISTINCT institution_code) AS VAR_02_NUM_CREDIT_INSTITUTIONS
FROM cic_current_debt
GROUP BY report_id;""", language="sql")
                
                st.code("""-- MẪU 2: Tính lịch sử nợ Cần chú ý (Nhóm 2) trong 12 tháng
SELECT 
    report_id,
    SUM(CASE WHEN attention_balance > 0 THEN 1 ELSE 0 END) AS VAR_04_MONTHS_ATTENTION_12M,
    MAX(attention_balance) AS VAR_05_MAX_ATTENTION_BAL_12M
FROM cic_debt_history_12m
GROUP BY report_id;""", language="sql")
                
                st.code("""-- MẪU 3: Bảng Longlist TỔNG HỢP (Join nhiều bảng)
SELECT 
    c.report_id,
    SUM(c.total_debt) AS VAR_01_TOTAL_CURRENT_DEBT,
    MAX(h.max_att) AS VAR_05_MAX_ATTENTION_BAL_12M,
    MAX(ct.max_debt_group) AS VAR_06_MAX_HIST_DEBT_GROUP
FROM cic_current_debt c
LEFT JOIN (
    SELECT report_id, MAX(attention_balance) as max_att 
    FROM cic_debt_history_12m GROUP BY report_id
) h ON c.report_id = h.report_id
LEFT JOIN (
    SELECT report_id, MAX(max_debt_group) as max_debt_group 
    FROM cic_contract GROUP BY report_id
) ct ON c.report_id = ct.report_id
GROUP BY c.report_id;""", language="sql")

            # Khu vực User nhập SQL
            default_sql = "SELECT * FROM cic_current_debt;"
            sql_query = st.text_area("Cấu hình câu lệnh SQL của bạn:", value=default_sql, height=150)
            
            if st.button("⚡ Thực thi truy vấn SQL", type="primary"):
                try:
                    import duckdb
                    # DuckDB tự động tìm các biến local DataFrame (như cic_current_debt) và chạy SQL
                    df_result = duckdb.query(sql_query).df()
                    
                    st.session_state.longlist_cic = df_result
                    st.success("Truy vấn thành công! Bảng Longlist CIC đã được cập nhật.")
                    st.dataframe(st.session_state.longlist_cic)
                except Exception as e:
                    st.error(f"Lỗi cú pháp SQL hoặc Bảng không tồn tại:\n\n{e}")
                    
        st.write("---")
        # Nút Next chỉ hiện ra khi bảng Longlist đã được tính toán/query thành công
        if not st.session_state.longlist_cic.empty:
            if st.button("▶Chuyển sang Cấu hình Model & Score"):
                st.session_state.active_tab = "Tab 3: Cấu hình Model & Score"
                st.rerun()

# ------------------------------------------
# TAB 3: CẤU HÌNH & TÍNH ĐIỂM (CẬP NHẬT MỚI NHẤT)
# ------------------------------------------
elif selected_tab == "Tab 3: Cấu hình Model & Score":
    st.header("3. Cấu hình Tham số & Tính điểm")
    
    if st.session_state.longlist_fin.empty and st.session_state.longlist_cic.empty:
        st.warning("Vui lòng chạy tính toán Longlist ở Tab 1 và Tab 2 trước khi cấu hình!")
        st.stop()

    # Phân tách rõ ràng 2 tập biến
    fin_vars = [col for col in st.session_state.longlist_fin.columns if col != 'report_id']
    cic_vars = [col for col in st.session_state.longlist_cic.columns if col != 'report_id']
    
    # Khởi tạo biến đếm số lượng sub-model trong session_state
    if 'model_count' not in st.session_state:
        st.session_state.model_count = 1

    # Nút điều khiển thêm/bớt Model
    col_btn1, col_btn2, _ = st.columns([2, 2, 6])
    with col_btn1:
        if st.button("➕ Thêm Sub-Model", width="stretch"):
            st.session_state.model_count += 1
            st.rerun()
    with col_btn2:
        if st.button("➖ Xóa Model cuối", width="stretch") and st.session_state.model_count > 1:
            st.session_state.model_count -= 1
            st.rerun()

    st.write("---")
    
    # Dictionary lưu toàn bộ cấu hình của tất cả các model được tạo
    all_models_config = {}

    # Render giao diện động cho từng Model
    for i in range(st.session_state.model_count):
        with st.container(border=True):
            col_name, col_source = st.columns(2)
            with col_name:
                m_name = st.text_input(f"Tên Model {i+1}:", value=f"Sub_Model_{i+1}", key=f"m_name_{i}")
            with col_source:
                m_source = st.selectbox(f"Nguồn biến cho [{m_name}]:", ["FIN", "CIC"], key=f"m_source_{i}")

            available_vars = fin_vars if m_source == "FIN" else cic_vars
            df_source = st.session_state.longlist_fin if m_source == "FIN" else st.session_state.longlist_cic

            m_intercept = st.number_input(f"Hệ số chặn (Intercept) của [{m_name}]:", value=0.0, key=f"m_int_{i}")
            selected_vars = st.multiselect(f"Chọn các biến cho [{m_name}]:", available_vars, key=f"m_vars_{i}")

            var_configs = {}
            if selected_vars:
                st.caption("Cấu hình trọng số và Bins cho từng biến đã chọn:")
                
            for var in selected_vars:
                with st.expander(f"Biến: {var} (Giá trị KH: {df_source[var][0]})", expanded=True):
                    coef = st.number_input(f"Hệ số (Coefficient) của {var}:", value=1.0, key=f"coef_{i}_{var}")
                    
                    st.write("Cấu hình Bins (Min, Max, WOE):")
                    default_bins = pd.DataFrame({"Min": [-999.0, 1.0], "Max": [1.0, 999.0], "WOE": [-0.5, 0.8]})
                    edited_bins = st.data_editor(default_bins, num_rows="dynamic", key=f"bins_{i}_{var}", width="stretch")
                    
                    var_configs[var] = {"coef": coef, "bins": edited_bins}

            if m_name in all_models_config:
                st.error(f"Trùng tên Model '{m_name}'. Vui lòng đổi tên để không bị lỗi Combine!")
            else:
                all_models_config[m_name] = {
                    "data": df_source,
                    "intercept": m_intercept,
                    "vars_config": var_configs
                }

    # ==========================================
    # COMBINE MODEL (MÔ HÌNH TỔNG HỢP)
    # ==========================================
    st.write("---")
    st.subheader("Cấu hình Combine Model (Mô hình Tổng hợp)")
    
    available_model_names = list(all_models_config.keys())
    selected_to_combine = st.multiselect(
        "1. Chọn các Sub-Models để đưa vào Combine Model:", 
        available_model_names, 
        default=available_model_names
    )

    combine_weights = {}
    if selected_to_combine:
        st.write("2. Thiết lập trọng số (%) cho từng Model:")
        cols = st.columns(len(selected_to_combine))
        for idx, m_name in enumerate(selected_to_combine):
            with cols[idx]:
                default_weight = 100.0 / len(selected_to_combine)
                w = st.number_input(f"Trọng số của [{m_name}] (%)", min_value=0.0, max_value=100.0, value=default_weight, key=f"weight_{m_name}")
                combine_weights[m_name] = w / 100.0
                
    if st.button("CHẠY TÍNH ĐIỂM (SCORING)", type="primary", width="stretch"):
        if sum(combine_weights.values()) <= 0 and selected_to_combine:
            st.warning("Tổng trọng số phải lớn hơn 0!")
        elif not selected_to_combine:
            st.warning("Vui lòng chọn ít nhất 1 Model để tính điểm!")
        else:
            # Hàm tính điểm cập nhật: Trả về cả Điểm tổng và Bảng phân rã chi tiết
            def calc_score_with_breakdown(longlist, config_vars, intercept):
                breakdown = {"Hệ số chặn (Intercept)": intercept}
                total_score = intercept
                
                for var, cfg in config_vars.items():
                    val = longlist[var][0]
                    coef = cfg['coef']
                    bins = cfg['bins']
                    
                    woe = 0.0
                    for _, row in bins.iterrows():
                        if pd.isna(row['Min']) or pd.isna(row['Max']) or pd.isna(row['WOE']): 
                            continue
                        if row['Min'] <= val <= row['Max']:
                            woe = float(row['WOE'])
                            break
                    
                    # Tính điểm của riêng biến này = WOE * Coefficient
                    var_score = woe * coef
                    breakdown[var] = var_score
                    total_score += var_score
                    
                return total_score, breakdown

            # Tính điểm cho từng Sub-Model
            sub_scores = {}
            sub_breakdowns = {}
            for m_name in selected_to_combine:
                cfg = all_models_config[m_name]
                score, breakdown = calc_score_with_breakdown(cfg['data'], cfg['vars_config'], cfg['intercept'])
                sub_scores[m_name] = score
                sub_breakdowns[m_name] = breakdown
            
            # Tính Final Score (Trung bình gia quyền)
            final_score = 0
            for m_name, s in sub_scores.items():
                final_score += s * combine_weights[m_name]
            
            # --- HIỂN THỊ KẾT QUẢ ---
            st.divider()
            st.markdown("### KẾT QUẢ CHẤM ĐIỂM KHÁCH HÀNG")
            
            # Tự động chia cột dựa trên số lượng Model + 1 cột cho Điểm Tổng
            res_cols = st.columns(len(sub_scores) + 1)
            
            # Hiển thị từng Model và chi tiết phân rã điểm
            for idx, (m_name, s) in enumerate(sub_scores.items()):
                with res_cols[idx]:
                    st.metric(f"Điểm {m_name}", round(s, 4))
                    with st.expander("🔍 Xem điểm thành phần", expanded=False):
                        # Chuyển dictionary breakdown thành DataFrame để in ra bảng đẹp
                        df_bd = pd.DataFrame(list(sub_breakdowns[m_name].items()), columns=['Thành phần', 'Điểm số'])
                        st.dataframe(df_bd, hide_index=True, width="stretch")
            
            # Hiển thị Final Score ở cột cuối cùng
            with res_cols[-1]:
                st.metric("FINAL SCORE", round(final_score, 4))
            
            # Logic ngưỡng phê duyệt
            if final_score > 5.0: 
                st.success("KẾT LUẬN: KHÁCH HÀNG ĐẠT ĐIỂM TÍN DỤNG TỐT")
            else:
                st.error("KẾT LUẬN: RỦI RO CAO - XEM XÉT TỪ CHỐI")

# Mẫu SQL CIC
# VAR_01_TOTAL_CURRENT_DEBT
# SELECT 
#     report_id,
#     SUM(total_debt) AS VAR_01_TOTAL_CURRENT_DEBT
# FROM cic_current_debt
# GROUP BY report_id;

# VAR_04_MONTHS_ATTENTION_12M
# SELECT 
#     report_id,
#     SUM(CASE WHEN attention_balance > 0 THEN 1 ELSE 0 END) AS VAR_04_MONTHS_ATTENTION_12M
# FROM cic_debt_history_12m
# GROUP BY report_id;

# VAR_06_MAX_HIST_DEBT_GROUP
# SELECT 
#     report_id,
#     MAX(CAST(max_debt_group AS INT)) AS VAR_06_MAX_HIST_DEBT_GROUP
# FROM cic_contract
# GROUP BY report_id;

# Nếu User Rủi ro muốn tạo thành một bảng Longlist gồm nhiều biến cùng lúc, họ có thể sử dụng câu lệnh LEFT JOIN lấy report_id làm gốc như sau:
# SELECT 
#     c.report_id,
#     SUM(c.total_debt) AS VAR_01_TOTAL_CURRENT_DEBT,
#     MAX(h.months_attention) AS VAR_04_MONTHS_ATTENTION_12M,
#     MAX(ct.max_hist_group) AS VAR_06_MAX_HIST_DEBT_GROUP
# FROM cic_current_debt c
# LEFT JOIN (
#     SELECT report_id, SUM(CASE WHEN attention_balance > 0 THEN 1 ELSE 0 END) AS months_attention 
#     FROM cic_debt_history_12m 
#     GROUP BY report_id
# ) h ON c.report_id = h.report_id
# LEFT JOIN (
#     SELECT report_id, MAX(CAST(max_debt_group AS INT)) AS max_hist_group 
#     FROM cic_contract 
#     GROUP BY report_id
# ) ct ON c.report_id = ct.report_id
# GROUP BY c.report_id;
