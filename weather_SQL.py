import requests
from dotenv import load_dotenv
import os
from datetime import datetime
from flask import Flask, render_template, request
import sqlite3

app = Flask(__name__)


# Set up the SQLite database
def init_db():
    conn = sqlite3.connect('weather_forecasts.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS forecasts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        city TEXT,
                        date TEXT,
                        avg_temp REAL,
                        avg_humidity REAL,
                        avg_wind REAL,
                        description TEXT)''')
    conn.commit()
    conn.close()


# Function to save forecast data into the database
def save_forecast_to_db(city, forecast_results):
    conn = sqlite3.connect('weather_forecasts.db')
    cursor = conn.cursor()

    for result in forecast_results:
        cursor.execute('''INSERT INTO forecasts (city, date, avg_temp, avg_humidity, avg_wind, description)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (city, result['date'], result['avg_temp'], result['avg_humidity'], result['avg_wind'],
                        result['description']))

    conn.commit()
    conn.close()


# Function to check if forecast for a city is already in the database
def get_forecast_from_db(city):
    conn = sqlite3.connect('weather_forecasts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM forecasts WHERE city = ? ORDER BY date DESC LIMIT 5", (city,))
    data = cursor.fetchall()
    conn.close()
    return data


# Function to fetch forecast from OpenWeatherMap API
def get_forecast(city, api_key):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric&lang=en"

    try:
        response = requests.get(url)
        response.raise_for_status()

        if response.status_code == 200:
            data = response.json()
            forecasts = {}

            for forecast in data['list']:
                dt = datetime.utcfromtimestamp(forecast['dt'])
                day = dt.date()

                if day not in forecasts:
                    forecasts[day] = {
                        'temps': [],
                        'humidity': [],
                        'winds': [],
                        'description': []
                    }

                forecasts[day]['temps'].append(forecast['main']['temp'])
                forecasts[day]['humidity'].append(forecast['main']['humidity'])
                forecasts[day]['winds'].append(forecast['wind']['speed'])
                forecasts[day]['description'].append(forecast['weather'][0]['description'])

            forecast_results = []
            for day, stats in forecasts.items():
                avg_temp = sum(stats['temps']) / len(stats['temps'])
                avg_humidity = sum(stats['humidity']) / len(stats['humidity'])
                avg_wind = sum(stats['winds']) / len(stats['winds'])
                most_common_desc = max(set(stats['description']), key=stats['description'].count)

                forecast_results.append({
                    'date': day,
                    'avg_temp': f"{avg_temp:.1f}°C",
                    'avg_humidity': f"{avg_humidity:.1f}%",
                    'avg_wind': f"{avg_wind:.1f} m/s",
                    'description': most_common_desc.capitalize()
                })

            # Save the forecast data to the database
            save_forecast_to_db(city, forecast_results)

            return forecast_results
        else:
            return f"Failed to get weather data. Status code: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return f"An error occurred while executing the request: {e}"


@app.route("/", methods=["GET", "POST"])
def index():
    load_dotenv()

    # Get the API key from environment variables
    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key:
        return "API key not found in environment variables!"

    forecast_data = None
    if request.method == "POST":
        city = request.form["city"]

        # First, check if forecast data for the city already exists in the database
        forecast_data_from_db = get_forecast_from_db(city)

        if forecast_data_from_db:
            # If data exists in the DB, use that data
            forecast_data = [
                {
                    'date': row[2],
                    'avg_temp': f"{row[3]:.1f}°C",
                    'avg_humidity': f"{row[4]:.1f}%",
                    'avg_wind': f"{row[5]:.1f} m/s",
                    'description': row[6].capitalize()
                }
                for row in forecast_data_from_db
            ]
        else:
            # If no data in DB, fetch from OpenWeatherMap and store it in the DB
            forecast_data = get_forecast(city, api_key)

        return render_template("index.html", forecast_data=forecast_data, city=city)

    return render_template("index.html", forecast_data=forecast_data)


if __name__ == "__main__":
    # Initialize the database when the app starts
    init_db()
    app.run(debug=True)
