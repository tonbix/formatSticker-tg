from telethon import TelegramClient, events
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
from cv2 import imread, imwrite, resize, IMREAD_UNCHANGED
from dotenv import load_dotenv
import asyncio
from os import getenv, remove
import subprocess
from enum import Enum, auto

MAX_STICKER_DIMENSION = 512
VIDEO_STICKER_BITRATE = 640
VIDEO_STICKER_FRAMERATE = 30

# Load environment variables
load_dotenv("data/.env")
BOT_TOKEN = getenv("BOT_TOKEN")
API_ID = int(getenv("API_ID"))
API_HASH = getenv("API_HASH")

# MTProxy config
MTPROXY_HOST = getenv("MTPROXY_HOST")
MTPROXY_PORT = int(getenv("MTPROXY_PORT"))
MTPROXY_SECRET = getenv("MTPROXY_SECRET")

proxy_creds = (MTPROXY_HOST, MTPROXY_PORT, MTPROXY_SECRET)

# Initialize Client
bot = TelegramClient(
    'my_sticker_bot',
    API_ID,
    API_HASH,
    connection=ConnectionTcpMTProxyRandomizedIntermediate,
    proxy=proxy_creds
)
bot.parse_mode = 'html'


class DocumentType(Enum):
    IMAGE = auto()
    VIDEO = auto()
    OTHER_FILE = auto()
    NO_DOCUMENT_ATTACHED = auto()
    UNEXPECTED_ERROR = auto()


SUPPORTED_IMAGE_EXTENSIONS = [ "png", "jpg", "jpeg", "jpe", "bmp", "dib", "jp2", "webp", "pbm", "pgm", "ppm", "pxm", "pnm", "sr", "ras", "tiff", "tif", "exr", "hdr", "pic", ]
SUPPORTED_VIDEO_EXTENSIONS = [ "mp4", "m4v", "mkv", "webm", "mov", "avi", "flv", "mpeg", "mpg", "ts", "3gp", "wmv", "asf", "gif", "apng", ]


async def identify_type_of_document(message) -> DocumentType:
    try:
        # looking if document is attached to message
        if not message.document:
            return DocumentType.NO_DOCUMENT_ATTACHED

        documentFileExtension = message.file.ext.lstrip('.').lower() if message.file.ext else ""

        # fetching type of document with supported types
        if documentFileExtension in SUPPORTED_IMAGE_EXTENSIONS:
            # contains image
            return DocumentType.IMAGE
        elif documentFileExtension in SUPPORTED_VIDEO_EXTENSIONS:
            # contains video
            return DocumentType.VIDEO
        else:
            # contains file with unexpected extension
            return DocumentType.OTHER_FILE
    except Exception as e:
        print(f"unexpected error: {e}")
        return DocumentType.UNEXPECTED_ERROR


async def read_image_dimensions_from_file(imagePath: str) -> tuple[int, int]:
    """
    extracting dimensions from image file
    returns tuple with width,height
    """
    image = imread(imagePath)
    height, width = image.shape[:2]
    return (width, height)


async def process_image(message, isDocument: bool = False) -> None:
    """
    extracting image from message and processing it
    """
    print(" - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - ")
    statusMessageHeader = "processing ur image. Should take a few seconds"
    statusMessage = await message.reply(statusMessageHeader + "\n[0/3] downloading image...")

    fileName = ""
    exportFileName = ""

    try:
        ext = message.file.ext or ".jpg"
        fileName = f"./temp/photo_{message.id}{ext}"
        
        await message.download_media(file=fileName)

        if isDocument:
            imageDimensions = await read_image_dimensions_from_file(fileName)
        else:
            imageDimensions = (message.file.width, message.file.height)

        print("input image:", end="  ")
        print(fileName, imageDimensions)

        # resizing image with opencv
        await statusMessage.edit(statusMessageHeader + "\n[1/3] processing image...")
        downloadedImage = imread(fileName, IMREAD_UNCHANGED)
        resizeRatio = MAX_STICKER_DIMENSION / max(imageDimensions)
        newDimensions = tuple(map(lambda x: round(x * resizeRatio), imageDimensions))
        resizedImage = resize(downloadedImage, newDimensions)
        
        exportFileName = f"./temp/resized_photo_{message.id}.png"
        imwrite(exportFileName, resizedImage)
        
        print("output image:", end=" ")
        print(exportFileName, newDimensions)

        # sending image back to user
        await statusMessage.edit(statusMessageHeader + "\n[2/3] sending file...")
        await message.reply(
            file=exportFileName,
            force_document=True,
            caption="<i>maybe u need this one from now @stickers</i>"
        )
        await statusMessage.edit(statusMessageHeader + "\n[3/3] done!")

    except Exception as e:
        await statusMessage.edit(statusMessageHeader + "\nsomething went wrong(")
        print(f'unexpected exception in process_image: "{e}"')
    finally:
        # cleaning created files in ./temp directory
        if fileName:
            try: remove(fileName)
            except: pass
        if exportFileName:
            try: remove(exportFileName)
            except: pass
        print(f'cleanup finished\n')


async def process_video(message) -> None:
    """
    extracting video from a message and processing it
    """
    print(" - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - ")
    statusMessageHeader = "processing ur video. Wait a little"
    statusMessage = await message.reply(statusMessageHeader + "\n[0/3] downloading video...")

    fileName = ""
    exportFileName = ""

    try:
        width = message.file.width or 512
        height = message.file.height or 512
        videoDimensions = (width, height)
        videoDuration = message.file.duration

        ext = message.file.ext or ".mp4"
        fileName = f"./temp/video_{message.id}{ext}"
        await message.download_media(file=fileName)
        
        print("input video:", end="  ")
        print(fileName, videoDimensions, videoDuration)

        # resizing video with ffmpeg
        await statusMessage.edit(statusMessageHeader + "\n[1/3] processing video...")
        resizeRatio = MAX_STICKER_DIMENSION / max(videoDimensions)
        newDimensions = tuple(map(lambda x: round(x * resizeRatio), videoDimensions))
        
        exportFileName = f"./temp/resized_video_{message.id}.webm"
        command = [
            "ffmpeg", "-i", fileName,
            "-vf", "scale={}:{},setsar=1".format(*newDimensions),
            "-c:v", "libvpx-vp9",
            "-b:v", f"{VIDEO_STICKER_BITRATE}k",
            "-r", str(VIDEO_STICKER_FRAMERATE),
            "-t", "3", "-an", "-y", exportFileName,
        ]

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            print("FFMPEG Error:")
            print(result.stderr)
            return

        print("output video:", end=" ")
        print(exportFileName, newDimensions)

        # sending video back to user
        await statusMessage.edit(statusMessageHeader + "\n[2/3] sending file...")
        await message.reply(
            file=exportFileName,
            force_document=True,
            caption="<i>maybe u need this one from now @stickers</i>"
        )
        await statusMessage.edit(statusMessageHeader + "\n[3/3] done!")

    except Exception as e:
        await statusMessage.edit(statusMessageHeader + "\nsomething went wrong(")
        print(f'unexpected exception in process_video: "{e}"')
    finally:
        if fileName:
            try: remove(fileName)
            except: pass
        if exportFileName:
            try: remove(exportFileName)
            except: pass
        print(f'cleanup finished\n')


async def process_document(message, typeOfContent: DocumentType) -> None:
    try:
        if typeOfContent == DocumentType.IMAGE:
            await process_image(message, isDocument=True)
        elif typeOfContent == DocumentType.VIDEO:
            REPLY_TEXT = (
                "videos sended as files isn't processing now...\n"
                + "if u want me to finish it faster DM me. You can find my contacts in /help"
            )
            await message.reply(REPLY_TEXT)
        elif typeOfContent == DocumentType.OTHER_FILE:
            REPLY_TEXT = (
                "uh... Idk this file extension...\n"
                + "i can't work with it :("
            )
            await message.reply(REPLY_TEXT)
    except Exception as e:
        print(e)


# --- ROUTING / HANDLERS ---

@bot.on(events.NewMessage(pattern='/start'))
async def command_start_handler(event) -> None:
    REPLY_TEXT = (
        " hewo. I'am telegram bot created for resizing ur images into telegram stickers format (rectangle with max dimension 512px in png)\n"
        + " my only commands is /help and /resize (shortcut /r) (i hope i have no reasons to explain)\n"
        + " also you can just send image in this chat and i'll resize it and convert to png automatically\n"
        + "<i> contact: https://tnbx.ru/tg (redirect)</i>"
    )
    await event.reply(REPLY_TEXT)


@bot.on(events.NewMessage(pattern='/help'))
async def command_help_handler(event) -> None:
    REPLY_TEXT = (
        "commands:\n"
        + " - /start - start (there's nothing to add)\n"
        + " - /help - this message\n"
        + " - /resize /r - resize attached/replied image to satisfy @stickers requirements (also can be triggered by sending image to a bot)\n"
        + "\ncontacts:\n"
        + " - https://tnbx.ru/tg (redirect)"
    )
    await event.reply(REPLY_TEXT)


# Routing photos
@bot.on(events.NewMessage(func=lambda e: e.photo and not e.is_reply))
async def message_photo_handler(event) -> None:
    message = event.message
    if event.is_private or (message.text and message.text.startswith("/r")):
        print("there's a message with an image! (from event attached message)")
        await process_image(message)

@bot.on(events.NewMessage(pattern=r'^/(resize|r)', func=lambda e: e.is_reply))
async def reply_message_photo_handler(event) -> None:
    replyMessage = await event.get_reply_message()
    if replyMessage and replyMessage.photo:
        print("there's a message with an image! (from a message reply)")
        await process_image(replyMessage)


# Routing videos
@bot.on(events.NewMessage(func=lambda e: (e.video or e.gif or e.video_note) and not e.is_reply))
async def message_video_handler(event) -> None:
    message = event.message
    if event.is_private or (message.text and message.text.startswith("/r")):
        print("there's a message with a video! (from event attached message)")
        await process_video(message)

@bot.on(events.NewMessage(pattern=r'^/(resize|r)', func=lambda e: e.is_reply))
async def reply_message_video_handler(event) -> None:
    replyMessage = await event.get_reply_message()
    if replyMessage and (replyMessage.video or replyMessage.gif or replyMessage.video_note):
        print("there's a message with a video! (from a message reply)")
        await process_video(replyMessage)


# Routing documents
@bot.on(events.NewMessage(func=lambda e: e.document and not (e.photo or e.video or e.gif or e.video_note) and not e.is_reply))
async def message_document_handler(event) -> None:
    message = event.message
    if event.is_private or (message.text and message.text.startswith("/r")):
        fileType = await identify_type_of_document(message)
        print("there's a message with a document! (from event attached message)")
        await process_document(message, fileType)

@bot.on(events.NewMessage(pattern=r'^/(resize|r)', func=lambda e: e.is_reply))
async def reply_message_document_handler(event) -> None:
    replyMessage = await event.get_reply_message()
    if replyMessage and replyMessage.document and not (replyMessage.photo or replyMessage.video or replyMessage.gif or replyMessage.video_note):
        fileType = await identify_type_of_document(replyMessage)
        print("there's a message with a document! (from a message reply)")
        await process_document(replyMessage, fileType)


async def main() -> None:
    await bot.start(bot_token=BOT_TOKEN)
    botUser = await bot.get_me()
    print(f"       [ logged in as @{botUser.username} (id:{botUser.id}) ]       \n")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    bot.loop.run_until_complete(main())

