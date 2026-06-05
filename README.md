# モーター制御（PID）調整・解析システム

本プロジェクトは、左右モーターのPIDゲイン調整、速度応答解析、および走行データの可視化を強力にサポートするシステムです。
実機やシミュレータからのCSVログデータを解析し、制御評価スコアの算出や、最適なPIDゲイン調整への自動アドバイスを行います。

システムは **サーバー側 (FastAPI)** と **ユーザー側 (Streamlit)** の二層構造で構成されており、インタラクティブな波形解析から、実機の走行ログ自動送信・可視化パイプラインまで統合的にカバーしています。

---

## 構成概要

```mermaid
graph TD
    A[実機 / シミュレータ] -- curl.exe 送信 --> B(サーバー側: FastAPI)
    B -- 結果保存 / 提供 --> C[Webダッシュボード: /dashboard]
    B -- データ提供 --> D(ユーザー側: Streamlit)
    D -- 同期リクエスト --> B
    D -- 可視化 / インタラクティブ調整 --> E[Streamlit UI]
```

### 1. サーバー側 (FastAPI)
- **ファイル**: [api.py](file:///c:/Users/takar/pid_adjust/api.py), [analyzer.py](file:///c:/Users/takar/pid_adjust/analyzer.py)
- **役割**: CSVファイルを受け取り、バックエンドで高速解析を実行、結果を `analysis_results/` ディレクトリに保存します。
- **エンドポイント**:
  - `POST /analyze`: CSVログとパラメータを受け取り、解析結果をJSONで返します。
  - `GET /dashboard`: 解析結果の推移を一覧表示するリアルタイムダッシュボード（HTML形式）を提供します。
  - `GET /results`: 過去の解析結果リストを取得します。

### 2. ユーザー側 (Streamlit)
- **ファイル**: [app.py](file:///c:/Users/takar/pid_adjust/app.py), [analyzer.py](file:///c:/Users/takar/pid_adjust/analyzer.py)
- **役割**: 解析データおよびゲイン調整のためのグラフィカルな対話インターフェースを提供します。
- **特徴**:
  - **ローカルCSV読み込み**: 手元にあるCSVファイルをドラッグ＆ドロップして即座に解析できます。
  - **サーバー同期モード**: サーバー側 (FastAPI) に蓄積された過去の測定ログを選択し、ターゲット値やPIDゲイン設定（Kp, Ki, Kd）を自動同期して解析・可視化できます。

---

## 環境構築

Windows環境（PowerShell または コマンドプロンプト）でのセットアップ手順です。

### 1. 仮想環境の作成と有効化

```powershell
# 1. 仮想環境の作成
python -m venv .venv

# 2. 仮想環境の有効化
# (PowerShellの場合)
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\.venv\Scripts\activate

# (コマンドプロンプトの場合)
.venv\Scripts\activate
```

### 2. 依存パッケージのインストール

```powershell
pip install -r requirements.txt
```

---

## 起動と使用方法

### A. サーバー側 (FastAPI) の起動

```powershell
python api.py
```
- サーバーが `http://localhost:8000` で起動します。
- ブラウザで `http://localhost:8000/dashboard` を開くと、送信されたデータ履歴とスコア推移をグラフィカルに確認できます。

#### コマンドラインからのデータ送信方法 (curl)
実機の測定が完了した際、以下のコマンドを実行してCSVログをサーバーへ即座に送信・解析させることができます。
```powershell
curl.exe -X POST -F "file=@runlog.csv" http://localhost:8000/analyze
```
*(※ Windows PowerShellのデフォルトの `curl` はエイリアスになっているため、必ず `curl.exe` と明記して呼び出してください。)*

ターゲット値などのパラメータを指定して送信することも可能です：
```powershell
curl.exe -X POST -F "file=@runlog.csv" -F "target_val=600" -F "kp_l=1.2" http://localhost:8000/analyze
```

---

### B. ユーザー側 (Streamlit) の起動

```powershell
streamlit run app.py
```
- ブラウザが起動し、`http://localhost:8501` に接続されます（初回起動時にEmail入力を求められた場合は、何も入力せずEnterを押してください）。

#### 使用モード
1. **ローカルCSVファイルをアップロード**:
   画面からCSVファイルをアップロードし、左側のサイドバーでターゲット値・ゲインを設定して解析します。
2. **サーバーと同期（最新データ）**:
   FastAPIサーバーと同期し、サーバー上に保存されている過去の測定履歴から選択して、当時のゲイン・ターゲット値等をワンクリックで復元・解析・可視化します。

---

## CSVファイル形式

解析対象のCSVファイルは、以下のカラムを含んでいる必要があります。

| カラム名 | 意味 |
| :--- | :--- |
| `time` | 時間軸（秒） |
| `leftSpeed` | 左モーターの実測速度 |
| `rightSpeed` | 右モーターの実測速度 |
| `leftPower` | 左モーターの制御出力値 |
| `rightPower` | 右モーターの制御出力値 |

**CSVファイルの記述例:**
```csv
time,leftSpeed,rightSpeed,leftPower,rightPower
0.0,0.0,0.0,0.0,0.0
0.1,50.2,49.8,25.5,24.8
0.2,100.5,101.2,51.0,50.5
...
```
