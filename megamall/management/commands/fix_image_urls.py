# your_app/management/commands/fix_image_urls.py

from django.core.management.base import BaseCommand
from your_app.models import Product  # Adjust to your app name
import cloudinary.api

class Command(BaseCommand):
    help = 'Fixes broken Cloudinary image URLs for existing products.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting URL migration...")
        
        # Get all products that have an image public ID
        # 'image' field holds the public_id
        products_to_update = Product.objects.all()

        if not products_to_update:
            self.stdout.write(self.style.WARNING("No products found to update."))
            return

        updated_count = 0
        failed_count = 0

        for product in products_to_update:
            public_id = product.image  # This is the public_id from Cloudinary
            
            if not public_id:
                continue

            try:
                # Retrieve the full resource details from Cloudinary using the public_id
                resource = cloudinary.api.resource(public_id)
                new_url = resource['secure_url']
                
                # Check if the URL has changed before updating
                if product.image_url != new_url:
                    product.image_url = new_url
                    product.save()  # This will update the MongoDB document
                    self.stdout.write(self.style.SUCCESS(f'✅ Updated URL for product "{product.name}"'))
                    updated_count += 1
                else:
                    self.stdout.write(f'➡️ URL for product "{product.name}" is already correct. Skipping.')

            except cloudinary.api.NotFound:
                self.stdout.write(self.style.ERROR(f'❌ Cloudinary resource not found for public_id: {public_id}. Skipping.'))
                failed_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ An unexpected error occurred for public_id: {public_id} - {e}. Skipping.'))
                failed_count += 1

        self.stdout.write(self.style.SUCCESS(f'\nMigration complete.'))
        self.stdout.write(self.style.SUCCESS(f'Updated {updated_count} URLs.'))
        self.stdout.write(self.style.WARNING(f'Failed to update {failed_count} URLs.'))