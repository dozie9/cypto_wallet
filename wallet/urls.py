from django.urls import path

from wallet.views import SendEthView, CoinListView


app_name = 'wallet'

urlpatterns = [
    path('send-eth/<str:coin>/', SendEthView.as_view(), name='send-eth'),
    path('coin-list/', CoinListView.as_view(), name='coins')
]
