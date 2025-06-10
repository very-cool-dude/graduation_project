from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from urllib.parse import quote
from pathlib import Path
import logging
import httpx

# ----------------------- НАСТРОЙКА ЛОГИРОВАНИЯ -----------------------
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "gateway.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Сервис generator запущен!")

# ----------------------- КОНФИГУРАЦИЯ -----------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

AUTH_SERVICE_URL = "http://auth_service:8003/verify"
REPORT_SERVICE_URL = "http://report_service:8002"
STT_SERVICE_URL = "http://stt_service:8005/transcribe"
LLM_SERVICE_URL = "http://llm_service:8006/generate"

# ----------------------- ЭНДПОИНТЫ -----------------------
# 🔐 Авторизация
@app.post("/auth")
async def auth_route(request: Request):
    payload = await request.json()
    logger.info(f"🔐 Авторизация запроса: {payload.get('login')}")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(AUTH_SERVICE_URL, json=payload)
            resp.raise_for_status()
            logger.info("✅ Авторизация успешна")
            return resp.json()
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка авторизации: {str(e)}")

# 📥 Отправка файла + шаблона + промпта
@app.post("/process")
async def process_route(
    audio: UploadFile = File(...),
    template_name: str = Form(...),
    prompt: str = Form(...),
    request: Request = None
):
    logger.info(f"📥 Обработка отчёта | шаблон: {template_name}, файл: {audio.filename}")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            files = {
                "audio": (audio.filename, await audio.read(), "audio/wav"),
                "template_name": (None, template_name),
                "prompt": (None, prompt),
            }

            headers = {}
            if request:
                auth_header = request.headers.get("Authorization")
                if auth_header:
                    headers["Authorization"] = auth_header

            resp = await client.post(f"{REPORT_SERVICE_URL}/report", files=files, headers=headers)
            resp.raise_for_status()

            logger.info("✅ Отчёт успешно сгенерирован")
            content = resp.content
            return StreamingResponse(
                iter([content]),
                media_type=resp.headers.get("content-type", "application/octet-stream"),
                headers={
                    "Content-Disposition": resp.headers.get("Content-Disposition", "attachment; filename=report.docx")
                }
            )
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ HTTP ошибка от report_service: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.error(f"❌ Ошибка проксирования: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка проксирования: {str(e)}")

# 📄 Список шаблонов
@app.get("/templates")
async def proxy_template_list():
    logger.info("📄 Запрос списка шаблонов")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{REPORT_SERVICE_URL}/templates")
            r.raise_for_status()
            logger.info("✅ Шаблоны получены")
            return r.json()
    except Exception as e:
        logger.error(f"❌ Ошибка получения шаблонов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения списка шаблонов: {e}")

# 📁 Получение отдельного файла шаблона
@app.get("/template/{filename}")
async def proxy_template_file(filename: str):
    logger.info(f"📁 Запрос файла шаблона: {filename}")
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", f"{REPORT_SERVICE_URL}/template/{filename}") as r:
                r.raise_for_status()
                file_bytes = b""
                async for chunk in r.aiter_bytes():
                    file_bytes += chunk

                filename_encoded = quote(filename)
                logger.info(f"✅ Шаблон {filename} получен")
                return StreamingResponse(
                    iter([file_bytes]),
                    media_type=r.headers.get("content-type", "application/octet-stream"),
                    headers={
                        "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
                    }
                )
    except Exception as e:
        logger.error(f"❌ Ошибка получения шаблона: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения шаблона: {e}")