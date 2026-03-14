import re
import uuid
from django import forms
from .models import Order


def normalize_phone_number(raw: str) -> str:
    raw = (raw or "").strip()
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

    delivery_lat = forms.CharField(required=False, widget=forms.HiddenInput())
    delivery_lon = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_customer_name(self):
        value = (self.cleaned_data.get("customer_name") or "").strip()
        if len(value) < 2:
            raise forms.ValidationError("Укажите имя.")
        return value

    def clean_customer_phone(self):
        return normalize_phone_number(self.cleaned_data.get("customer_phone"))

    def clean(self):
        cleaned = super().clean()
        fulfillment = cleaned.get("fulfillment")

        if fulfillment == Order.Fulfillment.DELIVERY:
            if not (cleaned.get("address_line") or "").strip():
                self.add_error("address_line", "Для доставки нужен адрес.")

            lat = (cleaned.get("delivery_lat") or "").strip()
            lon = (cleaned.get("delivery_lon") or "").strip()

            if not lat or not lon:
                self.add_error("address_line", "Нужно выбрать точку доставки на карте или через адрес.")
        else:
            cleaned["address_line"] = ""
            cleaned["address_entrance"] = ""
            cleaned["address_floor"] = ""
            cleaned["address_apartment"] = ""
            cleaned["delivery_lat"] = ""
            cleaned["delivery_lon"] = ""

        return cleaned


class OrderLookupPhoneForm(forms.Form):
    phone = forms.CharField(
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "placeholder": "+7 (___) ___-__-__",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        ),
    )

    def clean_phone(self):
        return normalize_phone_number(self.cleaned_data.get("phone"))


class OrderLookupPublicIdForm(forms.Form):
    public_id = forms.CharField(
        max_length=64,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Например: 4e68f0e9-....",
                "autocomplete": "off",
            }
        ),
    )

    def clean_public_id(self):
        raw = (self.cleaned_data.get("public_id") or "").strip()

        try:
            return uuid.UUID(raw)
        except (ValueError, TypeError, AttributeError):
            raise forms.ValidationError("Укажите корректный идентификатор заказа.")
