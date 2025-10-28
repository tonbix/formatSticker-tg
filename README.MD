# formatSticker-tg

a telegram bot created for converting ur images into telegram stickers format
for example u providing 44x44 png to bot. Bot will convert it into 512x512 webm and send back as sticker which you can upload in @stickers

what can do:
- any image format (compressed uncompressed) to static sticker (webp)
- any video format (compressed uncompressed video-note gif etc) to video sticker (webm)

installation:
clone repo, create temp folder, rename .env.copy to .env, put ur token in .env, run

```bash
git clone https://github.com/tonbix/formatSticker-tg.git
cd formatSticker-tg
mkdir temp
mv data/.env.copy data/.env
```

put token in .env file

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

