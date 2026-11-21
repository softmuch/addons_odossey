"""Vaccines by age (18/11/2026): the interval between the primary course doses moves from weeks to days."""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'product_template' AND column_name = 'vet_dose_interval_weeks'
    """)
    if not cr.fetchone():
        return
    cr.execute("ALTER TABLE product_template ADD COLUMN IF NOT EXISTS vet_dose_interval_days integer")
    cr.execute("""
        UPDATE product_template
           SET vet_dose_interval_days = vet_dose_interval_weeks * 7
         WHERE vet_dose_interval_weeks IS NOT NULL
    """)
