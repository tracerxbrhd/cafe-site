import re
from django import forms
from .models import Order


class CheckoutForm(forms.Form):
    fulfillment = forms.ChoiceField(
        choices=Order.Fulfillment.choices,
        initial=Order.Fulfillment.DELIVERY,
    )
    customer_name = forms.CharField(max_length=120)
    # customer_phone = forms.CharField(max_length=32)
    customer_phone = forms.CharField(
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "placeholder": "+7 (___) ___-__-__",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        ),
    )

    address_line = forms.CharField(max_length=255, required=False)
    address_entrance = forms.CharField(max_length=20, required=False)
    address_floor = forms.CharField(max_length=20, required=False)
    address_apartment = forms.CharField(max_length=20, required=False)

    customer_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean_customer_name(self):
        value = (self.cleaned_data.get("customer_name") or "").strip()
        if len(value) < 2:
            raise forms.ValidationError("Укажите имя.")
        return value

    def clean_customer_phone(self):
        raw = (self.cleaned_data.get("customer_phone") or "").strip()
        digits = re.sub(r"\D", "", raw)

        if not digits:
            raise forms.ValidationError("Укажите телефон.")

        if digits.startswith("8") and len(digits) == 11:
            digits = "7" + digits[1:]

        if len(digits) == 10:
            digits = "7" + digits

        if len(digits) != 11 or not digits.startswith("7"):
            raise forms.ValidationError("Укажите корректный номер телефона.")

        return f"+{digits}"

    def clean(self):
        cleaned = super().clean()
        fulfillment = cleaned.get("fulfillment")

        if fulfillment == Order.Fulfillment.DELIVERY:
            if not (cleaned.get("address_line") or "").strip():
                self.add_error("address_line", "Для доставки нужен адрес.")
        else:
            cleaned["address_line"] = ""
            cleaned["address_entrance"] = ""
            cleaned["address_floor"] = ""
            cleaned["address_apartment"] = ""

        return cleaned