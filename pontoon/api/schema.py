import graphene
from graphene_django import DjangoObjectType
from graphene_django.debug import DjangoDebug

from pontoon.api.util import get_fields

from pontoon.base.models import (
    Locale as LocaleModel,
    Project as ProjectModel,
    ProjectLocale as ProjectLocaleModel,
)

from pontoon.tags.models import Tag as TagModel


class Stats:
    missing_strings = graphene.Int()
    complete = graphene.Boolean()


class Tag(DjangoObjectType):
    class Meta:
        convert_choices_to_enum = False
        model = TagModel
        fields = (
            "slug",
            "name",
            "priority",
        )


class ProjectLocale(DjangoObjectType, Stats):
    class Meta:
        model = ProjectLocaleModel
        fields = (
            "project",
            "locale",
            "total_strings",
            "approved_strings",
            "pretranslated_strings",
            "strings_with_errors",
            "strings_with_warnings",
            "unreviewed_strings",
        )


class Project(DjangoObjectType, Stats):
    class Meta:
        convert_choices_to_enum = False
        model = ProjectModel
        fields = (
            "name",
            "slug",
            "disabled",
            "sync_disabled",
            "pretranslation_enabled",
            "visibility",
            "system_project",
            "info",
            "deadline",
            "priority",
            "contact",
            "total_strings",
            "approved_strings",
            "pretranslated_strings",
            "strings_with_errors",
            "strings_with_warnings",
            "unreviewed_strings",
        )

    localizations = graphene.List(ProjectLocale)
    tags = graphene.List(Tag)

    def resolve_localizations(obj, info):
        return obj.project_locale.all()

    def resolve_tags(obj, info):
        return obj.tag_set.all()


class Locale(DjangoObjectType, Stats):
    class Meta:
        model = LocaleModel
        fields = (
            "name",
            "code",
            "direction",
            "cldr_plurals",
            "plural_rule",
            "script",
            "population",
            "total_strings",
            "approved_strings",
            "pretranslated_strings",
            "strings_with_errors",
            "strings_with_warnings",
            "unreviewed_strings",
            "google_translate_code",
            "ms_translator_code",
            "systran_translate_code",
            "ms_terminology_code",
        )

    localizations = graphene.List(
        ProjectLocale,
        include_disabled=graphene.Boolean(False),
        include_system=graphene.Boolean(False),
    )

    def resolve_localizations(obj, info, include_disabled, include_system):
        projects = obj.project_locale.visible_for(info.context.user)

        records = projects.filter(
            project__disabled=False, project__system_project=False
        )

        if include_disabled:
            records |= projects.filter(project__disabled=True)

        if include_system:
            records |= projects.filter(project__system_project=True)

        return records.distinct()


class Query(graphene.ObjectType):
    debug = graphene.Field(DjangoDebug, name="__debug")

    # include_disabled=True will return both active and disabled projects.
    # include_system=True will return both system and non-system projects.
    projects = graphene.List(
        Project,
        include_disabled=graphene.Boolean(False),
        include_system=graphene.Boolean(False),
    )
    project = graphene.Field(Project, slug=graphene.String())

    locales = graphene.List(Locale)
    locale = graphene.Field(Locale, code=graphene.String())

    def resolve_projects(obj, info, include_disabled, include_system):
        fields = get_fields(info)

        projects = ProjectModel.objects.visible_for(info.context.user)
        records = projects.filter(disabled=False, system_project=False)

        if include_disabled:
            records |= projects.filter(disabled=True)

        if include_system:
            records |= projects.filter(system_project=True)

        if "projects.localizations" in fields:
            records = records.prefetch_related("project_locale__locale")

        if "projects.localizations.locale.localizations" in fields:
            raise Exception("Cyclic queries are forbidden")

        return records.distinct()

    def resolve_project(obj, info, slug):
        qs = ProjectModel.objects.visible_for(info.context.user)
        fields = get_fields(info)

        if "project.localizations" in fields:
            qs = qs.prefetch_related("project_locale__locale")

        if "project.tags" in fields:
            qs = qs.prefetch_related("tag_set")

        if "project.localizations.locale.localizations" in fields:
            raise Exception("Cyclic queries are forbidden")

        return qs.get(slug=slug)

    def resolve_locales(obj, info):
        qs = LocaleModel.objects
        fields = get_fields(info)

        if "locales.localizations" in fields:
            qs = qs.prefetch_related("project_locale__project")

        if "locales.localizations.project.localizations" in fields:
            raise Exception("Cyclic queries are forbidden")

        return qs.all()

    def resolve_locale(obj, info, code):
        qs = LocaleModel.objects
        fields = get_fields(info)

        if "locale.localizations" in fields:
            qs = qs.prefetch_related("project_locale__project")

        if "locale.localizations.project.localizations" in fields:
            raise Exception("Cyclic queries are forbidden")

        return qs.get(code=code)


schema = graphene.Schema(query=Query)
