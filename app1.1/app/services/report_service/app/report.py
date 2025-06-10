from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import aiofiles
import requests
import uuid
import logging
from tempfile import NamedTemporaryFile
from docx import Document

# ----------------------- НАСТРОЙКА ЛОГИРОВАНИЯ -----------------------
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "report.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Сервис report запущен!")

# ----------------------- КОНФИГУРАЦИЯ -----------------------
app = FastAPI()

TEMPLATE_DIR = Path(__file__).parent / "templates"
STT_URL = "http://stt_service:8004/transcribe"
LLM_URL = "http://llm_service:8005/generate"

# ----------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ -----------------------
def fill_template(template_path: Path, replacements: dict, output_path: Path):
    doc = Document(template_path)
    for para in doc.paragraphs:
        for key, val in replacements.items():
            tag = f"{{{{{key}}}}}"
            if tag in para.text:
                para.text = para.text.replace(tag, val)
    doc.save(output_path)

# ----------------------- ЭНДПОИНТЫ -----------------------
@app.get("/templates")
def list_templates():
    docx_files = sorted(f for f in TEMPLATE_DIR.glob("*.docx"))
    result = []
    for docx in docx_files:
        base = docx.stem
        prompt = TEMPLATE_DIR / f"{base}.prompt.txt"
        pdf = TEMPLATE_DIR / f"{base}.demo.pdf"
        result.append({
            "docx": f"/template/{docx.name}",
            "prompt": f"/template/{prompt.name}" if prompt.exists() else "",
            "pdf": f"/template/{pdf.name}" if pdf.exists() else "",
        })
    logger.info(f"📄 Шаблонов найдено: {len(result)}")
    return result

@app.get("/template/{filename}")
def get_template_file(filename: str):
    file_path = TEMPLATE_DIR / filename
    if file_path.exists():
        logger.info(f"📤 Файл отправлен: {filename}")
        return FileResponse(file_path)
    logger.warning(f"❌ Файл не найден: {filename}")
    raise HTTPException(status_code=404, detail="Файл не найден")

@app.post("/report")
async def generate_report(
    audio: UploadFile = File(...),
    template_name: str = Form(...),
    prompt: str = Form(...)
):
    logger.info(f"📥 Новый запрос на генерацию | шаблон: {template_name} | файл: {audio.filename}")

    temp_audio_path = Path("/tmp") / f"{uuid.uuid4()}.wav"
    try:
        async with aiofiles.open(temp_audio_path, "wb") as f:
            await f.write(await audio.read())
        logger.info(f"🔊 Аудиофайл сохранён: {temp_audio_path.name}")
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении WAV: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сохранения файла")

    # Распознавание речи (STT)
    try:
        with open(temp_audio_path, "rb") as f:
            files = {"audio": (audio.filename, f, "audio/wav")}
            stt_resp = requests.post(STT_URL, files=files)
            stt_resp.raise_for_status()
        transcription = stt_resp.json().get("text", "")
        logger.info(f"📡 Распознанный текст: {transcription}")
    except Exception as e:
        logger.error(f"❌ Ошибка STT: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка STT: {str(e)}")

    # Генерация ответа от LLM
    try:
        llm_payload = {
            "prompt": prompt,
            "transcription": transcription
        }
        llm_resp = requests.post(LLM_URL, json=llm_payload)
        llm_resp.raise_for_status()
        result_data = llm_resp.json().get("answer", {})
        logger.info(f"🤖 Ответ от LLM: {result_data}")
    except Exception as e:
        logger.error(f"❌ Ошибка LLM: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка генерации отчёта: {e}")

    # Генерация .docx
    try:
        template_path = TEMPLATE_DIR / template_name
        with NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            filled_path = Path(tmp.name)
            fill_template(template_path, result_data, filled_path)
            logger.info(f"🧾 DOCX сгенерирован: {filled_path.name}")
            return FileResponse(
                filled_path,
                filename="Готовый_отчёт.docx",
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
    except Exception as e:
        logger.error(f"❌ Ошибка формирования документа: {e}")
        raise HTTPException(status_code=500, detail="Ошибка формирования документа")