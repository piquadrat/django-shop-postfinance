#-*- coding: utf-8 -*-

from django.contrib import admin
from shop_postfinance.models import PostfinanceIPN


class PostFinanceIPNAdmin(admin.ModelAdmin):
    list_display = 'orderID', 'CN', 'amount', 'currency', 'PM', 'STATUS', 'created_at'
    list_filter = 'currency', 'STATUS', 'PM'
    date_hierarchy = 'created_at'
    readonly_fields = 'orderID', 'currency', 'amount', 'PM', 'ACCEPTANCE', 'STATUS', 'CARDNO', 'CN', 'TRXDATE', 'PAYID', 'NCERROR', 'BRAND', 'IPCTY', 'CCCTY', 'ECI', 'CVCCheck', 'AAVCheck', 'VC', 'IP', 'SHASIGN', 'updated_at', 'created_at'
    search_fields = 'orderID', 'CN'
admin.site.register(PostfinanceIPN, PostFinanceIPNAdmin)
