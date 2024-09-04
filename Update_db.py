import sqlite3
import pandas as pd
from datetime import date, datetime, time, timedelta
import os.path

from moexalgo import Market, Ticker, session


def console_title(title):
    """Функция отображения названия окна консоли"""
    if os.name == "nt":
        # Для Windows используем команду 'title'
        os.system("title " + title)
    else:
        # Для других операционных систем используем команду 'echo'
        os.system("echo -n -e '\033]0;" + title + "\a' > /dev/tty")



def log_plus(text):
    """Функция для записи в логфайл и вывода в консоль"""
    filelog = os.path.join('logfile.log') #log file

    with open(filelog, "a", encoding="utf-8") as logfile:
        # Получаем текущее время
        current_time = datetime.now().replace(microsecond=0)
        # Форматируем строку для записи в лог
        log_entry = f"{current_time}: {text}\n"
        # # Записываем строку в файл
        logfile.write(log_entry)
        print(log_entry, end="")

def stocks_in_db():
    Data_start = datetime.strptime("2022-01-01 00:00:00", "%Y-%m-%d %H:%M:%S")
    stock = Market('stocks').tickers() #получаем данные по ВСЕМ акциям
    stock_df = pd.DataFrame(stock) #помещаем в датафрейм

    with sqlite3.connect("db.db") as conn:
        cur = conn.cursor()
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS _ALL_stocks (
            ticker TEXT PRIMARY KEY,
            shortname TEXT,
            lotsize REAL,
            decimals INTEGER,
            minstep REAL,
            issuesize REAL,
            isin TEXT,
            regnumber TEXT,
            listlevel INTEGER            
            )
            """
        )
        stock_df.to_sql("_ALL_stocks", conn, if_exists="append", index=False)

        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS _ALL_stocks_with_first_candles (
            ticker TEXT PRIMARY KEY,
            first_date DATE,
            listlevel INTEGER,
            shortname TEXT)
            """
        )
        first_candles_df = stock_df[['ticker', 'listlevel', 'shortname']]

        for secid in stock_df["ticker"]:
            try:
                log_plus(f"Ищу первую свечу по акции {secid}")
                first_candle = pd.DataFrame(Ticker(secid).candles(date=Data_start, till_date=datetime.now(), period=1)).loc[0, "begin"]
                first_candles_df.loc[first_candles_df["ticker"] == secid, "first_date"] = first_candle
            except Exception as e:
                log_plus(f"Ошибка получения даты первой свечи по акции {secid}")
                first_candles_df.loc[first_candles_df["ticker"] == secid, "first_date"] = pd.NaT

        first_candles_df.to_sql("_ALL_stocks_with_first_candles", conn, if_exists="append", index=False)
        conn.commit()

def candles_with_last_date(limit, secid, last_date, period, conn, timeframe):
    till_date = datetime.now().replace(microsecond=0)
    count_candle = 0
    real_limit = limit
    while limit == real_limit:
        try:
            candle_df = Ticker(secid).candles(date=last_date, till_date=till_date, period=period)
        except Exception as e:
            log_plus(
                f"Ошибка от Мосбиржи при получении данных для акции {secid} с таймфреймом {period}. "
                f"\nПродолжаем сбор данных.")
            real_limit = 0
            continue

        candle_df = pd.DataFrame(candle_df, columns=[
            "begin",
            "end",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "value",
        ])
        real_limit = candle_df.shape[0]
        if not candle_df.empty:
            count_candle = (candle_df.shape[0] + count_candle)
            candle_df["begin"] = candle_df["begin"] + pd.Timedelta(hours=0, minutes=0, seconds=0)
            candle_df["begin"] = candle_df["begin"].dt.strftime("%Y-%m-%d %H:%M:%S")
            last_date = pd.to_datetime(candle_df.iloc[-1]["begin"])
            last_date = last_date + timeframe
        if count_candle > 1:
            candle_df.to_sql(f"{secid}_{period}", conn, if_exists="append", index=False)
        log_plus(f"Получили данные до {last_date}. Продолжаем скачивать")
        if count_candle > 1:
            log_plus(f"Скачано {count_candle} свечей с таймфреймом {period} для акции '{secid}'")
    return

def candles_without_last_date(limit, secid, first_date, period, conn, timeframe):
    till_date = datetime.now().replace(microsecond=0)
    count_candle = 0
    real_limit = limit
    while limit == real_limit:
        try:
            candle_df = Ticker(secid).candles(date=first_date, till_date=till_date, period=period)
        except Exception as e:
            log_plus(f"Ошибка от Мосбиржи при получении данных для акции {secid} с таймфреймом {period}. "
                f"\nПродолжаем сбор данных.")
            real_limit = 0
            continue

        candle_df = pd.DataFrame(candle_df, columns=[
            "begin",
            "end",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "value",
        ])
        real_limit = candle_df.shape[0]
        if not candle_df.empty:
            count_candle = (candle_df.shape[0] + count_candle)
            candle_df["begin"] = candle_df["begin"] + pd.Timedelta(hours=0, minutes=0,seconds=0)
            candle_df["begin"] = candle_df["begin"].dt.strftime("%Y-%m-%d %H:%M:%S")
            first_date = pd.to_datetime(candle_df.iloc[-1]["begin"])
            first_date = first_date + timeframe
        if count_candle > 1:
            candle_df.to_sql(f"{secid}_{period}", conn, if_exists="append", index=False)
    if count_candle > 1:
        log_plus(f"Скачано {count_candle} свечей с таймфреймом {period} для акции '{secid}'")


def table_exist(table_name, conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    result = cur.fetchone()
    return result is not None

def download_candels():
    limit = 50000
    periods = ["D", "1h", "10m", "1m"]
    timeframes = [
        timedelta(hours=24),
        timedelta(hours=1),
        timedelta(minutes=10),
        timedelta(minutes=1),
    ]

    with sqlite3.connect("db.db") as conn:
        cur = conn.cursor()

        cur.execute("SELECT ticker, first_date FROM _ALL_stocks_with_first_candles")
        tuple_list = cur.fetchall()

        for period, timeframe in zip(periods, timeframes):

            for secid, first_date in tuple_list:

                log_plus(f"Занимаемся акцией '{secid}'")

                if first_date is not None:
                    first_date = datetime.strptime(first_date, "%Y-%m-%d %H:%M:%S")
                    table_name = f"{secid}_{period}"
                    if table_exist(table_name, conn):
                        cur.execute(f"SELECT MAX(begin) FROM {secid}_{period}")
                        last_date = cur.fetchone()[0]
                        last_date = datetime.strptime(last_date, "%Y-%m-%d %H:%M:%S")

                        if last_date is not None and last_date <= datetime.now():
                            log_plus(f"Качаем свечи для акции '{secid}' с таймфреймом {period} начиная с {last_date}")
                            candles_with_last_date(limit, secid, last_date, period, conn, timeframe)
                            conn.commit()

                    else:
                        log_plus(f"Качаем свечи для акции '{secid}' с таймфреймом {period} начиная с {first_date}")
                        candles_without_last_date(limit, secid, first_date, period, conn, timeframe)
                        conn.commit()



if __name__ == "__main__":

    # username = ""
    # password = ""
    # session.authorize(username, password)
    # запоминаем время для записи продолжительности работы программы
    filelog = os.path.join('logfile.log') #log file

    with open(filelog, "a", encoding="utf-8") as logfile:
        log_plus("Обновляем базу данных.")
        # берем заведомо старую дату, чтобы найти самые ранние свечи (у нас с 22 года, но можно раньше)
        #stocks_in_db()

    download_candels()