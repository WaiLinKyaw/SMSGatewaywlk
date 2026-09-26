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

# မိမိ၏ Telegram User ID (ဂဏန်းအရှည်) ကို ထည့်ပါ (ဥပမာ - 123456789)
# .env ထဲတွင် ADMIN_USER_ID=123456789 ဟု ထည့်ထားနိုင်ပါသည်
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# Cloudflare Tunnel URL (အနောက်တွင် / ပါဝင်ရပါမည်)
DEFAULT_GATEWAY = "https://your-tunnel-url.trycloudflare.com/"
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

    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()
# -----------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Admin ဟုတ်/မဟုတ် စစ်ဆေးခြင်း
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ ခွင့်ပြုချက်မရှိပါ။ ဤ Bot ကို ပိုင်ရှင်သာ အသုံးပြုနိုင်ပါသည်။")
        return

    await update.message.reply_text(
        "👋 မင်္ဂလာပါ Admin!\n\n"
        "SMS ပို့ရန် အောက်ပါအတိုင်း ရိုက်ပို့နိုင်ပါသည် -\n"
        "`/send  `\n\n"
        "ဥပမာ -\n"
        "`/send 09123456789 မင်္ဂလာပါ`",
        parse_mode="Markdown"
    )

async def send_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # ---------------- Admin Whitelist Check ----------------
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ ခွင့်ပြုချက်မရှိပါ။ သင်သည် SMS ပို့ခွင့်မရှိပါ။")
        logging.warning(f"Unauthorized access attempt by User ID: {user_id}")
        return
    # -------------------------------------------------------

    # Argument အနည်းဆုံး ၂ ခု ပါရမည် (ဖုန်းနံပါတ် နှင့် စာသား)
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ အသုံးပြုပုံ မှားယွင်းနေပါသည်။\nဥပမာ: `/send 09123456789 မင်္ဂလာပါ`", parse_mode="Markdown")
        return

    phone_number = context.args[0]
    message_text = " ".join(context.args[1:])

    # Authorization API_KEY မလိုဘဲ Content-Type သာ ထည့်သွင်းခြင်း
    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "to": phone_number,
        "message": message_text
    }

    try:
        # Cloudflare မှတဆင့် ဖုန်းဆီ ဆက်သွယ်ရန် ၇ စက္ကန့်၊ SMS ပို့ပြီး response ပြန်လာရန် စက္ကန့် ၃၀ စောင့်မည်
        response = requests.post(
            ANDROID_GATEWAY_URL,
            json=payload,
            headers=headers,
            timeout=(7, 30)
        )

        if response.status_code in [200, 201]:
            await update.message.reply_text(
                f"✅ SMS ပို့ဆောင်မှု အောင်မြင်ပါသည် -\n"
                f"📞 ဖုန်း: `{phone_number}`\n"
                f"💬 စာသား: {message_text}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ SMS ပို့မရပါ (Status: {response.status_code})\nတုံ့ပြန်မှု: {response.text}")

    except requests.exceptions.ReadTimeout:
        await update.message.reply_text(f"⚠️ SMS ကို ဖုန်းဆီ ပို့ပြီးဖြစ်သော်လည်း Gateway တုံ့ပြန်မှု နှောင့်နှေးနေပါသည် (ဖုန်းတွင် စစ်ဆေးပါ) -\nဖုန်း: `{phone_number}`", parse_mode="Markdown")

    except requests.exceptions.ConnectTimeout:
        await update.message.reply_text("❌ Cloudflare Tunnel သို့ ချိတ်ဆက်၍ မရပါ (Connect Timeout)။ Tunnel URL မှန်ကန်မှုနှင့် Termux အခြေအနေကို စစ်ဆေးပါ။")

    except Exception as e:
        await update.message.reply_text(f"❌ ချိတ်ဆက်မှု အဆင်မပြေပါ: {str(e)}")

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send", send_sms))

    print("🤖 Bot စတင် အလုပ်လုပ်နေပါပြီ...")
    app.run_polling()