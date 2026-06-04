from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import json
import io
from analyzer import analyze_csv
import uvicorn

app = FastAPI(title="モーター調整補助APIサーバー")

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
    
    使用例:
    curl -X POST -F "file=@data.csv" -F "target_val=500" http://localhost:8000/analyze
    """
    try:
        # ファイル内容を読み込む
        contents = await file.read()
        csv_data = io.BytesIO(contents)
        
        # 解析実行
        result = analyze_csv(csv_data, target_val, kp_l, ki_l, kd_l, kp_r, ki_r, kd_r)
        
        return JSONResponse(content=result)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析エラー: {str(e)}")

@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
