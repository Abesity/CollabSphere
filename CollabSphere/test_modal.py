from django.test import RequestFactory
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import get_user_model
from tasks_app_collabsphere.views import task_detail

User = get_user_model()
u = User.objects.filter(username='NinaIsabelle').first()

rf = RequestFactory()
req = rf.get('/tasks/119/detail/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
req.user = u
req.session = SessionStore()
req.session['user_ID'] = 33
req.session.save()

try:
    res = task_detail(req, 119)
    print('Status:', res.status_code)
    content = res.content.decode('utf-8')
    
    print('Response length:', len(content))
    print('Has taskDetailModal:', 'taskDetailModal' in content)
    print('Has <!DOCTYPE:', '<!DOCTYPE' in content)
    print('Lines around taskDetailModal (or first 500):')
    if 'taskDetailModal' in content:
        idx = content.find('taskDetailModal')
        print(content[max(0, idx-300):idx+200])
    else:
        print(content[:500])
    
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()


