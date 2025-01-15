from django.db.models import Func, DateTimeField
from django.db.models.functions import Cast, Coalesce


class MonthsAdd(Func):
    """
    Custom function that is suitable for MS SQL and Postgresql. If using different database it is possible that
    it might need an update with custom resolve.
    Usage: Foo.objects.annotate(end_date=MonthsAdd('start_date', 'duration')).filter(end_date__gt=datetime.now)
    """
    # https://stackoverflow.com/questions/33981468/using-dateadd-in-django-filter

    arg_joiner = " + CAST("
    template = "%(expressions)s || 'months' as INTERVAL)"

    template_mssql = '%(function)s(MONTH, %(expressions)s)'
    function_mssql = "DATEADD"

    output_field = DateTimeField()
    arity = 2
    COUNTER = 0

    def as_sql(self, compiler, connection, **extra_context):

        if connection.vendor == 'microsoft':
            self.arg_joiner = ', '
            self.source_expressions = self.get_source_expressions(
            )[::-1] if self.COUNTER == 0 else self.get_source_expressions()
            self.template = self.template_mssql
            self.function = self.function_mssql
        self.COUNTER += 1
        return super().as_sql(compiler, connection, **extra_context)


def get_queryset_valid_at_date(queryset, date):
    filtered_qs = queryset.filter(
        validity_to__gte=date,
        validity_from__lte=date
    )
    if len(filtered_qs) > 0:
        return filtered_qs
    return queryset.filter(validity_from__date__lte=date, validity_to__isnull=True)
