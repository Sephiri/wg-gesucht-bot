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
STATE_FILE = Path("/app/bot_state")
RESTART_DELAY_SECONDS = 30

bot_process: asyncio.subprocess.Process | None = None


def save_state(running: bool):
    STATE_FILE.write_text("running" if running else "stopped")


def load_state() -> bool:
    if not STATE_FILE.exists():
        return True  # Standardmäßig starten beim ersten Start
    return STATE_FILE.read_text().strip() == "running"


def is_authorized(update: Update) -> bool:
    return str(update.effective_chat.id) == ALLOWED_CHAT_ID


async def _launch_bot() -> asyncio.subprocess.Process:
    global bot_process

    if bot_process and bot_process.returncode is None:
        return bot_process

    proc = await asyncio.create_subprocess_exec(
        "python3", "bot.py",
        cwd="/app",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    bot_process = proc
    asyncio.create_task(_stream_logs(proc))
    asyncio.create_task(_watch_bot(proc))
    return proc


async def _watch_bot(proc: asyncio.subprocess.Process):
    global bot_process

    returncode = await proc.wait()
    logger.warning("bot.py beendet (exit code %s)", returncode)

    if bot_process is proc:
        bot_process = None

    if load_state():
        logger.warning(
            "bot.py ist unerwartet beendet. Neustart in %s Sekunden...",
            RESTART_DELAY_SECONDS,
        )
        await asyncio.sleep(RESTART_DELAY_SECONDS)

        if load_state() and (bot_process is None or bot_process.returncode is not None):
            new_proc = await _launch_bot()
            logger.info("bot.py neu gestartet (PID %s)", new_proc.pid)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    global bot_process
    if bot_process and bot_process.returncode is None:
        await update.message.reply_text("⚠️ Bot läuft bereits.")
        return

    save_state(running=True)
    bot_process = await _launch_bot()
    logger.info("bot.py gestartet (PID %s)", bot_process.pid)
    await update.message.reply_text(f"▶️ Bot gestartet (PID {bot_process.pid})")


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    global bot_process
    if not bot_process or bot_process.returncode is not None:
        save_state(running=False)
        await update.message.reply_text("⚠️ Bot läuft nicht.")
        return

    save_state(running=False)
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
        await update.message.reply_text("✅ Bot läuft.")
    else:
        await update.message.reply_text("❌ Bot läuft nicht.")


async def _stream_logs(proc: asyncio.subprocess.Process):
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        logger.info("[bot.py] %s", line.decode().rstrip())


async def auto_start(application):
    global bot_process
    if load_state():
        bot_process = await _launch_bot()
        logger.info("bot.py automatisch gestartet (PID %s)", bot_process.pid)
        await application.bot.send_message(
            chat_id=ALLOWED_CHAT_ID,
            text=f"✅ Container gestartet.",
        )
    else:
        logger.info("bot.py bleibt gestoppt (letzter Zustand: gestoppt)")
        await application.bot.send_message(
            chat_id=ALLOWED_CHAT_ID,
            text="ℹ️ Container gestartet, aber bot.py bleibt gestoppt."
        )


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
