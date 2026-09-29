from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from billing.charges import record_charge
from billing.models import BillingAccount, LedgerEntry, TierPrice
from catalog.models import LLMModel
from chat.models import ChatMessage, ChatSession

URL = '/usage/'
PASSWORD = 'correct-horse-42'


def charged_turn(session, input_tokens, output_tokens, user=None):
    """One saved turn with its charge, as the chat services make them."""
    user = user or session.user
    tier_price = TierPrice.objects.get(tier=session.llm_model.tier)
    ChatMessage.objects.create(session=session, role='user', content='question')
    charge = record_charge(session.billing_account, user, input_tokens + output_tokens, tier_price)
    ChatMessage.objects.create(
        session=session, role='assistant', content='answer',
        input_tokens=input_tokens, output_tokens=output_tokens, charge=charge,
    )
    return charge


class UsagePageTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password=PASSWORD)
        self.personal = BillingAccount.objects.get(owner=self.alice)
        self.claude = LLMModel.objects.get(proxy_model_id='claude-haiku-4-5-20251001')  # Standard: 3
        self.session = ChatSession.objects.create(
            user=self.alice, llm_model=self.claude, billing_account=self.personal, title='Capitals',
        )
        self.client.force_login(self.alice)

    def test_login_needed(self):
        self.client.logout()
        response = self.client.get(URL)
        self.assertRedirects(response, f'/accounts/login/?next={URL}', fetch_redirect_response=False)

    def test_post_is_not_allowed(self):
        self.assertEqual(self.client.post(URL).status_code, 405)

    def test_lists_accounts_with_balances_including_negative(self):
        team = BillingAccount.objects.create(kind=BillingAccount.Kind.SHARED, name='Study group')
        team.members.add(self.alice)
        LedgerEntry.objects.create(account=team, amount_micro=-1_500_000, kind='admin_grant')
        response = self.client.get(URL)
        self.assertContains(response, 'alice (personal)')
        self.assertContains(response, '<td class="num">1,000</td>', html=True)
        self.assertContains(response, 'Study group')
        self.assertContains(response, '<td class="num">-1.5</td>', html=True)
        self.assertContains(response, 'one reply can take the balance below 0')

    def test_lists_charges_newest_first_with_details(self):
        charged_turn(self.session, 183, 12)                     # 0.585 credits at 3
        TierPrice.objects.filter(tier=self.claude.tier).update(price_per_1k_tokens=Decimal('10'))
        newest = charged_turn(self.session, 1000, 500)           # 15 credits at 10
        LedgerEntry.objects.filter(pk=newest.pk).update(created_at=timezone.now() + timedelta(minutes=1))

        response = self.client.get(URL)
        content = response.content.decode()
        self.assertContains(response, f'<a href="/chat/{self.session.pk}/">Capitals</a>', html=True)
        self.assertContains(response, 'Claude Haiku 4.5')
        self.assertContains(response, '183 / 12')
        self.assertContains(response, '1,000 / 500')
        self.assertContains(response, '<td class="num">3</td>', html=True)
        self.assertContains(response, '<td class="num">10</td>', html=True)
        self.assertContains(response, '<td class="num">0.585</td>', html=True)
        self.assertContains(response, '<td class="num">15</td>', html=True)
        self.assertLess(content.index('1,000 / 500'), content.index('183 / 12'))

    def test_deleted_chat_is_listed_without_a_link(self):
        charged_turn(self.session, 183, 12)
        kept = ChatSession.objects.create(
            user=self.alice, llm_model=self.claude, billing_account=self.personal, title='Kept chat',
        )
        charged_turn(kept, 50, 5)
        self.session.hide()

        response = self.client.get(URL)
        self.assertContains(response, '<td>Capitals (deleted)</td>', html=True)
        self.assertNotContains(response, f'href="/chat/{self.session.pk}/"')
        self.assertContains(response, '183 / 12')
        self.assertContains(response, '<td class="num">0.585</td>', html=True)
        self.assertContains(response, 'Claude Haiku 4.5')
        self.assertContains(response, f'<a href="/chat/{kept.pk}/">Kept chat</a>', html=True)

    def test_hides_grants_and_other_users_charges(self):
        bob = User.objects.create_user('bob', password=PASSWORD)
        team = BillingAccount.objects.create(kind=BillingAccount.Kind.SHARED, name='Study group')
        team.members.add(self.alice, bob)
        bobs_chat = ChatSession.objects.create(
            user=bob, llm_model=self.claude, billing_account=team, title='Bob secret chat',
        )
        charged_turn(bobs_chat, 777, 1)
        response = self.client.get(URL)
        self.assertNotContains(response, 'Bob secret chat')
        self.assertNotContains(response, '777')
        self.assertNotContains(response, 'Sign-up')
        self.assertContains(response, 'No charges yet.')

    def test_no_charges(self):
        self.assertContains(self.client.get(URL), 'No charges yet.')

    def test_fifty_per_page(self):
        for _ in range(51):
            charged_turn(self.session, 10, 1)
        first = self.client.get(URL)
        self.assertEqual(len(first.context['page'].object_list), 50)
        self.assertContains(first, 'Older')
        self.assertNotContains(first, 'Newer')
        second = self.client.get(URL + '?page=2')
        self.assertEqual(len(second.context['page'].object_list), 1)
        self.assertContains(second, 'Newer')
        self.assertEqual(self.client.get(URL + '?page=99').context['page'].number, 2)
        self.assertEqual(self.client.get(URL + '?page=abc').context['page'].number, 1)

    def test_nav_link(self):
        self.assertContains(self.client.get('/models/'), f'<a href="{URL}">Usage</a>', html=True)
        self.client.logout()
        self.assertNotContains(self.client.get('/accounts/login/'), f'href="{URL}"')

    def test_query_count_does_not_grow_with_rows(self):
        charged_turn(self.session, 10, 1)
        one = self.count_queries()
        for _ in range(9):
            charged_turn(self.session, 10, 1)
        self.assertEqual(self.count_queries(), one)

    def test_query_count_does_not_grow_with_deleted_chats(self):
        charged_turn(self.session, 10, 1)
        one = self.count_queries()
        for n in range(9):
            chat = ChatSession.objects.create(
                user=self.alice, llm_model=self.claude, billing_account=self.personal, title=f'chat {n}',
            )
            charged_turn(chat, 10, 1)
            chat.hide()
        self.assertEqual(self.count_queries(), one)

    def count_queries(self):
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(URL).status_code, 200)
        return len(queries)
