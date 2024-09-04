from aiogram import types

start_kb = [
    [
        types.InlineKeyboardButton(text="Что могу?", callback_data='help_user'),
        types.InlineKeyboardButton(text="Введите тикер", callback_data='ticker_user')
    ]
]
start_kb = types.InlineKeyboardMarkup(inline_keyboard=start_kb)

main_kb = [
    [
        types.InlineKeyboardButton(text="Прогноз", callback_data='predict'),
        types.InlineKeyboardButton(text="График", callback_data='graph')
    ],
    [
        types.InlineKeyboardButton(text="Выбрать другой тикер", callback_data='ticker_user')
    ]
]
main_kb = types.InlineKeyboardMarkup(inline_keyboard=main_kb)

main_kb_predict = [
    [types.InlineKeyboardButton(text="График", callback_data='graph')],
    [types.InlineKeyboardButton(text="Выбрать другой тикер", callback_data='ticker_user')]
]
main_kb_predict = types.InlineKeyboardMarkup(inline_keyboard=main_kb_predict)

main_kb_graph = [
    [types.InlineKeyboardButton(text="Прогноз", callback_data='predict')],
    [types.InlineKeyboardButton(text="Выбрать другой тикер", callback_data='ticker_user')]
]
main_kb_graph = types.InlineKeyboardMarkup(inline_keyboard=main_kb_graph)
