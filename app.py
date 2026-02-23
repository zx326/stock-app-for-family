import streamlit as st
import akshare as ak
import time
import pandas as pd
import json
import os
import requests
import logging
from functools import wraps
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Remove environment check function since STOCK_API_URL is not used

# Call the check at the beginning

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

# 添加重试装饰器
def retry_on_failure(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (2 ** attempt) + random.uniform(0, 1))  # 指数退避
            logger.error(f"All {max_retries} attempts failed for {func.__name__}")
            raise last_exception
        return wrapper
    return decorator

@retry_on_failure(max_retries=3, delay=2)
def fetch_stock_data(symbol):
    try:
        # 获取股票基本信息 - 移除headers参数
        try:
            stock_info_df = ak.stock_individual_info_em(symbol=symbol)
            stock_name = stock_info_df[stock_info_df['item'] == '股票简称']['value'].values[0]
        except Exception as e:
            logger.warning(f"Failed to get stock info for {symbol}: {e}")
            stock_name = f"{symbol}(未知)"
        
        # 获取历史行情数据
        try:
            # 添加超时设置和更详细的错误处理
            stock_hist = ak.stock_zh_a_hist(
                symbol=symbol, 
                period="daily", 
                adjust="qfq",
                timeout=15  # 增加到15秒超时
            )
            if not stock_hist.empty:
                latest_data = stock_hist.iloc[-1]
                price = float(latest_data['收盘'])
                # 计算历史最低价格
                historical_low = float(stock_hist['最低'].min())
                # 计算当前价格是历史最低价格的倍数
                price_to_low_ratio = price / historical_low if historical_low > 0 else 0
            else:
                logger.warning(f"No historical data for {symbol}")
                return {
                    "代码": symbol, 
                    "名称": stock_name,
                    "最新价": "无数据",
                    "历史最低": "无数据",
                    "相对历史低位": "无数据"
                }
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            error_msg = str(e)
            # 根据不同错误类型提供更具体的错误信息
            if "timeout" in error_msg.lower() or "time out" in error_msg.lower():
                error_detail = "网络超时"
            elif "not found" in error_msg.lower() or "不存在" in error_msg:
                error_detail = "股票代码不存在"
            else:
                error_detail = "网络连接异常"
                
            return {
                "代码": symbol, 
                "名称": stock_name,
                "最新价": f"行情错误:{error_detail}", 
                "历史最低": f"行情错误:{error_detail}",
                "相对历史低位": f"行情错误:{error_detail}"
            }
        
        return {
            "代码": symbol, 
            "名称": stock_name,
            "最新价": f"{price:.2f}", 
            "历史最低": f"{historical_low:.2f}",
            "相对历史低位": f"{price_to_low_ratio:.2f}倍"
        }
    except Exception as e:
        logger.error(f"Unexpected error for {symbol}: {e}")
        return {
            "代码": symbol, 
            "名称": f"{symbol}(处理错误)",
            "最新价": "Error", 
            "历史最低": "Error",
            "相对历史低位": "Error"
        }

# Simplified data fetching with threading for better performance
def get_stock_data_with_progress(symbols):
    data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(symbols)
    
    # Use ThreadPoolExecutor for concurrent processing
    with ThreadPoolExecutor(max_workers=min(10, len(symbols))) as executor:
        # Submit all tasks
        future_to_symbol = {executor.submit(fetch_stock_data, symbol): symbol for symbol in symbols}
        
        # Process completed tasks as they finish
        completed = 0
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                result = future.result(timeout=30)  # 30 second timeout per stock
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
            
            # Update progress
            completed += 1
            progress = completed / total
            progress_bar.progress(progress)
            status_text.text(f"已处理 {completed}/{total} 只股票")
    
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(data)

# Initialize selection state
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
    with st.spinner("正在获取股票数据..."):
        try:
            st.session_state.stock_data = get_stock_data_with_progress(st.session_state.stock_symbols)
            st.success("数据刷新成功！")
        except Exception as e:
            logger.exception("Failed to refresh stock data")
            st.error(f"数据刷新失败: {str(e)}")
            # 显示缓存数据如果有的话
            if 'stock_data' in st.session_state:
                st.info("显示上次获取的数据")

# Display the dataframe with only required columns
if 'stock_data' in st.session_state and not st.session_state.stock_data.empty:
    display_columns = ["代码", "名称", "最新价", "历史最低", "相对历史低位"]
    st.dataframe(st.session_state.stock_data[display_columns])
    
    # 添加数据更新时间
    st.caption(f"最后更新时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
else:
    st.write("暂无股票数据，请添加股票代码。")
    # 提供故障排除建议
    st.info("""
    **故障排除建议:**
    1. 检查网络连接是否正常
    2. 确认股票代码格式正确（如：000001）
    3. 尝试刷新页面后重新获取数据
    4. 如果问题持续，请联系管理员
    """)

# Add error boundary
try:
    # Main app logic here
    pass  # 占位符，表示不做任何操作
except Exception as e:
    logger.exception("An unexpected error occurred")
    st.error(f"应用遇到错误: {str(e)}")
    st.stop()