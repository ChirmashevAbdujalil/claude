from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.projects import services
from apps.projects.models import Project, ProjectMember

from ..forms import JoinProjectForm, ProjectForm
from .common import paginate, run_service

STAGES = [("", "Barchasi")] + list(Project.Stage.choices)


@login_required
def project_list(request):
    stage = request.GET.get("stage", "")
    query = request.GET.get("q", "").strip()
    projects = (
        Project.objects.select_related("owner")
        .prefetch_related("skills_needed")
        .annotate(member_count=Count("members", filter=Q(members__status="active")))
    )
    if request.GET.get("mine") == "1":
        projects = projects.filter(members__user=request.user)
    if stage:
        projects = projects.filter(stage=stage)
    if query:
        projects = projects.filter(Q(title__icontains=query) | Q(description__icontains=query))
    context = {
        "page": paginate(request, projects.order_by("-updated_at")),
        "stages": STAGES,
        "stage": stage,
        "q": query,
        "mine": request.GET.get("mine") == "1",
    }
    return render(request, "web/projects/list.html", context)


@login_required
def project_detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("owner").prefetch_related(
            "skills_needed", Prefetch("members", queryset=ProjectMember.objects.select_related("user"))
        ),
        pk=pk,
    )
    is_owner = project.owner_id == request.user.id
    members = list(project.members.all())
    membership = next((m for m in members if m.user_id == request.user.id), None)
    context = {
        "project": project,
        "is_owner": is_owner,
        "membership": membership,
        "active_members": [m for m in members if m.status == ProjectMember.Status.ACTIVE],
        "pending_members": [m for m in members if m.status == ProjectMember.Status.PENDING] if is_owner else [],
        "recommendations": services.recommend_teammates(project, limit=6) if is_owner else [],
        "join_form": JoinProjectForm(),
        "stage_index": Project.STAGE_ORDER.index(project.stage),
        "stage_labels": [label for _, label in Project.Stage.choices],
        "posts": project.posts.filter(is_hidden=False).select_related("author")[:5],
    }
    return render(request, "web/projects/detail.html", context)


@login_required
def project_form(request, pk=None):
    instance = None
    if pk:
        instance = get_object_or_404(Project, pk=pk)
        if instance.owner_id != request.user.id and not request.user.is_management:
            raise PermissionDenied
    form = ProjectForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        if instance is None:
            data = dict(form.cleaned_data)
            project = services.create_project(request.user, **data)
            messages.success(request, "Loyiha yaratildi! Endi jamoa yig'ing.")
        else:
            project = form.save()
            messages.success(request, "Loyiha yangilandi")
        return redirect("web:project-detail", pk=project.pk)
    return render(request, "web/projects/form.html", {"form": form, "instance": instance})


@login_required
@require_POST
def project_join(request, pk):
    project = get_object_or_404(Project, pk=pk)
    form = JoinProjectForm(request.POST)
    if form.is_valid():
        run_service(
            request,
            services.request_join,
            project,
            request.user,
            form.cleaned_data["role"],
            form.cleaned_data["message"],
            success="So'rov yuborildi. Asoschi tasdiqlashini kuting.",
        )
    return redirect("web:project-detail", pk=pk)


@login_required
@require_POST
def project_approve(request, pk, member_id):
    project = get_object_or_404(Project, pk=pk)
    run_service(request, services.approve_member, project, request.user, member_id, success="A'zo jamoaga qo'shildi")
    return redirect("web:project-detail", pk=pk)


@login_required
@require_POST
def project_advance(request, pk):
    project = get_object_or_404(Project, pk=pk)
    result = run_service(request, services.advance_stage, project, request.user)
    if result:
        messages.success(
            request, f"Tabriklaymiz! Loyiha «{result.get_stage_display()}» bosqichiga o'tdi. Jamoa +100 XP"
        )
    return redirect("web:project-detail", pk=pk)
