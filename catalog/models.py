from django.db import models


class Provider(models.TextChoices):
    # Values are also the proxy interface names send_chat() takes.
    OPENAI = 'openai', 'OpenAI'
    ANTHROPIC = 'anthropic', 'Anthropic'
    GOOGLE = 'google', 'Google'


class Tier(models.IntegerChoices):
    # Stored as numbers so models sort in tier order.
    VALUE = 1, 'Value'
    STANDARD = 2, 'Standard'
    PREMIUM = 3, 'Premium'


class LLMModelQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class LLMModel(models.Model):
    display_name = models.CharField(max_length=100)
    provider = models.CharField(max_length=20, choices=Provider.choices)
    proxy_model_id = models.CharField(
        max_length=100, unique=True, help_text='The model ID sent to the proxy.'
    )
    tier = models.PositiveSmallIntegerField(choices=Tier.choices)
    is_active = models.BooleanField(
        'active', default=True, help_text='Turn off to hide this model from users.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = LLMModelQuerySet.as_manager()

    class Meta:
        ordering = ['tier', 'display_name']
        verbose_name = 'LLM model'

    def __str__(self):
        return self.display_name
