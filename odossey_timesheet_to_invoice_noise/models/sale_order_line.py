import random
from collections import defaultdict

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # {group key: {timesheet id: [recorded hours, variation in minutes]}}
    # A group is the set of timesheets of the line printed and totalled together:
    # same To Invoice flag and same invoice. Its variations add up to zero.
    timesheet_noise = fields.Json(string="Printed Hours Variation", copy=False)

    @api.model
    def _generate_timesheet_noise(self, amounts, max_minutes):
        """ Random variation, in whole minutes, of a list of durations.

        Each variation is within +/- `max_minutes`, never brings a duration to zero
        or below, and all of them add up to zero.

        :param list[float] amounts: durations in hours
        :param int max_minutes: maximum variation of a duration
        :return: list of variations in minutes, in the same order
        """
        deltas = [0] * len(amounts)
        # lowest variation of each duration: keep at least one minute. Durations
        # that are not a whole number of minutes are left as they are: the report
        # rounds to the minute and would not show their variation faithfully.
        lows = [
            -min(max_minutes, max(round(amount * 60) - 1, 0))
            if abs(amount * 60 - round(amount * 60)) < 0.01 else 0
            for amount in amounts
        ]
        indexes = [i for i, low in enumerate(lows) if low < 0]
        if max_minutes <= 0 or len(indexes) < 2:
            return deltas

        def choices(index):
            return [d for d in range(lows[index], max_minutes + 1) if d]

        # draw everything but the last one, that balances the sum
        for _attempt in range(200):
            random.shuffle(indexes)
            draw = [random.choice(choices(i)) for i in indexes[:-1]]
            last = -sum(draw)
            if last and lows[indexes[-1]] <= last <= max_minutes:
                for index, delta in zip(indexes, draw + [last]):
                    deltas[index] = delta
                return deltas

        # fallback: opposite variations two by two
        random.shuffle(indexes)
        for first, second in zip(indexes[::2], indexes[1::2]):
            delta = random.randint(1, min(max_minutes, -lows[first], -lows[second]))
            if random.random() < 0.5:
                first, second = second, first
            deltas[first], deltas[second] = delta, -delta
        return deltas

    def _get_timesheet_noise(self):
        """ Hours to print for the timesheets of the lines.

        The variations are generated when missing and stored on the line; the ones
        already stored are reused as long as the recorded hours of their group did
        not change, so that a document printed again is identical.

        :return: {timesheet id: hours to print}
        """
        result = {}
        timesheets_by_line = defaultdict(lambda: self.env['account.analytic.line'])
        if self.ids:
            timesheets = self.env['account.analytic.line'].sudo().search([
                ('so_line', 'in', self.ids),
                ('project_id', '!=', False),
            ], order='date, id')
            for timesheet in timesheets:
                timesheets_by_line[timesheet.so_line.id] |= timesheet

        for line in self.sudo():
            max_minutes = line.company_id.timesheet_noise_minutes
            if max_minutes <= 0:
                continue
            groups = defaultdict(dict)
            for timesheet in timesheets_by_line[line.id]:
                key = '%d-%d' % (timesheet.to_invoice, timesheet.timesheet_invoice_id.id)
                groups[key][str(timesheet.id)] = round(timesheet.unit_amount, 4)

            stored = line.timesheet_noise or {}
            noise = {}
            for key, amounts in groups.items():
                group = stored.get(key) or {}
                if {timesheet_id: values[0] for timesheet_id, values in group.items()} != amounts:
                    deltas = self._generate_timesheet_noise(list(amounts.values()), max_minutes)
                    group = {
                        timesheet_id: [amount, delta]
                        for (timesheet_id, amount), delta in zip(amounts.items(), deltas)
                    }
                noise[key] = group
                for timesheet_id, (amount, delta) in group.items():
                    result[int(timesheet_id)] = amount + delta / 60

            if noise != stored:
                line.timesheet_noise = noise
        return result

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.timesheet_noise:
            res['timesheet_noise'] = {str(self.id): self.timesheet_noise}
        return res
