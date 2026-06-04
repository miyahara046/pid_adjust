# FastAPI サーバー利用手順

## セットアップ

### 1. 必要なパッケージをインストール

```bash
pip install fastapi uvicorn python-multipart
```

### 2. サーバーを起動

```bash
python api.py
```

サーバーは `http://localhost:8000` で起動します。

---

## curlコマンドの使用例

### シンプルな使い方

```bash
curl -X POST -F "file=@data.csv" http://localhost:8000/analyze
```

### ターゲット値を指定

```bash
curl -X POST -F "file=@data.csv" -F "target_val=600" http://localhost:8000/analyze
```

### 全パラメータを指定

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

### 結果をJSONで整形表示（PowerShell）

```powershell
curl -X POST -F "file=@data.csv" http://localhost:8000/analyze | ConvertFrom-Json | ConvertTo-Json
```

### 結果をJSONで整形表示（Linux/Mac）

```bash
curl -X POST -F "file=@data.csv" http://localhost:8000/analyze | python -m json.tool
```

### 結果をファイルに保存

```bash
curl -X POST -F "file=@data.csv" http://localhost:8000/analyze > result.json
```

---

## ファイル説明

- **api.py** - FastAPIサーバー実装
- **analyzer.py** - 解析ロジック（Streamlit と共有）
- **app.py** - Streamlit UI（従来通り使用可能）
- **API_USAGE.md** - 詳細な使用ガイド

---

## Streamlitとの使い分け

- **Streamlit (app.py)** - ブラウザでインタラクティブに使用
- **FastAPI (api.py)** - コマンドラインやスクリプトで自動化に使用

両方同時に起動することも可能です：

```bash
# ターミナル1
python api.py

# ターミナル2
streamlit run app.py
```
