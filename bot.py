import os
import base64
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from telegram.request import HTTPXRequest
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

# ক্লাউড হোস্টিংয়ের পোর্ট বাইন্ডিং প্রবলেম সমাধানের জন্য ছোট একটি Flask সার্ভার
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Telegram News Bot with Brevo API is running successfully!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# টেলিগ্রাম বট টোকেন এবং Brevo কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")

# কনভার্সেশন স্টেপস
GET_NEWS, GET_RECIPIents, GET_IMAGE = range(3)

# রিসিভারদের ড্রপডাউন/বাটন লিস্ট
RECEIVER_LIST = [
    {"name": "Adin", "email": "adinonlinenews@gmail.com"},
    {"name": "Samakal", "email": "samakallokaloy@gmail.com"},
    {"name": "Ittefaq", "email": "ittefaqdigital@gmail.com"},
    {"name": "Sattaypath", "email": "sattyapath@gmail.com"},
    {"name": "Samajer Kotha", "email": "samajerkatha@gmail.com"},
    {"name": "Daily Sun", "email": "news@daily-sun.com"},
    {"name": " Rabbil", "email": "sabbirrahmanrabbil05@gmail.com"},

]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["selected_emails"] = []
    await update.message.reply_text(
        "আসসালামু আলাইকুম! প্রথমে নিউজের বড় টেক্সটটি পাঠান (প্যারা আকারে), যা মেইলে পাঠানো হবে।"
    )
    return GET_NEWS

async def receive_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["news_text"] = update.message.text
    
    keyboard = []
    for idx, rec in enumerate(RECEIVER_LIST):
        keyboard.append([InlineKeyboardButton(f"⬜ {rec['name']} ({rec['email']})", callback_data=f"select_{idx}")])
    
    keyboard.append([InlineKeyboardButton("✅ সিলেকশন শেষ (Send)", callback_data="done_selection")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "নিচে থেকে যাদের মেইল পাঠাতে চান তাদের সিলেক্ট করুন (একাধিক সিলেক্ট করতে পারেন):",
        reply_markup=reply_markup
    )
    return GET_RECIPIents

async def handle_receiver_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    selected_emails = context.user_data.get("selected_emails", [])
    
    if data.startswith("select_"):
        idx = int(data.split("_")[1])
        target_email = RECEIVER_LIST[idx]["email"]
        
        if target_email in selected_emails:
            selected_emails.remove(target_email)
        else:
            selected_emails.append(target_email)
            
        context.user_data["selected_emails"] = selected_emails
        
        keyboard = []
        for i, rec in enumerate(RECEIVER_LIST):
            icon = "☑" if rec["email"] in selected_emails else "⬜"
            keyboard.append([InlineKeyboardButton(f"{icon} {rec['name']} ({rec['email']})", callback_data=f"select_{i}")])
        keyboard.append([InlineKeyboardButton("✅ সিলেকশন শেষ (Send)", callback_data="done_selection")])
        
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return GET_RECIPIents
        
    elif data == "done_selection":
        if not selected_emails:
            await query.edit_message_text("❌ আপনি কাউকে সিলেক্ট করেননি! দয়া করে অন্তত একজনকে সিলেক্ট করুন। /start দিয়ে আবার শুরু করুন।")
            return ConversationHandler.END
            
        await query.message.reply_text(
            f"মোট {len(selected_emails)} জনকে সিলেক্ট করা হয়েছে।\n\nএবার ইমেইলের সাথে পাঠানোর জন্য ছবিটি (Photo) দিন:"
        )
        return GET_IMAGE

async def receive_image_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "temp_image.jpg"
    await photo_file.download_to_drive(photo_path)

    news_text = context.user_data["news_text"]
    recipients = context.user_data["selected_emails"]

    paragraphs = news_text.split("\n\n")
    if not paragraphs:
        paragraphs = news_text.split("\n")

    subject = paragraphs[0] if paragraphs else "New News Update"
    body_content = "\n\n".join(paragraphs[1:]) if len(paragraphs) > 1 else news_text

    signature = (
        "\n\n-----------------------------------\n"
        "সাব্বির রহমান রাব্বীল\n"
        "যশোর বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয়\n"
        "মোবাইলঃ ০১৫৯০০৩৫১০৭"
    )

    full_email_body = body_content + signature
    html_content = f"<p>{full_email_body.replace(chr(10), '<br>')}</p>"

    # ছবি রিড করে বেস৬৪ (Base64) এনকোড করা Brevo অ্যাটাচমেন্টের জন্য
    with open(photo_path, "rb") as f:
        file_bytes = f.read()
        encoded_file = base64.b64encode(file_bytes).decode("utf-8")

    success_count = 0
    fail_count = 0

    try:
        # Brevo API কনফিগারেশন
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = BREVO_API_KEY
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

        sender = {"name": "Sabbir Rahman Rabbil", "email": SENDER_EMAIL}

        for recipient in recipients:
            try:
                to = [{"email": recipient}]
                attachment = [{
                    "content": encoded_file,
                    "name": "news_image.jpg"
                }]

                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                    to=to,
                    sender=sender,
                    subject=subject,
                    html_content=html_content,
                    attachment=attachment
                )

                api_instance.send_transac_email(send_smtp_email)
                success_count += 1
            except ApiException as e:
                fail_count += 1
                print(f"Brevo API Failed for {recipient}: {e}")

        await update.message.reply_text(
            f"✅ কাজ সম্পন্ন!\n"
            f"সফলভাবে পাঠানো হয়েছে: {success_count} টি মেইল\n"
            f"(কারও ক্ষেত্রে সমস্যা হলে ফেইলড: {fail_count} টি)"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Brevo কানেকশনে সমস্যা হয়েছে: {e}")

    if os.path.exists(photo_path):
        os.remove(photo_path)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("প্রক্রিয়াটি বাতিল করা হয়েছে। আবার শুরু করতে /start লিখুন।")
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")

def main():
    # ব্যাকগ্রাউন্ডে ফ্লাস্ক সার্ভার চালু করা যাতে ক্লাউড পোর্ট পেয়ে যায়
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # টাইমআউট সমস্যা সমাধানের জন্য HTTPXRequest কনফিগারেশন যুক্ত করা হয়েছে
    custom_request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0
    )

    app = ApplicationBuilder().token(BOT_TOKEN).request(custom_request).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_NEWS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_news)],
            GET_RECIPIents: [CallbackQueryHandler(handle_receiver_selection)],
            GET_IMAGE: [MessageHandler(filters.PHOTO, receive_image_and_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_error_handler(error_handler)

    print("Bot with Brevo API & Flask Port Binding is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
