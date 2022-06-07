from django.urls import path

from wallet.views import SendEthView


app_name = 'wallet'

urlpatterns = [
    path('send-eth/', SendEthView.as_view(), name='send-eth'),
]
