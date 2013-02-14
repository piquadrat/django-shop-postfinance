from django.db import models
from django.utils.translation import ugettext_lazy as _


PAYMENT_STATUS = (
    ('5', _('Authorized')),
    ('9', _('Payment requested')),
    ('0', _('Invalid or incomplete')),
    ('2', _('Authorization refused')),
    ('51', _('Authorization waiting')),
    ('52', _('Authorisation not known')),
    ('91', _('Payment processing')),
    ('92', _('Payment uncertain')),
    ('93', _('Payment refused')),
)


class PostfinanceIPN(models.Model):
    """
    A simple, dumb model that traces all the IPNs received from postfinance,
    for archiving reasons.
    
    This isn't really human friends, but should still be kept in the database
    for a while (most probably 10years if you're in Switzerland, since this is
    an accounting piece.
    
    I am not a lawyer :)
    """
    orderID = models.CharField(_('Order ID'), max_length=255)  #=Test27&
    currency = models.CharField(_('currency'), max_length=255)  #=CHF&
    amount = models.CharField(_('Amount'), max_length=255)   #=54&
    PM = models.CharField(_('Payment method'), max_length=255)  #=CreditCard&
    ACCEPTANCE = models.CharField(_('Authorization code'), max_length=255)  #=test123&
    STATUS = models.CharField(_('status'), max_length=255, choices=PAYMENT_STATUS)  #=9&
    CARDNO = models.CharField(_('Credit Card Number'), max_length=255)  #=XXXXXXXXXXXX3333&ED=0317&
    CN = models.CharField(_('Customer Name'), max_length=255)  #Testauzore+Testos&
    TRXDATE = models.CharField(_('Transaction Date'), max_length=255)  #=11/08/10&
    PAYID = models.CharField(_('Payment ID'), max_length=255)  #=8628366&
    NCERROR = models.CharField(_('Error code'), max_length=255)  #=0&
    BRAND = models.CharField(_('Card brand'), max_length=255)  #=VISA&
    IPCTY = models.CharField(max_length=255)  #=CH&
    CCCTY = models.CharField(max_length=255)  #=US&
    ECI = models.CharField(max_length=255)  #=7&
    CVCCheck = models.CharField(max_length=255)  #=NO&
    AAVCheck = models.CharField(max_length=255)  #=NO&
    VC = models.CharField(max_length=255)  #=NO&
    IP = models.CharField(max_length=255)  #=84.226.127.220&
    SHASIGN = models.CharField(max_length=255)  #=CEE483B0557B8E3437A55094221E15C7DB6A0D63
    
    # Timestamping
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u'%s (%s %s, %s)' % (self.orderID, self.amount, self.currency, self.PM)

    class Meta:
        verbose_name = _('PostFinance IPN')
        verbose_name_plural = _('PostFinance IPNs')