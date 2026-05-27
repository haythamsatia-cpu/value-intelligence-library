from django.db import models

from config.models import TimestampedModel, UUIDModel


class Domain(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Subdomain(UUIDModel, TimestampedModel):
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='subdomains')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['domain__name', 'name']
        unique_together = [['domain', 'name']]

    def __str__(self):
        return f'{self.domain.name} / {self.name}'


class Topic(UUIDModel, TimestampedModel):
    subdomain = models.ForeignKey(Subdomain, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['subdomain__domain__name', 'subdomain__name', 'name']
        unique_together = [['subdomain', 'name']]

    def __str__(self):
        return f'{self.subdomain} / {self.name}'


class Concept(UUIDModel, TimestampedModel):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='concepts')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['topic__subdomain__domain__name', 'topic__subdomain__name', 'topic__name', 'name']
        unique_together = [['topic', 'name']]

    def __str__(self):
        return f'{self.topic} / {self.name}'


class Tag(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
