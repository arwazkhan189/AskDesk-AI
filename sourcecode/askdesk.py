import tkinter as tk
from threading import Thread
import pytesseract
from PIL import ImageGrab, Image, ImageTk
import re
import time
import requests
import keyboard
import pyperclip
import google.generativeai as genai
import shutil
import os
import socket
from flask import Flask, request, jsonify

# Constants
GENAI_API_KEY = 'AIzaSyCE_xx-9VgX6YmKh1kBt2m8uZ51BC_ETFY'
DEFAULT_TESS_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
FLASK_PORT = 5000
answers = []
server_started = False

# Tesseract Path Config
if os.path.exists(DEFAULT_TESS_PATH):
    pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESS_PATH

# Flask Setup
flask_app = Flask(__name__)

@flask_app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    answers.clear()
    q = data.get('question', '').strip()
    a = data.get('answer', '').strip().replace('<', '&lt;').replace('>', '&gt;')
    formatted = f"""
    <b>Q:</b> {q}<br>
    <b>A:</b>
    <pre><code class="language-cpp">{a}</code></pre>
    <hr>
    """
    answers.append(formatted)
    return jsonify(success=True)

@flask_app.route('/')
def show_answers():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live Q&A</title>
        <meta http-equiv="refresh" content="5">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css" rel="stylesheet" />
        <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-cpp.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            pre {{ background: #f5f5f5; padding: 12px; border-radius: 8px; overflow-x: auto; }}
            hr {{ margin: 30px 0; }}
        </style>
    </head>
    <body>
        <h1>🧠 Live Q&A Feed</h1>
        {"".join(answers)}
    </body>
    </html>
    """


def run_flask_server():
    global server_started
    server_started = True
    flask_app.run(host="0.0.0.0", port=FLASK_PORT)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# GUI App
class AskDeskApp:
    def __init__(self):
        self.api_key = GENAI_API_KEY
        self.server_url = ""
        self.model = None
        self.running = False

        self.root = tk.Tk()
        self.root.title("AskDesk App")
        self.root.geometry("280x220")
        self.root.resizable(False, False)

        try:
            favicon = Image.open("favicon.ico")
            favicon = favicon.resize((32, 32), Image.LANCZOS)
            icon = ImageTk.PhotoImage(favicon)
            self.root.iconphoto(False, icon)
        except:
            pass

        tk.Label(self.root, text="Gemini API Key:").pack(pady=2)
        self.api_entry = tk.Entry(self.root, width=50, show="*")
        self.api_entry.insert(0, GENAI_API_KEY)
        self.api_entry.pack()

        tk.Label(self.root, text="Answer Format:").pack(pady=2)
        self.language_var = tk.StringVar(self.root)
        self.language_var.set("Python")
        language_menu = tk.OptionMenu(self.root, self.language_var, "Python", "C++", "Java")
        language_menu.pack()

        self.status_label = tk.Label(self.root, text="Press 'Start' to activate", fg="blue")
        self.status_label.pack(pady=8)

        self.server_label = tk.Label(self.root, text="Server not started", fg="gray")
        self.server_label.pack()

        self.start_button = tk.Button(self.root, text="Start", command=self.start_listener)
        self.start_button.pack(pady=10)

        Thread(target=run_flask_server, daemon=True).start()
        self.root.after(1000, self.update_server_status)
        self.root.mainloop()

    def update_server_status(self):
        if server_started:
            ip = get_ip()
            self.server_url = f"http://{ip}:{FLASK_PORT}/submit"
            self.server_label.config(text=f"Server at {ip}:{FLASK_PORT}", fg="green")
        self.root.after(1000, self.update_server_status)

    def start_listener(self):
        self.api_key = self.api_entry.get().strip() or GENAI_API_KEY

        if not shutil.which("tesseract") and not os.path.exists(DEFAULT_TESS_PATH):
            self.status_label.config(text="Tesseract not found", fg="red")
            return

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
            self.status_label.config(text="Listening for Ctrl + Q...", fg="green")
            self.running = True
            Thread(target=self.hotkey_loop, daemon=True).start()
        except Exception as e:
            self.status_label.config(text=f"Error: {e}", fg="red")

    def capture_screen_text(self):
        screenshot = ImageGrab.grab()
        return pytesseract.image_to_string(screenshot)

    def extract_question(self, text):
        questions = re.findall(r'([A-Z][^?]*\?)', text)
        return questions[0].strip() if questions else None

    def get_answer(self, question, mode):
        try:
            language = self.language_var.get()
            q_lower = question.lower()

            if mode == 'mcq':
                prompt = f"Only return the correct option with explanation. This is a multiple-choice question. Do not return any code. Question: {q_lower}"
            else:
                prompt = f"Only return the code in {language} without any comments or explanation. Just raw code. Question: {q_lower}"

            response = self.model.generate_content(prompt)
            answer = response.text.strip()
            pyperclip.copy(answer)
            return answer
        except Exception as e:
            return f"Error: {e}"


    def send_to_server(self, question, answer):
        try:
            requests.post(self.server_url, json={"question": question, "answer": answer})
        except Exception as e:
            print("Error sending to server:", e)

    def hotkey_loop(self):
        while self.running:
            if keyboard.is_pressed('ctrl+q'):
                self.status_label.config(text="🧠 Programming: Scanning...", fg="orange")
                text = self.capture_screen_text()
                question = self.extract_question(text)
                if question:
                    answer = self.get_answer(question, mode='code')
                    self.send_to_server(question, answer)
                    self.status_label.config(text="✅ Code copied & sent", fg="green")
                else:
                    self.status_label.config(text="⚠️ No question found", fg="red")
                time.sleep(1.2)

            if keyboard.is_pressed('ctrl+m'):
                self.status_label.config(text="🧠 MCQ: Scanning...", fg="orange")
                text = self.capture_screen_text()
                question = self.extract_question(text)
                if question:
                    answer = self.get_answer(question, mode='mcq')
                    self.send_to_server(question, answer)
                    self.status_label.config(text="✅ MCQ answer copied & sent", fg="green")
                else:
                    self.status_label.config(text="⚠️ No question found", fg="red")
                time.sleep(1.2)


if __name__ == "__main__":
    AskDeskApp()
