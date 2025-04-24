from django.db.models import Func, DateTimeField
from django.db.models.functions import Cast, Coalesce
import openpyxl
from decimal import Decimal


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

def parse_bank_file(file):
    wb = openpyxl.load_workbook(file)
    sheet = wb.active

    first_rows = [row for row in sheet.iter_rows(min_row=1, max_row=10, values_only=True)]

    if any("Txn. Date" in str(cell) for row in first_rows for cell in row if cell):
        return parse_excel_exim(file)
    else:
        return parse_excel_bdc(file)


# Fonction pour parser les fichier BDC
def parse_excel_bdc(file):
    wb = openpyxl.load_workbook(file)
    sheet = wb.active

    transactions = []
    total_kmf = Decimal("0.00")

    for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
        if not row or len(row) < 5:
            continue

        try:
            date = row[2]
            amount_raw = row[4]

            # Convertir le montant (gestion du format "2.000,50")
            amount_str = str(amount_raw).replace(",", ".").replace(" ", "")
            amount = Decimal(amount_str)

            if amount > 0:
                transactions.append({
                    "date": str(date),
                    "description": row[5],
                    "amount": str(amount),
                })
                total_kmf += amount
        except Exception as e:
            print(f"Erreur à la ligne {row_idx}: {row} - {e}")
            continue

    return {
        "transactions": transactions,
        "total_kmf": str(total_kmf),
        "count": len(transactions),
    }


# Fonction pour parser les fichier Exim
def parse_excel_exim(file):
    wb = openpyxl.load_workbook(file)
    sheet = wb.active

    transactions = []
    total_kmf = Decimal("0.00")
    start_parsing = False

    for row in sheet.iter_rows(values_only=True):
        if not start_parsing:
            if row and any("Txn. Date" in str(cell) for cell in row if cell):
                headers = [str(h).strip() if h else None for h in row]
                try:
                    date_idx = headers.index("Txn. Date")
                    desc_idx = headers.index("Description")
                    credit_idx = headers.index("Credit")
                except ValueError as e:
                    raise Exception("Colonnes attendues non trouvées dans le fichier (Txn. Date, Description, Credit)") from e
                start_parsing = True
                continue

        if start_parsing:
            if row and str(row[1]).startswith("Opening Balance"):
                break

            try:
                credit_val = row[credit_idx]
                if credit_val and Decimal(credit_val) > 0:
                    transactions.append({
                        "date": str(row[date_idx]),
                        "description": row[desc_idx],
                        "amount": str(Decimal(credit_val)),
                    })
                    total_kmf += Decimal(credit_val)
            except Exception as e:
                print(f"Erreur parsing ligne: {row} - {e}")
                continue

    return {
        "transactions": transactions,
        "total_kmf": str(total_kmf),
        "count": len(transactions),
    }
