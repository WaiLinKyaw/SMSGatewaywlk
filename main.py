import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Configurations
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_KEY = os.getenv("API_KEY")
# Traccar SMS Gateway URL (အနောက်တွင် /message မပါရပါ၊ root path သို့မဟုတ် slash သာ ဖြစ်ရပါမည်)
ANDROID_GATEWAY_URL = "http://192.168.100.204:8082/"  


logging.basicConfig(level=logging.INFO)

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
        await update.message.reply_text("အသုံးပြုပုံ မှားယွင်းနေပါသည်။\nဥပမာ: /send 09123456789 စာသား")
        return

    # Telegram မှ ပို့လိုက်သော ဖုန်းနံပါတ်နှင့် စာသားကို ယူခြင်း
    phone_number = context.args[0]
    message_text = " ".join(context.args[1:])

    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }

    # အသုံးပြုသူ ရိုက်ထည့်လိုက်သော ဖုန်းနံပါတ်နှင့် စာသားကို Payload ထဲသို့ ထည့်သွင်းခြင်း
    payload = {
        "to": phone_number,
        "message": message_text
    }
        # timeout=(connect_timeout, read_timeout)
        # ချိတ်ဆက်ဖို့ ၅ စက္ကန့်၊ ဖုန်းဆီမှ response ပြန်လာရန် စက္ကန့် ၃၀ စောင့်မည်
    try:
        response = requests.post(
            ANDROID_GATEWAY_URL,
            json=payload,
            headers=headers,
            timeout=(5,30)
        )

        if response.status_code in [200, 201]:
            await update.message.reply_text(f"✅ SMS ပို့ဆောင်မှု အောင်မြင်ပါသည် -\nဖုန်း: {phone_number}\nစာသား: {message_text}")
        else:
            await update.message.reply_text(f"❌ SMS ပို့မရပါ (Status: {response.status_code})\nတုံ့ပြန်မှု: {response.text}")

    except requests.exceptions.ReadTimeout:
        # SMS က ဖုန်းဆီ ရောက်သွားပြီးဖြစ်သော်လည်း response ပြန်လာတာ နောက်ကျသည့် အခြေအနေ
        await update.message.reply_text(f"⚠️ SMS ကို ဖုန်းဆီ ပို့ပြီးဖြစ်သော်လည်း Gateway တုံ့ပြန်မှု နှောင့်နှေးနေပါသည် (ဖုန်းတွင် စစ်ဆေးပါ) -\nဖုန်း: {phone_number}")

    except requests.exceptions.ConnectTimeout:
        await update.message.reply_text("❌ ဖုန်း IP သို့ လုံးဝ ချိတ်ဆက်၍ မရပါ (Connect Timeout)။")

    except Exception as e:
        await update.message.reply_text(f"❌ ချိတ်ဆက်မှု အဆင်မပြေပါ: {str(e)}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send", send_sms))
    
    print("Bot is running...")
    app.run_polling()