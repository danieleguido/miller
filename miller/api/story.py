import json
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAdminUser

from rest_framework import serializers,viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import  api_view, permission_classes, detail_route, list_route # cfr StoryViewSet

from miller.models import Story, Tag, Document, Caption
from miller.api.fields import OptionalFileField, JsonField
from miller.api.serializers import LiteDocumentSerializer, MatchingStorySerializer, AuthorSerializer, TagSerializer, StorySerializer, LiteStorySerializer, CreateStorySerializer


# ViewSets define the view behavior. Filter by status
class StoryViewSet(viewsets.ModelViewSet):
  queryset = Story.objects.all()
  serializer_class = CreateStorySerializer

  # retrieve by PK or slug
  def retrieve(self, request, *args, **kwargs):
    if request.user.is_authenticated():
      queryset = self.queryset.filter(Q(owner=request.user) | Q(authors=request.user) | Q(status=Story.PUBLIC)).distinct()
    else:
      queryset = self.queryset.filter(status=Story.PUBLIC).distinct()

    if 'pk' in kwargs and not kwargs['pk'].isdigit():
      story = get_object_or_404(queryset, slug=kwargs['pk'])
    else:
      story = get_object_or_404(queryset, pk=kwargs['pk'])
    
    serializer = StorySerializer(story,
        context={'request': request},
    )
    return Response(serializer.data)
  

  def list(self, request):
    filters = self.request.query_params.get('filters', None)
    
    if filters is not None:
      print filters
      try:
        filters = json.loads(filters)
        # print "filters,",filters
      except Exception, e:
        # print e
        filters = {}
    else:
      filters = {}
    
    if request.user.is_authenticated():
      stories = self.queryset.filter(Q(owner=request.user) | Q(authors=request.user) | Q(status=Story.PUBLIC)).filter(**filters).distinct()
    else:
      stories = self.queryset.filter(status=Story.PUBLIC).filter(**filters).distinct()
    # print stories.query
    page    = self.paginate_queryset(stories)
    print page
    if page is not None:
      serializer = LiteStorySerializer(page, many=True, context={'request': request})
      return self.get_paginated_response(serializer.data)

    serializer = LiteStorySerializer(queryset, many=True, context={'request': request})
    return Response(serializer.data)


  # for some tags require the request user to be staff user
  @permission_classes((IsAdminUser, ))
  def partial_update(self, request, *args, **kwargs):
    return super(StoryViewSet, self).partial_update(request, *args, **kwargs)


  @list_route(methods=['get'])
  def search(self, request):
    from miller.forms import SearchQueryForm
    from miller.helpers import search_whoosh_index
    form = SearchQueryForm(request.query_params)
    if not form.is_valid():
      return Response(form.errors, status=status.HTTP_201_CREATED)
    # get the results
    results = search_whoosh_index(form.cleaned_data['q'])
    
    filters = {
      'id__in': [hit['id'] for hit in results]
    }
    # check if the user is allowed this content
    if request.user.is_authenticated():
      stories = self.queryset.filter(Q(owner=request.user) | Q(authors=request.user) | Q(status=Story.PUBLIC)).filter(**filters).distinct()
    else:
      stories = self.queryset.filter(status=Story.PUBLIC).filter(**filters).distinct()

    def mapper(d):
      d.matches = []
      for hit in results:
        if int(d.id) == int(hit['id']):
          d.matches = hit
          break
      return d
    # enrich stories items (max 10 items)
    stories = map(mapper, stories)
    page    = self.paginate_queryset(stories)

    serializer = MatchingStorySerializer(stories, many=True,
      context={'request': request}
    )
    return self.get_paginated_response(serializer.data)


  @detail_route(methods=['put'])
  def tags(self, request, pk=None):
    queryset = self.queryset.filter(Q(owner=request.user) | Q(authors=request.user))

    story = get_object_or_404(queryset, pk=12333)


    # save, then return tagged items according to tagform
    serializer = StorySerializer(story,
        context={'request': request},
    )
    return Response(serializer.data)
  

  