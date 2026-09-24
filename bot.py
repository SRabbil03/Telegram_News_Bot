import os
import smtplib
from email.message import EmailMessage
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

# টেলিগ্রাম বট টোকেন এখানে বসান
BOT_TOKEN = os.getenv("BOT_TOKEN")

# জিমেইল কনফিগারেশন
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# কনভার্সেশন স্টেপস
GET_NEWS, GET_RECIPIents, GET_IMAGE = range(3)

# আপনার রিসিভারদের ড্রপডাউন/বাটন লিস্ট (এখানে আপনি ইচ্ছামমতো ইমেইল বাড়াতে পারবেন)
RECEIVER_LIST = [
    {"name": "Friend 1", "email": "sabbirrahmanrabbil05@gmail.com"},
    {"name": "Friend 2", "email": "230120.cse@student.just.edu.bd"},
    {"name": "Friend 3", "email": "papilioxuthus02@gmail.com"},
    # আপনার প্রয়োজনীয় আরও ইমেইল এখানে যুক্ত করতে পারেন
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # নতুন সেশনের জন্য সিলেকশন লিস্ট রিসেট করা
    context.user_data["selected_emails"] = []
    await update.message.reply_text(
        "আসসালামু আলাইকুম! প্রথমে নিউজের বড় টেক্সটটি পাঠান (প্যারা আকারে), যা মেইলে পাঠানো হবে।"
    )
    return GET_NEWS

async def receive_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["news_text"] = update.message.text
    
    # রিসিভার সিলেক্ট করার জন্য ইনলাইন বাটন তৈরি করা
    keyboard = []
    for idx, rec in enumerate(RECEIVER_LIST):
        # শুরুতে সব আনসিलेक्टেড থাকবে [ ]
        keyboard.append([InlineKeyboardButton(f"⬜ {rec['name']} ({rec['email']})", callback_data=f"select_{idx}")])
    
    # কনফার্ম করার জন্য ডান বাটন
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
        
        # টগল করা (সিলেক্ট থাকলে আনসিলেক্ট, না থাকলে সিলেক্ট)
        if target_email in selected_emails:
            selected_emails.remove(target_email)
        else:
            selected_emails.append(target_email)
            
        context.user_data["selected_emails"] = selected_emails
        
        # বাটনগুলোর স্টেট আপডেট করা (☑ এবং ⬜ দিয়ে বোঝানোর জন্য)
        keyboard = []
        for i, rec in enumerate(RECEIVER_LIST):
            icon = "☑" if rec["email"] in selected_emails else "⬜"
            keyboard.append([InlineKeyboardButton(f"{icon} {rec['name']} ({rec['email']})", callback_data=f"select_{i}")])
        keyboard.append([InlineKeyboardButton("✅ সিলেকশন শেষ (Send)", callback_data="done_selection")])
        
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return GET_RECIPIents
        
    elif data == "done_selection":
        if not selected_emails:
            await query.edit_message_text("❌ আপনি কাউকে সিলেক্ট করেননি! দয়া করে অন্তত একজনকে সিলেক্ট করুন। /start দিয়ে আবার শুরু করুন।")
            return ConversationHandler.END
            
        await query.message.reply_text(
            f"মোট {len(selected_emails)} জনকে সিলেক্ট করা হয়েছে।\n\nএবার ইমেইলের সাথে পাঠানোর জন্য ছবিটি (Photo) দিন:"
        )
        return GET_IMAGE

async def receive_image_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_path = "temp_image.jpg"
    await photo_file.download_to_drive(photo_path)

    news_text = context.user_data["news_text"]
    recipients = context.user_data["selected_emails"]

    # প্যারা আলাদা করা
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

    success_count = 0
    fail_count = 0

    try:
        # জিমেইলের SMTP সার্ভার একবার কানেক্ট করে লুপ চালিয়ে সবাইকে আলাদাভাবে মেইল পাঠানো
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            
            for recipient in recipients:
                try:
                    msg = EmailMessage()
                    msg["Subject"] = subject
                    msg["From"] = SENDER_EMAIL
                    msg["To"] = recipient  # প্রতিবার একক রিসিভার বসবে (মাল্টিপল হবে না)
                    msg.set_content(full_email_body)

                    # ছবি এটাচ করা
                    with open(photo_path, "rb") as f:
                        file_data = f.read()
                        file_name = os.path.basename(photo_path)
                    msg.add_attachment(file_data, maintype="image", subtype="jpeg", filename=file_name)

                    smtp.send_message(msg)
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    print(f"Failed for {recipient}: {e}")

        await update.message.reply_text(
            f"✅ কাজ সম্পন্ন!\n"
            f"সফলভাবে পাঠানো হয়েছে: {success_count} টি মেইল\n"
            f"(কারও ক্ষেত্রে সমস্যা হলে ফেইলড: {fail_count} টি)"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ জিমেইল কানেকশনে সমস্যা হয়েছে: {e}")

    # টেম্পোরারি ছবি ডিলিট করা
    if os.path.exists(photo_path):
        os.remove(photo_path)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("প্রক্রিয়াটি বাতিল করা হয়েছে। আবার শুরু করতে /start লিখুন।")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

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
    print("Bot with Dropdown Selection is running...")
    app.run_polling()

if __name__ == "__main__":
    main()