from documentos.models import Documento

def documentos_visibles_para_usuario(user):
    qs = Documento.objects.filter(leido_por_ia=True)

    if user.is_superuser or user.groups.filter(name="argos_consultas_general").exists():
        return qs  # acceso total

    dep = getattr(user, "dependencia", None)
    if not dep or not dep.dependencia_argos:
        return qs.none()  # sin dependencia -> nada

    return qs.filter(dependencia__dependencia_argos__sigla=dep.dependencia_argos.sigla)
