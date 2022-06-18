from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from wallet.utils import create_user_wallet_balance

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate wallet balance for all users.'

    def handle(self, *args, **options):
        for user in User.objects.all():
            create_user_wallet_balance(user)
        self.stdout.write('Wallet balance successfully created for users.')

