from flask import Flask, request, jsonify, render_template
import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

app = Flask(__name__)

# Setup Azure OpenAI
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-02-15-preview"
)
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")


@app.route('/')
def home():
    return render_template("chat.html")


@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get("message")

    system_prompt = """
    You are a helpful and knowledgeable travel assistant.

    Your job is to assist users with travel-related questions, such as finding hotel options, suggesting destinations, explaining visa requirements, or helping with planning itineraries.

    If the user asks for a hotel, try to understand the location, dates, number of people (adults and children), and their preferences. Respond clearly with relevant information or follow-up questions if details are missing.

    Use natural and concise language. Be friendly, proactive, and professional. Do not assume too much — clarify when something is ambiguous.

    Examples:
    - "Sure! What city are you traveling to, and when do you plan to check in?"
    - "Got it. You're looking for a hotel in Tokyo next weekend for two adults and a child aged 6. Do you have a budget in mind?"

    If the user is not asking about travel, behave as a general helpful assistant.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages
        )
        gpt_reply = response.choices[0].message.content.strip()
        return jsonify({"response": gpt_reply})
    except Exception as e:
        return jsonify({"response": f"❌ Error: {str(e)}"})



if __name__ == "__main__":
    app.run(debug=True)
