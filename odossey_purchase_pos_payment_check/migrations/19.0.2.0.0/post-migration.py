# License OPL-1


def migrate(cr, version):
    """A check already handed over to a supplier (`handed_to_partner_id`)
    is now simply 'transferred' -- it stays a third-party check, instead of
    being what used to make the "Cheques Propios" list. Runs after
    `l10n_latam_check_ext`'s own pre-migration has mapped the old state
    values (that module is a dependency of this one)."""
    cr.execute(
        "UPDATE l10n_latam_check SET check_state = 'transferred', "
        "check_state_third = 'transferred', check_state_own = NULL "
        "WHERE handed_to_partner_id IS NOT NULL"
    )
    cr.execute(
        "UPDATE pos_payment p SET check_state = 'transferred' FROM l10n_latam_check c "
        "WHERE p.l10n_latam_check_id = c.id AND c.check_state = 'transferred'"
    )
