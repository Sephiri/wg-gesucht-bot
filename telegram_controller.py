import asyncio
import os
import signal
import logging
from dotenv import load_dotenv
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot_process: asyncio.subprocess.Process | None = None


def is_authorized(update: Update) -> bool:
    return str(update.effective_chat.id) == ALLOWED_CHAT_ID


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    global bot_process
    if bot_process and bot_process.returncode is None:
        await update.message.reply_text("⚠️ Bot läuft bereits.")
        return

    bot_process = await asyncio.create_subprocess_exec(
        "python3", "bot.py",
        cwd="/app",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    logger.info("bot.py gestartet (PID %s)", bot_process.pid)
    await update.message.reply_text(f"▶️ Bot gestartet (PID {bot_process.pid})")

    # Log-Output im Hintergrund lesen
    asyncio.create_task(_stream_logs(bot_process))


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    global bot_process
    if not bot_process or bot_process.returncode is not None:
        await update.message.reply_text("⚠️ Bot läuft nicht.")
        return

    bot_process.send_signal(signal.SIGTERM)
    try:
        await asyncio.wait_for(bot_process.wait(), timeout=10)
    except asyncio.TimeoutError:
        bot_process.kill()
        await bot_process.wait()

    logger.info("bot.py gestoppt")
    await update.message.reply_text("⏹️ Bot gestoppt.")
    bot_process = None


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    if bot_process and bot_process.returncode is None:
        await update.message.reply_text(f"✅ Bot läuft.)")
    else:
        await update.message.reply_text("❌ Bot läuft nicht.")


async def _stream_logs(proc: asyncio.subprocess.Process):
    """Liest stdout/stderr vom Subprocess und loggt es."""
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        logger.info("[bot.py] %s", line.decode().rstrip())
    logger.info("bot.py beendet (exit code %s)", proc.returncode)


async def auto_start(application):
    global bot_process
    bot_process = await asyncio.create_subprocess_exec(
        "python3", "bot.py",
        cwd="/app",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    logger.info("bot.py automatisch gestartet (PID %s)", bot_process.pid)
    asyncio.create_task(_stream_logs(bot_process))


def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_API_TOKEN nicht gesetzt")
    if not ALLOWED_CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID nicht gesetzt")

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(auto_start).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))

    logger.info("Telegram Controller gestartet. Warte auf Befehle...")
    app.run_polling()


if __name__ == "__main__":
    main()
