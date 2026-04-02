import os
import logging
import tempfile
import httpx
from dotenv import load_dotenv
from telethon import TelegramClient, events

# Cargar variables de entorno
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")  # Tu número de teléfono con prefijo, ej: +34612345678
SOURCE_CHAT_ID = int(os.getenv("SOURCE_CHAT_ID"))
DEST_CHAT_ID = int(os.getenv("DEST_CHAT_ID"))

# Green API (WhatsApp)
GREEN_API_INSTANCE = os.getenv("GREEN_API_INSTANCE", "")
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN", "")
WHATSAPP_GROUP_ID = os.getenv("WHATSAPP_GROUP_ID", "")  # ej: 120363012345678901@g.us
WHATSAPP_ENABLED = all([GREEN_API_INSTANCE, GREEN_API_TOKEN, WHATSAPP_GROUP_ID])

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# El cliente usará tu cuenta personal (se guarda la sesión en "mi_cuenta.session")
client = TelegramClient("mi_cuenta", API_ID, API_HASH)


async def send_text_to_whatsapp(text: str):
    """Envía un mensaje de texto al grupo de WhatsApp vía Green API."""
    url = f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE}/sendMessage/{GREEN_API_TOKEN}"
    payload = {
        "chatId": WHATSAPP_GROUP_ID,
        "message": text,
    }
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(url, json=payload, timeout=15)
            resp.raise_for_status()
        logger.info("Texto enviado a WhatsApp")
    except Exception as e:
        logger.error("Error al enviar texto a WhatsApp: %s", e)


async def send_file_to_whatsapp(file_path: str, filename: str, caption: str = ""):
    """Envía un archivo (imagen, vídeo, documento…) al grupo de WhatsApp vía Green API."""
    url = f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE}/sendFileByUpload/{GREEN_API_TOKEN}"
    try:
        with open(file_path, "rb") as f:
            data = {
                "chatId": WHATSAPP_GROUP_ID,
                "caption": caption,
            }
            files = {
                "file": (filename, f),
            }
            async with httpx.AsyncClient() as http:
                resp = await http.post(url, data=data, files=files, timeout=30)
                resp.raise_for_status()
        logger.info("Archivo enviado a WhatsApp: %s", filename)
    except Exception as e:
        logger.error("Error al enviar archivo a WhatsApp: %s", e)


@client.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def forward_handler(event):
    """Reenvía cada mensaje nuevo del grupo origen al grupo destino (Telegram + WhatsApp)."""
    # --- Reenviar a Telegram ---
    try:
        await event.message.forward_to(DEST_CHAT_ID)
        logger.info("Mensaje reenviado a Telegram (id=%s)", event.message.id)
    except Exception as e:
        logger.error("Error al reenviar a Telegram: %s", e)

    # --- Reenviar a WhatsApp ---
    if WHATSAPP_ENABLED:
        sender = await event.get_sender()
        sender_name = getattr(sender, "first_name", "") or getattr(
            sender, "title", "Desconocido"
        )
        caption_prefix = f"📩 *{sender_name}*"
        text = event.message.text or event.message.message or ""

        if event.message.media:
            # Descargar el archivo a un temporal y enviarlo
            tmp_dir = tempfile.mkdtemp()
            try:
                downloaded = await event.message.download_media(file=tmp_dir)
                if downloaded:
                    filename = os.path.basename(downloaded)
                    caption = f"{caption_prefix}:\n{text}" if text else caption_prefix
                    await send_file_to_whatsapp(downloaded, filename, caption)
                else:
                    # No se pudo descargar, enviar solo texto
                    wa_text = f"{caption_prefix}:\n{text or '[Media no descargable]'}"
                    await send_text_to_whatsapp(wa_text)
            finally:
                # Limpiar archivos temporales
                import shutil

                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            wa_text = f"{caption_prefix}:\n{text}"
            await send_text_to_whatsapp(wa_text)


async def main():
    await client.start(phone=PHONE)
    me = await client.get_me()
    logger.info("Sesión iniciada como %s (@%s)", me.first_name, me.username)
    logger.info("Reenviando mensajes de %s → Telegram %s", SOURCE_CHAT_ID, DEST_CHAT_ID)
    if WHATSAPP_ENABLED:
        logger.info("WhatsApp activado → grupo %s", WHATSAPP_GROUP_ID)
    else:
        logger.info("WhatsApp desactivado (variables GREEN_API_* no configuradas)")
    await client.run_until_disconnected()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
