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

def upload_to_cloudinary(file, folder_name='general'):
    try:
        result = cloudinary.uploader.upload(
            file,
            folder=f"megamall/{folder_name}",  # ✅ This builds megamall/product
            resource_type="auto",
            use_filename=True,
            unique_filename=True,
            overwrite=False
        )
        return result
    except Exception as e:
        logger.error(f"Cloudinary upload error: {str(e)}")
        raise e


def generate_invoice_pdf(context):
    template = get_template('templates/invoice_template.html')
    html = template.render(context)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode('utf-8')), result)
    if not pdf.err:
        return result.getvalue()
    return None


def send_invoice_email(order, to_email):
    from megamall.models import OrderItem

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
