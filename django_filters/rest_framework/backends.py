
from __future__ import absolute_import

from django.template import RequestContext, Template, TemplateDoesNotExist, loader
from django.utils import six

from .. import compat
from . import filterset


CRISPY_TEMPLATE = """
{% load crispy_forms_tags %}
{% load i18n %}

<h2>{% trans "Field filters" %}</h2>
{% crispy filter.form %}
"""


FILTER_TEMPLATE = """
{% load i18n %}
<h2>{% trans "Field filters" %}</h2>
<form class="form" action="" method="get">
    {{ filter.form.as_p }}
    <button type="submit" class="btn btn-primary">{% trans "Submit" %}</button>
</form>
"""


class DjangoFilterBackend(object):
    default_filter_set = filterset.FilterSet

    @property
    def template(self):
        if compat.is_crispy():
            return 'django_filters/rest_framework/crispy_form.html'
        return 'django_filters/rest_framework/form.html'

    @property
    def template_default(self):
        if compat.is_crispy():
            return CRISPY_TEMPLATE
        return FILTER_TEMPLATE

    def get_filter_class(self, view, queryset=None):
        """
        Return the django-filters `FilterSet` used to filter the queryset.
        """
        filter_class = getattr(view, 'filter_class', None)
        filter_fields = getattr(view, 'filter_fields', None)

        if filter_class:
            filter_model = filter_class.Meta.model

            assert issubclass(queryset.model, filter_model), \
                'FilterSet model %s does not match queryset model %s' % \
                (filter_model, queryset.model)

            return filter_class

        if filter_fields:
            class AutoFilterSet(self.default_filter_set):
                class Meta:
                    model = queryset.model
                    fields = filter_fields

            return AutoFilterSet

        return None

    def filter_queryset(self, request, queryset, view):
        filter_class = self.get_filter_class(view, queryset)

        if filter_class:
            return filter_class(request.query_params, queryset=queryset, request=request).qs

        return queryset

    def to_html(self, request, queryset, view):
        filter_class = self.get_filter_class(view, queryset)
        if not filter_class:
            return None
        filter_instance = filter_class(request.query_params, queryset=queryset, request=request)

        context = {'filter': filter_instance}
        try:
            template = loader.get_template(self.template)
            return template.render(context, request)
        except TemplateDoesNotExist:
            template = Template(self.template_default)
            context = RequestContext(request, context)
            return template.render(context)

    def get_schema_fields(self, view):
        # This is not compatible with widgets where the query param differs from the
        # filter's attribute name. Notably, this includes `MultiWidget`, where query
        # params will be of the format `<name>_0`, `<name>_1`, etc...
        assert compat.coreapi is not None, 'coreapi must be installed to use `get_schema_fields()`'
        filter_class = self.get_filter_class(view, view.get_queryset())

        return [] if not filter_class else [
            compat.coreapi.Field(
                name=field_name, required=False, location='query', description=six.text_type(field.field.help_text))
            for field_name, field in filter_class().filters.items()
        ]
