from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
import json
import io
import os
from analyzer import analyze_csv
import uvicorn
from datetime import datetime

app = FastAPI(title="モーター調整補助APIサーバー")

# 結果を保存するディレクトリ
RESULTS_DIR = "analysis_results"
os.makedirs(RESULTS_DIR, exist_ok=True)

def save_result(result, timestamp_key):
    """解析結果をJSONファイルに保存"""
    filename = f"{RESULTS_DIR}/result_{timestamp_key}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return filename

def generate_dashboard_html(results_list=None):
    """ダッシュボードHTMLを生成"""
    if results_list is None:
        results_list = []
    
    # 結果ファイルを読み込む
    if not results_list:
        try:
            result_files = sorted([f for f in os.listdir(RESULTS_DIR) if f.endswith('.json')], reverse=True)
            for filename in result_files[-10:]:  # 最新10件
                try:
                    with open(os.path.join(RESULTS_DIR, filename), 'r', encoding='utf-8') as f:
                        results_list.append(json.load(f))
                except:
                    pass
        except:
            pass
    
    # スコア推移データ
    left_scores = [r['left_motor']['score'] for r in results_list]
    right_scores = [r['right_motor']['score'] for r in results_list]
    timestamps = [r['timestamp'][-8:-3] for r in results_list]  # HH:MM形式
    
    html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>モーター調整補助ダッシュボード</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 1400px;
                margin: 0 auto;
            }}
            .header {{
                background: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .header h1 {{
                color: #333;
                margin-bottom: 10px;
                font-size: 2em;
            }}
            .header p {{
                color: #666;
                font-size: 1em;
            }}
            .latest-result {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 20px;
            }}
            .metric-card {{
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .metric-card h2 {{
                color: #333;
                font-size: 1.3em;
                margin-bottom: 15px;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
            }}
            .metric {{
                display: flex;
                justify-content: space-between;
                margin: 10px 0;
                padding: 8px 0;
                border-bottom: 1px solid #eee;
            }}
            .metric-label {{
                color: #666;
                font-weight: 500;
            }}
            .metric-value {{
                color: #333;
                font-weight: bold;
                font-size: 1.1em;
            }}
            .score {{
                font-size: 2em;
                color: #667eea;
                text-align: center;
                margin: 20px 0;
            }}
            .advice {{
                background: #f0f4ff;
                padding: 15px;
                border-left: 4px solid #667eea;
                margin-top: 15px;
                border-radius: 5px;
                color: #333;
                line-height: 1.6;
                font-size: 0.95em;
            }}
            .chart-container {{
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }}
            .chart-container h2 {{
                color: #333;
                margin-bottom: 20px;
                font-size: 1.3em;
            }}
            .grid-2 {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }}
            .footer {{
                text-align: center;
                color: white;
                padding: 20px;
                font-size: 0.9em;
            }}
            .status-good {{
                color: #10b981;
                font-weight: bold;
            }}
            .status-warning {{
                color: #f59e0b;
                font-weight: bold;
            }}
            .status-bad {{
                color: #ef4444;
                font-weight: bold;
            }}
            @media (max-width: 768px) {{
                .latest-result {{
                    grid-template-columns: 1fr;
                }}
                .grid-2 {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 モーター調整補助ダッシュボード</h1>
                <p>FastAPI サーバーで送信されたデータをリアルタイム表示</p>
            </div>
    """
    
    if results_list:
        latest = results_list[0]
        left_motor = latest['left_motor']
        right_motor = latest['right_motor']
        balance = latest['balance']
        
        html += f"""
            <div class="latest-result">
                <div class="metric-card">
                    <h2>⬅️ 左モーター</h2>
                    <div class="score">{left_motor['score']:.1f}</div>
                    <div class="metric">
                        <span class="metric-label">最大速度</span>
                        <span class="metric-value">{left_motor['max_speed']:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">オーバーシュート</span>
                        <span class="metric-value">{left_motor['overshoot']:.2f}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">定常偏差</span>
                        <span class="metric-value">{left_motor['steady_error']:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">ハンチング周期</span>
                        <span class="metric-value">{left_motor['hunting_cycles']}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">推奨 Kp</span>
                        <span class="metric-value">{left_motor['suggested_kp']:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">推奨 Ki</span>
                        <span class="metric-value">{left_motor['suggested_ki']:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">推奨 Kd</span>
                        <span class="metric-value">{left_motor['suggested_kd']:.2f}</span>
                    </div>
                    <div class="advice">
                        <strong>アドバイス:</strong><br>
                        {'<br>'.join(left_motor['advice'])}
                    </div>
                </div>
                
                <div class="metric-card">
                    <h2>➡️ 右モーター</h2>
                    <div class="score">{right_motor['score']:.1f}</div>
                    <div class="metric">
                        <span class="metric-label">最大速度</span>
                        <span class="metric-value">{right_motor['max_speed']:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">オーバーシュート</span>
                        <span class="metric-value">{right_motor['overshoot']:.2f}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">定常偏差</span>
                        <span class="metric-value">{right_motor['steady_error']:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">ハンチング周期</span>
                        <span class="metric-value">{right_motor['hunting_cycles']}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">推奨 Kp</span>
                        <span class="metric-value">{right_motor['suggested_kp']:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">推奨 Ki</span>
                        <span class="metric-value">{right_motor['suggested_ki']:.2f}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">推奨 Kd</span>
                        <span class="metric-value">{right_motor['suggested_kd']:.2f}</span>
                    </div>
                    <div class="advice">
                        <strong>アドバイス:</strong><br>
                        {'<br>'.join(right_motor['advice'])}
                    </div>
                </div>
            </div>
            
            <div class="metric-card">
                <h2>⚖️ 左右バランス分析</h2>
                <div class="metric">
                    <span class="metric-label">左平均速度</span>
                    <span class="metric-value">{balance['left_avg_speed']:.2f}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">右平均速度</span>
                    <span class="metric-value">{balance['right_avg_speed']:.2f}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">差異率</span>
                    <span class="metric-value {('status-good' if balance['diff_ratio'] < 5 else 'status-warning' if balance['diff_ratio'] < 10 else 'status-bad')}">{balance['diff_ratio']:.2f}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">回帰係数</span>
                    <span class="metric-value">{balance['regression_a']:.6f}</span>
                </div>
            </div>
        """
        
        if len(left_scores) > 1:
            html += """
            <div class="chart-container">
                <h2>📊 スコア推移</h2>
                <div id="scoreChart" style="height: 400px;"></div>
                <script>
                    var data = [
                        {{
                            x: """ + json.dumps(timestamps) + """,
                            y: """ + json.dumps(left_scores) + """,
                            name: '左モーター',
                            mode: 'lines+markers',
                            line: {{color: '#667eea'}}
                        }},
                        {{
                            x: """ + json.dumps(timestamps) + """,
                            y: """ + json.dumps(right_scores) + """,
                            name: '右モーター',
                            mode: 'lines+markers',
                            line: {{color: '#764ba2'}}
                        }}
                    ];
                    var layout = {{
                        title: 'スコア推移（最新10件）',
                        xaxis: {{title: '時刻'}},
                        yaxis: {{title: 'スコア', range: [0, 100]}},
                        hovermode: 'x unified'
                    }};
                    Plotly.newPlot('scoreChart', data, layout);
                </script>
            </div>
            """
    else:
        html += """
            <div class="metric-card">
                <h2>📭 データなし</h2>
                <p>まだ解析データがありません。PowerShellスクリプトまたはAPIで解析を実行してください。</p>
            </div>
        """
    
    html += """
            <div class="footer">
                <p>このダッシュボードは FastAPI サーバーから自動生成されています</p>
                <p><code>http://localhost:8000/dashboard</code> でアクセス</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

@app.post("/analyze")
async def analyze_data(
    file: UploadFile = File(...),
    target_val: float = Form(500.0),
    kp_l: float = Form(1.00),
    ki_l: float = Form(0.00),
    kd_l: float = Form(0.00),
    kp_r: float = Form(1.00),
    ki_r: float = Form(0.00),
    kd_r: float = Form(0.00)
):
    """
    CSVファイルをアップロードして解析します。
    """
    try:
        contents = await file.read()
        csv_data = io.BytesIO(contents)
        
        result = analyze_csv(csv_data, target_val, kp_l, ki_l, kd_l, kp_r, ki_r, kd_r)
        
        # タイムスタンプキーを生成（マイクロ秒を含めて衝突防止）
        timestamp_key = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        
        # CSVファイルを保存
        csv_filename = f"{RESULTS_DIR}/data_{timestamp_key}.csv"
        with open(csv_filename, 'wb') as f:
            f.write(contents)
            
        # 結果をファイルに保存
        save_result(result, timestamp_key)
        
        return JSONResponse(content=result)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析エラー: {str(e)}")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """ダッシュボード表示"""
    return generate_dashboard_html()

@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "ok"}

@app.get("/results")
async def get_results():
    """保存された解析結果のリストを取得"""
    results_list = []
    try:
        if not os.path.exists(RESULTS_DIR):
            return []
        result_files = sorted([f for f in os.listdir(RESULTS_DIR) if f.startswith('result_') and f.endswith('.json')], reverse=True)
        for filename in result_files:
            try:
                timestamp_key = filename[7:-5]  # result_ と .json を除く
                with open(os.path.join(RESULTS_DIR, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    results_list.append({
                        "timestamp_key": timestamp_key,
                        "timestamp": data.get("timestamp", ""),
                        "target_val": data.get("target_val", 500.0),
                        "left_score": data.get("left_motor", {}).get("score", 0.0),
                        "right_score": data.get("right_motor", {}).get("score", 0.0),
                        "kp_l": data.get("kp_l", 1.0),
                        "ki_l": data.get("ki_l", 0.0),
                        "kd_l": data.get("kd_l", 0.0),
                        "kp_r": data.get("kp_r", 1.0),
                        "ki_r": data.get("ki_r", 0.0),
                        "kd_r": data.get("kd_r", 0.0),
                    })
            except Exception:
                pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"履歴読み込みエラー: {str(e)}")
    
    return results_list

@app.get("/results/{timestamp_key}/csv")
async def get_result_csv(timestamp_key: str):
    """指定されたタイムスタンプのCSVファイルを取得"""
    csv_path = os.path.join(RESULTS_DIR, f"data_{timestamp_key}.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="CSVファイルが見つかりません。")
    return FileResponse(csv_path, media_type="text/csv", filename=f"data_{timestamp_key}.csv")

@app.get("/results/{timestamp_key}/json")
async def get_result_json(timestamp_key: str):
    """指定されたタイムスタンプの解析結果JSONを取得"""
    json_path = os.path.join(RESULTS_DIR, f"result_{timestamp_key}.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="JSONファイルが見つかりません。")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JSONファイル読み込みエラー: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
