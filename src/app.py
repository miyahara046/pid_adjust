import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
import zipfile
import shutil
from datetime import datetime
from scipy.signal import find_peaks
import requests
import io
from analyzer import images_to_video, create_mock_runs

# モックデータの初期化（ローカルモード用）
try:
    create_mock_runs()
except Exception as e:
    pass


def fetch_results(api_url):
    try:
        response = requests.get(f"{api_url}/results", timeout=3.0)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

def fetch_result_csv(api_url, timestamp_key):
    try:
        response = requests.get(f"{api_url}/results/{timestamp_key}/csv", timeout=5.0)
        if response.status_code == 200:
            return io.BytesIO(response.content)
    except Exception:
        pass
    return None

def fetch_video_runs(api_url):
    try:
        response = requests.get(f"{api_url}/video/runs", timeout=3.0)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []

def generate_video_on_server(api_url, run_name, fps):
    try:
        response = requests.post(
            f"{api_url}/video/runs/{run_name}/generate",
            data={"fps": fps},
            timeout=30.0
        )
        if response.status_code == 200:
            return response.json()
        else:
            try:
                err_detail = response.json().get("detail", "不明なエラー")
            except:
                err_detail = response.text
            st.error(f"動画生成失敗: {err_detail}")
    except Exception as e:
        st.error(f"サーバー動画生成エラー: {e}")
    return None

def upload_zip_to_server(api_url, zip_file_bytes, run_name):
    try:
        files = {"file": ("images.zip", zip_file_bytes, "application/zip")}
        data = {"run_name": run_name} if run_name else {}
        response = requests.post(f"{api_url}/video/upload", files=files, data=data, timeout=30.0)
        if response.status_code == 200:
            return response.json()
        else:
            try:
                err_detail = response.json().get("detail", "不明なエラー")
            except:
                err_detail = response.text
            st.error(f"アップロード失敗: {err_detail}")
    except Exception as e:
        st.error(f"サーバーアップロードエラー: {e}")
    return None

def delete_run_on_server(api_url, run_name):
    try:
        response = requests.delete(f"{api_url}/video/runs/{run_name}", timeout=5.0)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"サーバー削除エラー: {e}")
    return None


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

st.set_page_config(page_title="総合調整補助ツール", layout="wide")

HISTORY_FILE = "history.csv"

st.title("総合調整補助ツール")
st.caption("PIDゲイン調整・速度応答解析・パワー解析・左右バランス調整・動画解析")

# session_state の初期化
if "target_val" not in st.session_state:
    st.session_state["target_val"] = 500.0
if "kp_l" not in st.session_state:
    st.session_state["kp_l"] = 1.00
if "ki_l" not in st.session_state:
    st.session_state["ki_l"] = 0.00
if "kd_l" not in st.session_state:
    st.session_state["kd_l"] = 0.00
if "kp_r" not in st.session_state:
    st.session_state["kp_r"] = 1.00
if "ki_r" not in st.session_state:
    st.session_state["ki_r"] = 0.00
if "kd_r" not in st.session_state:
    st.session_state["kd_r"] = 0.00
if "loaded_run_key" not in st.session_state:
    st.session_state["loaded_run_key"] = None

st.sidebar.header("データソース設定")
data_source = st.sidebar.radio(
    "データ入力モード",
    ["ローカルCSVファイルをアップロード", "サーバーと同期（最新データ）"]
)

api_url = "http://localhost:8000"
results = None
run_options = {}

if data_source == "サーバーと同期（最新データ）":
    api_url = st.sidebar.text_input("APIサーバーURL", value=api_url)
    if st.sidebar.button("🔄 サーバーからデータを再読込"):
        st.rerun()

    results = fetch_results(api_url)
    if results:
        for r in results:
            try:
                dt = datetime.fromisoformat(r["timestamp"])
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                formatted_time = r["timestamp"]
            display_str = f"🕒 {formatted_time} (左スコア: {r['left_score']:.1f}, 右スコア: {r['right_score']:.1f})"
            run_options[display_str] = r

        if "selected_run_display" in st.session_state and st.session_state["selected_run_display"] in run_options:
            selected_display = st.session_state["selected_run_display"]
        else:
            selected_display = list(run_options.keys())[0] if run_options else None
            if selected_display:
                st.session_state["selected_run_display"] = selected_display

        if selected_display:
            selected_run = run_options[selected_display]
            selected_key = selected_run["timestamp_key"]

            if st.session_state["loaded_run_key"] != selected_key:
                st.session_state["loaded_run_key"] = selected_key
                st.session_state["target_val"] = float(selected_run["target_val"])
                st.session_state["kp_l"] = float(selected_run["kp_l"])
                st.session_state["ki_l"] = float(selected_run["ki_l"])
                st.session_state["kd_l"] = float(selected_run["kd_l"])
                st.session_state["kp_r"] = float(selected_run["kp_r"])
                st.session_state["ki_r"] = float(selected_run["ki_r"])
                st.session_state["kd_r"] = float(selected_run["kd_r"])

st.sidebar.markdown("---")
st.sidebar.header("現在の制御パラメータ")

target_val = st.sidebar.number_input(
    "ターゲット値（目標スピード）",
    key="target_val",
    step=50.0
)

st.sidebar.markdown("---")

st.sidebar.subheader("左モーター")
kp_l = st.sidebar.number_input("Kp (左)", key="kp_l", step=0.1, format="%.2f")
ki_l = st.sidebar.number_input("Ki (左)", key="ki_l", step=0.05, format="%.2f")
kd_l = st.sidebar.number_input("Kd (左)", key="kd_l", step=0.05, format="%.2f")

st.sidebar.markdown("---")

st.sidebar.subheader("右モーター")
kp_r = st.sidebar.number_input("Kp (右)", key="kp_r", step=0.1, format="%.2f")
ki_r = st.sidebar.number_input("Ki (右)", key="ki_r", step=0.05, format="%.2f")
kd_r = st.sidebar.number_input("Kd (右)", key="kd_r", step=0.05, format="%.2f")

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

# タブを作成
tab_csv, tab_video = st.tabs(["CSV解析", "動画解析"])

# ========== タブ1: CSV解析 ==========
with tab_csv:
    df = None
    
    if data_source == "ローカルCSVファイルをアップロード":
        st.header("実機データの読み込み")
        # CSVファイルをユーザに選択してもらい、データを読み込む
        uploaded_file = st.file_uploader(
            "CSVファイルを選択してください",
            type=["csv"]
        )
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            
    else:  # "サーバーと同期（最新データ）"
        st.header("サーバーから測定結果を同期中")
        if results is None:
            st.error(f"APIサーバー ({api_url}) に接続できませんでした。サーバーが起動しているか確認してください。")
            st.info("※ ローカル環境での起動手順：\n`python api.py` を実行してAPIサーバーを起動してください。")
        elif len(results) == 0:
            st.warning("APIサーバーにはまだ解析データがアップロードされていません。")
            st.info("PowerShellスクリプトやcurl等でデータを送信すると、ここに自動同期されます。")
        else:
            selected_display = st.selectbox(
                "同期されたデータ履歴を選択してください",
                options=list(run_options.keys()),
                key="selected_run_display"
            )
            
            if selected_display:
                selected_run = run_options[selected_display]
                selected_key = selected_run["timestamp_key"]
                
                # CSVデータをロード
                csv_bytes = fetch_result_csv(api_url, selected_key)
                if csv_bytes is not None:
                    df = pd.read_csv(csv_bytes)
                else:
                    st.error("サーバーからのCSVデータの取得に失敗しました。")

    if df is not None:
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

with tab_video:
    st.header("🎥 動画解析 (画像から動画の生成・再生・ダウンロード)")
    st.caption("走行画像シーケンス（PNG/JPG）を結合して動画（MP4）を作成します。再生およびダウンロードが可能です。")

    if data_source == "ローカルCSVファイルをアップロード":
        st.subheader("📁 ローカルモード")
        
        # 1. 走行ディレクトリの選択
        local_runs_dir = "image_runs"
        available_local_runs = []
        if os.path.exists(local_runs_dir):
            available_local_runs = [d for d in os.listdir(local_runs_dir) if os.path.isdir(os.path.join(local_runs_dir, d))]
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.write("### 走行フォルダの指定")
            selected_local_run = st.selectbox(
                "利用可能なローカル画像ディレクトリ",
                options=available_local_runs,
                help="image_runs ディレクトリ内のフォルダです。"
            )
            
            # 手動パス指定も許可する
            default_path = ""
            if selected_local_run:
                default_path = os.path.abspath(os.path.join(local_runs_dir, selected_local_run))
            
            custom_path = st.text_input(
                "または、画像フォルダの絶対パスを入力してください",
                value=default_path,
                help="画像（PNG/JPG/JPEG）が保存されているフォルダを指定してください。"
            )
            
            # 画像ZIPアップロード機能（ローカル展開用）
            st.markdown("---")
            st.write("### 走行画像を新規追加 (ZIP)")
            uploaded_zip = st.file_uploader(
                "画像を含むZIPファイルをアップロードして展開",
                type=["zip"],
                key="local_zip_uploader"
            )
            new_run_name = st.text_input("新しい走行名 (アルファベット・数字)", placeholder="run_new_experiment", key="local_run_name")
            
            if st.button("ZIPファイルをローカルに展開", use_container_width=True):
                if uploaded_zip and new_run_name:
                    target_dir = os.path.join(local_runs_dir, new_run_name)
                    if os.path.exists(target_dir):
                        shutil.rmtree(target_dir)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    try:
                        with zipfile.ZipFile(uploaded_zip) as zip_ref:
                            # 画像のみを展開
                            extracted_count = 0
                            for zip_info in zip_ref.infolist():
                                if zip_info.is_dir():
                                    continue
                                filename = os.path.basename(zip_info.filename)
                                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                                    with zip_ref.open(zip_info) as source, open(os.path.join(target_dir, filename), "wb") as target:
                                        shutil.copyfileobj(source, target)
                                        extracted_count += 1
                                        
                        if extracted_count > 0:
                            st.success(f"ZIPファイルを展開しました。{extracted_count}枚の画像を {target_dir} に保存しました。")
                            st.rerun()
                        else:
                            shutil.rmtree(target_dir)
                            st.error("ZIPファイル内に画像ファイル (.png, .jpg, .jpeg) が見つかりませんでした。")
                    except Exception as e:
                        if os.path.exists(target_dir):
                            shutil.rmtree(target_dir)
                        st.error(f"ZIPファイルの処理エラー: {e}")
                else:
                    st.warning("ZIPファイルと新しい走行名を入力してください。")
            
        with col2:
            st.write("### 動画生成と再生")
            if custom_path and os.path.exists(custom_path) and os.path.isdir(custom_path):
                img_exts = ('.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG')
                images = [f for f in os.listdir(custom_path) if f.lower().endswith(img_exts)]
                st.info(f"📁 選択パス: `{custom_path}`\n\n📷 検出画像数: **{len(images)}** 枚")
                
                fps = st.slider("フレームレート (FPS)", min_value=1, max_value=60, value=10, step=1, key="local_fps")
                video_path = os.path.join(custom_path, "video.mp4")
                has_video = os.path.exists(video_path)
                
                generate_btn = st.button("🎬 動画を生成する", type="primary", use_container_width=True)
                
                if generate_btn:
                    with st.spinner("動画を生成中..."):
                        try:
                            images_to_video(custom_path, video_path, fps=fps)
                            st.success("動画の生成が完了しました！")
                            has_video = True
                        except Exception as e:
                            st.error(f"動画の生成に失敗しました: {e}")
                
                if has_video:
                    st.write("#### 🎥 生成された動画の再生")
                    try:
                        with open(video_path, "rb") as vf:
                            video_bytes = vf.read()
                        st.video(video_bytes)
                        st.download_button(
                            label="📥 動画をダウンロード",
                            data=video_bytes,
                            file_name="run_video.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"動画ファイルの読み込みエラー: {e}")
            else:
                st.warning("正しいディレクトリパスを指定してください。")
                
    else:  # "サーバーと同期（最新データ）"
        st.subheader("🌐 サーバー同期モード")
        
        # 1. サーバーの走行ディレクトリ一覧を取得
        server_runs = fetch_video_runs(api_url)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.write("### サーバー上の走行データ選択")
            if not server_runs:
                st.warning("サーバー上に画像データがありません。")
            else:
                run_names = [r["run_name"] for r in server_runs]
                selected_run_name = st.selectbox(
                    "走行データを選択してください",
                    options=run_names,
                    key="server_run_selectbox"
                )
                
                # 選択された走行データの詳細
                selected_run_info = next((r for r in server_runs if r["run_name"] == selected_run_name), None)
                if selected_run_info:
                    st.info(
                        f"📁 フォルダ名: `{selected_run_info['run_name']}`\n\n"
                        f"📷 画像数: **{selected_run_info['image_count']}** 枚\n\n"
                        f"🎬 動画ステータス: {'生成済み' if selected_run_info['has_video'] else '未生成'}"
                    )
                    
                    # 削除ボタン
                    if st.button("🗑️ この走行データをサーバーから削除", use_container_width=True):
                        res = delete_run_on_server(api_url, selected_run_name)
                        if res:
                            st.success(f"{selected_run_name} を削除しました。")
                            st.rerun()
            
            st.markdown("---")
            st.write("### 新しい走行データをサーバーにアップロード")
            uploaded_server_zip = st.file_uploader(
                "走行画像のZIPファイルをアップロード",
                type=["zip"],
                key="server_zip_uploader"
            )
            server_run_name = st.text_input("走行名 (省略時は自動生成)", placeholder="run_experiment_1", key="server_run_name")
            
            if st.button("🚀 サーバーにアップロードして展開", use_container_width=True):
                if uploaded_server_zip:
                    with st.spinner("サーバーに送信中..."):
                        zip_bytes = uploaded_server_zip.read()
                        res = upload_zip_to_server(api_url, zip_bytes, server_run_name)
                        if res:
                            st.success(f"アップロード成功！ 走行名: {res['run_name']} (画像数: {res['image_count']}枚)")
                            st.rerun()
                else:
                    st.warning("ZIPファイルを選択してください。")
                    
        with col2:
            st.write("### 動画生成と再生")
            if server_runs and 'selected_run_info' in locals() and selected_run_info:
                fps = st.slider("フレームレート (FPS)", min_value=1, max_value=60, value=10, step=1, key="server_fps")
                
                generate_btn = st.button("🎬 動画を生成する", type="primary", use_container_width=True, key="server_generate_btn")
                
                if generate_btn:
                    with st.spinner("サーバーで動画を生成中..."):
                        res = generate_video_on_server(api_url, selected_run_info["run_name"], fps)
                        if res:
                            st.success("動画の生成が完了しました！")
                            # 状態を更新するために再読み込み
                            st.rerun()
                
                if selected_run_info["has_video"]:
                    st.write("#### 🎥 生成された動画の再生")
                    video_url = f"{api_url}/video/runs/{selected_run_info['run_name']}/video"
                    st.video(video_url)
                    
                    # ダウンロードボタン用にファイルをダウンロード
                    try:
                        with st.spinner("ダウンロード用データを準備中..."):
                            video_resp = requests.get(video_url, timeout=10.0)
                            if video_resp.status_code == 200:
                                st.download_button(
                                    label="📥 動画をダウンロード",
                                    data=video_resp.content,
                                    file_name=f"{selected_run_info['run_name']}_video.mp4",
                                    mime="video/mp4",
                                    use_container_width=True
                                )
                            else:
                                st.error("動画データの取得に失敗しました。")
                    except Exception as e:
                        st.error(f"ダウンロード準備エラー: {e}")
            else:
                st.info("走行データを選択すると、動画の生成・再生が行えます。")