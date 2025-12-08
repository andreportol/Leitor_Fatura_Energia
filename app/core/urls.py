from django.urls import path
from .views import (
    CadastroView,
    ContactFormView,
    ContatoCrudView,
    LoginView,
    LogoutView,
    ProcessamentoView,
    QuemSomosView,
    TemplateViewsIndex,
)


app_name = 'core'

urlpatterns = [
    path('', TemplateViewsIndex.as_view(), name='index'),
    path('contato/enviar/', ContactFormView.as_view(), name='contact'),
    path('cadastro/', CadastroView.as_view(), name='cadastro'),
    path('quem-somos/', QuemSomosView.as_view(), name='quem_somos'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('processamento/', ProcessamentoView.as_view(), name='processamento'),
    path('contatos/', ContatoCrudView.as_view(), name='contatos'),
]
