from django.urls import path
from .views import upload_bank_file

urlpatterns = [
    path("bank/import", upload_bank_file, name="upload_bank_file"),
]
