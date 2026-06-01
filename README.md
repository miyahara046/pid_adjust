# pid_adjust

宮崎大学片山徹郎研究室チーム KatLab が作成する[ET ロボコン 2026](https://www.etrobo.jp/)アプライドクラスの走行システムに向けた、左右モーターのPIDゲイン調整・波形解析ツールです。

実機やシミュレータから出力されたログデータ（CSV）を読み込み、速度・出力波形の可視化、およびゲイン調整のアドバイスを自動で行うStreamlitアプリケーションです。

## 構成

### ./app.py

Streamlit アプリケーション本体

### ./.gitignore

Git追跡除外設定

### ./README.md

本ファイル（説明書）

## プロジェクトの起動

### ローカル環境（Windows / macOS）の場合

Windowsの「コマンドプロンプト（cmd）」または「PowerShell」を開き、```pid_adjust``` で以下を順に実行

1. 仮想環境（.venv）の作成

```shell
python -m venv .venv
```

1. 仮想環境の有効化

### コマンドプロンプトの場合

```shell
.venv\Scripts\activate
```

### PowerShellの場合

```PowerSell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\.venv\Scripts\activate
```

1. 必要なライブラリのインストール

```shell
pip install streamlit pandas plotly
```

1. アプリケーションの起動

```shell
streamlit run app.py
```

## 使用方法

1. 制御パラメータの設定:
画面左側のサイドバーで、現在の「目標スピード（ターゲット値）」と、ログ取得時の「左右のPIDゲイン（Kp, Ki, Kd）」を入力します。

2. データの読み込み:
実機から取得したCSVデータをドラッグ＆ドロップでアップロードします。

3. アドバイスの確認と調整:
画面上部に表示される「自動解析アドバイス（ゲインの上げ下げの提案）」を確認し、グラフを見ながら実機のゲイン調整に役立ててください
