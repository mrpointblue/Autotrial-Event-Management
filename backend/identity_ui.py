import hashlib,hmac,secrets,time,uuid
from fastapi import APIRouter,Form,Request,HTTPException
from fastapi.responses import RedirectResponse,JSONResponse,HTMLResponse
from starlette.requests import Request as StarletteRequest
from backend.database import DATA_DIR,current_tenant,current_user
from backend.services.identity import catalog,has_users,hash_password,check_password,authenticated,organizers,ROLES

router=APIRouter()

def redirect(path='/ui/events'):
    return RedirectResponse(path,status_code=303)

def require_admin():
    user=current_user.get()
    if not user or user['role'] not in ('admin','organizer_admin'):raise HTTPException(403,'Keine Berechtigung.')
    return user

class IdentityMiddleware:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        request=StarletteRequest(scope);path=scope['path'];method=scope['method']
        if path.startswith('/static/') or path=='/health':return await self.app(scope,receive,send)
        # Browser forms and JSON calls must originate on this installation.
        if method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if request.headers.get('sec-fetch-site')=='cross-site' or (origin and origin.rstrip('/')!=str(request.base_url).rstrip('/')):
                return await JSONResponse({'detail':'Anfrage von fremder Seite abgewiesen.'},403)(scope,receive,send)
        if path in ('/login','/setup'):
            return await self.app(scope,receive,send)
        user,tenant=authenticated(request.cookies.get('trial_session'))
        if not user or not tenant:
            response=JSONResponse({'detail':'Bitte anmelden.'},401) if path.startswith('/api/') else redirect('/login' if has_users() else '/setup')
            return await response(scope,receive,send)
        guard=request.headers.get('x-trial-organizer') or request.query_params.get('_tenant')
        if method not in ('GET','HEAD','OPTIONS') and guard and guard!=tenant['id']:
            return await JSONResponse({'detail':'Der Veranstalter wurde in einem anderen Fenster gewechselt. Bitte diese Seite neu laden.'},409)(scope,receive,send)
        restricted=path.startswith(('/ui/settings','/api/settings','/ui/admin','/api/admin')) and not (method=='GET' and path=='/ui/settings/logo')
        if restricted and user['role'] not in ('admin','organizer_admin'):
            return await JSONResponse({'detail':'Nur Administratoren dürfen Einstellungen verwalten.'},403)(scope,receive,send)
        if user['role']=='reader' and method not in ('GET','HEAD','OPTIONS') and path!='/logout':
            return await JSONResponse({'detail':'Dieses Konto hat nur Leserechte.'},403)(scope,receive,send)
        u=current_user.set(user);t=current_tenant.set(tenant)
        scope.setdefault('state',{}).update(user=user,tenant=tenant)
        try:await self.app(scope,receive,send)
        finally:current_tenant.reset(t);current_user.reset(u)

@router.get('/setup')
def setup_page(request:Request):
    if has_users():return redirect('/login')
    from backend.main import render
    return render(request,'login.html',setup=True)

@router.post('/setup')
def setup(username:str=Form(...),password:str=Form(...),setup_token:str=Form(...)):
    expected=(DATA_DIR/'setup-token.txt').read_text() if (DATA_DIR/'setup-token.txt').exists() else ''
    if not expected or not hmac.compare_digest(expected,setup_token):raise HTTPException(403,'Einrichtungsschlüssel ungültig.')
    if not 3<=len(username.strip())<=100 or not 12<=len(password)<=256:raise HTTPException(422,'Benutzername mindestens 3 Zeichen, Passwort 12–256 Zeichen.')
    with catalog() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM users').fetchone():raise HTTPException(409,'Einrichtung bereits abgeschlossen.')
        tenant=db.execute('SELECT id FROM organizers WHERE is_default=1').fetchone()[0]
        db.execute('INSERT INTO users VALUES (?,?,?,?,?,1)',(str(uuid.uuid4()),username.strip(),hash_password(password),'admin',tenant))
    (DATA_DIR/'setup-token.txt').unlink(missing_ok=True)
    return redirect('/login')

@router.get('/login')
def login_page(request:Request):
    if not has_users():return redirect('/setup')
    from backend.main import render
    return render(request,'login.html',setup=False)

@router.post('/login')
def login(request:Request,username:str=Form(...),password:str=Form(...)):
    if len(password)>256:raise HTTPException(401,'Anmeldung fehlgeschlagen.')
    key=request.client.host if request.client else 'unknown';now=time.time()
    with catalog() as db:
        attempt=db.execute('SELECT * FROM login_attempts WHERE client=?',(key,)).fetchone()
        if attempt and attempt['count']>=10 and attempt['until']>now:raise HTTPException(429,'Zu viele Versuche. Bitte in 15 Minuten erneut versuchen.')
        user=db.execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
        if not user or not check_password(password,user['password']):
            count=attempt['count']+1 if attempt and attempt['until']>now else 1
            db.execute('INSERT OR REPLACE INTO login_attempts VALUES (?,?,?)',(key,count,now+900));db.commit()
            raise HTTPException(401,'Anmeldung fehlgeschlagen.')
        db.execute('DELETE FROM login_attempts WHERE client=?',(key,))
        token=secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<?',(now,))
        db.execute('INSERT INTO sessions VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],user['organizer_id'],now+43200))
    response=redirect();response.set_cookie('trial_session',token,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=43200);response.delete_cookie('active_event');return response

@router.post('/logout')
def logout(request:Request):
    with catalog() as db:db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(request.cookies.get('trial_session','').encode()).hexdigest(),))
    response=redirect('/login');response.delete_cookie('trial_session');response.delete_cookie('active_event');return response

@router.get('/ui/admin')
def admin_page(request:Request):
    user=require_admin();tenant=current_tenant.get()
    with catalog() as db:
        users=[dict(r) for r in db.execute('SELECT id,username,role,organizer_id,active FROM users WHERE organizer_id=?',(tenant['id'],))]
    from backend.main import render
    return render(request,'admin.html',users=users,organizers=organizers() if user['role']=='admin' else [tenant],roles=ROLES,page='admin')

@router.post('/ui/admin/organizers')
def create_organizer(name:str=Form(...),organizer_id:str=Form('')):
    if require_admin()['role']!='admin':raise HTTPException(403,'Nur der übergeordnete Administrator darf Veranstalter anlegen.')
    if not name.strip() or len(name)>150:raise HTTPException(422,'Name erforderlich (maximal 150 Zeichen).')
    try:uid=str(uuid.UUID(organizer_id)) if organizer_id else str(uuid.uuid4())
    except ValueError:raise HTTPException(422,'Ungültige Veranstalter-ID.')
    with catalog() as db:
        if db.execute('SELECT 1 FROM organizers WHERE id=?',(uid,)).fetchone():raise HTTPException(409,'Veranstalter-ID existiert bereits.')
        db.execute('INSERT INTO organizers(id,name) VALUES (?,?)',(uid,name))
    tenant=next(t for t in organizers() if t['id']==uid);token=current_tenant.set(tenant)
    try:
        from backend.main import initialize_database
        initialize_database()
    finally:current_tenant.reset(token)
    return redirect('/ui/admin')

@router.post('/ui/admin/select')
def select_organizer(request:Request,organizer_id:str=Form(...)):
    if require_admin()['role']!='admin':raise HTTPException(403,'Keine Berechtigung.')
    if organizer_id not in {t['id'] for t in organizers()}:raise HTTPException(404,'Veranstalter nicht gefunden.')
    with catalog() as db:db.execute('UPDATE sessions SET organizer_id=? WHERE token=?',(organizer_id,hashlib.sha256(request.cookies['trial_session'].encode()).hexdigest()))
    response=redirect();response.delete_cookie('active_event');return response

@router.post('/ui/admin/profile')
def profile(name:str=Form(...),address:str=Form(''),contact:str=Form('')):
    require_admin()
    if not name.strip() or len(name)>150 or max(len(address),len(contact))>2000:raise HTTPException(422,'Bitte Angaben prüfen.')
    with catalog() as db:db.execute('UPDATE organizers SET name=?,address=?,contact=? WHERE id=?',(name,address,contact,current_tenant.get()['id']))
    return redirect('/ui/admin')

@router.post('/ui/admin/users')
def create_user(username:str=Form(...),password:str=Form(...),role:str=Form(...)):
    user=require_admin()
    if role not in ROLES or (role=='admin' and user['role']!='admin'):raise HTTPException(403,'Diese Rolle darf nicht vergeben werden.')
    if not 3<=len(username.strip())<=100 or not 12<=len(password)<=256:raise HTTPException(422,'Benutzername mindestens 3 Zeichen, Passwort 12–256 Zeichen.')
    with catalog() as db:
        if db.execute('SELECT 1 FROM users WHERE username=?',(username.strip(),)).fetchone():raise HTTPException(409,'Benutzername bereits vergeben.')
        db.execute('INSERT INTO users VALUES (?,?,?,?,?,1)',(str(uuid.uuid4()),username.strip(),hash_password(password),role,current_tenant.get()['id']))
    return redirect('/ui/admin')

@router.post('/ui/admin/users/{user_id}/disable')
def disable_user(user_id:str):
    actor=require_admin()
    with catalog() as db:
        target=db.execute('SELECT * FROM users WHERE id=? AND organizer_id=?',(user_id,current_tenant.get()['id'])).fetchone()
        if not target:raise HTTPException(404,'Benutzer nicht gefunden.')
        if target['id']==actor['id'] or (target['role']=='admin' and actor['role']!='admin'):raise HTTPException(403,'Dieses Konto kann nicht deaktiviert werden.')
        db.execute('UPDATE users SET active=0 WHERE id=?',(user_id,));db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
    return redirect('/ui/admin')
