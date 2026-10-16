# Part of Odossey. See LICENSE file for full copyright and licensing details.

# API roots. Paths are case-insensitive on PowerTranz side.
API_URLS = {
    'test': 'https://staging.ptranz.com/api/',
    'enabled': 'https://gateway.ptranz.com/api/',
}

# Currencies accepted by PowerTranz in the region (BAC Credomatic / FAC). Panama uses USD.
SUPPORTED_CURRENCIES = [
    'USD', 'PAB', 'CRC', 'GTQ', 'HNL', 'NIO', 'DOP', 'JMD', 'TTD', 'BBD', 'XCD', 'KYD', 'BSD', 'BZD',
    'EUR',
]

# The codes of the payment methods to activate when PowerTranz is activated.
DEFAULT_PAYMENT_METHOD_CODES = {
    # Primary payment methods.
    'card',
    # Brand payment methods.
    'visa',
    'mastercard',
    'amex',
}

# Mapping of `CardBrand` values (lowercased) returned by PowerTranz to Odoo payment method codes.
PAYMENT_METHODS_MAPPING = {
    'visa': 'visa',
    'mastercard': 'mastercard',
    'master card': 'mastercard',
    'amex': 'amex',
    'american express': 'amex',
    'discover': 'discover',
    'jcb': 'jcb',
}

# ISO response code meaning "approved".
APPROVED_ISO_CODE = '00'

# ISO response code of a successful SPI preprocessing (RedirectData + SpiToken returned).
SPI_PREPROCESSING_OK = 'SP4'

# HPP callback codes (these are not the payment result, only the card collection / 3DS stage).
HPP_DATA_COLLECTED = 'HP0'  # Card data collected on a non-3DS hosted page.
THREEDS_COMPLETE = '3D0'  # 3DS complete; check AuthenticationStatus.
THREEDS_NOT_SUPPORTED = ('3D1', 'SP1')  # The card is not enrolled in 3DS2.

# 3DS AuthenticationStatus values that allow completing the payment with liability shift.
THREEDS_AUTHENTICATED_STATUSES = ('Y', 'A')
THREEDS_UNAVAILABLE_STATUS = 'U'

# ChallengeWindowSize 5 = full page, as the hosted page is shown as a top-level document.
CHALLENGE_WINDOW_SIZE_FULL_PAGE = 5

# PowerTranz TransactionType codes.
TRANSACTION_TYPE_SALE = 2
TRANSACTION_TYPE_REFUND = 5
