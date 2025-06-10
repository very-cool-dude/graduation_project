import tkinter as tk
from tkinter import filedialog, messagebox
import requests
import os
import webbrowser
import logging
from pathlib import Path
from docx import Document

# ----------------------- НАСТРОЙКА ЛОГИРОВАНИЯ -----------------------
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "frontend.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ---------------------- КОНФИГУРАЦИЯ ----------------------
msg_ip = '192.168.1.106:8000'

GATEWAY_AUTH_URL = f"http://{msg_ip}/auth"
GATEWAY_PROCESS_URL = f"http://{msg_ip}/process"
TEMPLATE_SYNC_URL = f"http://{msg_ip}/templates"
TEMPLATE_FILE_URL = f"http://{msg_ip}/template/"
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# ---------------------- КЛАСС GUI ----------------------
class FrontendApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EMR Client")
        self.token = None
        self.role = None
        self.file_path = None
        self.templates = []

        TEMPLATE_DIR.mkdir(exist_ok=True)
        self.sync_templates()
        self.build_login_ui()

    def sync_templates(self):
        try:
            response = requests.get(TEMPLATE_SYNC_URL)
            data = response.json()
            logger.info(f"DEBUG TEMPLATE DATA: {data}")

            if not isinstance(data, list):
                raise Exception("Ожидался список шаблонов, но получено: " + str(type(data)))

            for item in data:
                for ftype in ["docx", "prompt", "pdf"]:
                    fname = item[ftype].split("/")[-1]
                    fpath = TEMPLATE_DIR / fname
                    if not fpath.exists():
                        r = requests.get(TEMPLATE_FILE_URL + fname)
                        with open(fpath, "wb") as out:
                            out.write(r.content)

        except Exception as e:
            messagebox.showerror("Ошибка загрузки шаблонов", str(e))
            logger.error(f"[ОШИБКА sync_templates] {e}")

    def build_login_ui(self):
        self.login_frame = tk.Frame(self.root)
        self.login_frame.pack(padx=20, pady=20)

        tk.Label(self.login_frame, text="Логин:").grid(row=0, column=0, sticky="e")
        self.login_entry = tk.Entry(self.login_frame)
        self.login_entry.grid(row=0, column=1)

        tk.Label(self.login_frame, text="Пароль:").grid(row=1, column=0, sticky="e")
        self.password_entry = tk.Entry(self.login_frame, show="*")
        self.password_entry.grid(row=1, column=1)

        tk.Button(self.login_frame, text="Войти", command=self.try_login).grid(row=2, column=0, columnspan=2, pady=10)

    def try_login(self):
        login = self.login_entry.get()
        password = self.password_entry.get()

        if not login or not password:
            messagebox.showerror("Ошибка", "Введите логин и пароль")
            return

        try:
            resp = requests.post(GATEWAY_AUTH_URL, json={"login": login, "password": password})
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("token")
                self.role = data.get("role")
                self.login_frame.destroy()
                if self.role == "admin":
                    self.build_admin_ui()
                else:
                    self.build_operator_ui()
            else:
                messagebox.showerror("Ошибка входа", "Неверные учетные данные")
                logger.warning("Ошибка входа: неверные данные")
        except Exception as e:
            messagebox.showerror("Ошибка подключения", str(e))
            logger.error(f"Ошибка подключения: {e}")

    def build_operator_ui(self):
        tk.Label(self.root, text="Выберите аудиофайл (.wav):").pack(pady=5)
        tk.Button(self.root, text="Загрузить WAV", command=self.select_wav).pack(pady=5)
        tk.Label(self.root, text="Выберите шаблон отчёта (.docx):").pack(pady=5)

        self.refresh_templates()
        self.template_var = tk.StringVar()
        if self.templates:
            self.template_var.set(self.templates[0])
        else:
            self.template_var.set("Нет шаблонов")

        self.template_menu = tk.OptionMenu(self.root, self.template_var, *self.templates)
        self.template_menu.pack(pady=5)
        self.update_template_menu()

        tk.Button(self.root, text="🚀 Отправить в обработку", command=self.send_request).pack(pady=10)
        self.status = tk.Label(self.root, text="Статус: ожидание", fg="blue")
        self.status.pack(pady=10)

    def build_admin_ui(self):
        tk.Label(self.root, text="Выберите шаблон для PROMPT:").pack(pady=5)

        self.refresh_templates()
        self.template_var = tk.StringVar()
        self.template_var.set(self.templates[0] if self.templates else "Нет шаблонов")

        self.template_menu = tk.OptionMenu(self.root, self.template_var, *self.templates, command=self.load_prompt_for_template)
        self.template_menu.pack(pady=5)
        self.update_template_menu()

        tk.Label(self.root, text="Редактировать PROMPT:").pack(pady=5)
        self.prompt_text = tk.Text(self.root, height=10, width=60)
        self.prompt_text.pack()

        tk.Button(self.root, text="📥 Скачать шаблон (.docx)", command=self.download_docx).pack(pady=5)
        tk.Button(self.root, text="👁 Открыть PDF предпросмотр", command=self.open_pdf_preview).pack(pady=5)

        if self.templates:
            self.load_prompt_for_template(self.template_var.get())

        tk.Button(self.root, text="💾 Сохранить PROMPT", command=self.save_prompt).pack(pady=5)
        tk.Button(self.root, text="📄 Загрузить шаблон", command=self.upload_docx).pack(pady=5)
        tk.Button(self.root, text="➕ Новый оператор", command=self.add_operator).pack(pady=5)

    def refresh_templates(self):
        self.templates = [f.name for f in TEMPLATE_DIR.glob("*.docx")]

    def load_prompt_for_template(self, template_name):
        prompt_file = TEMPLATE_DIR / template_name.replace(".docx", ".prompt.txt")
        self.prompt_text.delete("1.0", tk.END)
        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as f:
                self.prompt_text.insert(tk.END, f.read())

    def open_pdf_preview(self):
        base = self.template_var.get().replace(".docx", "")
        pdf_file = TEMPLATE_DIR / f"{base}.demo.pdf"
        if pdf_file.exists():
            webbrowser.open(f"file://{pdf_file.resolve()}")
        else:
            messagebox.showerror("Ошибка", "PDF предпросмотр не найден")

    def download_docx(self):
        selected_template = self.template_var.get()
        source = TEMPLATE_DIR / selected_template
        dest = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("DOCX files", "*.docx")])
        if dest:
            try:
                with open(source, "rb") as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                messagebox.showinfo("Скачивание", "Файл успешно сохранён")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    def select_wav(self):
        path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if path:
            self.file_path = path
            self.status.config(text=f"Файл выбран: {os.path.basename(path)}")

    def send_request(self):
        if not self.file_path:
            messagebox.showwarning("Ошибка", "Сначала выберите WAV-файл")
            return

        selected_template = self.template_var.get()
        prompt_file = TEMPLATE_DIR / selected_template.replace(".docx", ".prompt.txt")

        if not prompt_file.exists():
            messagebox.showwarning("Ошибка", "Файл PROMPT не найден")
            return

        with open(prompt_file, "r", encoding="utf-8") as f:
            prompt_text = f.read()

        try:
            self.status.config(text="⏳ Отправка запроса на отчёт...", fg="orange")
            logger.info("Старт отправки запроса")

            headers = {"Authorization": f"Bearer {self.token}"}

            with open(self.file_path, "rb") as audio_file:
                files = {
                    "audio": (os.path.basename(self.file_path), audio_file, "audio/wav"),
                    "template_name": (None, selected_template),
                    "prompt": (None, prompt_text)
                }

                logger.info(f"POST -> /report | template={selected_template}")
                response = requests.post(GATEWAY_PROCESS_URL, files=files, headers=headers)
                logger.info(f"HTTP {response.status_code}")

            if response.status_code == 200:
                save_path = filedialog.asksaveasfilename(
                    defaultextension=".docx",
                    filetypes=[("DOCX files", "*.docx")],
                    title="Сохранить отчёт как..."
                )
                if save_path:
                    with open(save_path, "wb") as f:
                        f.write(response.content)
                    self.status.config(text="✅ Отчёт сохранён", fg="green")
                    messagebox.showinfo("Успех", f"Файл сохранён в:\n{save_path}")
                    logger.info(f"Файл сохранён: {save_path}")
                else:
                    self.status.config(text="⚠️ Сохранение отменено", fg="orange")
                    logger.warning("Сохранение файла отменено пользователем")
            else:
                self.status.config(text="❌ Ошибка при генерации", fg="red")
                messagebox.showerror("Ошибка", response.text)
                logger.error(f"Ошибка от сервера: {response.text}")

        except Exception as e:
            self.status.config(text="❌ Ошибка соединения", fg="red")
            messagebox.showerror("Ошибка", str(e))
            logger.exception(f"Исключение при отправке: {e}")

    def upload_docx(self):
        path = filedialog.askopenfilename(filetypes=[("DOCX files", "*.docx")])
        if path:
            existing = [f.name for f in TEMPLATE_DIR.glob("Шаблон_*.docx")]
            numbers = [int(f.split("_")[1].split(".")[0]) for f in existing if f.split("_")[1].split(".")[0].isdigit()]
            next_number = max(numbers, default=0) + 1
            new_name = f"Шаблон_{next_number}.docx"
            dest = TEMPLATE_DIR / new_name

            with open(path, "rb") as src, open(dest, "wb") as dst:
                dst.write(src.read())

            self.refresh_templates()
            self.template_var.set(new_name)
            self.update_template_menu()
            messagebox.showinfo("Успешно", f"Файл сохранён как {new_name}")

    def update_template_menu(self):
        menu = self.template_menu["menu"]
        menu.delete(0, "end")
        for template in self.templates:
            menu.add_command(label=template, command=lambda value=template: self.template_var.set(value))

    def save_prompt(self):
        selected_template = self.template_var.get()
        prompt_file = TEMPLATE_DIR / selected_template.replace(".docx", ".prompt.txt")
        text = self.prompt_text.get("1.0", tk.END).strip()
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(text)
        messagebox.showinfo("Сохранено", f"PROMPT сохранён для {selected_template}")

    def add_operator(self):
        messagebox.showinfo("Создание оператора", "Добавлен новый оператор (заглушка)")

if __name__ == "__main__":
    logger.info("🔄 Запуск интерфейса")
    root = tk.Tk()
    app = FrontendApp(root)
    root.mainloop()