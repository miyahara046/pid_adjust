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
