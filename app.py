import streamlit as st
import akshare as ak
import time
import pandas as pd

st.title("A股实时监控")

# 用户输入股票代码
stock_symbols = st.text_input("请输入A股代码（多个代码用逗号分隔，如：000001,600000）:", "000001,600000")
symbols = [symbol.strip() for symbol in stock_symbols.split(',')]

# 缓存股票数据以提高性能
@st.cache_data(ttl=60)  # 缓存60秒
def fetch_stock_data(symbol):
    try:
        # 获取股票基本信息
        try:
            # 尝试获取股票名称 - 使用更可靠的API
            stock_info_df = ak.stock_individual_info_em(symbol=symbol)
            stock_name = stock_info_df[stock_info_df['item'] == '股票简称']['value'].values[0]
        except:
            stock_name = "未知"
        
        # 获取历史行情数据
        try:
            stock_hist = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")  # 使用前复权数据
            if not stock_hist.empty:
                latest_data = stock_hist.iloc[-1]
                price = float(latest_data['收盘'])
                open_price = float(latest_data['开盘'])
                change = ((price - open_price) / open_price * 100)
                volume = int(latest_data['成交量'])
                # 计算加权后的历史最低价格
                historical_low = float(stock_hist['最低'].min())
                # 计算当前价格是历史最低价格的倍数
                price_to_low_ratio = price / historical_low if historical_low > 0 else 0
            else:
                return {
                    "代码": symbol, 
                    "名称": stock_name,
                    "最新价": "无数据", 
                    "涨跌幅": "无数据", 
                    "成交量": "无数据",
                    "历史最低": "无数据",
                    "相对历史低位": "无数据"
                }
        except Exception as e:
            return {
                "代码": symbol, 
                "名称": stock_name,
                "最新价": f"行情错误:{str(e)}", 
                "涨跌幅": "行情错误", 
                "成交量": "行情错误",
                "历史最低": "行情错误",
                "相对历史低位": "行情错误"
            }
        
            
        return {
            "代码": symbol, 
            "名称": stock_name,
            "最新价": f"{price:.2f}", 
            "涨跌幅": f"{change:.2f}%", 
            "成交量": f"{volume:,}",
            "历史最低": f"{historical_low:.2f}",
            "相对历史低位": f"{price_to_low_ratio:.2f}倍"
        }
    except Exception as e:
        return {
            "代码": symbol, 
            "名称": f"基础信息错误:{str(e)}",
            "最新价": "Error", 
            "涨跌幅": "Error", 
            "成交量": "Error",
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
        progress_bar.progress((i + 1) / total)  # 更新进度条
    progress_bar.empty()  # 清除进度条
    return pd.DataFrame(data)

# 主逻辑
if st.button("刷新数据"):
    st.session_state.stock_data = get_stock_data_with_progress(symbols)
    st.dataframe(st.session_state.stock_data)
else:
    if 'stock_data' not in st.session_state or st.session_state.stock_data.empty:
        st.session_state.stock_data = get_stock_data_with_progress(symbols)
    st.dataframe(st.session_state.stock_data)