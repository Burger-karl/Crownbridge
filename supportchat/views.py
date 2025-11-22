import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.conf import settings


@csrf_exempt
def support_chatbot(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    data = json.loads(request.body)
    user_message = data.get("message")

    # Load Key From Settings
    GROQ_API_KEY = settings.GROQ_API_KEY

    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {
                "role": "system", 
                "content": "You are a helpful support assistant for CrownBridge Finance platform. "
                           "Your answers must be clear, friendly, and accurate."
            },
            {"role": "user", "content": user_message},
        ]
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload,
        headers=headers
    )

    bot_reply = response.json()["choices"][0]["message"]["content"]

    return JsonResponse({"reply": bot_reply})
