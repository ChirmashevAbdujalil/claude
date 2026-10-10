from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsReviewer(BasePermission):
    """O'qituvchi, dekanat, rektorat yoki admin."""

    message = "Bu amal faqat o'qituvchilar va rahbariyat uchun."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_reviewer)


class IsManagement(BasePermission):
    """Dekanat, rektorat yoki admin."""

    message = "Bu bo'lim faqat rahbariyat uchun."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_management)


class ReadOnlyOrReviewer(BasePermission):
    """Hamma o'qiy oladi, yozish faqat o'qituvchi va rahbariyatga."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or request.user.is_reviewer


class ReadOnlyOrPublisher(BasePermission):
    """Hamma o'qiy oladi, imkoniyat joylash hamkorlar va rahbariyatga."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_management or request.user.role == request.user.Role.PARTNER


class IsAuthorOrReadOnly(BasePermission):
    author_field = "author"

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return getattr(obj, getattr(view, "author_field", self.author_field)) == request.user or (
            request.user.is_management
        )
