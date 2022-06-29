# Generated by Django 4.0 on 2022-06-16 07:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0004_transaction_block_number'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='transaction',
            options={'ordering': ['-created_at']},
        ),
        migrations.AddField(
            model_name='transaction',
            name='contract_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='running_balance',
            field=models.DecimalField(blank=True, decimal_places=18, max_digits=36, null=True),
        ),
        migrations.CreateModel(
            name='WalletBalance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance', models.DecimalField(decimal_places=18, default=0, max_digits=36)),
                ('coin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wallet.coin')),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wallet.wallet')),
            ],
            options={
                'unique_together': {('wallet', 'coin')},
            },
        ),
    ]