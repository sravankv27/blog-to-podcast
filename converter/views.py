from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ConversionTask
from .agents import Orchestrator
import json

def index(request):
    return render(request, 'converter/index.html')

@csrf_exempt
def start_conversion(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            blog_url = data.get('blog_url')
            if not blog_url:
                return JsonResponse({'error': 'URL is required'}, status=400)

            task = ConversionTask.objects.create(url=blog_url)
            orchestrator = Orchestrator(task.id)
            orchestrator.start()

            return JsonResponse({'task_id': task.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid method'}, status=405)

def get_status(request, task_id):
    try:
        task = ConversionTask.objects.get(id=task_id)
        return JsonResponse({
            'status': task.status,
            'progress': task.progress,
            'current_step': task.current_step,
            'script': task.script,
            'audio_file': task.audio_file,
            'video_file': task.video_file,
            'error_message': task.error_message,
            'logs': task.logs
        })
    except ConversionTask.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
