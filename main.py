import asyncio
import logging
import schedule
import time

from aiogram.client.bot import DefaultBotProperties
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN

from handlers import register_user_messages
from Update_db import stocks_in_db, download_candels

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logger.error("Starting bot")

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher()

    register_user_messages(dp)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
    #Обновление БД каждые сутки
    # schedule.every(24).hours.do(download_candels)
    #
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)