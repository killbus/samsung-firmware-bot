""" SamFirm Bot mirror module"""
import re
from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE

from telethon import events, Button

from samfirm_bot import TG_LOGGER, TG_BOT_ADMINS, TG_CHANNEL
from samfirm_bot.samfirm_bot import BOT, SAM_FIRM, STORAGE


@BOT.on(events.NewMessage(from_users=TG_BOT_ADMINS,
                          pattern=r'/samup(?:@\S+)?(?: )(.*)(?: )([a-zA-Z0-9]{3})(?: )?(.*)?'))
async def mirror(event):
    """ Mirror Samsung firmware """
    try:
        version = event.pattern_match.group(3).upper()
    except IndexError:
        version = None
    model = event.pattern_match.group(1).upper()
    region = event.pattern_match.group(2).upper()
    bot_reply = await event.reply("__Preparing...__")
    command = SAM_FIRM.download_update(model, region, version)
    if not await STORAGE.has_space():
        await STORAGE.cleanup()
    process = await create_subprocess_shell(command, stdin=PIPE, stdout=PIPE)
    path = None
    while True:
        output = await process.stdout.readline()
        if output:
            line = output.decode("utf-8").strip()
            if "Could not" in line:
                await bot_reply.edit("**Not Found!**")
                return
            if "Checking" in line:
                await bot_reply.edit("__Checking...__")
            if "Version:" in line:
                version = re.search(r"(?:Version: )(.*)", line).group(1).split('/')[0]
                path = f"{model}/{region}/{version}"
                if await STORAGE.check(path):
                    await event.reply(f"**This firmware ({version}) is already mirrored!**", buttons=[
                        Button.url("Check here", await STORAGE.get_url(f"{model}/{region}/{version}"))])
                    process.kill()
                    return
                else:
                    await bot_reply.edit(f"**Firmware {version} found, starting download!**")
            if "Downloading" in line:
                await bot_reply.edit("__Downloading...__")
            if "Decrypting" in line:
                await bot_reply.edit("__Decrypting...__")
            if "Finished" in line:
                await bot_reply.edit("__Download Finished!...__")
        else:
            break
    await process.wait()
    download = SAM_FIRM.get_downloaded(model, region)
    TG_LOGGER.info(f"Mirroring {download}")
    if download:
        download_folder = '/'.join(download.split('/')[:-1]) + '/'
        await bot_reply.edit(f"**Downloaded {download} Successfully!**")
        SAM_FIRM.extract_files(download)
        await bot_reply.edit(f"**Extracted files, upload is going to start!**")
        uploaded = await STORAGE.move(download_folder, path)
        await bot_reply.edit(f"**Uploaded Successfully!**")
        buttons = [Button.url(version, uploaded)]
        await event.reply(f"**Download Here**", buttons=buttons, link_preview=False)
        message = f"**New file uploaded!**\n\n" \
                  f"**Device**: {SAM_FIRM.get_device_name(model)}\n" \
                  f"**Model:** {model}\n" \
                  f"**Region:** {region}\n"
        await BOT.send_message(TG_CHANNEL, message, buttons=buttons, link_preview=False)
        TG_LOGGER.info(f"Mirrored: {uploaded}")
