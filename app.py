import streamlit as st
import akshare as ak
import time
import pandas as pd
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from functools import lru_cache

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# Remove Redis cache setup
# cache = redis.Redis(host='localhost', port=6379, db=0)

# API endpoint for stock data
STOCK_API_URL = "https://api.example.com/stock/"

@lru_cache(maxsize=128)
def fetch_stock_data_cached(symbol):
    """Fetch stock data with built-in caching"""
    try:
        response = requests.get(f"{STOCK_API_URL}{symbol}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Fetched data for {symbol}")
            return symbol, data
        else:
            logger.error(f"Failed to fetch data for {symbol}: HTTP {response.status_code}")
            return symbol, None
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return symbol, None

def fetch_stock_data_sync(symbol):
    """Fetch stock data synchronously with caching"""
    return fetch_stock_data_cached(symbol)




STOCK_FILE = "stock_data.json"

st.title("A股实时监控")

# Function to save stock symbols to file
def save_stock_symbols(symbols):
    with open(STOCK_FILE, 'w') as f:
        json.dump(symbols, f)

# Function to load stock symbols from file
def load_stock_symbols():
    if os.path.exists(STOCK_FILE):
        with open(STOCK_FILE, 'r') as f:
            return json.load(f)
    return ["000001", "600000"]  # Default symbols

# Initialize session state for stock symbols if not exists
if 'stock_symbols' not in st.session_state:
    st.session_state.stock_symbols = load_stock_symbols()

# Function to add new stock symbols
def add_stock():
    new_symbols = st.session_state.new_stock_input.strip().split()
    for symbol in new_symbols:
        if symbol and symbol not in st.session_state.stock_symbols:
            st.session_state.stock_symbols.append(symbol)
    st.session_state.new_stock_input = ""  # Clear input after adding
    save_stock_symbols(st.session_state.stock_symbols)  # Save to file

# Function to remove selected stock symbols
def remove_selected_stocks():
    selected_stocks = [symbol for symbol, selected in st.session_state.selections.items() if selected]
    for symbol in selected_stocks:
        if symbol in st.session_state.stock_symbols:
            st.session_state.stock_symbols.remove(symbol)
    # Reset selections
    st.session_state.selections = {symbol: False for symbol in st.session_state.stock_symbols}
    # Clear stock data if all stocks are removed
    if not st.session_state.stock_symbols:
        st.session_state.stock_data = pd.DataFrame()
    save_stock_symbols(st.session_state.stock_symbols)  # Save to file

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

# 获取所有股票数据并显示进度条 - 改进版本
def get_stock_data_with_progress(symbols):
    data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(symbols)
    
    # Use ThreadPoolExecutor for concurrent data fetching
    with ThreadPoolExecutor(max_workers=min(len(symbols), 10)) as executor:
        # Submit all tasks
        future_to_symbol = {executor.submit(fetch_stock_data, symbol): symbol 
                          for symbol in symbols}
        
        # Process completed tasks as they finish
        completed = 0
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                result = future.result(timeout=30)  # 30 second timeout per task
                data.append(result)
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                # Add error entry
                data.append({
                    "代码": symbol,
                    "名称": "处理错误",
                    "最新价": "Error",
                    "历史最低": "Error", 
                    "相对历史低位": "Error"
                })
            
            completed += 1
            progress_bar.progress(completed / total)
            status_text.text(f"已处理 {completed}/{total} 只股票")
    
    progress_bar.empty()
    status_text.empty()
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
            st.rerun()

# Main content area
st.header("当前监控的股票")

# Get and display stock data
if st.button("刷新数据") or 'stock_data' not in st.session_state:
    st.session_state.stock_data = get_stock_data_with_progress(st.session_state.stock_symbols)

# Display the dataframe with only required columns
if 'stock_data' in st.session_state and not st.session_state.stock_data.empty:
    display_columns = ["代码", "名称", "最新价", "历史最低", "相对历史低位"]
    st.dataframe(st.session_state.stock_data[display_columns])
else:
    st.write("暂无股票数据，请添加股票代码。")
