"""Deterministic date scopes and retrieval context, independent of AI output."""
import re
from calendar import monthrange
from datetime import date, timedelta


def date_scope(question: str, today: date):
    """Return inclusive bounds, or None when no supported date scope is present."""
    text = question.casefold()
    iso_dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text)
    if iso_dates:
        if len(iso_dates) > 2:
            raise ValueError('Please specify one date or one date range using YYYY-MM-DD.')
        try:
            dates = [date.fromisoformat(value) for value in iso_dates]
        except ValueError:
            raise ValueError('Please use valid dates in YYYY-MM-DD format.') from None
        if len(dates) == 2 and dates[0] > dates[1]:
            raise ValueError('The start date must be on or before the end date.')
        if len(dates) == 1 and re.search(r'\b(since|before|after|until|from)\b', text):
            raise ValueError('Please specify both endpoints as YYYY-MM-DD to YYYY-MM-DD.')
        return dates[0], dates[-1]
    if re.search(r'\btoday\b', text) and re.search(r'\byesterday\b', text):
        return today - timedelta(days=1), today
    if len(re.findall(r'\b(?:this|last) (?:week|month|year)\b', text)) > 1:
        raise ValueError('Please ask about one calendar period or specify an explicit YYYY-MM-DD date range.')
    if re.search(r'\byesterday\b', text):
        day = today - timedelta(days=1)
        return day, day
    if re.search(r'\btoday\b', text):
        return today, today
    match = re.search(r'\b(?:last|past) (\d+) days?\b', text)
    if match:
        count = int(match.group(1))
        if not 1 <= count <= 3660:
            raise ValueError('Please choose a date range of 1 to 3660 days.')
        return today - timedelta(days=count - 1), today
    match = re.search(r'\b(this|last) (week|month|year)\b', text)
    if match:
        previous, unit = match.group(1) == 'last', match.group(2)
        if unit == 'week':
            start = today - timedelta(days=today.weekday(), weeks=int(previous))
            return start, start + timedelta(days=6)
        if unit == 'year':
            year = today.year - int(previous)
            return date(year, 1, 1), date(year, 12, 31)
        start = today.replace(day=1)
        if previous:
            start = (start - timedelta(days=1)).replace(day=1)
        return start, start.replace(day=monthrange(start.year, start.month)[1])
    names = 'january february march april may june july august september october november december'.split()
    match = re.search(r'\b(' + '|'.join(names) + r')\s+(\d{4})\b', text)
    if match:
        year, month = int(match.group(2)), names.index(match.group(1)) + 1
        return date(year, month, 1), date(year, month, monthrange(year, month)[1])
    if re.search(r'\b(?:last|this|next) (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend|summer|winter|spring|fall|autumn|night)\b', text) or re.search(r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b', text):
        raise ValueError('Please specify that date or period using YYYY-MM-DD or YYYY-MM-DD to YYYY-MM-DD.')
    # Named months with missing years or unsupported day formats must not silently search all time.
    if re.search(r'\b(?:in|during|since|from|on)\s+(?:' + '|'.join(names) + r')\b', text):
        raise ValueError('Please specify the date using YYYY-MM-DD, or a month and year such as October 2026.')
    return None


def retrieval_request(question: str, history: list[dict], today: date):
    previous_questions = [m['content'] for m in history if m.get('role') == 'user' and isinstance(m.get('content'), str)]
    def is_followup(text):
        return bool(re.search(r'\b(that|those|them|it|they|then|also|more|why|what about)\b', text.casefold()))
    scope = date_scope(question, today)
    if is_followup(question) and previous_questions:
        inherited = None
        for previous in previous_questions:
            previous_scope = date_scope(previous, today)
            if previous_scope is not None:
                inherited = previous_scope
            elif not is_followup(previous):
                inherited = None
        if scope is None:
            scope = inherited
        # User text only: generated answers must not become retrieval evidence.
        query = '\n'.join(previous[:2000] for previous in previous_questions[-2:]) + '\nFollow-up: ' + question
    else:
        query = question
    return query, scope
