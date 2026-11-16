"""Country-aware phone number validation using Google's libphonenumber metadata."""
from __future__ import annotations

import phonenumbers
from phonenumbers import PhoneNumberFormat


def country_options():
    """Return (display label, ISO region, calling code) for supported countries/territories."""
    import pycountry
    options = []
    for country in pycountry.countries:
        region = getattr(country, 'alpha_2', None)
        if not region:
            continue
        code = phonenumbers.country_code_for_region(region)
        if not code:
            continue
        options.append((f"{country.name} (+{code})", region, code))
    return sorted(options, key=lambda item: item[0].casefold())


def normalize_phone(national_number: str, region: str) -> str:
    """Validate a national-format number for the selected region and return E.164."""
    raw = str(national_number or '').strip()
    if not raw:
        return ''
    if not region or len(region) != 2 or not region.isalpha():
        raise ValueError('Please select a valid country/region for the phone number.')
    if raw.startswith('+'):
        raise ValueError('Enter the national phone number only; the country calling code is added automatically.')
    try:
        parsed = phonenumbers.parse(raw, region.upper())
    except phonenumbers.NumberParseException as exc:
        raise ValueError('Enter a valid phone number for the selected country.') from exc
    if not phonenumbers.is_valid_number_for_region(parsed, region.upper()):
        raise ValueError('This phone number is not valid for the selected country. Check its length and prefix.')
    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)


def national_from_e164(number: str, region: str) -> str:
    if not number:
        return ''
    try:
        parsed = phonenumbers.parse(str(number), None)
        if phonenumbers.is_valid_number(parsed) and phonenumbers.region_code_for_number(parsed) == region.upper():
            return str(parsed.national_number)
    except phonenumbers.NumberParseException:
        pass
    return str(number)
