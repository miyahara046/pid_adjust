import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from datetime import datetime

def detect_hunting(speed, target):
    speed = np.array(speed)
    centered = speed - np.mean(speed)

    peaks, _ = find_peaks(
        centered,
        prominence=target * 0.01
    )

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

def analyze_wave(time, speed, power, target):
    if len(speed) < 10:
        return None

    stable_start = int(len(speed) * 0.7)
    stable_speed = speed[stable_start:]

    hunting = detect_hunting(stable_speed, target)
    stable_power = power[stable_start:]

    max_speed = np.max(speed)

    overshoot = max(
        0,
        (np.percentile(speed, 99) - target) / target * 100
    )

    steady_error = target - np.mean(stable_speed)
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

    score -= result["overshoot"] * 1.5
    score -= abs(result["steady_error"]) / target * 100
    score -= result["stable_std"] / target * 100
    score -= result["saturation_ratio"] * 0.1

    if result["hunting_cycles"] >= 5:
        score -= 5

    return max(0, min(100, score))

def suggest_gain(result, kp, ki, kd, target):
    new_kp = kp
    new_ki = ki
    new_kd = kd

    if abs(result["steady_error"]) > target * 0.03:
        new_ki += 0.05

    if result["overshoot"] > 10:
        new_kd += 0.05
        new_kp *= 0.95

    if result["stable_std"] > target * 0.05:
        new_kd += 0.05
        new_kp *= 0.95

    if result["hunting_cycles"] >= 5:
        new_kd += 0.05
        new_kp *= 0.95

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

    if not advice:
        advice.append("追従性は良好です")

    return advice

def analyze_csv(csv_data, target_val, kp_l, ki_l, kd_l, kp_r, ki_r, kd_r):
    """CSVデータを解析して結果を返す"""
    df = pd.read_csv(csv_data)
    
    required_cols = ["time", "leftSpeed", "rightSpeed", "leftPower", "rightPower"]
    if not all(c in df.columns for c in required_cols):
        raise ValueError(f"必要列: {required_cols}")
    
    # 左モーター解析
    left_result = analyze_wave(
        df["time"].values,
        df["leftSpeed"].values,
        df["leftPower"].values,
        target_val
    )
    
    # 右モーター解析
    right_result = analyze_wave(
        df["time"].values,
        df["rightSpeed"].values,
        df["rightPower"].values,
        target_val
    )
    
    left_score = calculate_score(left_result, target_val)
    right_score = calculate_score(right_result, target_val)
    
    # ゲイン提案
    lkp, lki, lkd = suggest_gain(left_result, kp_l, ki_l, kd_l, target_val)
    rkp, rki, rkd = suggest_gain(right_result, kp_r, ki_r, kd_r, target_val)
    
    # 左右差分析
    left_avg = df["leftSpeed"].mean()
    right_avg = df["rightSpeed"].mean()
    diff_ratio = abs(left_avg - right_avg) / target_val * 100
    
    # 回帰直線
    diff = (df["leftSpeed"] - df["rightSpeed"]).values
    time = df["time"].values
    regression_y_ave = diff.mean()
    regression_x_ave = time.mean()
    ar_Num = ((time - regression_x_ave) * (diff - regression_y_ave)).sum()
    ar_Den = ((time - regression_x_ave) ** 2).sum()
    regression_a = ar_Num / ar_Den if ar_Den != 0 else 0
    regression_b = regression_y_ave - regression_a * regression_x_ave
    
    return {
        "timestamp": datetime.now().isoformat(),
        "target_val": target_val,
        "kp_l": float(kp_l),
        "ki_l": float(ki_l),
        "kd_l": float(kd_l),
        "kp_r": float(kp_r),
        "ki_r": float(ki_r),
        "kd_r": float(kd_r),
        "left_motor": {
            "score": float(left_score),
            "max_speed": float(left_result["max_speed"]),
            "overshoot": float(left_result["overshoot"]),
            "steady_error": float(left_result["steady_error"]),
            "stable_std": float(left_result["stable_std"]),
            "rise_time": float(left_result["rise_time"]) if left_result["rise_time"] else None,
            "saturation_ratio": float(left_result["saturation_ratio"]),
            "hunting_cycles": int(left_result["hunting_cycles"]),
            "suggested_kp": float(lkp),
            "suggested_ki": float(lki),
            "suggested_kd": float(lkd),
            "advice": create_advice(left_result, target_val)
        },
        "right_motor": {
            "score": float(right_score),
            "max_speed": float(right_result["max_speed"]),
            "overshoot": float(right_result["overshoot"]),
            "steady_error": float(right_result["steady_error"]),
            "stable_std": float(right_result["stable_std"]),
            "rise_time": float(right_result["rise_time"]) if right_result["rise_time"] else None,
            "saturation_ratio": float(right_result["saturation_ratio"]),
            "hunting_cycles": int(right_result["hunting_cycles"]),
            "suggested_kp": float(rkp),
            "suggested_ki": float(rki),
            "suggested_kd": float(rkd),
            "advice": create_advice(right_result, target_val)
        },
        "balance": {
            "left_avg_speed": float(left_avg),
            "right_avg_speed": float(right_avg),
            "diff_ratio": float(diff_ratio),
            "regression_a": float(regression_a),
            "regression_b": float(regression_b)
        }
    }

def images_to_video(image_dir, output_path, fps=10):
    """
    指定されたディレクトリ内の画像をつなぎ合わせて動画（MP4）を作成します。
    """
    try:
        import cv2
    except ImportError:
        raise ImportError("opencv-python がインストールされていません。'pip install -r requirements.txt' を実行してインストールしてください。")
        
    import os
    import re
    import glob
    
    # 画像ファイルを探す
    extensions = ('*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG')
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(image_dir, ext)))
        
    if not image_files:
        raise ValueError("指定されたディレクトリに画像ファイルが見つかりません。")
        
    # 自然順（数値の順序）でソート
    def natural_sort_key(s):
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
        
    image_files.sort(key=natural_sort_key)
    
    # 最初の画像からサイズを取得
    first_image = cv2.imread(image_files[0])
    if first_image is None:
        raise ValueError(f"画像を読み込めませんでした: {image_files[0]}")
        
    height, width, layers = first_image.shape
    size = (width, height)
    
    # VideoWriterの初期化 (MP4V形式)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, size)
    
    try:
        for filename in image_files:
            img = cv2.imread(filename)
            if img is not None:
                # リサイズが必要な場合はサイズを合わせる
                if img.shape[1] != width or img.shape[0] != height:
                    img = cv2.resize(img, size)
                out.write(img)
    finally:
        out.release()
        
    return output_path

def create_mock_runs():
    """
    デモ用の画像ディレクトリを作成します（走行画像データのシミュレーション）。
    """
    import os
    import math
    from PIL import Image, ImageDraw, ImageFont

    RUNS_DIR = "image_runs"
    if os.path.exists(RUNS_DIR) and len(os.listdir(RUNS_DIR)) > 0:
        return

    os.makedirs(RUNS_DIR, exist_ok=True)
    
    # 共通フォントの取得
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        font_large = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()
        font_large = ImageFont.load_default()

    # ---- 1. 加速走行（正常・安定） ----
    run_1_dir = os.path.join(RUNS_DIR, "sample_run_1_acceleration")
    os.makedirs(run_1_dir, exist_ok=True)
    
    width, height = 640, 480
    frames = 40
    speeds_1 = []
    
    for i in range(frames):
        img = Image.new("RGB", (width, height), color=(18, 18, 24))
        draw = ImageDraw.Draw(img)
        
        # グリッド線
        for x in range(0, width, 40):
            draw.line([(x, 0), (x, height)], fill=(30, 30, 40), width=1)
        for y in range(0, height, 40):
            draw.line([(0, y), (width, y)], fill=(30, 30, 40), width=1)
            
        # テレメトリ枠
        draw.rectangle([(10, 10), (630, 70)], outline=(50, 50, 70), width=2, fill=(25, 25, 35))
        
        draw.text((25, 20), "TELEMETRY: RUN_1 (ACCELERATION)", fill=(102, 126, 234), font=font_large)
        draw.text((25, 45), f"Frame: {i:02d} / {frames-1}   |   Time: {i*0.1:.1f}s", fill=(150, 150, 150), font=font)
        
        progress = i / (frames - 1)
        # PID的な立ち上がり速度の計算 (target=500, Kpが効いてスムーズに収束)
        speed = 500.0 * (1.0 - math.exp(-i / 6.0))
        # わずかなノイズを追加
        speed += (i % 3 - 1) * 2.0
        speeds_1.append(speed)
        
        # 車輪の描画
        cx = 120 + int(400 * progress)
        cy = 200
        radius = 45
        # 外輪
        draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)], outline=(255, 255, 255), width=3)
        # スポーク
        angle = progress * 6.0 * math.pi # 3回転
        sx = cx + int(radius * math.cos(angle))
        sy = cy + int(radius * math.sin(angle))
        draw.line([(cx, cy), (sx, sy)], fill=(102, 126, 234), width=4)
        
        # 速度テキスト
        draw.text((cx - 45, cy + radius + 10), f"Speed: {speed:.1f}", fill=(245, 158, 11), font=font)
        
        # リアルタイムグラフの描画枠
        graph_left, graph_top = 50, 300
        graph_width, graph_height = 540, 120
        draw.rectangle([(graph_left, graph_top), (graph_left + graph_width, graph_top + graph_height)], outline=(60, 60, 80), width=1, fill=(20, 20, 28))
        draw.text((graph_left + 10, graph_top + 5), "Real-time Speed Plot (Target: 500)", fill=(100, 100, 120), font=font)
        
        # ターゲットライン
        target_y = graph_top + graph_height - int((500.0 / 600.0) * graph_height)
        draw.line([(graph_left, target_y), (graph_left + graph_width, target_y)], fill=(239, 68, 68), width=1)
        
        # グラフのプロット
        points = []
        for idx, s in enumerate(speeds_1):
            px = graph_left + int(idx * (graph_width / (frames - 1)))
            py = graph_top + graph_height - int((s / 600.0) * graph_height)
            points.append((px, py))
            
        if len(points) > 1:
            draw.line(points, fill=(16, 185, 129), width=3)
            
        img.save(os.path.join(run_1_dir, f"frame_{i:02d}.png"))

    # ---- 2. 不安定なハンチング走行 ----
    run_2_dir = os.path.join(RUNS_DIR, "sample_run_2_hunting")
    os.makedirs(run_2_dir, exist_ok=True)
    
    speeds_2 = []
    for i in range(frames):
        img = Image.new("RGB", (width, height), color=(18, 18, 24))
        draw = ImageDraw.Draw(img)
        
        # グリッド線
        for x in range(0, width, 40):
            draw.line([(x, 0), (x, height)], fill=(30, 30, 40), width=1)
        for y in range(0, height, 40):
            draw.line([(0, y), (width, y)], fill=(30, 30, 40), width=1)
            
        # テレメトリ枠
        draw.rectangle([(10, 10), (630, 70)], outline=(70, 50, 50), width=2, fill=(35, 25, 25))
        
        draw.text((25, 20), "TELEMETRY: RUN_2 (UNSTABLE HUNTING)", fill=(239, 68, 68), font=font_large)
        draw.text((25, 45), f"Frame: {i:02d} / {frames-1}   |   Time: {i*0.1:.1f}s", fill=(150, 150, 150), font=font)
        
        progress = i / (frames - 1)
        # ハンチング（振動）する速度の計算
        oscillation = math.sin(i * 0.8) * 80.0
        speed = 500.0 * (1.0 - math.exp(-i / 4.0)) + oscillation
        speeds_2.append(speed)
        
        # 車輪の描画
        cx = 120 + int(400 * progress)
        cy = 200 + int(oscillation * 0.5)
        radius = 45
        # 外輪
        draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)], outline=(239, 68, 68), width=3)
        # スポーク
        angle = progress * 8.0 * math.pi
        sx = cx + int(radius * math.cos(angle))
        sy = cy + int(radius * math.sin(angle))
        draw.line([(cx, cy), (sx, sy)], fill=(239, 68, 68), width=4)
        
        # 速度テキスト
        draw.text((cx - 45, cy + radius + 10), f"Speed: {speed:.1f}", fill=(239, 68, 68), font=font)
        
        # リアルタイムグラフの描画枠
        graph_left, graph_top = 50, 300
        graph_width, graph_height = 540, 120
        draw.rectangle([(graph_left, graph_top), (graph_left + graph_width, graph_top + graph_height)], outline=(80, 60, 60), width=1, fill=(28, 20, 20))
        draw.text((graph_left + 10, graph_top + 5), "Real-time Speed Plot (Target: 500)", fill=(120, 100, 100), font=font)
        
        # ターゲットライン
        target_y = graph_top + graph_height - int((500.0 / 600.0) * graph_height)
        draw.line([(graph_left, target_y), (graph_left + graph_width, target_y)], fill=(239, 68, 68), width=1)
        
        # グラフのプロット
        points = []
        for idx, s in enumerate(speeds_2):
            px = graph_left + int(idx * (graph_width / (frames - 1)))
            py = graph_top + graph_height - int((s / 600.0) * graph_height)
            points.append((px, py))
            
        if len(points) > 1:
            draw.line(points, fill=(239, 68, 68), width=3)
            
        img.save(os.path.join(run_2_dir, f"frame_{i:02d}.png"))

