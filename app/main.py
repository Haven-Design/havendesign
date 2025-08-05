from fastapi import FastAPI, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import os
import uuid
import shutil
import json

from app.utilities.redact_pdf import redact_pdf

app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploaded_files"
RESULT_DIR = "redacted_files"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

@app.post("/redact")
async def redact(file: UploadFile = File(...), data: str = Form(...)):
    try:
        contents = await file.read()
        file_id = str(uuid.uuid4())
        input_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")

        with open(input_path, "wb") as f:
            f.write(contents)

        areas = json.loads(data)

        output_path = os.path.join(RESULT_DIR, f"redacted_{file.filename}")
        redact_pdf(input_path, areas, output_path)

        return JSONResponse(content={"file_url": f"/download/{os.path.basename(output_path)}"})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join(RESULT_DIR, filename)
    return FileResponse(file_path, media_type='application/pdf', filename=filename)