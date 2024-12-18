from fastapi import FastAPI, Request, Form, Depends, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import bcrypt
from starlette.status import HTTP_303_SEE_OTHER
from datetime import datetime

# Koneksi ke MongoDB
client = MongoClient("mongodb://10.253.128.179:27017/")  # Ganti sesuai konfigurasi
db = client["kana"]
users_collection = db["users"]
message_collection = db["messages"]
message_collection.create_index("username", unique=True)
users_collection.create_index("username", unique=True)

# Setup FastAPI dan Jinja2
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Fungsi hashing dan verifikasi password
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

# Halaman Registrasi (GET)
@app.get("/register", response_class=HTMLResponse)
def get_register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# Proses Registrasi (POST)
@app.post("/register")
def post_register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    hashed_password = hash_password(password)
    user_data = {"username": username, "password": hashed_password}
    try:
        users_collection.insert_one(user_data)
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)
    except DuplicateKeyError:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username sudah digunakan."})

# Halaman Login (GET)
@app.get("/login", response_class=HTMLResponse)
def get_login_page(request: Request, username: str = Cookie(None)):
    if username is not None:
        return RedirectResponse(url="/dashboard", status_code=HTTP_303_SEE_OTHER)  # Redirect if already logged in
    return templates.TemplateResponse("login.html", {"request": request})

# Proses Login (POST)
@app.post("/login")
async def post_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = users_collection.find_one({"username": username})
    if user and verify_password(password, user["password"]):
        response = RedirectResponse(url="/dashboard", status_code=HTTP_303_SEE_OTHER)
        response.set_cookie(key="username", value=username)  # Set cookie
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Username atau password salah."})

@app.get("/dashboard", response_class=HTMLResponse)
def success_page(request: Request, username: str = Cookie(None)):
    if username is None:
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)  # Redirect to login if not authenticated
    
    user_messages = message_collection.find_one({"username": username})
    messages = user_messages["messages"] if user_messages and "messages" in user_messages else []

    # Format timestamp untuk setiap pesan
    for message in messages:
        # Ubah timestamp menjadi objek datetime
        dt = datetime.fromisoformat(message["timestamp"])
        # Format sesuai dengan keinginan: "%d/%m %I:%M %p"
        message["formatted_timestamp"] = dt.strftime("%d/%m %I:%M %p")

    return templates.TemplateResponse("dash.html", {"request": request, "username": username, "messages": messages})

# Logout (GET)
@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)
    response.delete_cookie("username")  # Hapus cookie saat logout
    return response

# Halaman Kustom (GET)
@app.get("/{username}", response_class=HTMLResponse)
def read_user(request: Request, username: str):
    user = users_collection.find_one({"username": username})
    if user is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("user.html", {"request": request, "username": username})

@app.post("/{username}")
def post_message(
    request: Request,
    username: str,
    message: str = Form(...),
):
    # Mendapatkan waktu saat ini
    timestamp = datetime.now().isoformat()  # Menggunakan format ISO 8601 untuk waktu

    user_exist = message_collection.find_one({"username": username})
    if user_exist:
        # Tambahkan pesan beserta waktu ke array messages
        message_collection.update_one(
            {"username": username},
            {"$push": {"messages": {"text": message, "timestamp": timestamp}}}
        )
    else:
        # Buat dokumen baru dengan username dan pesan pertama beserta waktu
        message_collection.insert_one(
            {"username": username, "messages": [{"text": message, "timestamp": timestamp}]}
        )
    
    return templates.TemplateResponse("user.html", {"request": request, "msg": "Terkirim."})
