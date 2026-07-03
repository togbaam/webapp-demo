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

def load_mock_trans_longlist():
    """
    Giả lập một bảng lấy trực tiếp từ DB Transaction của ngân hàng.
    Chứa các hành vi giao dịch nội bộ của khách hàng.
    """
    features = {
        'report_id': "REQ_DEMO_001",
        'TRANS_01_AVG_BALANCE': 1500000000,   # Số dư bình quân 3 tháng (VND)
        'TRANS_02_TXN_COUNT': 125,            # Số lượng giao dịch trong tháng
        'TRANS_03_RETURNED_CHQ_COUNT': 0,     # Số séc bị trả lại
        'TRANS_04_LATE_PAYMENT_DAYS': 0,      # Số ngày trễ hạn thanh toán nội bộ
        'TRANS_05_CASH_IN_OUT_RATIO': 1.2     # Tỷ lệ tiền vào / tiền ra (Cash in/out ratio)
    }
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


def pull_cic_h2h_mock():
    """
    Giả lập API kết nối CIC H2H kéo dữ liệu JSON nguyên bản của khách hàng về hệ thống.
    (Sử dụng số liệu của Công ty A làm mẫu)
    """
    return {
        "report_info": {"query_time": "2026-06-23T10:15:00Z"},
        "current_debts": [
            {
                "institution_code": "TCTD_05", "report_date": "2026-05-31",
                "short_term_loans": {"standard": 3500000000, "attention": 0},
                "medium_term_loans": {"standard": 1200000000, "attention": 0},
                "total_debt": 4700000000
            }
        ],
        "attention_debt_12_months": [
            {"month": "05/2026", "attention_balance": 0},
            {"month": "08/2025", "attention_balance": 250000000},
            {"month": "07/2025", "attention_balance": 500000000},
            {"month": "06/2025", "attention_balance": 500000000}
        ],
        "debt_history_12_months": [
            {"month": "05/2026", "loan_balance": 4700000000},
            {"month": "06/2025", "loan_balance": 5500000000}
        ],
        "detailed_contracts": {
            "active_loans": [{
                "contract_no": "HD_ACB_2024_01", "max_debt_group": "2",
                "credit_limit_vnd": 5000000000, "remaining_principal_vnd": 4700000000,
                "term": "Trung hạn", "max_past_due_days_5yr": 45
            }]
        },
        "collaterals": [{
            "type": "Bằng Tài sản", "total_asset_value": 8500000000
        }]
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
# Khởi tạo luôn bảng Transaction có sẵn dữ liệu vì nó kéo thẳng từ DB nội bộ
if 'longlist_trans' not in st.session_state:
    st.session_state.longlist_trans = load_mock_trans_longlist()
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

    st.write("---")
    # Chọn phương thức trích xuất cho FIN
    method_fin = st.radio(
        "Cơ chế trích xuất biến vào Longlist FIN:", 
        ["Cách 1: Chạy Logic Python mặc định", "Cách 2: Cấu hình biến bằng SQL (Dynamic)"],
        horizontal=True,
        key="method_fin"
    )

    # CÁCH 1: PYTHON LOGIC
    if method_fin == "Cách 1: Chạy Logic Python mặc định":
        if st.button("▶ Chạy tính toán (Python Engine)", type="primary"):
            st.session_state.longlist_fin = calculate_fin_longlist(edited_bs, edited_is, edited_cf)
            st.success("Đã tính toán thành công FIN Longlist!")
            st.dataframe(st.session_state.longlist_fin)

    # CÁCH 2: DYNAMIC SQL
    else:
        st.markdown("💡 Bạn có thể `SELECT` trực tiếp trên 3 bảng dữ liệu vừa nhập: `edited_bs`, `edited_is`, `edited_cf`")
        
        with st.expander("📋 Xem mẫu SQL trích xuất biến Tài chính (Ví dụ)"):
            st.code("""-- MẪU: Tính Hệ số Nợ / Vốn CSH (Từ Bảng Cân Đối Kế Toán 'edited_bs')
SELECT 
    'REQ_DEMO_001' AS report_id,
    MAX(CASE WHEN Mã_số = '300' THEN Năm_2025 END) / NULLIF(MAX(CASE WHEN Mã_số = '400' THEN Năm_2025 END), 0) AS FIN_03_DEBT_TO_EQUITY
FROM edited_bs;""", language="sql")
            
        default_sql_fin = """SELECT 
    'REQ_DEMO_001' AS report_id,
    MAX(CASE WHEN Mã_số = '300' THEN Năm_2025 END) / NULLIF(MAX(CASE WHEN Mã_số = '400' THEN Năm_2025 END), 0) AS FIN_03_DEBT_TO_EQUITY
FROM edited_bs;"""
        
        sql_query_fin = st.text_area("Cấu hình câu lệnh SQL của bạn:", value=default_sql_fin, height=150, key="sql_fin")
        
        if st.button("⚡ Thực thi truy vấn SQL FIN", type="primary"):
            try:
                import duckdb
                # DuckDB tự động nhận diện các dataframe edited_bs, edited_is, edited_cf
                df_result_fin = duckdb.query(sql_query_fin).df()
                
                st.session_state.longlist_fin = df_result_fin
                st.success("Truy vấn thành công! Bảng Longlist FIN đã được cập nhật.")
                st.dataframe(st.session_state.longlist_fin)
            except Exception as e:
                st.error(f"Lỗi cú pháp SQL hoặc Bảng không tồn tại:\n\n{e}")

    st.write("---")
    # Nút Next chỉ hiện ra khi bảng Longlist FIN đã có dữ liệu
    if not st.session_state.longlist_fin.empty:
        if st.button("▶ Chuyển sang Tab 2: Dữ liệu CIC"):
            st.session_state.active_tab = "Tab 2: Dữ liệu CIC"
            st.rerun()

# ------------------------------------------
# TAB 2: DỮ LIỆU CIC (CHUẨN HÓA LUỒNG THEO KIẾN TRÚC MỚI)
# ------------------------------------------
elif selected_tab == "Tab 2: Dữ liệu CIC":
    st.header("2. Tiêu chuẩn hóa Luồng CIC")
    st.info("Luồng hệ thống: Kéo API CIC H2H ➔ Lưu vào [Table raw CIC] ➔ Xử lý qua [Feature Engineering] hoặc [SQL Text] ➔ Lưu [Table short list CIC]")
    
    # Nút bấm mô phỏng cổng kết nối CIC H2H thay vì upload file
    if st.button("🌐 Kết nối CIC H2H (Kéo dữ liệu tự động Công ty A)", type="primary"):
        with st.spinner("Đang kết nối cổng API CIC H2H..."):
            try:
                # 1. Lấy dữ liệu qua CIC H2H
                cic_data_raw = pull_cic_h2h_mock()
                
                # 2. Lưu vào Table raw CIC (Parse JSON thành các bảng chuẩn hóa)
                st.session_state.cic_parsed_tables = parse_cic_json_to_dfs(cic_data_raw)
                st.session_state.cic_h2h_connected = True
            except Exception as e:
                st.error(f"Lỗi kết nối H2H: {e}")
                st.stop()
                
    if st.session_state.get('cic_h2h_connected', False) and 'cic_parsed_tables' in st.session_state:
        st.success("✅ Dữ liệu H2H đã kéo thành công và lưu vào 5 bảng của [Table raw CIC]!")
        
        # Đưa các bảng RAW vào bộ nhớ local để DuckDB có thể đọc được bằng SQL
        parsed_tables = st.session_state.cic_parsed_tables
        cic_current_debt = parsed_tables['cic_current_debt']
        cic_debt_history_12m = parsed_tables['cic_debt_history_12m']
        cic_contract = parsed_tables['cic_contract']
        cic_bad_debt_5yr = parsed_tables['cic_bad_debt_5yr']
        cic_collateral = parsed_tables['cic_collateral']

        st.write("---")
        # Chọn phương thức xử lý theo Flowchart
        method_cic = st.radio(
            "Chọn cơ chế xử lý từ [Table raw CIC] sang [Table short list CIC]:", 
            ["Xử lý qua Feature Engineering (Python Engine)", "Xử lý qua SQL Text (Dynamic Query)"],
            horizontal=True
        )

        # ------------------------------------
        # CÁCH 1: LUỒNG FEATURE ENGINEERING
        # ------------------------------------
        if method_cic == "Xử lý qua Feature Engineering (Python Engine)":
            if st.button("▶ Chạy Feature Engineering", type="primary"):
                # Gọi hàm tính toán Longlist bằng Python
                st.session_state.longlist_cic = calculate_cic_longlist(parsed_tables)
                st.success("✅ Chạy Feature Engineering thành công! Dữ liệu đã lưu vào [Table short list CIC].")
                st.dataframe(st.session_state.longlist_cic)

        # ------------------------------------
        # CÁCH 2: LUỒNG SQL TEXT
        # ------------------------------------
        else:
            st.markdown("💡 Bạn có thể viết SQL trực tiếp trên 5 bảng Raw: `cic_current_debt`, `cic_debt_history_12m`, `cic_contract`, `cic_bad_debt_5yr`, `cic_collateral`")
            
            with st.expander("📋 Xem 3 mẫu SQL trích xuất biến CIC (Ví dụ)"):
                st.code("""-- MẪU 1: Lấy các biến từ Dư nợ hiện tại
SELECT 
    report_id,
    SUM(total_debt) AS VAR_01_TOTAL_CURRENT_DEBT,
    COUNT(DISTINCT institution_code) AS VAR_02_NUM_CREDIT_INSTITUTIONS
FROM cic_current_debt
GROUP BY report_id;""", language="sql")
                
                st.code("""-- MẪU 2: Bảng Longlist TỔNG HỢP (Join nhiều bảng)
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

            default_sql_cic = "SELECT * FROM cic_current_debt;"
            sql_query_cic = st.text_area("Cấu hình SQL Text của bạn:", value=default_sql_cic, height=150, key="sql_cic")
            
            if st.button("⚡ Thực thi truy vấn SQL CIC", type="primary"):
                try:
                    import duckdb
                    # Chạy Query trực tiếp trên các dataframe local
                    df_result_cic = duckdb.query(sql_query_cic).df()
                    
                    st.session_state.longlist_cic = df_result_cic
                    st.success("✅ Truy vấn SQL thành công! Dữ liệu đã lưu vào [Table short list CIC].")
                    st.dataframe(st.session_state.longlist_cic)
                except Exception as e:
                    st.error(f"Lỗi cú pháp SQL hoặc Bảng không tồn tại:\n\n{e}")
                    
        st.write("---")
        if not st.session_state.longlist_cic.empty:
            if st.button("▶ Chuyển sang Tab 3: Cấu hình Model & Score"):
                st.session_state.active_tab = "Tab 3: Cấu hình Model & Score"
                st.rerun()

# ------------------------------------------
# TAB 3: CẤU HÌNH & TÍNH ĐIỂM (CẬP NHẬT MỚI NHẤT)
# ------------------------------------------
elif selected_tab == "Tab 3: Cấu hình Model & Score":
    st.header("3. Cấu hình Tham số & Tính điểm")
    
    # Chặn nếu không có bất kỳ nguồn dữ liệu nào
    if st.session_state.longlist_fin.empty and st.session_state.longlist_cic.empty and st.session_state.longlist_trans.empty:
        st.warning("⚠️ Vui lòng chuẩn bị dữ liệu (FIN, CIC hoặc TRANS) trước khi cấu hình!")
        st.stop()

    # Phân tách rõ ràng 3 tập biến (Có check empty để tránh lỗi nếu user chưa chạy luồng nào)
    fin_vars = [col for col in st.session_state.longlist_fin.columns if col != 'report_id'] if not st.session_state.longlist_fin.empty else []
    cic_vars = [col for col in st.session_state.longlist_cic.columns if col != 'report_id'] if not st.session_state.longlist_cic.empty else []
    trans_vars = [col for col in st.session_state.longlist_trans.columns if col != 'report_id'] if not st.session_state.longlist_trans.empty else []
    
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
                # Bổ sung nguồn TRANS
                m_source = st.selectbox(f"Nguồn biến cho [{m_name}]:", ["FIN", "CIC", "TRANS"], key=f"m_source_{i}")

            # Đọc danh sách biến và Data tương ứng với lựa chọn
            if m_source == "FIN":
                available_vars = fin_vars
                df_source = st.session_state.longlist_fin
            elif m_source == "CIC":
                available_vars = cic_vars
                df_source = st.session_state.longlist_cic
            else: # m_source == "TRANS"
                available_vars = trans_vars
                df_source = st.session_state.longlist_trans

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
    # COMBINE MODEL (MÔ HÌNH TỔNG HỢP VÀ RATING SCALE)
    # ==========================================
    st.write("---")
    st.subheader("🎯 Cấu hình Combine Model (Mô hình Tổng hợp)")
    
    # Khởi tạo biến đếm số lượng Combine Model
    if 'combine_count' not in st.session_state:
        st.session_state.combine_count = 1

    # Nút điều khiển thêm/bớt Combine Model
    col_cb1, col_cb2, _ = st.columns([2, 2, 6])
    with col_cb1:
        if st.button("➕ Thêm Combine Model", width='stretch'):
            st.session_state.combine_count += 1
            st.rerun()
    with col_cb2:
        if st.button("➖ Xóa Combine Model", width='stretch') and st.session_state.combine_count > 1:
            st.session_state.combine_count -= 1
            st.rerun()

    st.write("---")
    all_combines_config = {}
    available_model_names = list(all_models_config.keys())

    # Giao diện cấu hình linh hoạt cho NHIỀU Combine Model
    for j in range(st.session_state.combine_count):
        with st.container(border=True):
            cb_name = st.text_input(f"Tên Combine Model {j+1}:", value=f"Combine_Model_{j+1}", key=f"cb_name_{j}")
            
            selected_to_combine = st.multiselect(
                f"Chọn các Sub-Models cho [{cb_name}]:", 
                available_model_names, 
                key=f"cb_select_{j}"
            )
            
            combine_weights = {}
            if selected_to_combine:
                cols = st.columns(len(selected_to_combine))
                for idx, m_name in enumerate(selected_to_combine):
                    with cols[idx]:
                        # Cấu hình Weight (w) cho từng sub-model trong phương trình f_total
                        w = st.number_input(f"Trọng số (Weight) của [{m_name}]", value=1.0, key=f"w_{j}_{m_name}")
                        combine_weights[m_name] = w
                        
            if cb_name in all_combines_config:
                st.error(f"⚠️ Trùng tên Combine Model '{cb_name}'. Vui lòng đổi tên!")
            else:
                all_combines_config[cb_name] = combine_weights

    # --- CẤU HÌNH BẢNG RATING (PD -> RANK) ---
    st.write("---")
    st.subheader("📊 Cấu hình Mapping Hạng Tín Dụng (Rating Scale)")
    with st.expander("Mở bảng cấu hình PD ra Hạng (10 Ranks)", expanded=False):
        st.markdown("Hệ thống sẽ lấy giá trị **PD Final (%)** so sánh từ trên xuống dưới với **PD Max (%)**. Nếu nhỏ hơn hoặc bằng thì gán Hạng tương ứng.")
        default_rating_scale = pd.DataFrame({
            "Hạng (Rank)": ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"],
            "PD Max (%)": [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]
        })
        rating_editor = st.data_editor(default_rating_scale, num_rows="dynamic", width='stretch')

# --- CẤU HÌNH PHÂN KHÚC (SEGMENTATION) ---
    st.write("---")
    st.subheader("🧩 Cấu hình Phân khúc Khách hàng (Segmentation)")
    
    # 1. Gom tất cả các biến từ 3 nguồn (FIN, CIC, TRANS) vào 1 list chung
    all_available_vars = []
    customer_values = {}
    for df in [st.session_state.get('longlist_fin', pd.DataFrame()), 
               st.session_state.get('longlist_cic', pd.DataFrame()), 
               st.session_state.get('longlist_trans', pd.DataFrame())]:
        if not df.empty:
            for col in df.columns:
                if col != 'report_id':
                    all_available_vars.append(col)
                    customer_values[col] = df[col][0]

    if all_available_vars:
        segment_var = st.selectbox("1. Chọn biến làm Căn cứ Phân khúc (Segment Variable):", all_available_vars)
        st.caption(f"💡 Giá trị thực tế của khách hàng hiện tại đối với biến **{segment_var}**: `{customer_values.get(segment_var, 'N/A')}`")

        st.markdown("2. Thiết lập các ngưỡng (Min, Max) và gán **Combine Model** tương ứng cho từng phân khúc:")
        
        combine_model_list = list(all_combines_config.keys())
        if combine_model_list:
            default_segments = pd.DataFrame({
                "Tên Phân Khúc": ["Rủi ro thấp", "Rủi ro cao"],
                "Min": [-999999.0, 1.0],
                "Max": [1.0, 999999.0],
                "Combine Model": [combine_model_list[0], combine_model_list[-1]]
            })
            
            # Sử dụng column_config để biến cột Combine Model thành dạng Dropdown list
            segment_editor = st.data_editor(
                default_segments, 
                num_rows="dynamic", 
                width='stretch',
                column_config={
                    "Combine Model": st.column_config.SelectboxColumn(
                        "Combine Model Áp dụng",
                        options=combine_model_list,
                        required=True
                    )
                }
            )
        else:
            st.warning("Vui lòng tạo ít nhất 1 Combine Model ở bước trên để cấu hình phân khúc!")
            segment_editor = pd.DataFrame()
    else:
        st.warning("Không có dữ liệu biến nào. Vui lòng kiểm tra lại quá trình trích xuất!")

    # --- ENGINE TÍNH TOÁN TỰ ĐỘNG THEO PHÂN KHÚC ---
    if st.button("🚀 CHẠY ĐÁNH GIÁ (SEGMENTATION & SCORING)", type="primary", width='stretch'):
        if 'segment_editor' not in locals() or segment_editor.empty:
            st.error("Chưa có cấu hình Phân khúc nào hợp lệ!")
            st.stop()
            
        # BƯỚC 1: TÌM PHÂN KHÚC CỦA KHÁCH HÀNG DỰA TRÊN BIẾN ĐÃ CHỌN
        customer_val = customer_values.get(segment_var, 0)
        matched_segment = None
        assigned_combine_model = None
        
        for _, row in segment_editor.iterrows():
            if pd.isna(row['Min']) or pd.isna(row['Max']):
                continue
            if row['Min'] <= customer_val <= row['Max']:
                matched_segment = row['Tên Phân Khúc']
                assigned_combine_model = row['Combine Model']
                break
                
        if not matched_segment:
            st.error(f"❌ Khách hàng nằm ngoài vùng phủ! (Giá trị {customer_val} của biến {segment_var} không khớp Bin nào).")
            st.stop()
            
        if assigned_combine_model not in all_combines_config:
            st.error(f"❌ Combine model '{assigned_combine_model}' đã chọn cho phân khúc này không tồn tại!")
            st.stop()

        st.success(f"Khách hàng rơi vào phân khúc: **{matched_segment}** ➔ Hệ thống tự động kích hoạt mô hình: **{assigned_combine_model}**")

        # BƯỚC 2: HÀM TÍNH ĐIỂM LÕI
        def calc_score_with_breakdown(longlist, config_vars, intercept):
            breakdown = {"Hệ số chặn (Intercept)": intercept}
            total_f = intercept
            for var, cfg in config_vars.items():
                val = longlist[var][0]
                coef = cfg['coef']
                bins = cfg['bins']
                woe = 0.0
                for _, r in bins.iterrows():
                    if pd.isna(r['Min']) or pd.isna(r['Max']) or pd.isna(r['WOE']): 
                        continue
                    if r['Min'] <= val <= r['Max']:
                        woe = float(r['WOE'])
                        break
                var_f = woe * coef
                breakdown[var] = var_f
                total_f += var_f
            return total_f, breakdown

        # BƯỚC 3: TÍNH ĐIỂM CHỈ DUY NHẤT CHO COMBINE MODEL ĐƯỢC CHỈ ĐỊNH
        weights = all_combines_config[assigned_combine_model]
        if not weights:
            st.warning(f"Combine Model [{assigned_combine_model}] chưa được cấu hình trọng số Sub-model!")
            st.stop()
            
        f_total = 0
        sub_breakdowns = {}
        sub_scores = {}
        
        # Chỉ quét các sub-models trực thuộc Combine model này
        for m_name, w in weights.items():
            cfg = all_models_config[m_name]
            score_f, breakdown = calc_score_with_breakdown(cfg['data'], cfg['vars_config'], cfg['intercept'])
            sub_scores[m_name] = score_f
            sub_breakdowns[m_name] = breakdown
            f_total += score_f * w
            
        # BƯỚC 4: CHUYỂN ĐỔI PD VÀ MAP VÀO RATING
        pd_final = 1 / (1 + np.exp(-f_total))
        pd_percent = pd_final * 100
        
        final_rank = "D"
        for _, row in rating_editor.iterrows():
            if pd_percent <= row["PD Max (%)"]:
                final_rank = row["Hạng (Rank)"]
                break
                
        # BƯỚC 5: HIỂN THỊ KẾT QUẢ CUỐI CÙNG
        st.divider()
        st.markdown("### 🏆 KẾT QUẢ CHẤM ĐIỂM & XẾP HẠNG (FINAL RESULT)")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tổng Điểm (f_total)", round(f_total, 4))
        c2.metric("Xác suất vỡ nợ (PD)", f"{round(pd_percent, 4)}%")
        c3.metric("Xếp Hạng (Rank)", final_rank)
        
        if final_rank in ["AAA", "AA", "A", "BBB", "BB"]: 
            c4.success("✅ ĐỦ ĐIỀU KIỆN")
        else:
            c4.error("❌ RỦI RO CAO")
        
        with st.expander(f"🔍 Xem chi tiết cấu thành điểm của mô hình [{assigned_combine_model}]", expanded=False):
            st.markdown(f"**Công thức:** $f_{{total}} = " + " + ".join([f"{w} \\times f_{{{m}}}" for m, w in weights.items()]) + "$")
            for m_name, w in weights.items():
                st.write(f"▶ **Sub-model: {m_name}** (Trọng số: {w}) ➔ Đóng góp **f = {round(sub_scores[m_name], 4)}**")
                df_bd = pd.DataFrame(list(sub_breakdowns[m_name].items()), columns=['Thành phần (Biến)', 'Giá trị (f)'])
                st.dataframe(df_bd, hide_index=True, width='stretch')
