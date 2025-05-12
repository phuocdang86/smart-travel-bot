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

    messages = [
        {"role": "system", "content": "You are a helpful travel assistant. Answer clearly and concisely."},
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
