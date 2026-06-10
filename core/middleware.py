from django.shortcuts import redirect

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not request.user.is_authenticated:
            allowed_paths = ['/login/', '/static/', '/admin/']
            if not any(request.path.startswith(path) for path in allowed_paths) and request.path != '/':
                return redirect('login')
        return self.get_response(request)