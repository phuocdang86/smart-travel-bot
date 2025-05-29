import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-02-15-preview"
)
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# General test question
question = "What is the weather like in London next week?"

messages = [
    {"role": "system", "content": "You are ChatGPT, a smart assistant that gives accurate, helpful, and conversational responses to general questions, including travel, weather, culture, and local knowledge."},
    {"role": "user", "content": question}
]

response = client.chat.completions.create(
    model=deployment_name,
    messages=messages
)

print("Response:")
print(response.choices[0].message.content.strip())
