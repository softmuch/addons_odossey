# Part of Odossey Travel. See LICENSE file for full copyright and licensing details.
"""Parsers for identity documents read by barcode / MRZ scanners.

Supported inputs:

* Argentine DNI PDF417 barcode (front side):
    - new format (2012+)
    - old format (2009-2012, starts with ``@``)
    - electronic DNI 2026 (unofficial, contains a signed JWT that is dropped)
* ICAO 9303 machine readable zones:
    - TD3 (passports, 2 lines x 44 chars)
    - TD1 (ID cards, 3 lines x 30 chars, e.g. Argentine DNI back side)

The module is pure Python (stdlib only) apart from the lazy translation
helper, so it can be unit-tested without a database.
"""

import re
from datetime import date

from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__, default_lang='en_US')

__all__ = ['DocumentParseError', 'parse_document', 'ISO3_TO_ISO2', 'mrz_check_digit']


class DocumentParseError(ValueError):
    """Raised when a scanned document cannot be parsed.

    The first argument is a lazy-translated string, so ``str(error)`` returns
    the message in the current user language.
    """

    def __str__(self):
        return str(self.args[0]) if self.args else ''


# ---------------------------------------------------------------------------
# Country codes
# ---------------------------------------------------------------------------

# Full ISO 3166-1 alpha-3 -> alpha-2 table
ISO3_TO_ISO2 = {
    'ABW': 'AW', 'AFG': 'AF', 'AGO': 'AO', 'AIA': 'AI', 'ALA': 'AX', 'ALB': 'AL',
    'AND': 'AD', 'ARE': 'AE', 'ARG': 'AR', 'ARM': 'AM', 'ASM': 'AS', 'ATA': 'AQ',
    'ATF': 'TF', 'ATG': 'AG', 'AUS': 'AU', 'AUT': 'AT', 'AZE': 'AZ', 'BDI': 'BI',
    'BEL': 'BE', 'BEN': 'BJ', 'BES': 'BQ', 'BFA': 'BF', 'BGD': 'BD', 'BGR': 'BG',
    'BHR': 'BH', 'BHS': 'BS', 'BIH': 'BA', 'BLM': 'BL', 'BLR': 'BY', 'BLZ': 'BZ',
    'BMU': 'BM', 'BOL': 'BO', 'BRA': 'BR', 'BRB': 'BB', 'BRN': 'BN', 'BTN': 'BT',
    'BVT': 'BV', 'BWA': 'BW', 'CAF': 'CF', 'CAN': 'CA', 'CCK': 'CC', 'CHE': 'CH',
    'CHL': 'CL', 'CHN': 'CN', 'CIV': 'CI', 'CMR': 'CM', 'COD': 'CD', 'COG': 'CG',
    'COK': 'CK', 'COL': 'CO', 'COM': 'KM', 'CPV': 'CV', 'CRI': 'CR', 'CUB': 'CU',
    'CUW': 'CW', 'CXR': 'CX', 'CYM': 'KY', 'CYP': 'CY', 'CZE': 'CZ', 'DEU': 'DE',
    'DJI': 'DJ', 'DMA': 'DM', 'DNK': 'DK', 'DOM': 'DO', 'DZA': 'DZ', 'ECU': 'EC',
    'EGY': 'EG', 'ERI': 'ER', 'ESH': 'EH', 'ESP': 'ES', 'EST': 'EE', 'ETH': 'ET',
    'FIN': 'FI', 'FJI': 'FJ', 'FLK': 'FK', 'FRA': 'FR', 'FRO': 'FO', 'FSM': 'FM',
    'GAB': 'GA', 'GBR': 'GB', 'GEO': 'GE', 'GGY': 'GG', 'GHA': 'GH', 'GIB': 'GI',
    'GIN': 'GN', 'GLP': 'GP', 'GMB': 'GM', 'GNB': 'GW', 'GNQ': 'GQ', 'GRC': 'GR',
    'GRD': 'GD', 'GRL': 'GL', 'GTM': 'GT', 'GUF': 'GF', 'GUM': 'GU', 'GUY': 'GY',
    'HKG': 'HK', 'HMD': 'HM', 'HND': 'HN', 'HRV': 'HR', 'HTI': 'HT', 'HUN': 'HU',
    'IDN': 'ID', 'IMN': 'IM', 'IND': 'IN', 'IOT': 'IO', 'IRL': 'IE', 'IRN': 'IR',
    'IRQ': 'IQ', 'ISL': 'IS', 'ISR': 'IL', 'ITA': 'IT', 'JAM': 'JM', 'JEY': 'JE',
    'JOR': 'JO', 'JPN': 'JP', 'KAZ': 'KZ', 'KEN': 'KE', 'KGZ': 'KG', 'KHM': 'KH',
    'KIR': 'KI', 'KNA': 'KN', 'KOR': 'KR', 'KWT': 'KW', 'LAO': 'LA', 'LBN': 'LB',
    'LBR': 'LR', 'LBY': 'LY', 'LCA': 'LC', 'LIE': 'LI', 'LKA': 'LK', 'LSO': 'LS',
    'LTU': 'LT', 'LUX': 'LU', 'LVA': 'LV', 'MAC': 'MO', 'MAF': 'MF', 'MAR': 'MA',
    'MCO': 'MC', 'MDA': 'MD', 'MDG': 'MG', 'MDV': 'MV', 'MEX': 'MX', 'MHL': 'MH',
    'MKD': 'MK', 'MLI': 'ML', 'MLT': 'MT', 'MMR': 'MM', 'MNE': 'ME', 'MNG': 'MN',
    'MNP': 'MP', 'MOZ': 'MZ', 'MRT': 'MR', 'MSR': 'MS', 'MTQ': 'MQ', 'MUS': 'MU',
    'MWI': 'MW', 'MYS': 'MY', 'MYT': 'YT', 'NAM': 'NA', 'NCL': 'NC', 'NER': 'NE',
    'NFK': 'NF', 'NGA': 'NG', 'NIC': 'NI', 'NIU': 'NU', 'NLD': 'NL', 'NOR': 'NO',
    'NPL': 'NP', 'NRU': 'NR', 'NZL': 'NZ', 'OMN': 'OM', 'PAK': 'PK', 'PAN': 'PA',
    'PCN': 'PN', 'PER': 'PE', 'PHL': 'PH', 'PLW': 'PW', 'PNG': 'PG', 'POL': 'PL',
    'PRI': 'PR', 'PRK': 'KP', 'PRT': 'PT', 'PRY': 'PY', 'PSE': 'PS', 'PYF': 'PF',
    'QAT': 'QA', 'REU': 'RE', 'ROU': 'RO', 'RUS': 'RU', 'RWA': 'RW', 'SAU': 'SA',
    'SDN': 'SD', 'SEN': 'SN', 'SGP': 'SG', 'SGS': 'GS', 'SHN': 'SH', 'SJM': 'SJ',
    'SLB': 'SB', 'SLE': 'SL', 'SLV': 'SV', 'SMR': 'SM', 'SOM': 'SO', 'SPM': 'PM',
    'SRB': 'RS', 'SSD': 'SS', 'STP': 'ST', 'SUR': 'SR', 'SVK': 'SK', 'SVN': 'SI',
    'SWE': 'SE', 'SWZ': 'SZ', 'SXM': 'SX', 'SYC': 'SC', 'SYR': 'SY', 'TCA': 'TC',
    'TCD': 'TD', 'TGO': 'TG', 'THA': 'TH', 'TJK': 'TJ', 'TKL': 'TK', 'TKM': 'TM',
    'TLS': 'TL', 'TON': 'TO', 'TTO': 'TT', 'TUN': 'TN', 'TUR': 'TR', 'TUV': 'TV',
    'TWN': 'TW', 'TZA': 'TZ', 'UGA': 'UG', 'UKR': 'UA', 'UMI': 'UM', 'URY': 'UY',
    'USA': 'US', 'UZB': 'UZ', 'VAT': 'VA', 'VCT': 'VC', 'VEN': 'VE', 'VGB': 'VG',
    'VIR': 'VI', 'VNM': 'VN', 'VUT': 'VU', 'WLF': 'WF', 'WSM': 'WS', 'YEM': 'YE',
    'ZAF': 'ZA', 'ZMB': 'ZM', 'ZWE': 'ZW',
}

# ICAO 9303 specific codes (used in MRZ) that are not ISO 3166-1 alpha-3
MRZ_SPECIAL_CODES = {
    'D': 'DE',      # Germany
    'GBD': 'GB',    # British Overseas Territories Citizen
    'GBN': 'GB',    # British National (Overseas)
    'GBO': 'GB',    # British Overseas Citizen
    'GBP': 'GB',    # British Protected Person
    'GBS': 'GB',    # British Subject
    'RKS': 'XK',    # Kosovo
    'XKX': 'XK',    # Kosovo (alternative)
}


def _iso2(code):
    if not code:
        return None
    return MRZ_SPECIAL_CODES.get(code) or ISO3_TO_ISO2.get(code)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GENDER_MAP = {'M': 'male', 'F': 'female', 'X': 'other'}

_MRZ_WEIGHTS = (7, 3, 1)
_CUIL_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
_DATE4_RE = re.compile(r'^(\d{2})/(\d{2})/(\d{4})$')
_DATE2_RE = re.compile(r'^(\d{2})/(\d{2})/(\d{2})$')
_MRZ_CHARS_RE = re.compile(r'^[A-Z0-9<]+$')
_KEYBOARD_HINT = _lt(
    "Check that the scanner keyboard layout matches the operating system "
    "keyboard layout (e.g. both set to Spanish or both to US English)."
)


def _empty_result():
    return {
        'doc_type': None,
        'last_name': None,
        'first_names': None,
        'gender': None,
        'dni_number': None,
        'dni_tramite': None,
        'dni_ejemplar': None,
        'cuil': None,
        'birthdate': None,
        'issue_date': None,
        'expiry_date': None,
        'document_number': None,
        'passport_number': None,
        'nationality_code': None,
        'nationality_code2': None,
        'issuing_country_code': None,
        'issuing_country_code2': None,
        'warnings': [],
        'raw_format_note': None,
    }


def _title(value):
    value = ' '.join((value or '').split())
    return value.title() if value else None


def _digits(value):
    value = re.sub(r'\D', '', value or '')
    return value.lstrip('0') or (value and '0') or None


def _raw_digits(value):
    """Digits keeping the leading zeros (procedure numbers have a fixed length)."""
    return re.sub(r'\D', '', value or '') or None


def _two_digit_year_birth(yy):
    current = date.today().year % 100
    return (1900 if yy > current else 2000) + yy


def _make_date(year, month, day, label):
    try:
        return date(year, month, day)
    except ValueError:
        raise DocumentParseError(_lt("Invalid %(label)s date in the document.", label=label)) from None


def _parse_date4(value, label):
    match = _DATE4_RE.match(value or '')
    if not match:
        raise DocumentParseError(_lt(
            "Invalid %(label)s date %(value)r in the document (expected dd/mm/yyyy).",
            label=label, value=value,
        ))
    day, month, year = map(int, match.groups())
    return _make_date(year, month, day, label)


def _parse_date2(value, label, birth=False):
    match = _DATE2_RE.match(value or '')
    if not match:
        raise DocumentParseError(_lt(
            "Invalid %(label)s date %(value)r in the document (expected dd/mm/yy).",
            label=label, value=value,
        ))
    day, month, yy = map(int, match.groups())
    year = _two_digit_year_birth(yy) if birth else 2000 + yy
    return _make_date(year, month, day, label)


def mrz_check_digit(value):
    """ICAO 9303 check digit (weights 7,3,1; 0-9, A-Z=10-35, '<'=0)."""
    total = 0
    for i, char in enumerate(value):
        if char.isdigit():
            num = int(char)
        elif 'A' <= char <= 'Z':
            num = ord(char) - 55
        elif char == '<':
            num = 0
        else:
            raise ValueError(char)
        total += num * _MRZ_WEIGHTS[i % 3]
    return total % 10


def _mrz_check_ok(value, check_char):
    if check_char == '<':
        check = 0
    elif check_char.isdigit():
        check = int(check_char)
    else:
        return False
    return mrz_check_digit(value) == check


def cuil_check_digit(base10):
    """Return the CUIL/CUIT mod 11 check digit for a 10-digit string, or None if not computable."""
    if len(base10) != 10 or not base10.isdigit():
        return None
    remainder = sum(int(d) * w for d, w in zip(base10, _CUIL_WEIGHTS)) % 11
    check = 11 - remainder
    if check == 11:
        return 0
    if check == 10:
        return None
    return check


# ---------------------------------------------------------------------------
# PDF417 (Argentine DNI front side)
# ---------------------------------------------------------------------------

def _set_gender(result, value):
    result['gender'] = GENDER_MAP.get((value or '').strip().upper()[:1])


def _set_cuil(result, cuil3, dni):
    cuil3 = re.sub(r'\D', '', cuil3 or '')
    if not cuil3:
        return
    if len(cuil3) != 3 or not dni or len(dni) > 8:
        result['warnings'].append(str(_lt("CUIL data in the barcode is malformed; CUIL ignored.")))
        return
    prefix, check = cuil3[:2], int(cuil3[2])
    base = prefix + dni.zfill(8)
    if cuil_check_digit(base) != check:
        result['warnings'].append(str(_lt("CUIL check digit is invalid; CUIL ignored.")))
        return
    result['cuil'] = '%s-%s-%s' % (prefix, dni.zfill(8), check)


def _parse_dni_new(fields, result):
    # tramite@apellido@nombres@sexo@dni@ejemplar@f_nac@f_emision[@cuil3]
    result['doc_type'] = 'dni_new'
    result['dni_tramite'] = _raw_digits(fields[0])
    result['last_name'] = _title(fields[1])
    result['first_names'] = _title(fields[2])
    _set_gender(result, fields[3])
    result['dni_number'] = _digits(fields[4])
    result['dni_ejemplar'] = fields[5].upper() or None
    result['birthdate'] = _parse_date4(fields[6], _lt("birth"))
    result['issue_date'] = _parse_date4(fields[7], _lt("issue"))
    result['nationality_code'] = 'ARG'
    result['issuing_country_code'] = 'ARG'
    if len(fields) > 8:
        _set_cuil(result, fields[8], result['dni_number'])


def _parse_dni_old(fields, result):
    # @dni@ejemplar@?@apellido@nombres@nacionalidad@f_nac@sexo@f_emision@tramite@?@f_venc@...
    result['doc_type'] = 'dni_old'
    result['dni_number'] = _digits(fields[1])
    result['dni_ejemplar'] = fields[2].upper() or None
    result['last_name'] = _title(fields[4])
    result['first_names'] = _title(fields[5])
    nationality = fields[6].upper()
    if nationality.startswith('ARG'):
        result['nationality_code'] = 'ARG'
    elif len(nationality) == 3 and nationality in ISO3_TO_ISO2:
        result['nationality_code'] = nationality
    result['birthdate'] = _parse_date4(fields[7], _lt("birth"))
    _set_gender(result, fields[8])
    result['issue_date'] = _parse_date4(fields[9], _lt("issue"))
    result['dni_tramite'] = _raw_digits(fields[10])
    if len(fields) > 12 and fields[12]:
        try:
            result['expiry_date'] = _parse_date4(fields[12], _lt("expiry"))
        except DocumentParseError:
            result['warnings'].append(str(_lt("Expiry date in the barcode could not be read.")))
    result['issuing_country_code'] = 'ARG'


def _parse_dni_electronic(fields, result):
    # tramite@apellido@nombres@dni@ejemplar@dd/mm/yy@dd/mm/yy@<JWT>
    result['doc_type'] = 'dni_electronic'
    result['dni_tramite'] = _raw_digits(fields[0])
    result['last_name'] = _title(fields[1])
    result['first_names'] = _title(fields[2])
    result['dni_number'] = _digits(fields[3])
    result['dni_ejemplar'] = fields[4].upper() or None
    result['birthdate'] = _parse_date2(fields[5], _lt("birth"), birth=True)
    result['issue_date'] = _parse_date2(fields[6], _lt("issue"))
    result['nationality_code'] = 'ARG'
    result['issuing_country_code'] = 'ARG'
    result['raw_format_note'] = str(_lt(
        "Electronic DNI (unofficial format): gender is not encoded; digital signature discarded."
    ))


def _unparseable_pdf417():
    return DocumentParseError(_lt(
        "The scanned barcode is not a recognised Argentine DNI format. %(hint)s",
        hint=_KEYBOARD_HINT,
    ))


def _parse_pdf417(text):
    result = _empty_result()
    text = text.strip()
    if '@' not in text and text.count('"') >= 7:
        text = text.replace('"', '@')
        result['warnings'].append(str(_lt(
            "The barcode used '\"' instead of '@' as separator: the scanner keyboard "
            "layout probably does not match the system layout."
        )))
    if '@' not in text:
        raise _unparseable_pdf417()
    fields = [f.strip() for f in re.sub(r'[\r\n]+', '', text).split('@')]

    def is_date4(value):
        return bool(_DATE4_RE.match(value))

    def is_date2(value):
        return bool(_DATE2_RE.match(value))

    if fields[0] == '' and len(fields) >= 13 and fields[1][:1].isalnum() and is_date4(fields[7]):
        _parse_dni_old(fields, result)
    elif (len(fields) >= 8 and any(f.startswith('eyJ') for f in fields[7:])
          and fields[3].isdigit() and is_date2(fields[5]) and is_date2(fields[6])):
        _parse_dni_electronic(fields, result)
    elif (8 <= len(fields) <= 10 and fields[3].upper() in GENDER_MAP
          and fields[4].isdigit() and is_date4(fields[6]) and is_date4(fields[7])):
        _parse_dni_new(fields, result)
    else:
        raise _unparseable_pdf417()
    if not result['dni_number']:
        raise DocumentParseError(_lt("The DNI number could not be read from the barcode."))
    return result


# ---------------------------------------------------------------------------
# MRZ (ICAO 9303)
# ---------------------------------------------------------------------------

def _normalize_mrz(text):
    text = (text or '').upper().replace('«', '<')
    text = re.sub(r'[ \t]+', '', text)
    lines = [line for line in re.split(r'[\r\n]+', text) if line]
    return lines


def _split_mrz_lines(text, warnings):
    lines = _normalize_mrz(text)
    if len(lines) == 1:
        single = lines[0]
        if len(single) == 88:
            lines = [single[:44], single[44:]]
        elif len(single) == 90:
            lines = [single[:30], single[30:60], single[60:]]
    if len(lines) == 2:
        fmt, width = 'td3', 44
    elif len(lines) == 3:
        fmt, width = 'td1', 30
    else:
        raise DocumentParseError(_lt(
            "The MRZ must have 2 lines of 44 characters (passport) or 3 lines of 30 characters (ID card)."
        ))
    fixed = []
    for line in lines:
        if len(line) > width or len(line) < width - 6:
            raise DocumentParseError(_lt(
                "Invalid MRZ line length: %(length)s characters found, %(width)s expected.",
                length=len(line), width=width,
            ))
        if len(line) < width:
            warnings.append(str(_lt("An MRZ line was shorter than expected and was padded with fillers.")))
            line = line.ljust(width, '<')
        if not _MRZ_CHARS_RE.match(line):
            raise DocumentParseError(_lt("The MRZ contains invalid characters (only A-Z, 0-9 and '<' allowed)."))
        fixed.append(line)
    return fmt, fixed


def _mrz_names(value, result):
    value = value.rstrip('<')
    if '<<' in value:
        last, first = value.split('<<', 1)
    else:
        last, first = value, ''
    result['last_name'] = _title(last.replace('<', ' '))
    result['first_names'] = _title(first.replace('<', ' '))


def _mrz_date(value, label, expiry=False):
    if not value.isdigit():
        raise DocumentParseError(_lt("Invalid %(label)s date in the MRZ.", label=label))
    yy, month, day = int(value[:2]), int(value[2:4]), int(value[4:6])
    year = 2000 + yy if expiry else _two_digit_year_birth(yy)
    return _make_date(year, month, day, label)


def _require_check(value, check_char, label):
    if not _mrz_check_ok(value, check_char):
        raise DocumentParseError(_lt(
            "MRZ check digit failed for the %(label)s. Please scan the document again.",
            label=label,
        ))


def _optional_check(value, check_char, result):
    if not _mrz_check_ok(value, check_char):
        result['warnings'].append(str(_lt("MRZ check digit failed for the optional data field.")))


def _dni_from_optional(value):
    for chunk in re.findall(r'\d+', value or ''):
        if 7 <= len(chunk) <= 8:
            return chunk.lstrip('0') or None
    return None


def _country(value):
    return value.replace('<', '') or None


def _parse_td3(lines, result):
    l1, l2 = lines
    result['doc_type'] = 'mrz_td3'
    if l1[0] != 'P':
        result['warnings'].append(str(_lt("The MRZ document code is not a passport code.")))
    result['issuing_country_code'] = _country(l1[2:5])
    _mrz_names(l1[5:44], result)

    number, number_check = l2[0:9], l2[9]
    birth, birth_check = l2[13:19], l2[19]
    expiry, expiry_check = l2[21:27], l2[27]
    optional, optional_check = l2[28:42], l2[42]
    _require_check(number, number_check, _lt("document number"))
    _require_check(birth, birth_check, _lt("birth date"))
    _require_check(expiry, expiry_check, _lt("expiry date"))
    _require_check(l2[0:10] + l2[13:20] + l2[21:43], l2[43], _lt("whole MRZ (composite)"))
    _optional_check(optional, optional_check, result)

    result['document_number'] = result['passport_number'] = number.replace('<', '') or None
    result['nationality_code'] = _country(l2[10:13])
    result['birthdate'] = _mrz_date(birth, _lt("birth"))
    _set_gender(result, l2[20])
    result['expiry_date'] = _mrz_date(expiry, _lt("expiry"), expiry=True)
    if 'ARG' in (result['nationality_code'], result['issuing_country_code']):
        result['dni_number'] = _dni_from_optional(optional)


def _parse_td1(lines, result):
    l1, l2, l3 = lines
    result['doc_type'] = 'mrz_td1'
    result['issuing_country_code'] = _country(l1[2:5])

    number, number_check, optional1 = l1[5:14], l1[14], l1[15:30]
    if number_check == '<' and optional1.strip('<'):
        # Long document number: continues in the optional field, followed by its check digit
        extension = optional1.split('<', 1)[0]
        number, number_check = number + extension[:-1], extension[-1]
        optional1 = optional1[len(extension):]
    birth, birth_check = l2[0:6], l2[6]
    expiry, expiry_check = l2[8:14], l2[14]
    _require_check(number, number_check, _lt("document number"))
    _require_check(birth, birth_check, _lt("birth date"))
    _require_check(expiry, expiry_check, _lt("expiry date"))
    _require_check(l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29], l2[29], _lt("whole MRZ (composite)"))

    document_number = number.replace('<', '') or None
    result['document_number'] = document_number
    result['birthdate'] = _mrz_date(birth, _lt("birth"))
    _set_gender(result, l2[7])
    result['expiry_date'] = _mrz_date(expiry, _lt("expiry"), expiry=True)
    result['nationality_code'] = _country(l2[15:18])
    _mrz_names(l3, result)
    if 'ARG' in (result['nationality_code'], result['issuing_country_code']):
        if document_number and document_number.isdigit() and 7 <= len(document_number) <= 8:
            result['dni_number'] = document_number.lstrip('0') or None
        else:
            result['dni_number'] = _dni_from_optional(optional1) or _dni_from_optional(l2[18:29])


def _parse_mrz(text):
    result = _empty_result()
    fmt, lines = _split_mrz_lines(text, result['warnings'])
    if fmt == 'td3':
        _parse_td3(lines, result)
    else:
        _parse_td1(lines, result)
    return result


def _looks_like_mrz(text):
    lines = _normalize_mrz(text)
    joined = ''.join(lines)
    return bool(joined) and bool(_MRZ_CHARS_RE.match(joined)) and '<' in joined and len(joined) >= 80


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_document(raw, doc_type='auto'):
    """Parse a scanned identity document.

    :param str raw: raw scanner output (PDF417 barcode content or MRZ text)
    :param str doc_type: ``'auto'`` (detect), ``'dni'`` (force Argentine DNI
        PDF417) or ``'mrz'`` (force ICAO MRZ)
    :return: dict with the parsed values (``None`` when unknown)
    :raise DocumentParseError: when the input cannot be parsed or a mandatory
        check digit fails
    """
    if doc_type not in ('auto', 'dni', 'mrz'):
        raise DocumentParseError(_lt("Unknown document type %(doc_type)r.", doc_type=doc_type))
    text = (raw or '').strip() if isinstance(raw, str) else ''
    if not text:
        raise DocumentParseError(_lt("No document data was received from the scanner."))
    if doc_type == 'dni':
        result = _parse_pdf417(text)
    elif doc_type == 'mrz':
        result = _parse_mrz(text)
    elif '@' in text or text.count('"') >= 7:
        result = _parse_pdf417(text)
    elif _looks_like_mrz(text):
        result = _parse_mrz(text)
    else:
        raise _unrecognised_document()
    result['nationality_code2'] = _iso2(result['nationality_code'])
    result['issuing_country_code2'] = _iso2(result['issuing_country_code'])
    return result


def _unrecognised_document():
    return DocumentParseError(_lt(
        "The scanned data is neither an Argentine DNI barcode nor a passport/ID card MRZ. %(hint)s",
        hint=_KEYBOARD_HINT,
    ))
