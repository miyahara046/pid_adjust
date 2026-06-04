# FastAPI サーバー使用ガイド

## セットアップ

### 1. 必要なパッケージのインストール

```bash
pip install fastapi uvicorn
```

### 2. サーバーの起動

```bash
python api.py
```

サーバーは `http://localhost:8000` で起動します。

---

## API エンドポイント

### `/analyze` - POST

CSVファイルをアップロードして解析を実行します。

#### パラメータ

- `file` (必須): CSVファイル
- `target_val` (オプション): ターゲット値（デフォルト: 500.0）
- `kp_l`, `ki_l`, `kd_l` (オプション): 左モーターのPIDゲイン
- `kp_r`, `ki_r`, `kd_r` (オプション): 右モーターのPIDゲイン

#### 使用例

**基本的な使い方:**

```bash
curl -X POST -F "file=@data.csv" http://localhost:8000/analyze
```

**ターゲット値を指定:**

```bash
curl -X POST -F "file=@data.csv" -F "target_val=600" http://localhost:8000/analyze
```

**すべてのパラメータを指定:**

```bash
curl -X POST \
  -F "file=@data.csv" \
  -F "target_val=500" \
  -F "kp_l=1.0" \
  -F "ki_l=0.05" \
  -F "kd_l=0.1" \
  -F "kp_r=1.0" \
  -F "ki_r=0.05" \
  -F "kd_r=0.1" \
  http://localhost:8000/analyze
```

**JSON形式で結果を整形して表示（PowerShellの場合）:**

```powershell
curl -X POST -F "file=@data.csv" http://localhost:8000/analyze | ConvertFrom-Json | ConvertTo-Json
```

**Linux/Macの場合:**

```bash
curl -X POST -F "file=@data.csv" http://localhost:8000/analyze | python -m json.tool
```

---

### `/health` - GET

サーバーの状態確認

```bash
curl http://localhost:8000/health
```

---

## レスポンス形式

```json
{
  "timestamp": "2026-06-04T12:34:56.789012",
  "target_val": 500.0,
  "left_motor": {
    "score": 85.5,
    "max_speed": 520.3,
    "overshoot": 4.06,
    "steady_error": -2.5,
    "stable_std": 5.2,
    "rise_time": 0.123,
    "saturation_ratio": 15.3,
    "hunting_cycles": 2,
    "suggested_kp": 0.95,
    "suggested_ki": 0.05,
    "suggested_kd": 0.15,
    "advice": [
      "追従性は良好です"
    ]
  },
  "right_motor": {
    "score": 82.1,
    ...
  },
  "balance": {
    "left_avg_speed": 498.5,
    "right_avg_speed": 502.1,
    "diff_ratio": 0.72,
    "regression_a": 0.015,
    "regression_b": -1.5
  }
}
```

---

## CSVファイル形式

必須列:

- `time`: 時間（秒）
- `leftSpeed`: 左モーター速度
- `rightSpeed`: 右モーター速度
- `leftPower`: 左モーター出力
- `rightPower`: 右モーター出力

例:

```csv
time,leftSpeed,rightSpeed,leftPower,rightPower
0.0,0.0,0.0,0.0,0.0
0.1,50.2,49.8,25.5,24.8
0.2,100.5,101.2,51.0,50.5
...
```

---

## トラブルシューティング

### ポート 8000 が既に使用されている場合

別のポートで起動:

```bash
python -c "import uvicorn; from api import app; uvicorn.run(app, host='0.0.0.0', port=8001)"
```

その場合はcurlのURLを `http://localhost:8001/analyze` に変更してください。

### ファイルが見つからない

CSVファイルがカレントディレクトリにあることを確認してください。
相対パスまたは絶対パスでファイルを指定してください。
