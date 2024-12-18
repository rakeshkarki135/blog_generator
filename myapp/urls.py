from django.urls import path   
from .views import *                  

urlpatterns = [
     path('',  index , name='index' ),
     path('login', usr_login, name='login'),
     path('signup', signup, name='signup'),
     path('logout', usr_logout, name='logout'),
     path('generate-blog', generate_blog, name='generate-blog'),
     path('blog-list', blog_list, name="blog-list"),
     path('blog-detail/<int:pk>', blog_detail, name='blog-detail'),
]