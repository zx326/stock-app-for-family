import streamlit as st
import akshare as ak
import pandas as pd

# 设置页面标题
st.set_page_config(page_title="A股实时行情", layout="wide")
st.title("📈 A股实时行情查询")

# 创建一个按钮
if st.button("🔄 点击获取最新数据"):
    # 显示加载提示
    with st.spinner("正在获取数据，请稍候..."):
        try:
            # 调用 akshare 获取 A 股实时行情
            df = ak.stock_zh_a_spot_em()
            # 显示数据表格
            st.success(f"获取成功！共 {len(df)} 只股票")
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"获取数据失败：{e}")
else:
    st.info("👆 点击上方按钮获取实时行情")