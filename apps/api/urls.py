from rest_framework.routers import DefaultRouter
from .views import (
    TaxonomyDataViewSet,
    OrganelleMetadataViewSet,
    IRIdentificationViewSet,
)

router = DefaultRouter()
router.register(r"taxonomy", TaxonomyDataViewSet, basename="taxonomy")
router.register(
    r"organelle-metadata", OrganelleMetadataViewSet, basename="organelle-metadata"
)
router.register(
    r"ir-identification", IRIdentificationViewSet, basename="ir-identification"
)

urlpatterns = router.urls
