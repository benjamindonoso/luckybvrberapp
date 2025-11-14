import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
import pytz
import pandas as pd
import os
from email.mime.text import MIMEText
import base64
from PIL import Image

# ---------------- CONFIGURACIÓN GENERAL ----------------
st.set_page_config(page_title="💈 Lucky Bvrber 🍀", page_icon="💇", layout="wide")

# Cargar estilo CSS
try:
    with open("style/main.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("⚠️ No se encontró style/main.css")

# ---------------- IMÁGENES ----------------
def load_image(path, size=(400, 300)):
    if os.path.exists(path):
        img = Image.open(path)
        img.thumbnail(size)
        return img
    else:
        st.warning(f"No se encontró la imagen {path}")
        return None

banner = load_image("images/banner.jpg", size=(1200, 400))
if banner:
    st.image(banner, width="stretch")

# ---------------- DATOS DE SERVICIOS ----------------
SERVICIOS = {
    "Corte Clasico": {"precio": 9000, "imagen": "images/Corte_Clasico.jpg"},
    "Corte Premium": {"precio": 15000, "imagen": "images/Corte_Premium.jpg"},
    "Domicilio": {"precio": 15000, "imagen": "images/Corte_Domicilio.jpg"},
    "Tintura": {"precio": 40000, "imagen": "images/tintura.jpg"},
    "Ondulacion permanente": {"precio": 35000, "imagen": "images/Ondulado_Permanente.jpg"},
}

# ---------------- CONFIGURACIÓN ----------------
WORK_START, WORK_END, SLOT_MINUTES = 9, 18, 45
TIMEZONE = "America/Santiago"
CALENDAR_ID = "lucky.bvrber5@gmail.com"
SHEET_ID = "1z4E18eS62VUacbIHb2whKzLYTsS5zyYnRNZTqFFiQgc"

tz = pytz.timezone(TIMEZONE)   # <<< ESTA LÍNEA DEBE IR AQUÍ

# ---------------- AUTENTICACIÓN GOOGLE ----------------
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send"
]

# ---- AUTENTICACIÓN OAUTH2 ----
@st.cache_resource
def build_services():
    creds = None

    # Si existe token.json, lo usamos
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # Si no existe o expiró, pedimos login OAuth2
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Oculta el mensaje del navegador en Streamlit
            with st.spinner("🔐 Abriendo autorización de Google..."):
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)

        # Guardamos token
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    # Construimos servicios
    calendar = build("calendar", "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)
    gmail = build("gmail", "v1", credentials=creds)

    return calendar, sheets, gmail

calendar_service, sheets_service, gmail_service = build_services()

# ---------------- FUNCIONES DE GOOGLE ----------------
def get_day_events(service, fecha):
    start = tz.localize(datetime(fecha.year, fecha.month, fecha.day, 0, 0))
    end = start + timedelta(days=1)
    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    return events.get("items", [])

def is_slot_free(start, end, events):
    for event in events:
        s = event["start"].get("dateTime")
        e = event["end"].get("dateTime")
        if s and e:
            s, e = datetime.fromisoformat(s), datetime.fromisoformat(e)
            if start < e and end > s:
                return False
    return True

def create_calendar_event(service, start, end, title, desc, email):
    event = {
        "summary": title,
        "description": desc,
        "start": {"dateTime": start.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end.isoformat(), "timeZone": TIMEZONE},
        "attendees": [{"email": email}],
    }
    service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

def append_to_sheet(service, data):
    service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range="A1",
        valueInputOption="RAW",
        body={"values": [data]}
    ).execute()

def send_gmail_message(service, to, subject, body):
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

# ---------------- INTERFAZ ----------------
st.title("💈 Reserva tu cita con 𝓛𝓾𝓬𝓴𝔂 𝐵𝓋𝓇𝒷𝑒𝓇 🍀")

nombre = st.text_input("👤 Nombre completo")
email = st.text_input("📧 Correo electrónico")
fecha = st.date_input("📅 Fecha de la cita")

if fecha:
    events = get_day_events(calendar_service, fecha)
    slots = []
    hora = WORK_START
    while hora + (SLOT_MINUTES / 60) <= WORK_END:
        start = tz.localize(datetime(fecha.year, fecha.month, fecha.day, int(hora)))
        end = start + timedelta(minutes=SLOT_MINUTES)
        if is_slot_free(start, end, events):
            slots.append(f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}")
        hora += SLOT_MINUTES / 60
    hora_sel = st.selectbox("🕒 Horas disponibles", slots) if slots else st.warning("Sin horarios libres.")
else:
    hora_sel = None

st.subheader("💇‍♂️ Servicios disponibles")
cols = st.columns(len(SERVICIOS))
for i, (nombre_servicio, datos) in enumerate(SERVICIOS.items()):
    with cols[i]:
        img = load_image(datos["imagen"])
        if img:
            st.image(img)
        st.markdown(f"**{nombre_servicio}** — 💵 ${datos['precio']}")
st.markdown("""**Descripción de servicios:**
- **Servicio clásico:** Corte de pelo a gusto, junto con un perfilado de cejas y barba + aplicación de productos para dar forma y estilizar el cabello + una bebida de cortesía al momento del servicio.
- **Servicio premium:** Corte de pelo a gusto, junto con un perfilado de cejas y barba, además incluye limpieza, exfoliación e hidratación de la piel + aplicación de productos para dar forma y estilizar el cabello + una bebida de cortesía al momento del servicio.
- **Servicio a domicilio:** Corte de pelo a gusto, junto con un perfilado de cejas y barba + aplicación de productos para dar forma y estilizar el cabello + una bebida de cortesía al momento del servicio, todo en la comodidad de su casa (el valor puede aumentar dependiendo de la lejanía del domicilio).
""")
servicio = st.selectbox("✂️ Elige tu servicio", list(SERVICIOS.keys()))

# Inicializamos la variable de sesión
if "reserva_confirmada" not in st.session_state:
    st.session_state["reserva_confirmada"] = False

# Botón de confirmación
if st.button("📆 Confirmar reserva") and not st.session_state["reserva_confirmada"]:
    if not nombre or not email or not fecha or not hora_sel:
        st.error("Por favor, completa todos los campos.")
    else:
        start_str, end_str = hora_sel.split(" - ")
        start_dt = tz.localize(datetime.combine(fecha, datetime.strptime(start_str, "%H:%M").time()))
        end_dt = tz.localize(datetime.combine(fecha, datetime.strptime(end_str, "%H:%M").time()))
        precio = SERVICIOS[servicio]["precio"]

        if not is_slot_free(start_dt, end_dt, events):
            st.error("⛔ Ese horario ya está ocupado.")
        else:
            try:
                title = f"{servicio} — {nombre}"
                desc = f"Cliente: {nombre}\nEmail: {email}\nServicio: {servicio}\nPrecio: ${precio}"

                create_calendar_event(calendar_service, start_dt, end_dt, title, desc, email)
                append_to_sheet(sheets_service, [
                    fecha.strftime("%Y-%m-%d"), start_str, nombre, email, servicio, precio
                ])
                send_gmail_message(
                    gmail_service,
                    email,
                    "Confirmación de cita — Lucky Barber",
                    f"Hola {nombre}, tu cita para {servicio} fue confirmada para el {fecha} a las {start_str}. 💈\nPrecio: ${precio}\n¡Te esperamos!"
                )
                st.success("✅ Cita confirmada y correo enviado.")
                # Marcamos como confirmada para desactivar el botón
                st.session_state["reserva_confirmada"] = True
            except HttpError as e:
                st.error(f"Error en Google API: {e}")