import math
from typing import List, Literal, Tuple
from urllib.parse import quote

import pandas as pd
import streamlit as st


def resistance_search_keyword(r_k: float) -> str:
    """将阻值（kΩ）转为经销商搜索关键词，如 10.5 -> 10.5k，0.82 -> 820。"""
    if r_k >= 1000:
        s = f"{r_k / 1000:.1f}M"
        return s.replace(".0M", "M")
    if r_k >= 1:
        if abs(r_k - round(r_k)) < 0.001:
            return f"{int(round(r_k))}k"
        return f"{r_k:.2f}k".rstrip("0").rstrip(".")
    return str(int(round(r_k * 1000)))


def resistor_purchase_urls(r_k: float) -> dict:
    """返回某阻值（kΩ）在 Digi-Key、Mouser、立创商城的电阻搜索页 URL。"""
    q = resistance_search_keyword(r_k)
    # 立创与 Mouser 常用 k/Ω 搜索；Digi-Key 用 keywords
    return {
        "digikey": f"https://www.digikey.com/en/products/filter/resistors/52?keywords={quote(q + ' ohm')}",
        "mouser": f"https://www.mouser.com/c/passive-components/resistors/?q={quote(q)}",
        "lcsc": f"https://www.lcsc.com/products/Resistors_52.html?q={quote(q)}",
    }


def yageo_0402_value_code(r_k: float) -> str:
    """
    将阻值（kΩ）转为 Yageo 规格书中的阻值编码（R/K/M 表示小数点）。
    例：0.82 -> 820R，10 -> 10K，10.5 -> 10K5，2.7 -> 2K7，100 -> 100K，1.0 -> 1M。
    """
    r_ohm = r_k * 1000.0
    if r_ohm >= 1e6:
        m_val = r_ohm / 1e6
        if abs(m_val - round(m_val)) < 0.01:
            return f"{int(round(m_val))}M"
        return f"{int(m_val)}M{int(round((m_val % 1) * 10))}"
    if r_ohm >= 1e3:
        k_val = r_ohm / 1e3
        s = f"{k_val:.2f}"
        a, b = s.split(".")
        if int(b) == 0:
            return f"{int(a)}K"
        b_trim = b.rstrip("0")
        return f"{int(a)}K{b_trim}"
    if abs(r_ohm - round(r_ohm)) < 0.01:
        return f"{int(round(r_ohm))}R"
    return f"{int(r_ohm)}R{int(round((r_ohm % 1) * 10))}"


def yageo_0402_mpn(r_k: float) -> str:
    """返回 Yageo 0402、1% 精度、7 寸盘装的料号（RC0402FR-07 + 阻值码 + L）。"""
    code = yageo_0402_value_code(r_k)
    return f"RC0402FR-07{code}L"


def resistor_purchase_urls_by_mpn(mpn: str) -> dict:
    """
    按 MPN 返回各商城搜索/产品页 URL（国际站 + 国内站）。
    - 国际：Digi-Key、Mouser、立创商城。
    - 国内：贸泽电子 (Mouser 中国)、得捷电子 (Digi-Key 中国)，使用 f-string 拼接 MPN 生成直达搜索链接。
    """
    q = quote(mpn)
    return {
        "digikey": f"https://www.digikey.com/en/products/result?keywords={q}",
        "mouser": f"https://www.mouser.com/ProductDetail/YAGEO/{quote(mpn, safe='')}",
        "lcsc": f"https://www.szlcsc.com/so/s?q={q}",
        "mouser_cn": f"https://www.mouser.cn/c/?q={q}",
        "digikey_cn": f"https://www.digikey.cn/zh/products/result?keywords={q}",
    }


def generate_e_series_values(series: Literal["E24", "E96"], min_k: float = 0.1, max_k: float = 1_000.0) -> List[float]:
    """
    生成近似的 E 系列标准阻值（单位：kΩ）。

    为避免在代码中硬编码大表，这里按 IEC 逻辑在对数量表上等分后做四舍五入，
    得到与标准 E24 / E96 非常接近的一组值，足以用于工程设计与对比。
    """
    if series == "E24":
        steps = 24
        scale = 10.0
        divisor = 10.0
    elif series == "E96":
        steps = 96
        scale = 100.0
        divisor = 100.0
    else:
        raise ValueError("Unsupported series")

    base_values = []
    for n in range(steps):
        raw = 10 ** (n / steps) * scale
        rounded = round(raw)
        value = rounded / divisor
        base_values.append(value)

    # 去重并排序
    base_values = sorted(set(base_values))

    values_k = []
    decade = 0.1
    while decade <= max_k * 1.01:
        for v in base_values:
            candidate = v * decade
            if min_k <= candidate <= max_k:
                values_k.append(candidate)
        decade *= 10

    # 再次去重排序（避免边界重叠）
    return sorted(set(round(v, 4) for v in values_k))


@st.cache_data
def get_standard_resistors_k() -> List[float]:
    """返回合并后的 E24 + E96 标准阻值列表（单位：kΩ）。"""
    e24 = generate_e_series_values("E24")
    e96 = generate_e_series_values("E96")
    return sorted(set(e24 + e96))


def calculate_theoretical_resistor(
    mode: Literal["固定 R2 算 R1", "固定 R1 算 R2"],
    v_out: float,
    v_fb: float,
    fixed_r_k: float,
) -> Tuple[float, Literal["R1", "R2"]]:
    """
    根据模式与目标电压，计算理论精确电阻值（单位：kΩ）。

    公式：Vout = Vfb * (1 + R1/R2)
    """
    if v_fb <= 0:
        raise ValueError("Vfb 必须大于 0。")
    if v_out <= v_fb:
        raise ValueError("Vout 必须大于 Vfb，否则反馈电阻比将为负或无意义。")
    if fixed_r_k <= 0:
        raise ValueError("固定电阻值必须大于 0。")

    ratio = v_out / v_fb

    if mode == "固定 R2 算 R1":
        r2_k = fixed_r_k
        r1_k = r2_k * (ratio - 1.0)
        if r1_k <= 0:
            raise ValueError("计算得到的 R1 为非正值，请检查输入。")
        return r1_k, "R1"
    else:  # 固定 R1 算 R2
        r1_k = fixed_r_k
        denom = ratio - 1.0
        if denom <= 0:
            raise ValueError("计算得到的 R2 分母为非正值，请检查输入。")
        r2_k = r1_k / denom
        if r2_k <= 0:
            raise ValueError("计算得到的 R2 为非正值，请检查输入。")
        return r2_k, "R2"


def find_best_standard_values(
    mode: Literal["固定 R2 算 R1", "固定 R1 算 R2"],
    v_out_target: float,
    v_fb: float,
    fixed_r_k: float,
    theoretical_k: float,
    candidates_k: List[float],
    top_n: int = 5,
):
    """
    针对理论精确值，在标准阻值库中寻找误差最小的前 top_n 个组合。
    返回一个列表，每个元素为 dict，包含 R1, R2, 实际 Vout, 误差百分比。
    """
    results = []

    for cand in candidates_k:
        # 理论值附近的候选可以适当优先，但这里直接全遍历并按误差排序
        if mode == "固定 R2 算 R1":
            r1_k = cand
            r2_k = fixed_r_k
        else:  # 固定 R1 算 R2
            r1_k = fixed_r_k
            r2_k = cand

        actual_v_out = v_fb * (1.0 + r1_k / r2_k)
        error_pct = (actual_v_out - v_out_target) / v_out_target * 100.0

        results.append(
            {
                "R1 (kΩ)": r1_k,
                "R2 (kΩ)": r2_k,
                "R1 MPN (Yageo 0402)": yageo_0402_mpn(r1_k),
                "R2 MPN (Yageo 0402)": yageo_0402_mpn(r2_k),
                "实际 Vout (V)": actual_v_out,
                "误差 (%)": error_pct,
            }
        )

    # 以绝对误差排序，取前 top_n
    results_sorted = sorted(results, key=lambda x: abs(x["误差 (%)"]))
    return results_sorted[:top_n]


def main():
    st.set_page_config(
        page_title="DC-DC 反馈电阻智能计算器",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 极客风样式：主区 + 侧边栏高对比度、科技感配色
    st.markdown(
        """
        <style>
        body {
            background-color: #0b1020;
        }
        .main {
            background-color: #0b1020;
            color: #e0e6ff;
        }
        /* 侧边栏：深色底 + 左侧高亮条，整体提高文字对比度 */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0a0e1a 0%, #060a12 100%);
            border-left: 3px solid #00d4ff;
            box-shadow: inset 0 0 40px rgba(0, 212, 255, 0.06);
        }
        section[data-testid="stSidebar"] > div {
            color: #e8f4fc;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            color: #00d4ff !important;
            font-weight: 600;
            letter-spacing: 0.02em;
        }
        section[data-testid="stSidebar"] label {
            color: #c8e4ff !important;
            font-weight: 500;
        }
        section[data-testid="stSidebar"] p {
            color: #c8e4ff !important;
        }
        section[data-testid="stSidebar"] .stRadio label {
            color: #c8e4ff !important;
        }
        section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
            color: #c8e4ff !important;
        }
        section[data-testid="stSidebar"] span {
            color: #c8e4ff !important;
        }
        h1, h2, h3 {
            color: #8be9fd;
        }
        .theoretical-box {
            padding: 1rem 1.5rem;
            border-radius: 0.5rem;
            border: 1px solid #50fa7b33;
            background: radial-gradient(circle at top left, #13203a, #050814);
            color: #f8f8f2;
            font-family: "JetBrains Mono", "Fira Code", monospace;
        }
        .theoretical-label {
            font-size: 0.9rem;
            color: #bd93f9;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        .theoretical-value {
            font-size: 1.6rem;
            font-weight: 600;
            color: #50fa7b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("DC-DC 反馈电阻智能计算器")

    # 侧边栏输入区域
    with st.sidebar:
        st.header("参数配置")
        v_out = st.number_input("目标输出电压 Vout (V)", min_value=0.0, value=5.0, step=0.1, format="%.3f")
        v_fb = st.number_input("芯片参考电压 Vfb (V)", min_value=0.0, value=0.8, step=0.01, format="%.3f")

        mode = st.radio(
            "计算模式",
            options=["固定 R2 算 R1", "固定 R1 算 R2"],
            index=0,
        )

        if mode == "固定 R2 算 R1":
            fixed_r_k = st.number_input(
                "下臂电阻 R2 (kΩ)",
                min_value=0.0,
                value=10.0,
                step=0.1,
                format="%.3f",
            )
        else:
            fixed_r_k = st.number_input(
                "上臂电阻 R1 (kΩ)",
                min_value=0.0,
                value=100.0,
                step=0.1,
                format="%.3f",
            )

    # 主区域：公式展示
    st.subheader("反馈公式")
    st.latex(r"V_{out} = V_{fb} \times \left(1 + \frac{R_1}{R_2}\right)")

    if v_out == 0 or v_fb == 0 or fixed_r_k == 0:
        st.info("请在左侧完整输入 Vout、Vfb 以及固定电阻值（均需大于 0）。")
        return

    try:
        theoretical_k, which = calculate_theoretical_resistor(mode, v_out, v_fb, fixed_r_k)
    except ValueError as e:
        st.error(str(e))
        return

    # 理论电阻高亮显示
    which_label = "R1" if which == "R1" else "R2"
    col_theo, col_spacer = st.columns([2, 3])
    with col_theo:
        st.markdown(
            f"""
            <div class="theoretical-box">
                <div class="theoretical-label">理论精确电阻值 ({which_label})</div>
                <div class="theoretical-value">{theoretical_k:.3f} kΩ</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 查找最佳标准阻值组合
    standard_values_k = get_standard_resistors_k()
    best_results = find_best_standard_values(
        mode=mode,
        v_out_target=v_out,
        v_fb=v_fb,
        fixed_r_k=fixed_r_k,
        theoretical_k=theoretical_k,
        candidates_k=standard_values_k,
        top_n=5,
    )

    if not best_results:
        st.warning("在当前标准阻值范围内未找到合适的组合，请调整参数或扩展阻值范围。")
        return

    df = pd.DataFrame(best_results)
    col_order = ["R1 (kΩ)", "R2 (kΩ)", "R1 MPN (Yageo 0402)", "R2 MPN (Yageo 0402)", "实际 Vout (V)", "误差 (%)"]
    df = df[col_order]

    # 设置格式与颜色（误差 < 1% 绿色）
    def highlight_error(val):
        try:
            if abs(val) < 1.0:
                return "color: #50fa7b; font-weight: 600;"
            else:
                return "color: #ff5555;"
        except Exception:
            return ""

    styler = (
        df.style.format(
            {
                "R1 (kΩ)": "{:.3f}",
                "R2 (kΩ)": "{:.3f}",
                "实际 Vout (V)": "{:.4f}",
                "误差 (%)": "{:+.3f}",
            }
        )
        .applymap(highlight_error, subset=["误差 (%)"])
    )

    st.subheader("前 5 个最佳标准阻值组合")
    st.dataframe(styler, use_container_width=True)

    # 仅对误差 < ±1% 的组合展示 R1、R2 的 Yageo 0402 MPN、采购链接及 MPN 表格（链接/库存/单价）
    within_1pct = [r for r in best_results if abs(r["误差 (%)"]) < 1.0]
    if within_1pct:
        st.subheader("推荐采购（误差 < ±1%）— Yageo 0402")
        # 基于 MPN 生成表格：第一列 MPN，第二列 Digi-Key 或 Mouser 链接（直接显示网址），第三列 库存，第四列 单价
        table_rows = []
        seen_mpns = set()
        placeholder = "需在官网查看"
        for r in within_1pct:
            mpn1 = yageo_0402_mpn(r["R1 (kΩ)"])
            mpn2 = yageo_0402_mpn(r["R2 (kΩ)"])
            for mpn in (mpn1, mpn2):
                if mpn in seen_mpns:
                    continue
                seen_mpns.add(mpn)
                urls = resistor_purchase_urls_by_mpn(mpn)
                table_rows.append({"MPN": mpn, "链接": urls["digikey"], "库存": placeholder, "单价": placeholder})
                table_rows.append({"MPN": mpn, "链接": urls["mouser_cn"], "库存": placeholder, "单价": placeholder})
        if table_rows:
            st.markdown("**基于 MPN 的表格（链接 / 库存 / 单价）**")
            df_mpn = pd.DataFrame(table_rows)
            st.dataframe(
                df_mpn,
                use_container_width=True,
                column_config={
                    "MPN": st.column_config.TextColumn("MPN", width="medium"),
                    "链接": st.column_config.LinkColumn("链接"),
                    "库存": st.column_config.TextColumn("库存", width="small"),
                    "单价": st.column_config.TextColumn("单价", width="small"),
                },
                hide_index=True,
            )
            st.caption("库存与单价未接入 Digi-Key/Mouser API，当前显示「需在官网查看」；点击链接打开对应商城页面可查看实时库存与单价。")
        for i, row in enumerate(within_1pct, 1):
            r1_k, r2_k = row["R1 (kΩ)"], row["R2 (kΩ)"]
            v_act, err = row["实际 Vout (V)"], row["误差 (%)"]
            mpn1 = yageo_0402_mpn(r1_k)
            mpn2 = yageo_0402_mpn(r2_k)
            u1 = resistor_purchase_urls_by_mpn(mpn1)
            u2 = resistor_purchase_urls_by_mpn(mpn2)
            with st.expander(f"组合 {i}：R1 = {r1_k:.3f} kΩ，R2 = {r2_k:.3f} kΩ，实际 Vout = {v_act:.4f} V，误差 = {err:+.3f}%"):
                st.markdown("**R1（上臂）**")
                st.code(mpn1, language=None)
                st.markdown("**国内元器件商城直达搜索（R1）**")
                st.markdown(f"[贸泽电子 (Mouser 中国)]({u1['mouser_cn']}) · [得捷电子 (Digi-Key 中国)]({u1['digikey_cn']})")
                st.markdown("**R2（下臂）**")
                st.code(mpn2, language=None)
                st.markdown("**国内元器件商城直达搜索（R2）**")
                st.markdown(f"[贸泽电子 (Mouser 中国)]({u2['mouser_cn']}) · [得捷电子 (Digi-Key 中国)]({u2['digikey_cn']})")
    else:
        st.caption("当前前 5 个组合误差均 ≥ ±1%，暂无推荐采购链接；可调整 Vout / Vfb / 固定电阻以获取更优组合。")


if __name__ == "__main__":
    main()

