from inspect import iscoroutinefunction
from asgiref.sync import sync_to_async

from strawberry.extensions import Extension

from strawberry.extensions.utils import is_introspection_field


class SyncToAsync(Extension):
    def __init__(self, thread_sensitive: bool = True):
        self._thread_sensitive = thread_sensitive

    def resolve(self, _next, root, info, *args, **kwargs):
        # Skip introspection fields
        if is_introspection_field(info):
            return _next(root, info, *args, **kwargs)

        # grabed from here:
        # https://github.com/strawberry-graphql/strawberry/blob/669ca1266883acf7f319c2aa2c735df858c79c74/strawberry/types/fields/resolver.py#L130
        if not iscoroutinefunction(_next):
            return sync_to_async(_next, thread_sensitive=self._thread_sensitive)(
                root, info, *args, **kwargs
            )

        return _next(root, info, *args, **kwargs)