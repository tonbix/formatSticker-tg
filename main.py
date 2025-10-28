from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, PhotoSize, Document from aiogram.enums import ParseMode, ChatType, ContentType
from cv2 import imread, imwrite, resize, IMREAD_UNCHANGED
from dotenv import load_dotenv
from asyncio import run
from os import getenv, remove
import subprocess
from enum import Enum, auto


MAX_STICKER_DIMENSION = 512
VIDEO_STICKER_BITRATE = 640
VIDEO_STICKER_FRAMERATE = 30

load_dotenv("data/.env")
BOT_TOKEN = getenv("BOT_TOKEN")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


class DocumentType(Enum):
    IMAGE = auto()
    VIDEO = auto()
    OTHER_FILE = auto()
    NO_DOCUMENT_ATTACHED = auto()
    UNEXPECTED_ERROR = auto()


SUPPORTED_IMAGE_EXTENSIONS = [ "png", "jpg", "jpeg", "jpe", "bmp", "dib", "jp2", "webp", "pbm", "pgm", "ppm", "pxm", "pnm", "sr", "ras", "tiff", "tif", "exr", "hdr", "pic", ]
SUPPORTED_VIDEO_EXTENSIONS = [ "mp4", "m4v", "mkv", "webm", "mov", "avi", "flv", "mpeg", "mpg", "ts", "3gp", "wmv", "asf", "gif", "apng", ]


async def identify_type_of_document(message: Message) -> DocumentType:
    try:
        # looking if document is attached to message
        if not message.document:
            # if not returning code 3 - no document attached to message
            return DocumentType.NO_DOCUMENT_ATTACHED

        # parsing file
        documentFileId = message.document.file_id
        document = await bot.get_file(documentFileId)
        documentFileExtension = document.file_path.split(".")[-1]

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


async def process_image(message: Message, isDocument: bool = False) -> None:
    """
    extracting image from message and processing it
    processing include:
    - download image to temporary file
    - resize using opencv
    - save back into another temporary file with png extension
    - send edited image to user
    - remove temporary files

    isDocument affecting way of reading dimensions of image
    """

    print(
        " - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - "
    )
    # notifying user that bot accepted his request
    statusMessageHeader = "processing ur image. Should take a few seconds"
    statusMessage = await message.reply(
        statusMessageHeader + "\n[0/3] downloading image..."
    )

    try:
        if isDocument:
            print("processing as document")
            # selecting document as a place where image stored
            if message.document:
                targetPhoto = message.document
            else:
                return
        else:
            # selecting photo with best quality (message.photo contains a lot of available sizes)
            if message.photo:
                targetPhoto = message.photo[-1]
            else:
                return

        # downloading and parsing image from telegram servers
        imageFileId = targetPhoto.file_id
        image = await bot.get_file(imageFileId)
        imageFileExtension = image.file_path.split(".")[-1]
        fileName = (
            f"./temp/photo{targetPhoto.file_unique_id}.{imageFileExtension}"
        )
        await bot.download(image, fileName)

        if isDocument:
            # document has no width-height attributes so using more complex way to obtain that
            imageDimensions = await read_image_dimensions_from_file(fileName)
        else:
            imageDimensions = (targetPhoto.width, targetPhoto.height)

        print("input image:", end="  ")
        print(fileName, imageDimensions)

        # resizing image with opencv
        await statusMessage.edit_text(
            statusMessageHeader + "\n[1/3] processing image..."
        )
        downloadedImage = imread(fileName, IMREAD_UNCHANGED)
        resizeRatio = MAX_STICKER_DIMENSION / max(imageDimensions)
        newDimensions = tuple(
            map(lambda x: round(x * resizeRatio), imageDimensions)
        )
        resizedImage = resize(downloadedImage, newDimensions)
        exportFileName = (
            f"./temp/resized_photo{targetPhoto.file_unique_id}.png"
        )
        imwrite(exportFileName, resizedImage)
        print("output image:", end=" ")
        print(exportFileName, newDimensions)

        # sending image back to user
        await statusMessage.edit_text(
            statusMessageHeader + "\n[2/3] sending file..."
        )
        imageToSend = FSInputFile(exportFileName)
        await message.reply_document(
            imageToSend,
            caption="<i>maybe u need this one from now @stickers</i>",
        )
        await statusMessage.edit_text(statusMessageHeader + "\n[3/3] done!")
    except Exception as e:
        await statusMessage.edit_text(
            statusMessageHeader + "\nsomething went wrong("
        )
        print(f'unexpected exception in process_image: "{e}"')
    finally:
        # cleaning created files in ./temp directory
        remove(fileName)
        remove(exportFileName)
        print(f'successfully removed: "{fileName}" and "{exportFileName}"\n')


async def process_video(message: Message, messageType: ContentType) -> None:
    """
    extracting video from a message and processing it
    processing works same as for photos (but using ffmpeg instead of opencv) and has an additional block of code for downloading because of many types of messages that contains video information
    output format is x.webm
    """

    print(
        " - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - "
    )
    # notifying user that bot accepted his request
    statusMessageHeader = "processing ur video. Wait a little"
    statusMessage = await message.reply(
        statusMessageHeader + "\n[0/3] downloading video..."
    )

    try:
        # selecting correct child of message
        match messageType:
            case ContentType.VIDEO:
                # downloading video
                print("downloading: video")
                video = message.video
            case ContentType.VIDEO_NOTE:
                # downloading video_note as video
                print("downloading: video note")
                video = message.video_note
            case ContentType.ANIMATION:
                # downloading animation as video
                print("downloading: animation")
                video = message.animation
            case _:
                print("unexpected type of message. Aborting")
                return

        # downloading and parsing video from telegram servers
        if (
            messageType == ContentType.VIDEO
            or messageType == ContentType.ANIMATION
        ):
            # VIDEO and ANIMATION stores 2 dimensions so write them down
            videoDimensions = (video.width, video.height)
        elif messageType == ContentType.VIDEO_NOTE:
            # VIDEO_NOTE don't store two dimensions under width and height so using length as both dimensions
            videoDimensions = (video.length,) * 2
        videoFileId = video.file_id
        videoDuration = video.duration
        videoFile = await bot.get_file(videoFileId)
        videoFileExtension = videoFile.file_path.split(".")[-1]
        fileName = f"./temp/video{video.file_unique_id}.{videoFileExtension}"
        await bot.download(videoFile, fileName)
        print("input video:", end="  ")
        print(fileName, videoDimensions, videoDuration)

        # resizing video with ffmpeg
        await statusMessage.edit_text(
            statusMessageHeader + "\n[1/3] processing video..."
        )
        resizeRatio = MAX_STICKER_DIMENSION / max(videoDimensions)
        newDimensions = tuple(
            map(lambda x: round(x * resizeRatio), videoDimensions)
        )
        exportFileName = f"./temp/resized_video{video.file_unique_id}.webm"
        command = [
            "ffmpeg",
            "-i",
            fileName,
            "-vf",
            "scale={}:{},setsar=1".format(*newDimensions),
            "-c:v",
            "libvpx-vp9",
            "-b:v",
            f"{VIDEO_STICKER_BITRATE}k",
            "-r",
            str(VIDEO_STICKER_FRAMERATE),
            "-t",
            "3",
            "-an",
            "-y",
            exportFileName,
        ]

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            print("FFMPEG Error:")
            print(result.stderr)
            return

        print("output video:", end=" ")
        print(exportFileName, newDimensions)

        # sending video back to user
        await statusMessage.edit_text(
            statusMessageHeader + "\n[2/3] sending file..."
        )
        videoToSend = FSInputFile(exportFileName)
        await message.reply_document(
            videoToSend,
            caption="<i>maybe u need this one from now @stickers</i>",
        )
        await statusMessage.edit_text(statusMessageHeader + "\n[3/3] done!")
    except Exception as e:
        await statusMessage.edit_text(
            statusMessageHeader + "\nsomething went wrong("
        )
        print(f'unexpected exception in process_video: "{e}"')
    finally:
        # cleaning created files in ./temp directory
        remove(fileName)
        remove(exportFileName)
        print(f'successfully removed: "{fileName}" and "{exportFileName}"\n')


async def process_document(message: Message, typeOfContent: DocumentType) -> None:
    """
    handling a documents (files) in two different modes. Image mode and video mode (same as for process_image and process_video but has another way to extract dimensions from image)
    """

    try:
        if typeOfContent == DocumentType.IMAGE:
            # image mode
            await process_image(message, isDocument=True)
        if typeOfContent == DocumentType.VIDEO:
            # video mode
            REPLY_TEXT = (
                "videos sended as files isn't processing now...\n"
                + "if u want me to finish it faster DM me. You can find my contacts in /help"
            )

            await message.reply(REPLY_TEXT)
        if typeOfContent == DocumentType.OTHER_FILE:
            # unexpected file extension
            REPLY_TEXT = (
                "uh... Idk this file extension...\n"
                + "i can't work with it :("
            )

            await message.reply(REPLY_TEXT)
        else:
            # other answers
            pass
    finally:
        pass


@dp.startup()
async def startup_handler() -> None:
    """
    handling startup event
    """

    botUser = await bot.get_me()
    print(
        f"       [ logged in as @{botUser.username} (id:{botUser.id}) ]       \n"
    )


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    handling start command
    """

    REPLY_TEXT = (
        " hewo. I'am telegram bot created for resizing ur images into telegram stickers format (rectangle with max dimension 512px in png)\n"
        + " my only commands is /help and /resize (shortcut /r) (i hope i have no reasons to explain)\n"
        + " also you can just send image in this chat and i'll resize it and convert to png automatically\n"
        + "<i> contact: https://tnbx.ru/tg (redirect)</i>"
    )

    await message.reply(REPLY_TEXT)


@dp.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    """
    handling help command
    """

    REPLY_TEXT = (
        "commands:\n"
        + " - /start - start (there's nothing to add)\n"
        + " - /help - this message\n"
        + " - /resize /r - resize attached/replied image to satisfy @stickers requirements (also can be triggered by sending image to a bot)\n"
        + "\ncontacts:\n"
        + " - https://tnbx.ru/tg (redirect)"
    )

    await message.reply(REPLY_TEXT)


# routing photos
@dp.message(F.photo)
async def message_photo_handler(message: Message) -> None:
    """
    handling a message that contains an image
    """

    if message.chat.type == ChatType.PRIVATE or (
        message.caption and message.caption.startswith("/r")
    ):
        print("there's a message with an image! (from event attached message)")
        await process_image(message)


@dp.message(Command("resize", "r"), F.reply_to_message.photo)
async def reply_message_photo_handler(message: Message) -> None:
    """
    handling a message replying to a message that contains an image
    """

    replyMessage = message.reply_to_message

    print("there's a message with an image! (from a message reply)")
    await process_image(replyMessage)


# routing videos
@dp.message(F.video | F.animation | F.video_note)
async def message_video_handler(message: Message) -> None:
    """
    handling a message that contains a video (video, animation, video_note)
    """

    if message.chat.type == ChatType.PRIVATE or (
        message.caption and message.caption.startswith("/r")
    ):
        messageType = message.content_type

        print("there's a message with a video! (from event attached message)")
        await process_video(message, messageType)


@dp.message(
    Command("resize", "r"),
    F.reply_to_message.video
    | F.reply_to_message.animation
    | F.reply_to_message.video_note,
)
async def reply_message_video_handler(message: Message) -> None:
    """
    handling a message replying to a message that contains a video (video, animation, video_note)
    """

    replyMessage = message.reply_to_message
    messageType = replyMessage.content_type

    print("there's a message with a video! (from a message reply)")
    await process_video(replyMessage, messageType)


# routing documents
@dp.message(F.document)
async def message_document_handler(message: Message) -> None:
    """
    handling a message that contains a document
    identifying type of content in document and routing to processor if possible
    """

    fileType = await identify_type_of_document(message)

    print("there's a message with a document! (from event attached message)")
    await process_document(message, fileType)


@dp.message(Command("resize", "r"), F.reply_to_message.document)
async def reply_message_document_handler(message: Message) -> None:
    """
    handling a message replying to a message that contains a document
    identifying type of content in document and routing to processor if possible
    """

    replyMessage = message.reply_to_message

    fileType = await identify_type_of_document(replyMessage)

    print("there's a message with a document! (from a message reply)")
    await process_document(replyMessage, fileType)


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    run(main())

