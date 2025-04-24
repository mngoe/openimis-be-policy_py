# Create your views here.

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .serializers import BankImportUploadSerializer
from .models import BankImport
from .utils import parse_bank_file
from core.models import InteractiveUser
import logging

logger = logging.getLogger(__name__)

@api_view(["POST"])
def upload_bank_file(request):
    serializer = BankImportUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    file = serializer.validated_data.get("file")
    user = InteractiveUser.objects.filter(login_name=request.user.username).first()
    errors = []
    transactions_result = {}

    try:
        logger.info(f"Upload fichier banque (user={user.id}, file={file})")
        
        bank_import = BankImport.objects.create(user=user, stored_file=file)

        transactions_result = parse_bank_file(bank_import.stored_file)

        logger.info(f"{transactions_result['count']} transactions créditées extraites")

    except Exception as exc:
        logger.exception("Erreur durant l'import EXIM")
        errors.append(str(exc))

    return Response({
        "success": len(errors) == 0,
        "errors": errors,
        **transactions_result
    }, status=status.HTTP_200_OK if not errors else status.HTTP_400_BAD_REQUEST)
