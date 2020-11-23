from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import Union
from utils.ramda import parse_dt, if_else, isinstance, identity, obj_with, getitem

DateType = Union[date, str, int]
parse_to_datetime = if_else(isinstance(datetime), identity, parse_dt)
DateRangeType = enumerate(['days', 'months', 'years', 'weeks'])


class DateRange(object):
    start_date: datetime
    end_date: datetime
    range_type: DateRangeType

    def __init__(self,
                 start: DateType,
                 end: DateType,
                 rtype: DateRangeType = 'days',
                 step: int = 1):
        self.start_date = parse_to_datetime(start)
        self.end_date = parse_to_datetime(end)
        assert self.end_date > self.start_date, 'end date must be grater then start date.'
        self.range_type = rtype
        args = obj_with(step, self.range_type)
        self.step = relativedelta(**args)

    def _iter_by_month(self):
        """
        for month, year in DateRange('2019-03-15', '2020-1-1', rtype='months'):
            ....
        """
        s: date = self.start_date
        while s < self.end_date:
            yield s
            s += self.step
        if self.end_date.month >= s.month:
            yield self.end_date

    def _iter_by_year(self):
        s: date = self.start_date
        while s < self.end_date:
            yield s.year
            s += self.step
        yield self.end_date

    def _iter_by_day(self):
        s: date = self.start_date
        while s <= self.end_date:
            yield s.day, s.month, s.year

    def __iter__(self):
        return getitem(self.range_type)({
            'days': None,
            'months': self._iter_by_month,
            'weeks': None,
            'years': self._iter_by_year,
        })()
