from flask import Flask, request, jsonify, render_template, session
import os
import requests
import json
from datetime import datetime
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
    api_version="2024-02-15-preview"
)
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Travel Advisor API Setup
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
TRAVEL_SEARCH_URL = "https://travel-advisor.p.rapidapi.com/locations/search"
HOTEL_LIST_URL = "https://travel-advisor.p.rapidapi.com/hotels/list"

headers = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST
}

def parse_dates(text):
    match = re.search(r"(\d{1,2})[-–](\d{1,2})/(\d{2,4})", text)
    if match:
        start_day, end_day, month = match.groups()
        year = datetime.now().year
        start_date = f"{year}-{int(month):02d}-{int(start_day):02d}"
        end_date = f"{year}-{int(month):02d}-{int(end_day):02d}"
        return start_date, end_date
    return None, None

def extract_travel_info(user_input):
    extraction_prompt = f"""
Extract and return the following from the user's travel request in JSON:
- City
- Check-in date (format YYYY-MM-DD)
- Check-out date (format YYYY-MM-DD)
- Number of adults
- Number of children
- Preferences (e.g. CBD, budget, sorting)
Return "unknown" if any field is missing. If the number of customers unknown, set 1 adult as default.

Input: {user_input}
"""
    messages = [{"role": "system", "content": "You extract structured travel info."},
                {"role": "user", "content": extraction_prompt}]
    response = client.chat.completions.create(
        model=deployment_name,
        messages=messages
    )
    return json.loads(response.choices[0].message.content.strip())

def extract_option_number(text):
    match = re.search(r'option\s*(\d+)', text.lower())
    return int(match.group(1)) if match else None

def get_city_location_id(city):
    params = {"query": city, "limit": "1"}
    res = requests.get(TRAVEL_SEARCH_URL, headers=headers, params=params)
    try:
        return res.json()["data"][0]["result_object"]["location_id"]
    except:
        return None

def get_hotels(location_id, checkin, adults="2"):
    params = {
        "location_id": location_id,
        "checkin": checkin,
        "adults": adults,
        "nights": "1",
        "currency": "USD",
        "sort": "price"
    }
    res = requests.get(HOTEL_LIST_URL, headers=headers, params=params)
    hotels = res.json().get("data", [])
    result = []
    for h in hotels[:5]:
        if h.get("name") and h.get("price"):
            result.append({
                "name": h["name"],
                "location": h["location_string"],
                "price": h["price"],
                "rating": h.get("rating", "N/A"),
                "summary": f"{h['name']} – {h['location_string']}, {h['price']} (Rating: {h.get('rating', 'N/A')})"
            })
    return result

@app.route('/')
def home():
    return render_template("chat.html")

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get("message")

    if "messages" not in session:
        session["messages"] = [
            {"role": "system", "content": "You're a natural, helpful travel assistant. Never repeat questions. Use memory to avoid re-asking what's already known. Respond conversationally and ask only what's missing."}
        ]
    if "extracted" not in session:
        session["extracted"] = {}

    history = session.get("messages", [])
    history.append({"role": "user", "content": user_input})

    checkin_parsed, _ = parse_dates(user_input)

    intent_prompt = f"""
Determine if the following user message is intended to inquire about hotel booking or planning a trip.
Respond only with 'yes' or 'no'.
Message: {user_input}
"""
    intent_response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {"role": "system", "content": "You determine intent to book a hotel."},
            {"role": "user", "content": intent_prompt}
        ]
    ).choices[0].message.content.strip()

    print("🤖 GPT intent detection response:", intent_response)
    intent_check = intent_response.strip().lower()
    intent_check = "yes" if intent_check == "yes" else "no"

    if intent_check != "yes":
        session["extracted"] = {}
        session["messages"] = session["messages"][:1]

    extracted = {}
    if intent_check == "yes":
        extracted = extract_travel_info(user_input)

    for k, v in extracted.items():
        if isinstance(v, str):
            if v.lower() != "unknown":
                session["extracted"][k] = v
        else:
            session["extracted"][k] = v

    if checkin_parsed:
        parsed_year = int(checkin_parsed.split("-")[0])
        current_year = datetime.now().year
        if ("Check-in date" not in session["extracted"]) or (int(session["extracted"].get("Check-in date", "0000-00-00").split("-")[0]) < current_year):
            session["extracted"]["Check-in date"] = checkin_parsed

    info = session.get("extracted", {})
    print("🔍 Extracted info from session:", info)
    print("📅 Parsed check-in (from parse_dates):", checkin_parsed)
    filled = all(key in info for key in ["City", "Check-in date"])

    def summarize_info(info):
        parts = []
        if "City" in info:
            parts.append(f"destination: {info['City']}")
        if "Check-in date" in info:
            parts.append(f"check-in on {info['Check-in date']}")
        if "Number of adults" in info:
            parts.append(f"{info['Number of adults']} adult(s)")
        if "Preferences" in info:
            parts.append(f"preferences: {info['Preferences']}")
        return ", ".join(parts)

    option_requested = extract_option_number(user_input)
    if option_requested and "hotels" in session:
        index = option_requested - 1
        if 0 <= index < len(session["hotels"]):
            selected = session["hotels"][index]
            gpt_reply = f"Here are more details about **{selected['name']}**:\n\n" \
                         f"**Location:** {selected['location']}\n" \
                         f"**Price:** {selected['price']}\n" \
                         f"**Rating:** {selected['rating']}\n" \
                         f"This hotel is known for being affordable and well-located in the city center."
            session["messages"] = history + [{"role": "assistant", "content": gpt_reply}]
            return jsonify({"response": gpt_reply.replace('\n', '<br>')})

    if filled and intent_check == "yes":
        city, checkin = info["City"], info["Check-in date"]
        adults = str(info.get("Number of adults", "1"))
        location_id = get_city_location_id(city)
        if location_id:
            hotels = get_hotels(location_id, checkin, adults)
            session["hotels"] = hotels
            if hotels:
                hotel_msg = "<ul>" + "".join(f"<li><strong>Option {i+1}:</strong> {h['summary']}</li>" for i, h in enumerate(hotels)) + "</ul>"
            else:
                hotel_msg = "I couldn’t find any hotels — maybe try different dates."
            assistant_prompt = f"""
You are a helpful and friendly travel assistant.
Here’s what the user has told you so far:

- City: {city}
- Check-in date: {checkin}
- Guests: {adults} adult(s)
- Preferences: {info.get('Preferences', 'not specified')}

Please respond in a natural, conversational way. If everything is known, suggest a few hotels using bullet points. Be warm and engaging — not robotic.

Here are the hotel results:
{hotel_msg}
"""
        else:
            assistant_prompt = f"The city '{city}' could not be found. Ask the user to recheck the spelling."
    else:
        assistant_prompt = "You are a warm, friendly travel assistant. The user just said hello or sent a casual greeting. Reply naturally and helpfully — say something like: 'Hi there! I’m your travel assistant. I can help with planning trips, finding hotels, or answering travel questions. Just let me know what you need!' Avoid asking for destination or travel dates unless the user brings them up."

    messages = [{"role": "system", "content": assistant_prompt}] + session["messages"]
    gpt_reply = client.chat.completions.create(
        model=deployment_name,
        messages=messages
    ).choices[0].message.content.strip()

    session["messages"] = session["messages"] + [{"role": "assistant", "content": gpt_reply}]
    return jsonify({"response": gpt_reply.replace('\n', '<br>')})

@app.route('/reset', methods=['POST'])
def reset():
    session.pop("messages", None)
    session.pop("extracted", None)
    session.pop("hotels", None)
    return jsonify({"response": "Reset complete."})

if __name__ == "__main__":
    app.run(debug=True)
