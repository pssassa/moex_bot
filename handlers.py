import os
import asyncio

from aiogram import types, html, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from state import Ticker
from kb import start_kb, main_kb, main_kb_graph, main_kb_predict
from predict_function import prediction, graphic, info_tick, search_in_db, information_tick

user_ticker = None
async def start_command(message: types.Message, state: FSMContext):
    await message.answer(f'<b>{html.quote(message.from_user.full_name)},</b> привет!\n\n'
                         f'Я бот-помощник! Я умею отображать графики акций и строить прогноз изменения цены. '
                         f'Я лишь даю советы новичкам в инвестициях, а не стопроцентный прогноз.\n'
                         f'\n<b>ВСЮ ОТВЕТСТВЕННОСТЬ ВЫ БЕРЕТЕ НА СЕБЯ!</b>\n\n'
                         f'Для того, чтобы вызвать справку введите "/help" или нажмите на кнопку "Что могу?". \n'
                         f'Для того, чтобы вызвать список доступных тикеров, введите "/tickers".',
                         reply_markup=start_kb)
    await state.clear()


async def help_command(message: types.Message, state: FSMContext):
    await message.answer(f'С помощью этого бота Вы можете узнать график изменения цены на акцию и ее прогноз.\n'
                         f'Для этого нужно нажать на кнопку "Введите тикер", ввести тикер и выбрать необходимую кнопку!\n'
                         f'Для того, чтобы вызвать список доступных тикеров введите "/tickers".\n',
                         reply_markup=start_kb)
    await state.clear()


async def ticker_info(message: types.Message, state: FSMContext):
    inform = info_tick()
    header = "<b>Ticker  ShortName</b>\n\n"
    # Преобразуем DataFrame в список строк с нужным форматированием
    inform_list = [f"{row['Ticker']} - {row['ShortName']}" for index, row in inform.iterrows()]
    # Разделяем список на две части
    mid_point = len(inform_list) // 2
    part1 = inform_list[:mid_point]
    part2 = inform_list[mid_point:]
    # Объединяем строки в одну длинную строку с разделением на новые строки
    inform_str1 = header + '\n'.join(part1)
    inform_str2 = header + '\n'.join(part2)
    # Отправляем каждую часть отдельно
    await message.answer(inform_str1, reply_markup=start_kb)
    await message.answer(inform_str2, reply_markup=start_kb)
    await state.clear()


async def get_help(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer(f'С помощью этого бота Вы можете узнать график изменения цены на акцию и ее прогноз.\n'
                         f'Для этого нужно нажать на кнопку "Введите тикер", ввести тикер и выбрать необходимую кнопку!\n'
                         f'Для того чтобы вызвать список доступных тикеров введите "/tickers".\n',
                         reply_markup=start_kb)
    await c.answer()
    await state.clear()

async def get_ticker(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer(f"Введите тикер интересующей акции")
    await c.answer()
    await state.set_state(Ticker.name)

async def name_ticker(message: types.Message, state: FSMContext):
    global user_ticker
    user_ticker = message.text.upper()
    if search_in_db(user_ticker) == True:
        try:
            tickers = information_tick()
            match_ticker = tickers[tickers['Ticker'] == user_ticker]
            ticker = match_ticker.iloc[0]['Ticker']
            short_name = match_ticker.iloc[0]['ShortName']
            inf_tick = match_ticker.iloc[0]['Information']
            await message.answer(f"Вы ввели - {ticker}, это компания - {short_name}.\n\n{inf_tick}", reply_markup=main_kb)
            await state.clear()
        except:
            pass
    else:
        await message.answer(f"Вы ввели неизвестный тикер, попробуйте еще раз!")

async def generate_predict(user_ticker, chat_id, message_id, bot):
    try:
        file_predict = prediction(user_ticker)
        photo = FSInputFile(file_predict)
        await bot.send_photo(chat_id, photo=photo, reply_markup=main_kb_predict, reply_to_message_id=message_id)
    except Exception as e:
        await bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")
    finally:
        # Удаление файла, если он существует
        if os.path.exists(file_predict):
            os.remove(file_predict)


async def get_predict(c: types.CallbackQuery, state: FSMContext):
    global user_ticker
    await c.message.answer("Пожалуйста, подождите, идет генерация прогноза \n Процесс может занять продолжительное время!")
    await c.answer()
    await state.clear()
    asyncio.create_task(generate_predict(user_ticker, c.message.chat.id, c.message.message_id, c.bot))



async def get_graph(c: types.CallbackQuery, state: FSMContext):
    global user_ticker
    await state.clear()
    try:
        await c.message.answer("Пожалуйста, подождите, идет генерация графика")
        # Генерация графика
        file_graphic = graphic(user_ticker)
        # Отправка графика пользователю
        photo = FSInputFile(file_graphic)
        await c.message.answer_photo(photo=photo, reply_markup=main_kb_graph)

        # Отправка ответа на callback запрос
        await c.answer()
    except Exception as e:
        # Обработка возможных исключений и отправка сообщения об ошибке
        await c.message.answer(f"Произошла ошибка: {str(e)}")
    finally:
        # Удаление файла, если он существует
        if os.path.exists(file_graphic):
            os.remove(file_graphic)

def register_user_messages(dp: Dispatcher):
    dp.message.register(start_command, CommandStart())
    dp.message.register(help_command, Command('help'))
    dp.message.register(ticker_info, Command('tickers'))
    dp.callback_query.register(get_help, F.data == 'help_user')
    dp.callback_query.register(get_ticker, F.data == 'ticker_user')
    dp.message.register(name_ticker, Ticker.name)
    dp.callback_query.register(get_predict, F.data == 'predict')
    dp.callback_query.register(get_graph, F.data == 'graph')

