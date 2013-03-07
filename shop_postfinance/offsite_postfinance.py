from django import forms
from django.conf import settings
from django.conf.urls import patterns, url
from django.db import models
from django.core.urlresolvers import reverse
from django.forms.forms import DeclarativeFieldsMetaclass
from django.http import (HttpResponseBadRequest, HttpResponse, 
    HttpResponseRedirect, Http404)
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.utils.translation import get_language, ugettext_lazy as _
from django.utils.http import urlencode
from django.views.decorators.csrf import csrf_exempt
from shop_postfinance.forms import ValueHiddenInput
from shop_postfinance.models import PostfinanceIPN
from shop_postfinance.utils import security_check, compute_security_checksum


def absolute_url(request, path):
    return '%s://%s%s' % ('https' if request.is_secure() else 'http', 
                          request.get_host(), path)


class OffsitePostfinanceBackend(object):
    backend_name = "Postfinance"
    backend_verbose_name = _("Postfinance")
    url_namespace = "postfinance"
    
    #===========================================================================
    # Defined by the backends API
    #===========================================================================
    
    def __init__(self, shop):
        self.shop = shop
        assert getattr(settings, 'POSTFINANCE_SECRET_KEY', None), 'You need to define a POSTFINANCE_SECRET_KEY="..." setting in your settings file.'
        assert getattr(settings, 'POSTFINANCE_PSP_ID', None), 'Please define a POSTFINANCE_PSP_ID="..." setting in your settings file.'
        assert getattr(settings, 'POSTFINANCE_CURRENCY', None), 'Please define a POSTFINANCE_CURRENCY="..." setting in your settings file.'
        self.extra_data = getattr(settings, 'POSTFINANCE_EXTRA_CONFIGS', {})
        self.language_conversion_table = getattr(settings, 'POSTFINANCE_RFC5646_CONVERSION_TABLE', {})
        self.fallback_language = getattr(settings, 'POSTFINANCE_FALLBACK_LANGUAGE', None)
        if self.fallback_language:
            # validate
            errmsg = ('POSTFINANCE_FALLBACK_LANGUAGE setting must be in '
                'format "xx_YY" where "xx" is a ISO-639-1 code and "YY" a '
                'ISO-3166 code.')
            assert self.fallback_language.count('_') == 1, errmsg
            assert len(self.fallback_language) == 5, errmsg
            assert self.fallback_language[0].islower(), errmsg
            assert self.fallback_language[1].islower(), errmsg
            assert self.fallback_language[2] == '_'
            assert self.fallback_language[3].isupper(), errmsg
            assert self.fallback_language[4].isupper(), errmsg
        else:
            self.fallback_language = 'de_DE'
        self.entry_url = getattr(settings, 'POSTFINANCE_ENTRY_URL', 'https://e-payment.postfinance.ch/ncol/test/orderstandard_utf8.asp')
        self.skip_confirmation = getattr(settings, 'POSTFINANCE_SKIP_CONFIRMATION_VIEW', False)
    
    def _convert_language(self, rfc5646_language_code):
        """
        Turn a RFC5646 (http://tools.ietf.org/html/rfc5646) language code into
        ISO-639-1+ISO-3166 language codes using the
        POSTFINANCE_RFC5646_CONVERSION_TABLE setting or returns the fallback
        as defined in POSTFINANCE_FALLBACK_LANGUAGE (or 'de_DE' if None is
        defined).
        """
        found = self.language_conversion_table.get(rfc5646_language_code)
        if found:
            return found
        return self.fallback_language

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^$', self.view_that_asks_for_money, name='postfinance' ),
            url(r'^success/$', self.postfinance_return_successful_view, name='postfinance_success'),
            url(r'^instantpaymentnotification/$', csrf_exempt(self.postfinance_ipn), name='postfinance_ipn'),
            url(r'^somethinghardtoguess/instantpaymentnotification/$', csrf_exempt(self.postfinance_ipn), kwargs={'deprecated': True}),
        )
        return urlpatterns

    def get_form_initial(self, request, order, **fields):
        order_id = self.shop.get_order_unique_id(order)
        amount = self.shop.get_order_total(order)
        currency = settings.POSTFINANCE_CURRENCY.upper()
        language = self._convert_language(get_language())

        amount = str(int(amount * 100))

        initial = {
            'PSPID': settings.POSTFINANCE_PSP_ID,
            'orderID': order_id,
            'amount': amount,
            'currency': currency,
            'language': language,
            'ACCEPTURL': absolute_url(request, reverse('postfinance_success')),
            'CANCELURL': absolute_url(request, reverse('cart_delete')),
        }
        initial.update(self.extra_data)
        initial.update(**fields)
        initial['SHASign'] = compute_security_checksum(**initial)
        return initial

    def get_form(self, request, order, prefix=None, **fields):
        initial = self.get_form_initial(request, order, **fields)

        fields = {}
        for key in initial:
            fields[key] = forms.CharField(widget=ValueHiddenInput())

        form_class = DeclarativeFieldsMetaclass('PostfinanceForm', (forms.Form,), fields)
        return form_class(initial=initial, prefix=prefix)

    #===========================================================================
    # Views
    #===========================================================================
    
    def view_that_asks_for_money(self, request):
        """
        We need this to be a method and not a function, since we need to have
        a reference to the shop interface
        """
        order = self.shop.get_order(request)
        if self.skip_confirmation:
            data = self.get_form_initial(request, order)
            url = '%s?%s' % (self.entry_url, urlencode(data))
            return HttpResponseRedirect(url)
        context = RequestContext(request, {'form': self.get_form(request, order), 'url': self.entry_url})
        return render_to_response("shop_postfinance/payment.html", context)
    
    def postfinance_return_successful_view(self, request):
        if request.GET:
            self.postfinance_ipn(request)
        return HttpResponseRedirect(self.shop.get_finished_url())
    
    def postfinance_ipn(self, request, deprecated=False):
        """
        Similar to paypal's IPN, postfinance will send an instant notification
        to the website, passing the following parameters in the URL:
        
        orderID=Test27&
        currency=CHF&
        amount=54&
        PM=CreditCard&
        ACCEPTANCE=test123&
        STATUS=9&
        CARDNO=XXXXXXXXXXXX3333&ED=0317&
        CN=Testauzore+Testos&
        TRXDATE=11/08/10&
        PAYID=8628366&
        NCERROR=0&
        BRAND=VISA&
        IPCTY=CH&
        CCCTY=US&
        ECI=7&
        CVCCheck=NO&
        AAVCheck=NO&
        VC=NO&
        IP=84.226.127.220&
        SHASIGN=CEE483B0557B8E3437A55094221E15C7DB6A0D63
        
        Confirms that payment has been completed and marks invoice as paid.
        This can come from two sources: Either the client was redirected to our
        success page from postfinance (and so the order information is contained
        in GET parameters), or the client messed up and postfinance sends us a
        direct server-to-server http connection with parameters passed in the
        POST fields.
        
        """
        if deprecated:
            import warnings
            warnings.warn('usage of this URL is deprecated. Please use the URL without the "somethinghardtoguess" part.', DeprecationWarning)
        data = request.REQUEST
        # Verify that the info is valid (with the SHA sum)
        if self.confirm_payment_data(data):
            return HttpResponse('OKAY')
        else:  # Checksum failed
            return HttpResponseBadRequest()

    def confirm_payment_data(self, data):
        try:
            valid = security_check(data, settings.POSTFINANCE_SHAOUT_KEY)
        except KeyError:
            valid = False
        if valid:
            order_id = data['orderID']
            try:
                order = self.shop.get_order_for_id(order_id)
            except models.ObjectDoesNotExist:
                raise Http404('Order does not exist on this machine')
            transaction_id = data['PAYID']
            amount = data['amount']
            # Create an IPN transaction trace in the database
            ipn, created = PostfinanceIPN.objects.get_or_create(
                orderID=order_id,
                defaults=dict(
                    currency=data.get('currency', ''),
                    amount=data.get('amount', ''),
                    PM=data.get('PM', ''),
                    ACCEPTANCE=data.get('ACCEPTANCE', ''),
                    STATUS=data.get('STATUS', ''),
                    CARDNO=data.get('CARDNO', ''),
                    CN=data.get('CN', ''),
                    TRXDATE=data.get('TRXDATE', ''),
                    PAYID=data.get('PAYID', ''),
                    NCERROR=data.get('NCERROR', ''),
                    BRAND=data.get('BRAND', ''),
                    IPCTY=data.get('IPCTY', ''),
                    CCCTY=data.get('CCCTY', ''),
                    ECI=data.get('ECI', ''),
                    CVCCheck=data.get('CVCCheck', ''),
                    AAVCheck=data.get('AAVCheck', ''),
                    VC=data.get('VC', ''),
                    IP=data.get('IP', ''),
                    SHASIGN=data.get('SHASIGN', ''),
                )
            )
            if created:
                # This actually records the payment in the shop's database
                self.shop.confirm_payment(order, amount, transaction_id, self.backend_name)

            return True

        else:  # Checksum failed
            return False
