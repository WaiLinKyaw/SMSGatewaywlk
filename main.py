import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Configurations
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_KEY = os.getenv("API_KEY")

# Cloudflare Tunnel URL ကို Environment Variable ကနေ ဖတ်မည် (မရှိပါက fallback default ကို သုံးမည်)
# မှတ်ချက်: URL အဆုံးတွင် '/' ပါဝင်ရပါမည်
DEFAULT_GATEWAY = "https://anti-latino-acting-maintain.trycloudflare.com/"
ANDROID_GATEWAY_URL = os.getenv("ANDROID_GATEWAY_URL", DEFAULT_GATEWAY)

if not ANDROID_GATEWAY_URL.endswith("/"):
    ANDROID_GATEWAY_URL += "/"

# ---------------- Log Configurations ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Bot token ပါဝင်နေသော Telegram API URL များကို httpx log ထဲ မပေါ်စေရန် WARNING level သို့ ပြောင်းလဲခြင်း
logging.getLogger("httpx").setLevel(logging.WARNING)
# ----------------------------------------------------


# ---------------- Render Health Check Server ----------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    # Health check request များ log ထဲတွင် မရှုပ်စေရန်
    def log_message(self, format, *args):
        pass

def run_health_server():
    # Render မှ သတ်မှတ်ပေးသော PORT သို့မဟုတ် default 8080 ကို အသုံးပြုမည်
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()
# -----------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "SMS ပို့ရန် အောက်ပါအတိုင်း ရိုက်ပို့ပါ -\n"
        "/send  \n\n"
        "ဥပမာ -\n"
        "/send 09123456789 မင်္ဂလာပါ"
    )

async def send_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # စစ်ဆေးခြင်း: argument အနည်းဆုံး ၂ ခု ပါရမည် (ဖုန်းနံပါတ် နှင့် စာသား)
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ အသုံးပြုပုံ မှားယွင်းနေပါသည်။\nဥပမာ: /send 09123456789 မင်္ဂလာပါ")
        return

    # Telegram မှ ပို့လိုက်သော ဖုန်းနံပါတ်နှင့် စာသားကို ယူခြင်း
    phone_number = context.args[0]
    message_text = " ".join(context.args[1:])

    headers = {
        "Content-Type": "application/json"
    }
    # API_KEY ရှိမှသာ Authorization header ထည့်ပေးမည် (Traccar SMS Gateway မှာ Token မခံထားပါက မလိုပါ)
    if API_KEY:
        headers["Authorization"] = API_KEY

    # အသုံးပြုသူ ရိုက်ထည့်လိုက်သော ဖုန်းနံပါတ်နှင့် စာသားကို Payload ထဲသို့ ထည့်သွင်းခြင်း
    payload = {
        "to": phone_number,
        "message": message_text
    }

    try:
        # timeout=(connect_timeout, read_timeout)
        # Cloudflare မှတဆင့် ဖုန်းဆီ ဆက်သွယ်ရန် ၇ စက္ကန့်၊ SMS ပို့ပြီး response ပြန်လာရန် စက္ကန့် ၃၀ စောင့်မည်
        response = requests.post(
            ANDROID_GATEWAY_URL,
            json=payload,
            headers=headers,
            timeout=(7, 30)
        )

        if response.status_code in [200, 201]:
            await update.message.reply_text(f"✅ SMS ပို့ဆောင်မှု အောင်မြင်ပါသည် -\nဖုန်း: {phone_number}\nစာသား: {message_text}")
        else:
            await update.message.reply_text(f"❌ SMS ပို့မရပါ (Status: {response.status_code})\nတုံ့ပြန်မှု: {response.text}")

    except requests.exceptions.ReadTimeout:
        # SMS က ဖုန်းဆီ ရောက်သွားပြီးဖြစ်သော်လည်း response ပြန်လာတာ နောက်ကျသည့် အခြေအနေ
        await update.message.reply_text(f"⚠️ SMS ကို ဖုန်းဆီ ပို့ပြီးဖြစ်သော်လည်း Gateway တုံ့ပြန်မှု နှောင့်နှေးနေပါသည် (ဖုန်းတွင် စစ်ဆေးပါ) -\nဖုန်း: {phone_number}")

    except requests.exceptions.ConnectTimeout:
        await update.message.reply_text("❌ Cloudflare Tunnel သို့ ချိတ်ဆက်၍ မရပါ (Connect Timeout)။ Tunnel URL မှန်ကန်မှုနှင့် Termux အခြေအနေကို စစ်ဆေးပါ။")

    except Exception as e:
        await update.message.reply_text(f"❌ ချိတ်ဆက်မှု အဆင်မပြေပါ: {str(e)}")

if __name__ == "__main__":
    # Render အတွက် Port Scan မအောင်မြင်သည့် Error ကို ဖြေရှင်းရန် Health Check Server ကို background thread ဖြင့် စတင်ခြင်း
    threading.Thread(target=run_health_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send", send_sms))
    
    print("Bot is running...")
    app.run_polling()