from django.urls import path

from wallet.views import SendEthView, CoinListView, MyTransactionView


app_name = 'wallet'

urlpatterns = [
    path('wallet/send-eth/<str:coin>/', SendEthView.as_view(), name='send-eth'),
    path('', CoinListView.as_view(), name='coins'),
    path('wallet/transactions/', MyTransactionView.as_view(), name='my-transactions')
]
