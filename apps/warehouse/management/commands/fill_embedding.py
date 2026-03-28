from django.core.management.base import BaseCommand
from apps.warehouse.models.base import ProductVariant
from google import genai
import os

class Command(BaseCommand):
    help = 'Barcha mahsulotlar uchun embeddinglarni yaratadi'

    def handle(self, *args, **kwargs):
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        variants = ProductVariant.objects.filter(embedding__isnull=True)
        
        self.stdout.write(f"{variants.count()} ta mahsulot vektorlanmoqda...")

        for v in variants:
            text = f"{v.product.name} {v.brand} {v.size}".strip().lower()
            try:
                res = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text
                )
                v.embedding = res.embeddings[0].values
                v.save()
                self.stdout.write(self.style.SUCCESS(f"Tayyor: {text}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Xato: {text} - {e}"))

        self.stdout.write(self.style.SUCCESS("Barcha embeddinglar yakunlandi!"))