import sqlite3
import pandas as pd
import plotly.graph_objs as go

from pmdarima.arima import auto_arima
from statsmodels.tsa.statespace.sarimax import SARIMAX

def graphic(user_ticker):
    #Загрузка данных из БД в датафрейм
    with sqlite3.connect("db.db") as conn:
        cur = conn.cursor()
        query = f"SELECT end, close FROM {user_ticker}_D"
        cur.execute(query)
        tuple_list = cur.fetchall()
        df = pd.DataFrame(tuple_list, columns=['Date', 'Price'])
        split_index = len(df) // 2
        half_df = df.iloc[split_index:]
        half_df.set_index('Date', inplace=True)

        fig = go.Figure()
        #Построение графика
        fig.add_trace(go.Scatter(
            x=half_df.index,
            y=half_df['Price'],
            mode='lines',
            line=dict(color='orange')
        ))

        fig.update_layout(
            title=f"Price change schedule {user_ticker} from {half_df.iloc[0].name} to {half_df.iloc[-1].name}",
            xaxis_title="Date",
            yaxis_title="Price",
            legend_title="Legend",
            width=900,
            height=600
        )
        #Сохранение графика как файла
        file_path = f"{user_ticker}_graphic.png"
        fig.write_image(file_path)

        return file_path

def info_tick(): #Получение списка тикеров и шортнейма
    with sqlite3.connect("db.db") as conn:
        cur = conn.cursor()
        query = "SELECT ticker, shortname FROM _ALL_stocks"
        cur.execute(query)
        tuple_list = cur.fetchall()
        df = pd.DataFrame(tuple_list, columns=['Ticker', 'ShortName',])
        return df

def information_tick(): #Получение тикера, шортнейма и кратк. информ
    with sqlite3.connect("db.db") as conn:
        cur = conn.cursor()
        query = "SELECT ticker, shortname, information FROM _ALL_stocks"
        cur.execute(query)
        tuple_list = cur.fetchall()
        df = pd.DataFrame(tuple_list, columns=['Ticker', 'ShortName', 'Information'])
        return df


def search_in_db(user_ticker): #Поиск существует ли интерисующий тикер
    with sqlite3.connect("db.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT ticker FROM _ALL_stocks")
        tuple_list = cur.fetchall()

        # Преобразуем список кортежей в список строк
        tickers = [item[0] for item in tuple_list]

        if user_ticker in tickers:
            return True
        else:
            return False


def prediction(user_ticker): #Функция прогнозирования
    with sqlite3.connect("db.db") as conn:
        cur = conn.cursor()
        query = f"SELECT end, close FROM {user_ticker}_D"
        cur.execute(query)
        tuple_list = cur.fetchall()
        df = pd.DataFrame(tuple_list, columns=['Date', 'Price'])
        #Преобразование даты
        df['Date'] = pd.to_datetime(df['Date'])
        df['date'] = df['Date'].dt.date
        df['time'] = df['Date'].dt.time
        df.drop(['time', 'date'], axis=1, inplace=True)
        df["Date"] = pd.to_datetime(df["Date"], format='%Y-%m-%d')
        df['Year'] = df['Date'].dt.year
        df["Month"] = df["Date"].dt.month
        df["Day"] = df["Date"].dt.day
        #Поиск параметров модели и построение модели
        parametr_arima = auto_arima(df['Price'], seasonal=True, m=52, suppress_warnings=True)
        order = parametr_arima.order
        pdq = list(order)
        seasonal_order = pdq[0], pdq[1], pdq[2], 52
        model_sarimax = SARIMAX(df['Price'], order=order, seasonal_order=seasonal_order)
        fitted_model = model_sarimax.fit()
        #Построение прогноза
        predictions = fitted_model.predict(len(df['Price']), len(df) + 60)
        split_index = len(df) // 8
        quat_df = df.iloc[7*split_index:]
        quat_df.set_index('Date', inplace=True)
        df.set_index('Date', inplace=True)
        start_date = pd.Timestamp(df.index[-1])

        # Создаем диапазон дат для прогноза, начиная со следующего дня после последней даты
        forecast_dates = pd.date_range(start=start_date + pd.Timedelta(days=1), periods=len(predictions), freq='D')

        # Создаем DataFrame с прогнозами и добавляем столбец с датами
        predictions_with_dates = pd.DataFrame({'Date': forecast_dates, 'Predictions': predictions})
        predictions_with_dates.set_index('Date', inplace=True)

        fig = go.Figure()
        one_week_in_ms = 7 * 24 * 60 * 60 * 1000

        # Представления графиков
        fig.add_trace(go.Scatter(
            x=quat_df.index,
            y=quat_df['Price'],
            mode='lines',
            name=f'Price {user_ticker}',
            line=dict(color='orange')
        ))

        # Add predictions line plot
        fig.add_trace(go.Scatter(
            x=predictions_with_dates.index,
            y=predictions_with_dates['Predictions'],
            mode='lines',
            name=f'Forecast {user_ticker}',
            line=dict(color='green')
        ))

        fig.update_layout(
            title=f"{user_ticker} - Price forecast",
            xaxis_title="Date",
            yaxis_title="Price",
            legend_title="Legend",
            width=1100,
            height=600,
            xaxis=dict(
                dtick=one_week_in_ms,
                tickformat="%d %b %Y"  # формат отображения даты
            ),
            yaxis=dict(
                dtick=5  # Задайте нужный интервал между метками на оси Y
            )
        )

        file_path = f"{user_ticker}_prediction.png"
        fig.write_image(file_path)

        return file_path