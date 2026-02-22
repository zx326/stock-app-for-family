import streamlit as st
import akshare as ak
import time
import pandas as pd

st.title("A股实时监控")

# 用户输入股票代码
stock_symbols = st.text_input("请输入A股代码（多个代码用逗号分隔，如：000001,600000）:", "000001,600000")

# 将输入的股票代码转换为列表
symbols = [symbol.strip() for symbol in stock_symbols.split(',')]

# 创建一个空的DataFrame来存储股票数据
if 'stock_data' not in st.session_state:
    st.session_state.stock_data = pd.DataFrame()

# 定义获取股票数据的函数
def get_stock_data(symbols):
    data = []
    for symbol in symbols:
        try:
            # 获取A股实时数据
            stock_data = ak.stock_zh_a_spot_em()
            stock_info = stock_data[stock_data['代码'] == symbol]
            
            if not stock_info.empty:
                price = stock_info['最新价'].iloc[0]
                change = stock_info['涨跌幅'].iloc[0]
                volume = stock_info['成交量'].iloc[0]
                data.append({"代码": symbol, "最新价": price, "涨跌幅": f"{change}%", "成交量": volume})
            else:
                data.append({"代码": symbol, "最新价": "N/A", "涨跌幅": "N/A", "成交量": "N/A"})
        except Exception as e:
            data.append({"代码": symbol, "最新价": "Error", "涨跌幅": "Error", "成交量": "Error"})
    
    return pd.DataFrame(data)

# 主循环
while True:
    # 获取最新的股票数据
    st.session_state.stock_data = get_stock_data(symbols)
    
    # 显示数据
    st.dataframe(st.session_state.stock_data)
    
    # 等待5秒后重新获取数据
    time.sleep(5)
    
    # 重新运行脚本以更新数据
    st.rerun()  # 修改：使用 st.rerun() 替代 st.experimental_rerun()