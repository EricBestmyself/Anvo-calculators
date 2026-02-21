# DC-DC 反馈电阻智能计算器

基于 Streamlit 的 DC-DC 反馈分压电阻计算工具：根据目标输出电压与芯片 Vfb 计算 R1/R2，匹配 E24/E96 标准阻值，并生成 Yageo 0402 MPN 与国内商城（贸泽/得捷）直达搜索链接。

## 功能

- **公式**：\( V_{out} = V_{fb} \times (1 + R_1/R_2) \)，支持「固定 R2 算 R1」或「固定 R1 算 R2」
- **标准阻值**：内置 E24/E96 系列，输出误差最小的前 5 组组合及实际 Vout、误差%
- **Yageo 0402**：自动输出 R1/R2 的 MPN（如 `RC0402FR-0710KL`）
- **采购链接**：推荐组合（误差 &lt; ±1%）下展示贸泽电子 (Mouser 中国)、得捷电子 (Digi-Key 中国) 直达搜索链接
- **MPN 表格**：按 MPN 列出 Digi-Key / Mouser 链接及库存、单价占位（可后续接 API）

## 运行

```bash
pip install -r requirements.txt
streamlit run dc_dc_feedback_calculator.py
```

浏览器访问 `http://localhost:8501`。

## 技术栈

- Python 3
- Streamlit（界面）
- Pandas（表格与格式化）

## 许可

MIT 或按需自定。
