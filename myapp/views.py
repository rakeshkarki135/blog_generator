import os
import json
import openai
import yt_dlp
import assemblyai as aai

from decouple import config
from django.http import JsonResponse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from .models import BlogPost


assembly_ai_api_key = config("ASSEMPLY_AI_API_KEY", cast=str)
open_ai_api_key = config("OPEN_AI_API_KEY", cast=str)

# Create your views here.
@login_required(login_url='login')
def index(request):
     return render(request, 'index.html')

# csrf_excempt allow transferr of data using post without csrf token
@csrf_exempt
def generate_blog(request):
     if request.method == 'POST':
          try:
               # loading the json data from index.html
               data = json.loads(request.body)
               # storing the utube link in yt_link
               yt_link = data['link']
               
               print(yt_link)
               
               # getting youtube title
               title = yt_title(yt_link)
               print(title)
               if not title:
                    return JsonResponse({'error':'Failed to generate blog from given link'}, status = 500)

               # get transcript
               transcription = get_transcription(yt_link)
               if not transcription:
                    return JsonResponse({'error':'Failed to get Transcript'}, status = 500)
                    
               
               # use openai to generate blog
               blog_content = generate_blog_from_transcription(transcription)
               if not blog_content:
                    return JsonResponse({'error':'Failed to generate blog article'}, status=500)
               
               # save blog article to database
               new_blog_article = BlogPost.objects.create(
                    user = request.user,
                    youtube_title = title,
                    youtube_link = yt_link,
                    generated_content = blog_content
                    
               )
               
               # retiurn blog article as a response
               return JsonResponse({'content':blog_content})
               
          except(KeyError, json.JSONDecodeError ):
               return JsonResponse({'error':'Invalid data sent'}, status = 400)
          
          
     else:
          return JsonResponse({'error':'Invalid Request Method'}, status=405)
     
     

def yt_title(link):
     try:
          ydl_opts = {'quiet': True}
          with yt_dlp.YoutubeDL(ydl_opts) as ydl:
               info = ydl.extract_info(link, download=False)
               return info.get('title', 'Unknown Title')
     except Exception as e:
          print(f"Error fetching title with yt-dlp: {e}")
          return "Unknown Title"


def download_audio(link):
     try:
          # Fetch video title
          title = yt_title(link)
          print(f"Video Title: {title}")

          # yt-dlp options to download audio only
          ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': 'downloads/%(title)s.%(ext)s',
                    'postprocessors': [
                         {
                              'key': 'FFmpegExtractAudio',
                              'preferredcodec': 'mp3',
                              'preferredquality': '192',
                         }
                    ],
                    'ffmpeg_location': '/usr/bin/ffmpeg',  # Replace with the full path to your FFmpeg binary
                    }

          # Ensure the downloads folder exists
          download_folder = "downloads"
          if not os.path.exists(download_folder):
               os.makedirs(download_folder)

          # Download audio
          with yt_dlp.YoutubeDL(ydl_opts) as ydl:
               info = ydl.extract_info(link, download=True)
               file_path = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')

          print(f"Audio downloaded and converted successfully: {file_path}")
          return file_path

     except Exception as e:
          print(f"An error occurred while downloading audio: {e}")
          return None

     
def get_transcription(link):
     audio_file = download_audio(link)
     
     if audio_file is None:
          print('Audio is missing')
          return None
     
     try:
          aai.settings.api_key = assembly_ai_api_key
          
          # getting the transcriber function that transforms audio to text
          transcriber = aai.Transcriber()
          transcript = transcriber.transcribe(audio_file)
          
          
          return transcript.text
     
     except Exception as e:
          print(f"Erro occured during transcription {e}")
          return JsonResponse({'error':'Failed to transcribe audio file'})
          


def generate_blog_from_transcription(transcription):
     openai.api_key = open_ai_api_key
     prompt = f"Based on the following transcript from youtube video, write a comprehensive blog article , write it based on transcript, but dont make it look like youtube vide , make it look like a proper blog article:\n\n{transcription}\n\n:Article: "
     
     # Use the newer `chat/completions` endpoint
     response = openai.ChatCompletion.create(
          model="gpt-4o-mini",  # Replace with `gpt-4` if needed
          messages=[
               {"role": "system", "content": "You are a professional blog writer."},
               {"role": "user", "content": prompt}
          ],
          max_tokens=1000,
          temperature=0.7  # Adjust for creativity
     )
     
     # Extract the response text
     generated_content = response['choices'][0]['message']['content'].strip()
     
     return generated_content


def blog_list(request):
     blog_articles = BlogPost.objects.filter(user =request.user)
     return render(request, 'all-blogs.html', {'blog_articles':blog_articles})
     
     
def blog_detail(request, pk):
     blog_detail = get_object_or_404(BlogPost, id=pk)
     
     if request.user == blog_detail.user:
          return render(request, 'blog.html', {'blog_detail': blog_detail})
     else:
          return redirect('index')
          
     
def signup(request):
     error_message = {}
     if request.method == "POST":
          username = request.POST['username']
          email = request.POST['email']
          password = request.POST['password']
          repeatPassword = request.POST['repeatPassword']
          
          if password == repeatPassword:
               try:
                    if User.objects.filter(email=email).exists():
                         error_message = 'Email already Exists'
                         return render(request, 'signup.html', { 'error_message':error_message })
                    
                    if User.objects.filter(username=username).exists():
                         error_message = 'Username already Exists'
                         return render(request, 'signup.html', { 'error_message':error_message })
                         
                    user = User.objects.create_user(username=username, email=email, password=password)
                    user.save()
                    return redirect('login')
                    
               except:
                    error_message = 'Error while creating Account'
          else:
               error_message = "Recheck your Password"
          
     return render(request, 'signup.html', { 'error_message':error_message })

def usr_login(request):
     if request.method == 'POST':
          username = request.POST['username']
          password = request.POST['password']
          
          if '@' in username:
               user_obj = User.objects.filter(email=username).first()
               if not user_obj:
                    messages.error(request, 'User does not Exist')
                    return redirect('login')
               
               username = user_obj.username
          
          else:
               if not User.objects.filter(username=username).exists():
                    messages.error(request, 'User does not Exist')
                    return redirect('login')
          
          user = authenticate(request, username=username ,  password=password)
          if  user is not None:
               login(request, user)
               return redirect('index')
          else:
               messages.error(request, 'Invalid Credentials')
               return redirect('login')
               
     return render(request, 'login.html')

def usr_logout(request):
     logout(request)
     return redirect('login')