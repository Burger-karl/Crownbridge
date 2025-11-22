from django.urls import path
from .views import support_chatbot

urlpatterns = [
    path("chat/", support_chatbot, name="support_chat"),
]
