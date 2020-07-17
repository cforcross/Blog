from django.shortcuts import render, get_object_or_404
from .models import Post, Comment
from django.core.paginator import Paginator, EmptyPage,PageNotAnInteger
from django.views.generic import ListView,DetailView
from .forms import EmailPostForm, CommentForm, SearchForm
from django.core.mail import send_mail
from taggit.models import Tag
from django.db.models import Count
from django.contrib.postgres.search import SearchVector,SearchQuery,SearchRank

# Create your views here.

def post_list(request, tag_slug=None):
    object_list = Post.published.all()
    tag = None
    #Enables all users list posts tagged with a specific tag
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        object_list = object_list.filter(tags__in=[tag])

    ######### Handles Pagination ###############
    # posts = Post.published.all()
    paginator =Paginator(object_list,3)
    page = request.GET.get('page')#indicates current page parameter
    try:
        posts=paginator.page(page)
    except PageNotAnInteger:
        #if page is not an integer return the first page
        posts = paginator.page(1)
    except EmptyPage:
        #if page is out of range deliver last page of results
        posts = paginator.page(paginator.num_pages)
    
    context= {
        'page':page,
        'posts':posts,
        'tag':tag,
    }
    return render(request,'blog/list.html',context=context)


def post_detail(request, year,month, day, post):
    post = get_object_or_404(Post, slug=post,
                             status = 'published',
                             publish__year=year,
                             publish__month=month,
                             publish__day=day)
    #list of active comments for this post
    #remember the related_name in the Comment model.py   
    comments = post.comments.filter(active=True)
    
    new_comment = None
    if request.method == 'POST':
        #A comment was posted
        comment_form = CommentForm(data=request.POST)
        if comment_form.is_valid():
            #Create comment object but dont save to database yet
            #because you want to modify the object before saving it  so
            #set commit to false
            new_comment = comment_form.save(commit=False)
            #Assigns current post to the comment
            #This ensures each comment is assigned to its correct post
            new_comment.post = post
            #save the comment to the database
            new_comment.save()
    else:
        comment_form = CommentForm()
    # List of similar posts
    post_tags_ids = post.tags.values_list('id',flat=True)
    similar_posts = Post.published.filter(tags__in=post_tags_ids).exclude(id=post.id)
    similar_posts = similar_posts.annotate(same_tags=Count('tags')).order_by('-same_tags','-publish')[:4]
    context = {
        'post':post,
        'comments':comments,
        'new_comments':new_comment,
        'comment_form':comment_form,
        'similar_posts':similar_posts
    }

    return render(request,'blog/detail.html',context=context)


class PostListView(ListView):
    queryset = Post.published.all()
    context_object_name = 'posts'
    paginate_by = 3
    template_name = 'blog/list.html'

def post_share(request,post_id):
    #retrieve post by id
    #makes sure the retreieve post has a published status
    post = get_object_or_404(Post, id=post_id, status='published')
    sent = False
    if request.method == 'POST':
        #form was submitted
        form = EmailPostForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(
                post.get_absolute_url()
            )
            subject =  f"{cd['name']} recommends you read " \
                        f"{post.title}"
            message =  f"Read {post.title} at {post_url}\n\n" \
                        f"{cd['name']}\'s comments: {cd['comments']}"

            send_mail(subject, message, 'admin@myblog.com',
                        [cd['to']])
            sent=True
            
            #send email
    else:
        form = EmailPostForm()
    context = {
        'post':post,
        'form':form,
        'sent':sent
    }
    return render(request,'blog/share.html', context=context)

def post_search(request):
    form = SearchForm()
    query = None
    results = []
    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            search_vector = SearchVector('title',wiight='A')+SearchVector(
                'body',weight='B'
            )
            search_query = SearchQuery(query)
            results = Post.published.annotate(
                search = search_vector,
                rank = SearchRank(search_vector,search_query)
            ).filter(rank_gte=0.3).order_by('-rank')
            
    context = {
        'form':form,
        'query':query,
        'results':results
    }
    return render (request,'blog/search.html',context=context)