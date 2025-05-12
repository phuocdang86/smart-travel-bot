from flask import Flask, request, jsonify, render_template
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()


# Add this for debugging
print("🔍 Endpoint:", os.getenv("AZURE_OPENAI_ENDPOINT"))
print("🔍 API Key starts with:", os.getenv("AZURE_OPENAI_API_KEY")[:5])
print("🔍 Deployment:", os.getenv("AZURE_OPENAI_DEPLOYMENT"))


app = Flask(__name__)

# Setup Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-15-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")  # e.g., "gpt-4"

@app.route('/')
def home():
    return render_template("chat.html")

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')

    response = client.chat.completions.create(
        model=deployment_name,
        messages=[{"role": "user", "content": user_input}],
    )

    return jsonify({'response': response.choices[0].message.content})

if __name__ == '__main__':
    app.run(debug=True)

