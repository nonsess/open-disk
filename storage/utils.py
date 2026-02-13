from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import quote

def _redirect_to_path(path: str) -> HttpResponseRedirect:
    url = reverse('file_list')
    if path:
        url += f"?path={quote(path)}"
    return redirect(url)
