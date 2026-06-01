import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# ページの設定
st.set_page_config(page_title="PIDゲイン調整・解析ツール", layout="wide")

st.title("🤖 左右モーター PIDゲインアドバイザーツール")
st.caption("実機のCSVデータを解析し、PIDゲインの調整アドバイスを自動で提案します。")

# ----------------------------------------------------
# サイドバー：設定パラメータ
# ----------------------------------------------------
st.sidebar.header("⚙️ 現在の制御パラメータ")
target_val = st.sidebar.number_input("ターゲット値（目標スピード）", value=500.0, step=50.0)

st.sidebar.markdown("---")
st.sidebar.subheader("左モーター 現状ゲイン")
kp_l = st.sidebar.number_input("Kp (左)", value=1.00, step=0.1, format="%.2f")
ki_l = st.sidebar.number_input("Ki (左)", value=0.00, step=0.1, format="%.2f")
kd_l = st.sidebar.number_input("Kd (左)", value=0.00, step=0.1, format="%.2f")

st.sidebar.markdown("---")
st.sidebar.subheader("右モーター 現状ゲイン")
kp_r = st.sidebar.number_input("Kp (右)", value=1.00, step=0.1, format="%.2f")
ki_r = st.sidebar.number_input("Ki (右)", value=0.00, step=0.1, format="%.2f")
kd_r = st.sidebar.number_input("Kd (右)", value=0.00, step=0.1, format="%.2f")

# ----------------------------------------------------
# 関数：波形解析とゲイン提案ロジック
# ----------------------------------------------------
def analyze_wave(time, speed, power, target):
    """
    実測スピードの波形を解析し、状況に応じたアドバイスを返す
    """
    if len(speed) < 10:
        return "データが少なすぎます。", "normal"
        
    # 後半（定常状態と思われる区間、全体の最後の30%）のデータを抽出
    stable_start_idx = int(len(speed) * 0.7)
    stable_speed = speed[stable_start_idx:]
    stable_power = power[stable_start_idx:]
    
    # 1. 最高速度とオーバーシュートの計算
    max_speed = np.max(speed)
    overshoot_ratio = (max_speed - target) / target if max_speed > target else 0.0
    
    # 2. 定常偏差（目標値との平均的なズレ）の計算
    avg_stable_speed = np.mean(stable_speed)
    steady_state_error = target - avg_stable_speed
    
    # 3. 立ち上がり速度（前半で目標の80%に達するまでのデータ点数）
    reached_80 = np.where(speed >= target * 0.8)[0]
    rise_time_idx = reached_80[0] if len(reached_80) > 0 else len(speed)
    
    # 4. 振動（ハンチング）の検知：定常状態での速度の標準偏差（ばらつき）
    stable_std = np.std(stable_speed)
    
    # --- 判定と提案の生成 ---
    advice = []
    status_type = "success"
    
    # A. そもそも立ち上がっていない（目標値に全然届いていない）
    if max_speed < target * 0.7:
        advice.append("⚠️ **立ち上がりが非常に遅い、またはパワー不足です**")
        advice.append("- モーター出力（Power）が100に張り付いている場合は、ハードウェアの限界（電圧不足やギヤ比の問題）です。")
        advice.append("- 出力に余裕がある場合は、**比例ゲイン（Kp）を大きく**して応答性を上げてください。")
        status_type = "error"
        return "\n".join(advice), status_type

    # B. ハンチング（激しい振動）の検知
    if stable_std > target * 0.05:  # 目標値の5%以上の変動がある場合
        advice.append("🚨 **定常状態で速度が激しく振動（ハンチング）しています**")
        advice.append("- 制御が過敏すぎます。**比例ゲイン（Kp）または積分ゲイン（Ki）を小さく**してください。")
        advice.append("- 振動を抑えるために、**微分ゲイン（Kd）を少しずつ足してみる**のも効果的です。")
        status_type = "warning"
        return "\n".join(advice), status_type

    # C. オーバーシュートの判定
    if overshoot_ratio > 0.10:  # 10%以上の行き過ぎ
        advice.append("⚠️ **立ち上がり時に目標値を大きく行き過ぎています（オーバーシュート大）**")
        advice.append("- 行き過ぎを抑えるために、**微分ゲイン（Kd）を大きく**するか、**Kpを少し小さく**してください。")
        advice.append("- 積分ゲイン（Ki）が大きすぎてもオーバーシュートの原因になります。")
        status_type = "warning"
        
    # D. 定常偏差（ズレ）の判定
    if abs(steady_state_error) > target * 0.03:  # 3%以上のズレが残る
        if steady_state_error > 0:
            advice.append("📉 **目標値に一歩届かない状態で安定しています（定常偏差あり）**")
            advice.append("- 残ったズレを相殺するために、**積分ゲイン（Ki）を少しずつ（0.05〜0.1など）足して**ください。")
        else:
            advice.append("📈 **目標値を少し超えた位置で安定してしまっています**")
            advice.append("- **積分ゲイン（Ki）を調整**するか、摩擦や負荷の変動を確認してください。")
        if status_type != "warning": status_type = "info"

    # E. 問題なし
    if not advice:
        advice.append("✨ **非常に綺麗な追従波形です！**")
        advice.append("- 現在のゲインバランスは良好です。実機の挙動（急な負荷変化への強さなど）を見ながら微調整してください。")
        status_type = "success"
        
    return "\n".join(advice), status_type

# ----------------------------------------------------
# メイン画面：CSVファイルのアップロード
# ----------------------------------------------------
st.header("📂 実機データの読み込み")
uploaded_file = st.file_uploader("左右モーターの周期データ（CSV）を選択してください。", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.success("データの読み込みに成功しました！")
    
    required_cols = ['time', 'leftSpeed', 'rightSpeed', 'leftPower', 'rightPower']
    if all(col in df.columns for col in required_cols):
        
        # ----------------------------------------------------
        # 🔥 ゲイン提案（アドバイザー機能）の表示
        # ----------------------------------------------------
        st.header("🧠 PIDゲイン調整のアドバイス（自動解析結果）")
        
        adv_col1, adv_col2 = st.columns(2)
        
        with adv_col1:
            st.subheader("⬅️ 左モーターへの提案")
            advice_l, type_l = analyze_wave(df['time'].values, df['leftSpeed'].values, df['leftPower'].values, target_val)
            if type_l == "success": st.success(advice_l)
            elif type_l == "info": st.info(advice_l)
            elif type_l == "warning": st.warning(advice_l)
            else: st.error(advice_l)
            
        with adv_col2:
            st.subheader("➡️ 右モーターへの提案")
            advice_r, type_r = analyze_wave(df['time'].values, df['rightSpeed'].values, df['rightPower'].values, target_val)
            if type_r == "success": st.success(advice_r)
            elif type_r == "info": st.info(advice_r)
            elif type_r == "warning": st.warning(advice_r)
            else: st.error(advice_r)
            
        # ----------------------------------------------------
        # グラフの表示
        # ----------------------------------------------------
        st.header("📈 モーター速度 & 出力波形確認")
        col1, col2 = st.columns(2)
        
        with col1:
            fig_l = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=("Speed", "Power"))
            fig_l.add_trace(go.Scatter(x=df['time'], y=[target_val]*len(df), name='Target', line=dict(color='red', dash='dash')), row=1, col=1)
            fig_l.add_trace(go.Scatter(x=df['time'], y=df['leftSpeed'], name='Actual', line=dict(color='blue')), row=1, col=1)
            fig_l.add_trace(go.Scatter(x=df['time'], y=df['leftPower'], name='Power', line=dict(color='purple')), row=2, col=1)
            fig_l.update_layout(height=450, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_l, use_container_width=True)

        with col2:
            fig_r = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=("Speed", "Power"))
            fig_r.add_trace(go.Scatter(x=df['time'], y=[target_val]*len(df), name='Target', line=dict(color='red', dash='dash')), row=1, col=1)
            fig_r.add_trace(go.Scatter(x=df['time'], y=df['rightSpeed'], name='Actual', line=dict(color='green')), row=1, col=1)
            fig_r.add_trace(go.Scatter(x=df['time'], y=df['rightPower'], name='Power', line=dict(color='orange')), row=2, col=1)
            fig_r.update_layout(height=450, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_r, use_container_width=True)
            
    else:
        st.error(f"CSVファイルの列名を確認してください。必要な列名: {required_cols}")
else:
    st.info("👆 実機から出力したCSVファイルをアップロードすると、ここに自動解析アドバイスとグラフが表示されます。")