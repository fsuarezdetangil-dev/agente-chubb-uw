"""
Inicialización del LLM compartido para todos los nodos.
Usa AzureChatOpenAI con las variables de .env.
"""

import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv()


def get_llm(temperature: float = 0.0) -> AzureChatOpenAI:
    """Devuelve una instancia de AzureChatOpenAI lista para usar."""
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=temperature,
    )
