# Part of Odossey Travel. See LICENSE file for full copyright and licensing details.
# All personal data below is FAKE (test fixtures only).
from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.odossey_travel.tools.id_parsers import (
    DocumentParseError,
    ISO3_TO_ISO2,
    cuil_check_digit,
    mrz_check_digit,
    parse_document,
)

DNI_NEW = '00123456789@PEREZ@JUAN CARLOS@M@30123456@A@15/03/1985@10/01/2015@203'
DNI_NEW_NO_CUIL = '00123456789@GOMEZ@ANA MARIA@F@30123456@B@01/12/1990@20/06/2018'
DNI_OLD = (
    '@30123456    @A@1@PEREZ@JUAN CARLOS@ARGENTINA@15/03/1985@M@10/01/2010'
    '@00123456789@7777@10/01/2025@123@@'
)
FAKE_JWT = 'eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.ZmFrZXNpZw'
DNI_ELECTRONIC = '00123456789@PEREZ@JUAN CARLOS@30123456@C@15/03/85@10/01/26@' + FAKE_JWT

TD3_SPECIMEN = (
    'P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n'
    'L898902C36UTO7408122F1204159ZE184226B<<<<<10'
)
TD3_ARG = (
    'P<ARGPEREZ<<JUAN<CARLOS<<<<<<<<<<<<<<<<<<<<<\n'
    'AAA1234565ARG8503150M300101930123456<<<<<<24'
)
TD1_ARG = (
    'IDARG30123456<2<<<<<<<<<<<<<<<\n'
    '8503150M3503155ARG<<<<<<<<<<<8\n'
    'PEREZ<<JUAN<CARLOS<<<<<<<<<<<<'
)
TD1_ESP = (
    'IDESPABC1234560<<<<<<<<<<<<<<<\n'
    '9207042F3101012ESP<<<<<<<<<<<0\n'
    'GARCIA<LOPEZ<<MARIA<<<<<<<<<<<'
)


@tagged('post_install', '-at_install')
class TestIdParsers(TransactionCase):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def test_check_digit_helpers(self):
        self.assertEqual(mrz_check_digit('L898902C3'), 6)
        self.assertEqual(mrz_check_digit('740812'), 2)
        self.assertEqual(mrz_check_digit('<<<<<'), 0)
        self.assertEqual(cuil_check_digit('2030123456'), 3)
        self.assertEqual(cuil_check_digit('2730123456'), 8)
        self.assertIsNone(cuil_check_digit('123'))

    def test_iso_table(self):
        self.assertGreaterEqual(len(ISO3_TO_ISO2), 249)
        self.assertEqual(ISO3_TO_ISO2['ARG'], 'AR')
        self.assertEqual(ISO3_TO_ISO2['ESP'], 'ES')
        self.assertEqual(ISO3_TO_ISO2['GBR'], 'GB')
        self.assertEqual(ISO3_TO_ISO2['DEU'], 'DE')

    # ------------------------------------------------------------------
    # DNI PDF417
    # ------------------------------------------------------------------
    def test_dni_new(self):
        res = parse_document(DNI_NEW)
        self.assertEqual(res['doc_type'], 'dni_new')
        self.assertEqual(res['last_name'], 'Perez')
        self.assertEqual(res['first_names'], 'Juan Carlos')
        self.assertEqual(res['gender'], 'male')
        self.assertEqual(res['dni_number'], '30123456')
        self.assertEqual(res['dni_tramite'], '00123456789')
        self.assertEqual(res['dni_ejemplar'], 'A')
        self.assertEqual(res['birthdate'], date(1985, 3, 15))
        self.assertEqual(res['issue_date'], date(2015, 1, 10))
        self.assertIsNone(res['expiry_date'])
        self.assertEqual(res['cuil'], '20-30123456-3')
        self.assertEqual(res['nationality_code'], 'ARG')
        self.assertEqual(res['issuing_country_code2'], 'AR')
        self.assertEqual(res['warnings'], [])

    def test_dni_new_without_cuil_and_female(self):
        res = parse_document(DNI_NEW_NO_CUIL, doc_type='dni')
        self.assertEqual(res['doc_type'], 'dni_new')
        self.assertEqual(res['gender'], 'female')
        self.assertEqual(res['first_names'], 'Ana Maria')
        self.assertIsNone(res['cuil'])
        self.assertEqual(res['warnings'], [])

    def test_dni_new_gender_x(self):
        res = parse_document(DNI_NEW.replace('@M@', '@X@'))
        self.assertEqual(res['gender'], 'other')

    def test_dni_new_invalid_cuil(self):
        res = parse_document(DNI_NEW[:-3] + '205')
        self.assertIsNone(res['cuil'])
        self.assertEqual(len(res['warnings']), 1)
        self.assertEqual(res['dni_number'], '30123456')

    def test_dni_new_whitespace_and_newline(self):
        res = parse_document('  \n' + DNI_NEW + '\r\n')
        self.assertEqual(res['dni_number'], '30123456')

    def test_dni_keyboard_wedge_quotes(self):
        res = parse_document(DNI_NEW.replace('@', '"'))
        self.assertEqual(res['doc_type'], 'dni_new')
        self.assertEqual(res['dni_number'], '30123456')
        self.assertEqual(res['cuil'], '20-30123456-3')
        self.assertEqual(len(res['warnings']), 1)

    def test_dni_old(self):
        res = parse_document(DNI_OLD)
        self.assertEqual(res['doc_type'], 'dni_old')
        self.assertEqual(res['dni_number'], '30123456')
        self.assertEqual(res['dni_ejemplar'], 'A')
        self.assertEqual(res['last_name'], 'Perez')
        self.assertEqual(res['first_names'], 'Juan Carlos')
        self.assertEqual(res['nationality_code'], 'ARG')
        self.assertEqual(res['nationality_code2'], 'AR')
        self.assertEqual(res['birthdate'], date(1985, 3, 15))
        self.assertEqual(res['gender'], 'male')
        self.assertEqual(res['issue_date'], date(2010, 1, 10))
        self.assertEqual(res['dni_tramite'], '00123456789')
        self.assertEqual(res['expiry_date'], date(2025, 1, 10))

    def test_dni_electronic(self):
        res = parse_document(DNI_ELECTRONIC)
        self.assertEqual(res['doc_type'], 'dni_electronic')
        self.assertEqual(res['dni_number'], '30123456')
        self.assertEqual(res['dni_tramite'], '00123456789')
        self.assertEqual(res['dni_ejemplar'], 'C')
        self.assertIsNone(res['gender'])
        self.assertEqual(res['birthdate'], date(1985, 3, 15))
        self.assertEqual(res['issue_date'], date(2026, 1, 10))
        for value in res.values():
            self.assertNotIn('eyJ', str(value))

    def test_dni_electronic_birth_century_pivot(self):
        current_yy = date.today().year % 100
        future_yy = (current_yy + 1) % 100
        raw = DNI_ELECTRONIC.replace('15/03/85', '15/03/%02d' % future_yy)
        res = parse_document(raw)
        self.assertEqual(res['birthdate'].year, 1900 + future_yy)
        raw = DNI_ELECTRONIC.replace('15/03/85', '15/03/%02d' % current_yy)
        res = parse_document(raw)
        self.assertEqual(res['birthdate'].year, 2000 + current_yy)

    def test_dni_errors(self):
        for raw in (
            '',
            '   ',
            'hello world',
            '00123456789@PEREZ@JUAN',
            '00123456789@PEREZ@JUAN@M@30123456@A@1985-03-15@10/01/2015@203',
            '00123456789@PEREZ@JUAN@M@30123456@A@31/02/1985@10/01/2015@203',
        ):
            with self.subTest(raw=raw), self.assertRaises(DocumentParseError) as ctx:
                parse_document(raw)
            self.assertTrue(str(ctx.exception))
        with self.assertRaises(DocumentParseError):
            parse_document(TD3_SPECIMEN, doc_type='dni')
        with self.assertRaises(DocumentParseError):
            parse_document(DNI_NEW, doc_type='passport')

    def test_unparseable_mentions_keyboard(self):
        with self.assertRaises(DocumentParseError) as ctx:
            parse_document('00123456789@PEREZ@JUAN')
        self.assertIn('keyboard', str(ctx.exception).lower())

    # ------------------------------------------------------------------
    # MRZ
    # ------------------------------------------------------------------
    def test_mrz_td3_icao_specimen(self):
        res = parse_document(TD3_SPECIMEN)
        self.assertEqual(res['doc_type'], 'mrz_td3')
        self.assertEqual(res['last_name'], 'Eriksson')
        self.assertEqual(res['first_names'], 'Anna Maria')
        self.assertEqual(res['passport_number'], 'L898902C3')
        self.assertEqual(res['document_number'], 'L898902C3')
        self.assertEqual(res['issuing_country_code'], 'UTO')
        self.assertEqual(res['nationality_code'], 'UTO')
        self.assertIsNone(res['nationality_code2'])
        self.assertEqual(res['birthdate'], date(1974, 8, 12))
        self.assertEqual(res['gender'], 'female')
        self.assertEqual(res['expiry_date'], date(2012, 4, 15))
        self.assertIsNone(res['dni_number'])
        self.assertEqual(res['warnings'], [])

    def test_mrz_td3_single_line_spaces_and_guillemets(self):
        raw = TD3_SPECIMEN.replace('\n', '').replace('<', '«').lower()
        raw = raw[:10] + '  ' + raw[10:]
        res = parse_document(raw)
        self.assertEqual(res['passport_number'], 'L898902C3')
        res = parse_document(TD3_SPECIMEN.replace('\n', '\r\n'), doc_type='mrz')
        self.assertEqual(res['last_name'], 'Eriksson')

    def test_mrz_td3_argentina(self):
        res = parse_document(TD3_ARG)
        self.assertEqual(res['doc_type'], 'mrz_td3')
        self.assertEqual(res['passport_number'], 'AAA123456')
        self.assertEqual(res['nationality_code'], 'ARG')
        self.assertEqual(res['nationality_code2'], 'AR')
        self.assertEqual(res['issuing_country_code2'], 'AR')
        self.assertEqual(res['dni_number'], '30123456')
        self.assertEqual(res['last_name'], 'Perez')
        self.assertEqual(res['first_names'], 'Juan Carlos')
        self.assertEqual(res['gender'], 'male')
        self.assertEqual(res['birthdate'], date(1985, 3, 15))
        self.assertEqual(res['expiry_date'], date(2030, 1, 1))

    def test_mrz_td3_check_digit_errors(self):
        l1, l2 = TD3_SPECIMEN.split('\n')
        cases = {
            'document number': l2[:9] + '7' + l2[10:],
            'birth date': l2[:19] + '3' + l2[20:],
            'expiry date': l2[:27] + '0' + l2[28:],
            'composite': l2[:43] + '9',
        }
        for label, bad_l2 in cases.items():
            with self.subTest(label=label), self.assertRaises(DocumentParseError) as ctx:
                parse_document(l1 + '\n' + bad_l2)
            self.assertIn(label, str(ctx.exception))

    def test_mrz_td3_optional_check_warning(self):
        l1, l2 = TD3_ARG.split('\n')
        # change optional check digit (pos 42) and recompute composite -> warning only
        bad = l2[:42] + '9'
        bad += str(mrz_check_digit(bad[0:10] + bad[13:20] + bad[21:43]))
        res = parse_document(l1 + '\n' + bad)
        self.assertEqual(len(res['warnings']), 1)
        self.assertEqual(res['passport_number'], 'AAA123456')

    def test_mrz_td1_argentina_dni(self):
        res = parse_document(TD1_ARG)
        self.assertEqual(res['doc_type'], 'mrz_td1')
        self.assertEqual(res['document_number'], '30123456')
        self.assertEqual(res['dni_number'], '30123456')
        self.assertIsNone(res['passport_number'])
        self.assertEqual(res['issuing_country_code'], 'ARG')
        self.assertEqual(res['nationality_code2'], 'AR')
        self.assertEqual(res['last_name'], 'Perez')
        self.assertEqual(res['first_names'], 'Juan Carlos')
        self.assertEqual(res['gender'], 'male')
        self.assertEqual(res['birthdate'], date(1985, 3, 15))
        self.assertEqual(res['expiry_date'], date(2035, 3, 15))

    def test_mrz_td1_single_line_90(self):
        res = parse_document(TD1_ARG.replace('\n', ''))
        self.assertEqual(res['doc_type'], 'mrz_td1')
        self.assertEqual(res['dni_number'], '30123456')

    def test_mrz_td1_foreign(self):
        res = parse_document(TD1_ESP)
        self.assertEqual(res['document_number'], 'ABC123456')
        self.assertIsNone(res['dni_number'])
        self.assertIsNone(res['passport_number'])
        self.assertEqual(res['last_name'], 'Garcia Lopez')
        self.assertEqual(res['first_names'], 'Maria')
        self.assertEqual(res['gender'], 'female')
        self.assertEqual(res['nationality_code2'], 'ES')
        self.assertEqual(res['birthdate'], date(1992, 7, 4))
        self.assertEqual(res['expiry_date'], date(2031, 1, 1))

    def test_mrz_td1_check_digit_errors(self):
        l1, l2, l3 = TD1_ARG.split('\n')
        with self.assertRaises(DocumentParseError):
            parse_document('\n'.join([l1[:14] + '9' + l1[15:], l2, l3]))
        with self.assertRaises(DocumentParseError):
            parse_document('\n'.join([l1, l2[:6] + '1' + l2[7:], l3]))
        with self.assertRaises(DocumentParseError):
            parse_document('\n'.join([l1, l2[:14] + '0' + l2[15:], l3]))
        with self.assertRaises(DocumentParseError) as ctx:
            parse_document('\n'.join([l1, l2[:29] + '0', l3]))
        self.assertIn('composite', str(ctx.exception))

    def test_mrz_special_country_codes(self):
        l1, l2 = TD3_SPECIMEN.split('\n')
        l1 = l1[:2] + 'D<<' + l1[5:]
        l2 = l2[:10] + 'D<<' + l2[13:43]
        l2 += str(mrz_check_digit(l2[0:10] + l2[13:20] + l2[21:43]))
        res = parse_document(l1 + '\n' + l2)
        self.assertEqual(res['nationality_code'], 'D')
        self.assertEqual(res['nationality_code2'], 'DE')
        self.assertEqual(res['issuing_country_code2'], 'DE')

    def test_mrz_errors(self):
        for raw in (
            'P<UTOERIKSSON<<ANNA',
            TD3_SPECIMEN + '\nEXTRA<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<',
            TD3_SPECIMEN.replace('L898902C3', 'L898902C$'),
        ):
            with self.subTest(raw=raw), self.assertRaises(DocumentParseError):
                parse_document(raw, doc_type='mrz')
        with self.assertRaises(DocumentParseError):
            parse_document(DNI_NEW, doc_type='mrz')
