from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from wallet.utils import update_wallet_balances

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate wallet balance for all users.'

    def handle(self, *args, **options):
        for user in User.objects.all():
            update_wallet_balances(user)
        self.stdout.write('Wallet balance successfully sync for users.')

