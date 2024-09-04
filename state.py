from aiogram.fsm.state import StatesGroup, State

class Ticker(StatesGroup):
    name = State()