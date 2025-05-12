import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2024-02-15-preview"
)

deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")

response = client.chat.completions.create(
    model=deployment_name,
    messages=[{"role": "user", "content": "Say hello"}]
)

print(response.choices[0].message.content)
