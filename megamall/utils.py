import os
from io import BytesIO
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils.html import strip_tags

import cloudinary.uploader
import logging

logger = logging.getLogger(__name__)

# ----------------------------
# Cloudinary Upload Utility
# ----------------------------
def upload_to_cloudinary(file, folder='products'):
    """
    Upload a file to Cloudinary with proper error handling
    """
    try:
        # Ensure Cloudinary is configured
        if not hasattr(settings, 'CLOUDINARY_STORAGE'):
            raise Exception("Cloudinary is not configured")
        
        # Handle different file types
        if hasattr(file, 'read'):
            # File object - read it properly
            if hasattr(file, 'seek') and hasattr(file, 'tell'):
                # Reset file pointer if possible
                current_pos = file.tell()
                file.seek(0)
                file_content = file.read()
                file.seek(current_pos)  # Reset to original position
            else:
                file_content = file.read()
        else:
            # Assume it's a file path or already in the right format
            file_content = file
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            file_content,
            folder=folder,
            resource_type="auto",  # auto-detect image, video, raw
            use_filename=True,
            unique_filename=True,
            overwrite=False
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Cloudinary upload error: {str(e)}")
        raise e

# ----------------------------
# PDF Generation Utility
# ----------------------------
def generate_invoice_pdf(context):
    """
    Render a PDF invoice from the given context using the invoice template.
    """
    try:
        template = get_template('invoice_template.html')  # Assumes template is in your app's templates/ folder
        html = template.render(context)
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode('utf-8')), result)
        if not pdf.err:
            return result.getvalue()
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
    return None

# ----------------------------
# Email Sending Utility
# ----------------------------
def send_invoice_email(order, to_email):
    """
    Sends an invoice email with a PDF attachment to the specified recipient.
    """
    from megamall.models import OrderItem

    try:
        # Build context
        order_items = order.order_items.all()
        context = {
            'order': order,
            'order_items': order_items,
            'guest_user': order.guest_user,
            'shipping_address': order.shipping_address,
        }

        # Generate PDF
        pdf = generate_invoice_pdf(context)
        if pdf is None:
            logger.error("Invoice PDF generation returned None.")
            return False

        # Prepare email
        subject = f"Invoice for your Order #{order.id}"
        message = strip_tags(
            f"Dear {order.guest_user.get_full_name()},\n\nPlease find attached your invoice."
        )
        email = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [to_email])
        email.attach(f"invoice_{order.id}.pdf", pdf, 'application/pdf')
        email.send(fail_silently=False)
        return True

    except Exception as e:
        logger.error(f"Failed to send invoice email: {str(e)}")
        return False
