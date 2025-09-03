from django.utils.deprecation import MiddlewareMixin

class EarlyPatchMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        # Apply patches before any request is processed
        self.apply_early_patches()
        super().__init__(get_response)
    
    def apply_early_patches(self):
        """
        Apply patches before any other code runs
        """
        try:
            # Import and patch the update_last_login function directly
            import django.contrib.auth.models
            
            # Completely replace the function with a no-op
            def no_op_update_last_login(sender, **kwargs):
                # Do absolutely nothing
                return
            
            django.contrib.auth.models.update_last_login = no_op_update_last_login
            
            # Also patch it in the signals module if it exists
            try:
                import django.contrib.auth.signals
                django.contrib.auth.signals.update_last_login = no_op_update_last_login
            except:
                pass
                
            print("Early patches applied successfully")
            
        except Exception as e:
            print(f"Early patching failed: {e}")