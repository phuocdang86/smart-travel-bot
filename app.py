from flask import Flask, request, jsonify, render_template, session
import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import AzureOpenAI
import re

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "travel-secret-key")

# Azure OpenAI Setup
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-12-01-preview"
)
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")

BOOKING_LOCATION_URL = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchDestination"
BOOKING_HOTEL_LIST_URL = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchHotels"
BOOKING_HOTEL_PHOTOS_URL = "https://booking-com15.p.rapidapi.com/api/v1/hotels/getHotelPhotos"

headers = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST,
    "Accept": "application/json"
}

def extract_travel_info(user_input):
    prompt = f"""
Today’s date is {datetime.today().strftime('%Y-%m-%d')}.

You are a smart travel assistant. From the user’s message, extract and return the following in JSON:
- City
- Check-in date (YYYY-MM-DD, must be today or a future date)
- Check-out date (YYYY-MM-DD, must be after check-in date)
- Number of nights
- Number of adults (default to 1 if unknown)
- Number of children (default to 0 if unknown)
- Preferences (e.g. CBD, budget, view)

Be flexible and handle follow-up messages like changes in group size, stay duration and other enquiries. Always maintain previous information if not updated.
Ensure the dates are not in the past.

Input: {user_input}
"""
    messages = [
        {"role": "system", "content": "Extract structured travel info from user input."},
        {"role": "user", "content": prompt}
    ]
    response = client.chat.completions.create(model=deployment_name, messages=messages)
    extracted = response.choices[0].message.content.strip()
    return json.loads(extracted)

def get_city_location_id(city):
    params = {"query": city}
    try:
        res = requests.get(BOOKING_LOCATION_URL, headers=headers, params=params)
        res.raise_for_status()
        data = res.json().get("data", [])
        for loc in data:
            name = loc.get("name", "").lower()
            if city.lower() in name:
                return loc.get("dest_id")
        return None
    except Exception as e:
        print("[ERROR] Could not extract dest_id:", e)
        return None

def get_hotels(location_id, checkin, checkout, adults="1", children="0"):
    try:
        nights = (datetime.strptime(checkout, "%Y-%m-%d") - datetime.strptime(checkin, "%Y-%m-%d")).days
        if nights <= 0:
            nights = 1
            checkout = (datetime.strptime(checkin, "%Y-%m-%d") + timedelta(days=nights)).strftime("%Y-%m-%d")

        params = {
            "dest_id": location_id,
            "search_type": "CITY",
            "arrival_date": checkin,
            "departure_date": checkout,
            "adults": adults,
            "children_qty": children,
            "room_qty": "1",
            "page_number": "1",
            "units": "metric",
            "temperature_unit": "c",
            "languagecode": "en-us",
            "currency_code": "USD"
        }

        res = requests.get(BOOKING_HOTEL_LIST_URL, headers=headers, params=params)

        hotels = res.json().get("data", {}).get("hotels", [])
        result = []
        for h in hotels[:5]:
            prop = h.get("property", {})
            if h.get("hotel_id"):
                photo_urls = prop.get("photoUrls") or []
                photo_url = photo_urls[0] if photo_urls else None
                result.append({
                    "name": prop.get("name"),
                    "location": prop.get("wishlistName", "Unknown location"),
                    "price": prop.get("priceBreakdown", {}).get("grossPrice", {}).get("value", "N/A"),
                    "rating": prop.get("reviewScore", "N/A"),
                    "photo": photo_url,
                    "summary": f"{prop.get('name')} – {prop.get('wishlistName', '')}, ${prop.get('priceBreakdown', {}).get('grossPrice', {}).get('value', 'N/A')} (Rating: {prop.get('reviewScore', 'N/A')})"
                })
        return result
    except Exception as e:
        print("[ERROR] Failed to parse hotel response:", e)
        return []

def get_hotel_photo(hotel_id):
    try:
        params = {"hotel_id": hotel_id}
        res = requests.get(BOOKING_HOTEL_PHOTOS_URL, headers=headers, params=params)
        data = res.json()
        if data:
            return data[0].get("url")
    except:
        pass
    return None

@app.route('/')
def home():
    return render_template("chat.html")

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get("message")
    if "messages" not in session:
        session["messages"] = []
    if "extracted" not in session:
        session["extracted"] = {}

    session["messages"].append({"role": "user", "content": user_input})

    intent_prompt = f"""
Classify the user's intent as either hotel or general.
Message: {user_input}
Respond with: hotel or general
"""
    intent_response = client.chat.completions.create(
        model=deployment_name,
        messages=[{"role": "system", "content": "Intent classifier."}, {"role": "user", "content": intent_prompt}]
    ).choices[0].message.content.strip().lower()

    intent = intent_response if intent_response in ["hotel", "general"] else "general"

    if intent == "hotel":
        extracted = extract_travel_info(user_input)
        default_notices = []

        for k in ["City", "Check-in date", "Check-out date", "Number of nights", "Number of adults", "Number of children", "Preferences"]:
            new_val = extracted.get(k)
            if new_val not in [None, "unknown", "null", "", []]:
                session["extracted"][k] = new_val

        info = session["extracted"]

        if not info.get("Number of adults"):
            info["Number of adults"] = "1"
            default_notices.append("Defaulting to 1 adult.")

        if not info.get("Number of children"):
            info["Number of children"] = "0"
            default_notices.append("Defaulting to 0 children.")

        city = info.get("City")
        checkin = info.get("Check-in date")
        checkout = info.get("Check-out date")
        adults = str(info.get("Number of adults", "1"))
        children = str(info.get("Number of children", "0"))

        if city and checkin and checkout:
            location_id = get_city_location_id(city)
            if location_id:
                hotels = get_hotels(location_id, checkin, checkout, adults, children)
                session["hotels"] = hotels
                if hotels:
                    hotel_msg = "<ul>" + "".join(f"<li><strong>Option {i+1}:</strong> {h['summary']}</li>" for i, h in enumerate(hotels)) + "</ul>"
                    notice_text = " ".join(default_notices)
                    if notice_text:
                        notice_text += " Let me know if you'd like to adjust the number of adults or children."
                    reply = f"{notice_text}<br>Here are some hotel options in {city} from {checkin} to {checkout}:<br>{hotel_msg}"
                else:
                    reply = f"I couldn't find any hotels in {city} for those dates. Would you like to try different dates or another city?"
            else:
                reply = f"Sorry, I couldn't find the location '{city}'. Please try rephrasing."
        else:
            reply = "Could you please let me know the city and check-in/check-out dates for your hotel search?"
    else:
        reply = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant who can answer general questions naturally."},
                {"role": "user", "content": user_input}
            ]
        ).choices[0].message.content.strip()

    session["messages"].append({"role": "assistant", "content": reply})
    return jsonify({"response": reply.replace('\n', '<br>')})

@app.route('/reset', methods=['POST'])
def reset():
    session.clear()
    return jsonify({"response": "Reset complete."})

if __name__ == '__main__':
    app.run(debug=True)
