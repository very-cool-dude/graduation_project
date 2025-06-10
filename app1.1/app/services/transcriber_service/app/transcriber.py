from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from gradio_client import Client, handle_file
from pathlib import Path
import shutil
import uuid
import logging

# ----------------------- НАСТРОЙКА ЛОГИРОВАНИЯ -----------------------
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "transcriber.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Сервис transcriber запущен!")

# ----------------------- КОНФИГУРАЦИЯ -----------------------
app = FastAPI()

UPLOAD_DIR = Path("/tmp/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

client = Client("hf-audio/whisper-large-v3")

# ----------------------- ЭНДПОИНТЫ -----------------------
@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    try:
        temp_filename = f"{uuid.uuid4()}.wav"
        temp_path = UPLOAD_DIR / temp_filename

        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        logger.info(f"📥 Получен файл: {audio.filename} → {temp_filename}")

        result = client.predict(
            inputs=handle_file(str(temp_path)),
            task="transcribe",
            api_name="/predict"
        )

        logger.info(f"✅ Распознавание завершено | Результат: {result[:80]}...")
        return {"text": result}

    except Exception as e:
        logger.error(f"❌ Ошибка обработки файла: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})