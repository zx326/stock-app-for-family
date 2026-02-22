import streamlit as st
import akshare as ak
import time
import pandas as pd

st.title("A股实时监控")

# Initialize session state for stock symbols if not exists
if 'stock_symbols' not in st.session_state:
    st.session_state.stock_symbols = ["000001", "600000"]

# Function to add new stock symbols
def add_stock():
    new_symbols = st.session_state.new_stock_input.strip().split()
    for symbol in new_symbols:
        if symbol and symbol not in st.session_state.stock_symbols:
            st.session_state.stock_symbols.append(symbol)
    st.session_state.new_stock_input = ""  # Clear input after adding

# Function to remove selected stock symbols
def remove_selected_stocks():
    selected_stocks = [symbol for symbol, selected in st.session_state.selections.items() if selected]
    for symbol in selected_stocks:
        if symbol in st.session_state.stock_symbols:
            st.session_state.stock_symbols.remove(symbol)
    # Reset selections
    st.session_state.selections = {symbol: False for symbol in st.session_state.stock_symbols}

# 缓存股票数据以提高性能
@st.cache_data(ttl=60)  # 缓存60秒
def fetch_stock_data(symbol):
    try:
        # 获取股票基本信息
        try:
            stock_info_df = ak.stock_individual_info_em(symbol=symbol)
            stock_name = stock_info_df[stock_info_df['item'] == '股票简称']['value'].values[0]
        except:
            stock_name = "未知"
        
        # 获取历史行情数据
        try:
            stock_hist = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
            if not stock_hist.empty:
                latest_data = stock_hist.iloc[-1]
                price = float(latest_data['收盘'])
                # 计算历史最低价格
                historical_low = float(stock_hist['最低'].min())
                # 计算当前价格是历史最低价格的倍数
                price_to_low_ratio = price / historical_low if historical_low > 0 else 0
            else:
                return {
                    "代码": symbol, 
                    "名称": stock_name,
                    "最新价": "无数据",
                    "历史最低": "无数据",
                    "相对历史低位": "无数据"
                }
        except Exception as e:
            return {
                "代码": symbol, 
                "名称": stock_name,
                "最新价": f"行情错误:{str(e)}", 
                "历史最低": "行情错误",
                "相对历史低位": "行情错误"
            }
        
        return {
            "代码": symbol, 
            "名称": stock_name,
            "最新价": f"{price:.2f}", 
            "历史最低": f"{historical_low:.2f}",
            "相对历史低位": f"{price_to_low_ratio:.2f}倍"
        }
    except Exception as e:
        return {
            "代码": symbol, 
            "名称": f"基础信息错误:{str(e)}",
            "最新价": "Error", 
            "历史最低": "Error",
            "相对历史低位": "Error"
        }

# 获取所有股票数据并显示进度条
def get_stock_data_with_progress(symbols):
    data = []
    progress_bar = st.progress(0)
    total = len(symbols)
    for i, symbol in enumerate(symbols):
        data.append(fetch_stock_data(symbol))
        progress_bar.progress((i + 1) / total)
    progress_bar.empty()
    return pd.DataFrame(data)

# 初始化选择状态
if 'selections' not in st.session_state:
    st.session_state.selections = {symbol: False for symbol in st.session_state.stock_symbols}

# Sidebar for stock management
with st.sidebar:
    st.header("股票管理")
    
    # Add stocks
    st.text_input("添加股票代码(多个代码用空格分隔):", key="new_stock_input")
    st.button("增加股票", on_click=add_stock)
    
    # Delete stocks
    st.subheader("删除股票")
    # Update selections based on current stock list
    st.session_state.selections = {symbol: st.session_state.selections.get(symbol, False) 
                                   for symbol in st.session_state.stock_symbols}
    
    # Display checkboxes for each stock
    for symbol in st.session_state.stock_symbols:
        st.session_state.selections[symbol] = st.checkbox(
            f"{symbol}", 
            value=st.session_state.selections[symbol],
            key=f"select_{symbol}"
        )
    
    # Delete selected stocks
    if any(st.session_state.selections.values()):
        selected_count = sum(st.session_state.selections.values())
        if st.button(f"删除选中的 {selected_count} 只股票"):
            remove_selected_stocks()
            st.experimental_rerun()

# Main content area
st.header("当前监控的股票")

# Get and display stock data
if st.button("刷新数据") or 'stock_data' not in st.session_state:
    st.session_state.stock_data = get_stock_data_with_progress(st.session_state.stock_symbols)

# Display the dataframe with only required columns
if 'stock_data' in st.session_state:
    display_columns = ["代码", "名称", "最新价", "历史最低", "相对历史低位"]
    st.dataframe(st.session_state.stock_data[display_columns])