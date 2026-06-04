import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
from datetime import datetime
from scipy.signal import find_peaks

def detect_hunting(speed, target):
    speed = np.array(speed)
    # 入力を中心化して上下振動成分を抽出しやすくする
    centered = speed - np.mean(speed)

    # 正方向のピーク（速度上昇時の山）を検出
    peaks, _ = find_peaks(
        centered,
        prominence=target * 0.01
    )

    # 負方向のピーク（速度下降時の谷）を検出
    valleys, _ = find_peaks(
        -centered,
        prominence=target * 0.01
    )

    cycle_count = min(len(peaks), len(valleys))

    return {
        "peaks": len(peaks),
        "valleys": len(valleys),
        "cycles": cycle_count
    }

st.set_page_config(page_title="PIDゲイン調整・解析ツール", layout="wide")

HISTORY_FILE = "history.csv"

st.title("左右モーター PIDゲインアドバイザーツール")
st.caption("CSV解析・左右差分析・ゲイン提案・評価スコア・履歴管理")

st.sidebar.header("現在の制御パラメータ")

target_val = st.sidebar.number_input(
    "ターゲット値（目標スピード）",
    value=500.0,
    step=50.0
)

st.sidebar.markdown("---")

st.sidebar.subheader("左モーター")
kp_l = st.sidebar.number_input("Kp (左)", value=1.00, step=0.1, format="%.2f")
ki_l = st.sidebar.number_input("Ki (左)", value=0.00, step=0.05, format="%.2f")
kd_l = st.sidebar.number_input("Kd (左)", value=0.00, step=0.05, format="%.2f")

st.sidebar.markdown("---")

st.sidebar.subheader("右モーター")
kp_r = st.sidebar.number_input("Kp (右)", value=1.00, step=0.1, format="%.2f")
ki_r = st.sidebar.number_input("Ki (右)", value=0.00, step=0.05, format="%.2f")
kd_r = st.sidebar.number_input("Kd (右)", value=0.00, step=0.05, format="%.2f")

def analyze_wave(time, speed, power, target):
    # 入力が十分でない場合は解析しない
    if len(speed) < 10:
        return None

    # 末尾70%を安定領域とみなして解析する
    stable_start = int(len(speed) * 0.7)
    stable_speed = speed[stable_start:]

    # 安定領域のハンチング（周期的な上下振動）を検出
    hunting = detect_hunting(stable_speed, target)
    stable_power = power[stable_start:]

    # 解析対象全体の最大値
    max_speed = np.max(speed)

    # 99パーセンタイルを使って極端なピーク影響を抑えたオーバーシュート評価
    overshoot = max(
        0,
        (np.percentile(speed, 99) - target) / target * 100
    )

    # 安定領域の平均値との差分で定常偏差を算出
    steady_error = target - np.mean(stable_speed)

    # 安定領域の揺らぎ量を標準偏差で評価
    stable_std = np.std(stable_speed)

    reached = np.where(speed >= target * 0.8)[0]

    rise_time = (
        float(time[reached[0]])
        if len(reached) > 0
        else None
    )

    saturation_ratio = np.mean(np.abs(power) >= 95) * 100

    return {
        "max_speed": max_speed,
        "overshoot": overshoot,
        "steady_error": steady_error,
        "stable_std": stable_std,
        "rise_time": rise_time,
        "saturation_ratio": saturation_ratio,
        "stable_power": np.mean(stable_power),
        "hunting_cycles": hunting["cycles"]
    }

def calculate_score(result, target):
    score = 100.0

    # オーバーシュートが大きいほど減点
    score -= result["overshoot"] * 1.5

    # 定常偏差、揺らぎ、飽和の影響を正規化して減点
    score -= abs(result["steady_error"]) / target * 100
    score -= result["stable_std"] / target * 100
    score -= result["saturation_ratio"] * 0.1

    # ハンチングサイクルが多い場合は追従性が悪いとみなして減点
    if result["hunting_cycles"] >= 5:
        score -= 5

    # スコアを0〜100にクランプ
    return max(0, min(100, score))

def suggest_gain(result, kp, ki, kd, target):
    # 今のゲインを元に提案値を計算
    new_kp = kp
    new_ki = ki
    new_kd = kd

    # 定常偏差が大きければ積分ゲインを追加
    if abs(result["steady_error"]) > target * 0.03:
        new_ki += 0.05

    # オーバーシュートが大きい場合は微分を強め、比例を抑える
    if result["overshoot"] > 10:
        new_kd += 0.05
        new_kp *= 0.95

    # 変動が大きい場合も微分強化と比例抑制
    if result["stable_std"] > target * 0.05:
        new_kd += 0.05
        new_kp *= 0.95

    # ハンチング周期が多い場合は追従性改善のため微分を強化
    if result["hunting_cycles"] >= 5:
        new_kd += 0.05
        new_kp *= 0.95

    # 立ち上がりが遅いなら比例ゲインを増加
    if result["rise_time"] is not None and result["rise_time"] > 0.4:
        new_kp *= 1.10

    return (
        round(new_kp, 2),
        round(new_ki, 2),
        round(new_kd, 2)
    )

def create_advice(result, target):
    advice = []

    if result["saturation_ratio"] > 80:
        advice.append("Powerが飽和しています。ハードウェア限界の可能性があります。")

    if result["overshoot"] > 10:
        advice.append("オーバーシュート大 → Kd増加またはKp減少を推奨")

    if abs(result["steady_error"]) > target * 0.03:
        advice.append("定常偏差あり → Ki増加を推奨")

    if result["stable_std"] > target * 0.05:
        advice.append("ハンチング傾向 → Kd増加またはKp低減を推奨")

    if result["hunting_cycles"] >= 5:
        advice.append("ハンチング周期が多い → Kd増加またはKp減少を検討してください")

    # どの指標にも該当しない場合は良好判定を出力
    if not advice:
        advice.append("追従性は良好です")

    return advice

st.header("実機データの読み込み")

# CSVファイルをユーザに選択してもらい、データを読み込む
uploaded_file = st.file_uploader(
    "CSVファイルを選択してください",
    type=["csv"]
)

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    required_cols = [
        "time",
        "leftSpeed",
        "rightSpeed",
        "leftPower",
        "rightPower"
    ]

    if not all(c in df.columns for c in required_cols):
        st.error(f"必要列: {required_cols}")
        st.stop()

    left_result = analyze_wave(
        df["time"].values,
        df["leftSpeed"].values,
        df["leftPower"].values,
        target_val
    )

    right_result = analyze_wave(
        df["time"].values,
        df["rightSpeed"].values,
        df["rightPower"].values,
        target_val
    )

    left_score = calculate_score(left_result, target_val)
    right_score = calculate_score(right_result, target_val)

    st.header("評価スコア")

    c1, c2 = st.columns(2)

    c1.metric("左スコア", f"{left_score:.1f}")
    c2.metric("右スコア", f"{right_score:.1f}")

    st.header("解析結果")

    metrics = pd.DataFrame({
        "項目": [
            "最大速度",
            "オーバーシュート[%]",
            "定常偏差",
            "立上り時間",
            "標準偏差",
            "ハンチング周期",
            "Power飽和率[%]"
        ],
        "左": [
            left_result["max_speed"],
            left_result["overshoot"],
            left_result["steady_error"],
            left_result["rise_time"],
            left_result["stable_std"],
            left_result["hunting_cycles"],
            left_result["saturation_ratio"]
        ],
        "右": [
            right_result["max_speed"],
            right_result["overshoot"],
            right_result["steady_error"],
            right_result["rise_time"],
            right_result["stable_std"],
            right_result["hunting_cycles"],
            right_result["saturation_ratio"]
        ]
    })

    st.dataframe(metrics, use_container_width=True)

    st.header("左右差分析")

    left_avg = df["leftSpeed"].mean()
    right_avg = df["rightSpeed"].mean()

    diff_ratio = abs(left_avg - right_avg) / target_val * 100

    if diff_ratio > 5:
        if left_avg < right_avg:
            st.warning(f"左モーターが {diff_ratio:.1f}% 遅いです")
        else:
            st.warning(f"右モーターが {diff_ratio:.1f}% 遅いです")
    else:
        st.success("左右差は小さいです")

    # 回帰直線の計算
    diff = (df["leftSpeed"] - df["rightSpeed"]).values
    time = df["time"].values
    
    regression_y_ave = diff.mean()
    regression_x_ave = time.mean()

    ar_Num = ((time - regression_x_ave) * (diff - regression_y_ave)).sum()
    ar_Den = ((time - regression_x_ave) ** 2).sum()

    regression_a = ar_Num / ar_Den if ar_Den != 0 else 0
    regression_b = regression_y_ave - regression_a * regression_x_ave
    
    # 回帰直線を計算
    regression_line = regression_a * time + regression_b
    
    # グラフに回帰直線を追加
    fig_diff = go.Figure()
    
    fig_diff.add_trace(
        go.Scatter(x=time, y=diff, name="実測値", mode="lines")
    )
    
    fig_diff.add_trace(
        go.Scatter(x=time, y=regression_line, name="回帰直線", mode="lines",
                   line=dict(dash="dash", color="red"))
    )
    
    fig_diff.update_layout(
        title="左右速度差の推移",
        xaxis_title="時間",
        yaxis_title="速度差",
        hovermode="x unified"
    )
    
    st.plotly_chart(fig_diff, use_container_width=True)


    st.header("ゲイン提案")

    lkp, lki, lkd = suggest_gain(
        left_result,
        kp_l,
        ki_l,
        kd_l,
        target_val
    )

    rkp, rki, rkd = suggest_gain(
        right_result,
        kp_r,
        ki_r,
        kd_r,
        target_val
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("左モーター")
        st.write(f"Kp: {lkp}")
        st.write(f"Ki: {lki}")
        st.write(f"Kd: {lkd}")
        for a in create_advice(left_result, target_val):
            st.write("- " + a)

    with col2:
        st.subheader("右モーター")
        st.write(f"Kp: {rkp}")
        st.write(f"Ki: {rki}")
        st.write(f"Kd: {rkd}")
        for a in create_advice(right_result, target_val):
            st.write("- " + a)

    st.header("波形表示")

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Left Speed",
            "Right Speed",
            "Left Power",
            "Right Power"
        )
    )

    fig.add_trace(
        go.Scatter(x=df["time"], y=df["leftSpeed"]),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(x=df["time"], y=df["rightSpeed"]),
        row=1, col=2
    )

    fig.add_trace(
        go.Scatter(x=df["time"], y=df["leftPower"]),
        row=2, col=1
    )

    fig.add_trace(
        go.Scatter(x=df["time"], y=df["rightPower"]),
        row=2, col=2
    )

    # ターゲット値の横線を追加
    fig.add_hline(y=target_val, line_dash="dash", line_color="red",
                  row=1, col=1, annotation_text="Target", annotation_position="right")
    
    fig.add_hline(y=target_val, line_dash="dash", line_color="red",
                  row=1, col=2, annotation_text="Target", annotation_position="right")

    st.plotly_chart(fig, use_container_width=True)

    if st.button("調整履歴を保存"):
        row = pd.DataFrame([{
            "datetime": datetime.now(),
            "kp_l": kp_l,
            "ki_l": ki_l,
            "kd_l": kd_l,
            "kp_r": kp_r,
            "ki_r": ki_r,
            "kd_r": kd_r,
            "score_l": left_score,
            "score_r": right_score
        }])

        if os.path.exists(HISTORY_FILE):
            history = pd.read_csv(HISTORY_FILE)
            history = pd.concat([history, row])
        else:
            history = row

        history.to_csv(HISTORY_FILE, index=False)
        st.success("履歴保存完了")

    if os.path.exists(HISTORY_FILE):
        st.header("調整履歴")
        history = pd.read_csv(HISTORY_FILE)
        st.dataframe(history, use_container_width=True)

        fig_history = go.Figure()

        fig_history.add_trace(
            go.Scatter(
                y=history["score_l"],
                name="Left Score"
            )
        )

        fig_history.add_trace(
            go.Scatter(
                y=history["score_r"],
                name="Right Score"
            )
        )

        st.plotly_chart(
            fig_history,
            use_container_width=True
        )