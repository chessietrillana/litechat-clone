from decimal import Decimal

from django.template import Context, Template
from django.test import SimpleTestCase

from billing.units import credits_to_micro, format_credits, micro_to_credits


class CreditsToMicroTests(SimpleTestCase):
    def test_whole_and_fractional_credits(self):
        self.assertEqual(credits_to_micro(Decimal('1')), 1_000_000)
        self.assertEqual(credits_to_micro(1000), 1_000_000_000)
        self.assertEqual(credits_to_micro(Decimal('250.5')), 250_500_000)
        self.assertEqual(credits_to_micro(Decimal('0.000001')), 1)
        self.assertEqual(credits_to_micro(Decimal('-1.5')), -1_500_000)

    def test_more_than_six_decimals_is_refused(self):
        with self.assertRaises(ValueError):
            credits_to_micro(Decimal('0.0000001'))

    def test_float_and_bool_are_refused(self):
        for bad in (1.5, True, '1'):
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                credits_to_micro(bad)

    def test_round_trip(self):
        self.assertEqual(micro_to_credits(250_500_000), Decimal('250.5'))
        self.assertEqual(credits_to_micro(micro_to_credits(183)), 183)


class FormatCreditsTests(SimpleTestCase):
    def test_formats(self):
        cases = {
            1_000_000_000: '1,000',
            999_817_000: '999.817',
            183: '0.000183',
            0: '0',
            -1_500_000: '-1.5',
            1_234_567_890_000: '1,234,567.89',
        }
        for micro, text in cases.items():
            with self.subTest(micro=micro):
                self.assertEqual(format_credits(micro), text)

    def test_template_filter(self):
        rendered = Template('{% load billing %}{{ amount|credits }}').render(Context({'amount': 999_817_000}))
        self.assertEqual(rendered, '999.817')
